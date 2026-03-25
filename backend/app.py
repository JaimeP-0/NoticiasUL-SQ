from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_compress import Compress
from singleton_config import ConfigSingleton
from datetime import datetime
from database import Database
from database_json import DatabaseJSON
import json
import os
from firebase_service import FirebaseService
from config import Config
from permissions import require_permission, require_role, get_user_permissions, get_user_role_from_request
from jwt_auth import generate_token, verify_token, require_auth, get_user_from_token, get_token_from_request
from cache import cache
from news_service_facade import NewsServiceFacade
from decorators import LoggingDecorator
from action_logger import action_logger, NIVELES_AFECTACION
# Intentar importar Flask-Limiter para rate limiting
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    LIMITER_AVAILABLE = True
except ImportError:
    LIMITER_AVAILABLE = False

# Importar utilidades de contraseñas después de configurar logging
from password_utils import hash_password, verify_password, is_password_hashed
from observer_pattern import (
    get_news_event_subject, 
    get_auth_event_subject,
    CacheInvalidationObserver,
    LoggingObserver,
    NotificationObserver
)
from mediator_pattern import get_news_mediator
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import uuid

# Intentar importar Pusher (opcional)
try:
    import pusher
    PUSHER_AVAILABLE = True
except ImportError:
    PUSHER_AVAILABLE = False

# Handler personalizado que maneja errores de rotación en Windows
class SafeTimedRotatingFileHandler(TimedRotatingFileHandler):
    """TimedRotatingFileHandler que maneja errores de rotación en Windows"""
    def doRollover(self):
        """Sobrescribir doRollover para manejar errores de permisos en Windows"""
        try:
            super().doRollover()
        except (OSError, PermissionError) as e:
            # Si falla la rotación (archivo en uso por OneDrive u otro proceso),
            # simplemente continuar sin rotar. El log seguirá escribiendo en el archivo actual.
            # Esto es mejor que romper todo el sistema de logging.
            pass  # Silenciosamente ignorar el error de rotación

# Configurar logging con rotación diaria
def setup_logging():
    """Configurar logging con rotación diaria de archivos"""
    # Crear directorio de logs si no existe
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configurar formato de logs
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para archivo de backend con rotación diaria
    # Los archivos se guardarán como: app_back.log, app_back.log.2024-01-15, etc.
    back_log_file = os.path.join(log_dir, 'app_back.log')
    back_file_handler = SafeTimedRotatingFileHandler(
        filename=back_log_file,
        when='midnight',  # Rotar a medianoche
        interval=1,       # Cada día
        backupCount=30,   # Mantener 30 días de logs
        encoding='utf-8'
    )
    back_file_handler.setLevel(logging.INFO)
    back_file_handler.setFormatter(log_format)
    back_file_handler.suffix = '%Y-%m-%d'  # Formato de fecha en el nombre del archivo
    
    # Handler para archivo de frontend (peticiones HTTP) con rotación diaria
    # Los archivos se guardarán como: app_front.log, app_front.log.2024-01-15, etc.
    front_log_file = os.path.join(log_dir, 'app_front.log')
    front_file_handler = SafeTimedRotatingFileHandler(
        filename=front_log_file,
        when='midnight',  # Rotar a medianoche
        interval=1,       # Cada día
        backupCount=30,   # Mantener 30 días de logs
        encoding='utf-8'
    )
    front_file_handler.setLevel(logging.INFO)
    front_file_handler.setFormatter(log_format)
    front_file_handler.suffix = '%Y-%m-%d'
    
    # Filtrar logs relacionados con peticiones HTTP del frontend
    class FrontendFilter(logging.Filter):
        def filter(self, record):
            message = record.getMessage()
            # Logs relacionados con peticiones HTTP, login, auth, etc.
            frontend_keywords = [
                '[LOGIN]', '[AUTH/ME]', '[JWT]', 
                'Endpoint llamado', 'Endpoint de', 'petición',
                'Headers recibidos', 'Cookies recibidas', 'Origen de la petición',
                'Respuesta de', 'GET /api', 'POST /api', 'PUT /api', 'DELETE /api'
            ]
            return any(keyword in message for keyword in frontend_keywords)
    
    # Filtrar logs del backend (todo lo que NO sea frontend)
    class BackendFilter(logging.Filter):
        def filter(self, record):
            message = record.getMessage()
            # Excluir logs de frontend
            frontend_keywords = [
                '[LOGIN]', '[AUTH/ME]', '[JWT]',
                'Endpoint llamado', 'Endpoint de', 'petición',
                'Headers recibidos', 'Cookies recibidas', 'Origen de la petición',
                'Respuesta de', 'GET /api', 'POST /api', 'PUT /api', 'DELETE /api'
            ]
            return not any(keyword in message for keyword in frontend_keywords)
    
    back_file_handler.addFilter(BackendFilter())
    front_file_handler.addFilter(FrontendFilter())
    
    # Handler para archivo de acciones de usuarios (separado)
    # Los archivos se guardarán como: actions.log, actions.log.2024-01-15, etc.
    actions_log_file = os.path.join(log_dir, 'actions.log')
    actions_file_handler = SafeTimedRotatingFileHandler(
        filename=actions_log_file,
        when='midnight',  # Rotar a medianoche
        interval=1,       # Cada día
        backupCount=30,   # Mantener 30 días de logs
        encoding='utf-8'
    )
    actions_file_handler.setLevel(logging.INFO)
    actions_file_handler.setFormatter(log_format)
    actions_file_handler.suffix = '%Y-%m-%d'
    
    # Filtrar solo mensajes que empiecen con [ACCION]
    class ActionsFilter(logging.Filter):
        def filter(self, record):
            return '[ACCION]' in record.getMessage()
    
    actions_file_handler.addFilter(ActionsFilter())
    
    # Handler para consola (mantener salida en terminal)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    
    # Configurar el logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(back_file_handler)  # Handler de backend
    root_logger.addHandler(front_file_handler)  # Handler de frontend
    root_logger.addHandler(actions_file_handler)  # Handler de acciones
    root_logger.addHandler(console_handler)  # Handler de consola
    
    return root_logger

# Inicializar logging
setup_logging()
logger = logging.getLogger(__name__)
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
logger.info(f"Sistema de logging inicializado - Backend: {os.path.join(log_dir, 'app_back.log')}, Frontend: {os.path.join(log_dir, 'app_front.log')}, Acciones: {os.path.join(log_dir, 'actions.log')}")

app = Flask(__name__)

# Configurar CORS con soporte para cookies
# Nota: No se puede usar '*' con supports_credentials=True, por eso especificamos orígenes
# Permitir dominios de Cloudflare Tunnel dinámicamente usando un decorador
def is_cloudflare_origin(origin):
    """Verificar si el origen es un dominio de Cloudflare Tunnel"""
    if not origin:
        return False
    return origin.endswith('.trycloudflare.com') or 'trycloudflare.com' in origin

# Configurar CORS con manejo dinámico de orígenes
# Usar un decorador @app.after_request para manejar CORS manualmente para Cloudflare
CORS(
    app, 
    origins=Config.CORS_ORIGINS,  # Orígenes estáticos
    supports_credentials=True,
    allow_headers=['Content-Type', 'Authorization'],
    methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    expose_headers=['Set-Cookie']
)

# Decorador para permitir orígenes de Cloudflare dinámicamente y agregar headers de seguridad
@app.after_request
def after_request_cors(response):
    """Agregar headers CORS para dominios de Cloudflare y headers de seguridad"""
    try:
        origin = request.headers.get('Origin', '')
        if origin and is_cloudflare_origin(origin):
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response.headers['Access-Control-Expose-Headers'] = 'Set-Cookie'
        
        # Headers de seguridad HTTP
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:"
        
        # Strict Transport Security (solo en HTTPS)
        if request.is_secure or origin.startswith('https://'):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    except Exception as e:
        logger.error(f"Error en after_request_cors: {e}")
    return response

logger.info(f"CORS configurado para orígenes: {Config.CORS_ORIGINS} y dominios de Cloudflare Tunnel (dinámico)")

# Inicializar Rate Limiter (si está disponible)
limiter = None
if LIMITER_AVAILABLE:
    try:
        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=["200 per day", "50 per hour"],
            storage_uri="memory://"
        )
        logger.info("Rate limiting habilitado")
    except Exception as e:
        logger.error(f"Error al inicializar rate limiter: {e}")
        limiter = None
else:
    logger.warning("Rate limiting no disponible (Flask-Limiter no instalado)")

# Función helper para aplicar rate limiting condicionalmente
def apply_rate_limit(limit_str):
    """Aplicar rate limiting si está disponible"""
    if limiter:
        return limiter.limit(limit_str)
    return lambda f: f

# Habilitar compresión gzip
Compress(app)

# Inicializar servicios
# Usar DatabaseJSON si DATABASE_TYPE es 'json', sino usar Database (MySQL)
if Config.DATABASE_TYPE == 'json':
    db = DatabaseJSON()
    logger.info("📁 Usando base de datos JSON local")
    # Inicializar tablas en JSON
    db.init_tables()
else:
    db = Database()
    logger.info("🗄️ Usando base de datos MySQL")
firebase = FirebaseService()

# Inicializar Firebase (opcional, no crítico si no está configurado)
firebase.initialize()

# Inicializar Observer Pattern - Sujetos de eventos
news_event_subject = get_news_event_subject()
auth_event_subject = get_auth_event_subject()

# Registrar Observers para eventos de noticias
cache_observer = CacheInvalidationObserver(cache)
logging_observer = LoggingObserver()
notification_observer = NotificationObserver()

news_event_subject.attach(cache_observer)
news_event_subject.attach(logging_observer)
news_event_subject.attach(notification_observer)

# Inicializar Mediator Pattern - Coordinador de servicios
news_mediator = get_news_mediator(cache_service=cache, observer_subject=news_event_subject)

# Inicializar fachada de noticias (Facade Pattern) con Mediator
news_facade = NewsServiceFacade(db=db, firebase=firebase, mediator=news_mediator)

# Inicializar Pusher (opcional)
pusher_client = None
if PUSHER_AVAILABLE and Config.PUSHER_APP_ID and Config.PUSHER_KEY and Config.PUSHER_SECRET:
    try:
        pusher_client = pusher.Pusher(
            app_id=Config.PUSHER_APP_ID,
            key=Config.PUSHER_KEY,
            secret=Config.PUSHER_SECRET,
            cluster=Config.PUSHER_CLUSTER,
            ssl=True
        )
        logger.info("Pusher inicializado correctamente")
    except Exception as e:
        logger.error(f"Error al inicializar Pusher: {e}")
        pusher_client = None
else:
    logger.info("Pusher no configurado (variables de entorno faltantes)")

def send_pusher_event(channel, event, data):
    """Enviar evento a Pusher si está disponible"""
    if pusher_client:
        try:
            pusher_client.trigger(channel, event, data)
            logger.debug(f"[PUSHER] Evento enviado: {channel}/{event}")
        except Exception as e:
            logger.error(f"[PUSHER] Error al enviar evento: {e}")

@app.route('/api/register', methods=['POST'])
def register():
    """Endpoint para registro de nuevos usuarios (solo crea usuarios con rol 'usuario')"""
    try:
        data = request.get_json() or {}
        usuario = data.get("usuario")
        password = data.get("password")
        nombre = data.get("nombre", "")
        email = data.get("email", "")
        
        if not usuario or not password:
            return jsonify({"error": "Usuario y contraseña requeridos"}), 400
        
        existing_user = db.execute_query(
            "SELECT idUsuario FROM usuarios_nul WHERE usuario = %s",
            (usuario,),
            fetch_one=True
        )
        
        if existing_user:
            return jsonify({"error": "El usuario ya existe"}), 400
        
        # Hashear contraseña antes de almacenarla
        hashed_password = hash_password(password)
        
        # Crear nuevo usuario con rol 'usuario' por defecto (siempre)
        user_id = db.execute_query(
            "INSERT INTO usuarios_nul (usuario, contrasena, nombre, email, rol) VALUES (%s, %s, %s, %s, %s)",
            (usuario, hashed_password, nombre, email, 'usuario')
        )
        
        # Registrar acción de registro
        action_logger.log_action(
            usuario=usuario,
            accion='registro_usuario',
            nivel='aviso',
            descripcion=f"Usuario '{usuario}' se registró automáticamente"
        )
        return jsonify({
            "mensaje": "Usuario registrado exitosamente",
            "usuario": usuario,
            "nombre": nombre,
            "rol": "usuario"
        }), 201
    except Exception as e:
        logger.error(f"Error en registro: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": "Error al registrar usuario"}), 500

@app.route('/api/users', methods=['GET'])
@require_permission('manage_admins')
def get_users():
    """Obtener todos los usuarios (solo superadmin) - con caché"""
    try:
        # NO crear tablas, solo leer de las existentes
        # Caché para usuarios (TTL más largo: 2 minutos)
        cache_key = "users_list"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return jsonify(cached_result), 200
        
        users = db.execute_query(
            "SELECT idUsuario, usuario, nombre, email, rol, fecha_creacion FROM usuarios_nul ORDER BY fecha_creacion DESC",
            fetch_all=True
        )
        
        # Convertir fecha a string para JSON
        for user in users:
            if user.get('fecha_creacion'):
                # Si la fecha ya es string (JSON), no convertir
                if not isinstance(user['fecha_creacion'], str):
                    user['fecha_creacion'] = user['fecha_creacion'].strftime("%Y-%m-%d %H:%M:%S")
            # No enviar la contraseña
            if 'contrasena' in user:
                del user['contrasena']
        
        result = users if users else []
        
        # Guardar en caché (TTL de 30 segundos)
        cache.set(cache_key, result, ttl=30)
        
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error al obtener usuarios: {e}")
        return jsonify({"error": "Error al obtener usuarios"}), 500

@app.route('/api/users', methods=['POST'])
@require_permission('manage_admins')
def create_user():
    """Endpoint para crear usuarios con roles específicos (solo superadmin)"""
    try:
        data = request.get_json() or {}
        usuario = data.get("usuario")
        password = data.get("password")
        nombre = data.get("nombre", "")
        email = data.get("email", "")
        rol = data.get("rol", "usuario")
        
        # Validar que el rol sea válido
        valid_roles = ['superadmin', 'admin', 'maestro', 'usuario']
        if rol not in valid_roles:
            return jsonify({"error": f"Rol inválido. Roles permitidos: {valid_roles}"}), 400
        
        logger.info(f"Superadmin creando usuario - Usuario: {usuario}, Rol: {rol}")
        
        if not usuario or not password:
            return jsonify({"error": "Usuario y contraseña requeridos"}), 400
        
        # Verificar si el usuario ya existe
        existing_user = db.execute_query(
            "SELECT idUsuario FROM usuarios_nul WHERE usuario = %s",
            (usuario,),
            fetch_one=True
        )
        
        if existing_user:
            return jsonify({"error": "El usuario ya existe"}), 400
        
        # Obtener usuario actual que está creando el usuario
        current_user = get_user_from_token()
        creador_usuario = current_user.get('usuario', 'desconocido') if current_user else 'desconocido'
        creador_rol = current_user.get('rol', 'desconocido') if current_user else 'desconocido'
        
        # Hashear contraseña antes de almacenarla
        hashed_password = hash_password(password)
        
        # Crear usuario con el rol especificado
        user_id = db.execute_query(
            "INSERT INTO usuarios_nul (usuario, contrasena, nombre, email, rol) VALUES (%s, %s, %s, %s, %s)",
            (usuario, hashed_password, nombre, email, rol)
        )
        
        # Limpiar caché de usuarios
        cache.delete("users_list")
        
        # Registrar acción de creación de usuario
        action_logger.log_action(
            usuario=creador_usuario,
            accion='crear_usuario',
            nivel='movimiento',
            descripcion=f"Usuario '{usuario}' creado con rol '{rol}' por '{creador_usuario}' (rol: {creador_rol})"
        )
        return jsonify({
            "mensaje": "Usuario creado exitosamente",
            "usuario": usuario,
            "nombre": nombre,
            "rol": rol
        }), 201
    except Exception as e:
        logger.error(f"Error al crear usuario: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": "Error al crear usuario"}), 500

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@require_permission('manage_admins')
def update_user(user_id):
    """Actualizar rol de un usuario (solo superadmin) - NO permite cambiar contraseñas"""
    try:
        data = request.get_json() or {}
        nuevo_rol = data.get("rol")
        
        # Verificar que el usuario existe
        user_existente = db.execute_query(
            "SELECT idUsuario, usuario, rol FROM usuarios_nul WHERE idUsuario = %s",
            (user_id,),
            fetch_one=True
        )
        
        if not user_existente:
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        # Validar que el rol sea válido si se proporciona
        if nuevo_rol:
            valid_roles = ['superadmin', 'admin', 'maestro', 'usuario']
            if nuevo_rol not in valid_roles:
                return jsonify({"error": f"Rol inválido. Roles permitidos: {valid_roles}"}), 400
        
        # Solo actualizar el rol
        if nuevo_rol is None:
            return jsonify({"error": "Debe proporcionar un rol para actualizar"}), 400
        
        db.execute_query(
            "UPDATE usuarios_nul SET rol = %s WHERE idUsuario = %s",
            (nuevo_rol, user_id)
        )
        
        # Obtener el usuario actualizado
        usuario_actualizado = db.execute_query(
            "SELECT idUsuario, usuario, nombre, email, rol, fecha_creacion FROM usuarios_nul WHERE idUsuario = %s",
            (user_id,),
            fetch_one=True
        )
        
        if usuario_actualizado and usuario_actualizado.get('fecha_creacion'):
            # Si la fecha ya es string (JSON), no convertir
            if not isinstance(usuario_actualizado['fecha_creacion'], str):
                usuario_actualizado['fecha_creacion'] = usuario_actualizado['fecha_creacion'].strftime("%Y-%m-%d %H:%M:%S")
        
        # Obtener usuario actual que está actualizando el usuario
        current_user = get_user_from_token()
        actualizador_usuario = current_user.get('usuario', 'desconocido') if current_user else 'desconocido'
        actualizador_rol = current_user.get('rol', 'desconocido') if current_user else 'desconocido'
        
        # Limpiar caché de usuarios
        cache.delete("users_list")
        
        # Registrar acción de actualización de usuario
        action_logger.log_action(
            usuario=actualizador_usuario,
            accion='actualizar_usuario',
            nivel='movimiento',
            descripcion=f"Rol de usuario '{user_existente['usuario']}' actualizado de '{user_existente['rol']}' a '{nuevo_rol}' por '{actualizador_usuario}' (rol: {actualizador_rol})"
        )
        return jsonify({
            "mensaje": "Rol actualizado exitosamente",
            "usuario": usuario_actualizado
        }), 200
    except Exception as e:
        logger.error(f"Error al actualizar usuario: {e}")
        return jsonify({"error": "Error al actualizar usuario"}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@require_permission('manage_admins')
def delete_user(user_id):
    """Eliminar un usuario (solo superadmin)"""
    try:
        # Verificar que el usuario existe
        user_existente = db.execute_query(
            "SELECT idUsuario, usuario, rol FROM usuarios_nul WHERE idUsuario = %s",
            (user_id,),
            fetch_one=True
        )
        
        if not user_existente:
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        # No permitir eliminar al último superadmin
        if user_existente['rol'] == 'superadmin':
            superadmin_count = db.execute_query(
                "SELECT COUNT(*) as total FROM usuarios_nul WHERE rol = 'superadmin'",
                fetch_one=True
            )
            if superadmin_count and superadmin_count.get('total', 0) <= 1:
                return jsonify({"error": "No se puede eliminar el último superadmin del sistema"}), 400
        
        # Eliminar usuario
        db.execute_query(
            "DELETE FROM usuarios_nul WHERE idUsuario = %s",
            (user_id,)
        )
        
        # Obtener usuario actual que está eliminando el usuario
        current_user = get_user_from_token()
        eliminador_usuario = current_user.get('usuario', 'desconocido') if current_user else 'desconocido'
        eliminador_rol = current_user.get('rol', 'desconocido') if current_user else 'desconocido'
        
        # Limpiar caché de usuarios
        cache.delete("users_list")
        
        # Registrar acción de eliminación de usuario
        action_logger.log_action(
            usuario=eliminador_usuario,
            accion='eliminar_usuario',
            nivel='movimiento',
            descripcion=f"Usuario '{user_existente['usuario']}' (rol: {user_existente['rol']}) eliminado por '{eliminador_usuario}' (rol: {eliminador_rol})"
        )
        return jsonify({
            "mensaje": "Usuario eliminado exitosamente"
        }), 200
    except Exception as e:
        logger.error(f"Error al eliminar usuario: {e}")
        return jsonify({"error": "Error al eliminar usuario"}), 500

@app.route('/api/login', methods=['POST', 'OPTIONS'])
@apply_rate_limit("5 per minute")
def login():
    """Endpoint para autenticación de usuarios - usa cookies HTTP-only con rate limiting"""
    # Manejar preflight OPTIONS para CORS
    if request.method == 'OPTIONS':
        response = jsonify({})
        origin = request.headers.get('Origin', '')
        if origin and ('trycloudflare.com' in origin or origin in Config.CORS_ORIGINS):
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response, 200
    
    try:
        logger.info("[LOGIN] Endpoint de login llamado")
        logger.info(f"[LOGIN] Origen de la petición: {request.headers.get('Origin')}")
        logger.info(f"[LOGIN] Referer: {request.headers.get('Referer')}")
        logger.info(f"[LOGIN] Host: {request.headers.get('Host')}")
        logger.info(f"[LOGIN] Cookies recibidas: {dict(request.cookies)}")
        logger.info(f"[LOGIN] Método: {request.method}")
        logger.info(f"[LOGIN] Content-Type: {request.headers.get('Content-Type')}")
        
        data = request.get_json() or {}
        usuario = data.get("usuario")
        password = data.get("password")
        
        logger.info(f"[LOGIN] Intento de login para usuario: {usuario}")
        
        if not usuario or not password:
            logger.warning("[LOGIN] Usuario o contraseña faltantes")
            # Asegurar headers CORS para Cloudflare en respuesta de error
            response = jsonify({"error": "Usuario y contraseña requeridos"})
            origin = request.headers.get('Origin', '')
            if origin and is_cloudflare_origin(origin):
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
            return response, 400
        
        try:
            user = db.execute_query(
                "SELECT `idUsuario`, `usuario`, `contrasena`, `nombre`, `rol` FROM `usuarios_nul` WHERE `usuario` = %s",
                (usuario,),
                fetch_one=True
            )
        except Exception as e:
            logger.error(f"[LOGIN] Error en login: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Los headers CORS ya se agregan automáticamente por el decorador @app.after_request
            return jsonify({
                "error": "Error al consultar la base de datos",
                "message": "No se pudo conectar al servidor de base de datos. Por favor, intenta nuevamente."
            }), 500
        
        if not user:
            logger.warning(f"[LOGIN] Usuario no encontrado: {usuario}")
            # Registrar intento de login fallido como ataque
            action_logger.log_action(
                usuario=usuario,
                accion='login_fallido',
                nivel='ataque',
                descripcion=f"Intento de login fallido: usuario '{usuario}' no encontrado"
            )
            # Asegurar headers CORS para Cloudflare en respuesta de error
            response = jsonify({"error": "Credenciales incorrectas"})
            origin = request.headers.get('Origin', '')
            if origin and is_cloudflare_origin(origin):
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
            return response, 401
        
        stored_password = user.get('contrasena', '')
        input_password = password
        
        logger.info(f"[LOGIN] Verificando contraseña...")
        
        # Verificar si la contraseña almacenada es un hash bcrypt o texto plano (migración)
        if is_password_hashed(stored_password):
            # Contraseña está hasheada, usar bcrypt
            password_valid = verify_password(input_password, stored_password)
        else:
            # Contraseña en texto plano (legacy), comparar directamente y luego hashear
            logger.warning(f"[LOGIN] Usuario '{usuario}' tiene contraseña en texto plano. Debe actualizarse.")
            password_valid = (stored_password == input_password)
            
            # Si la contraseña es correcta, actualizar a hash
            if password_valid:
                try:
                    hashed_password = hash_password(input_password)
                    db.execute_query(
                        "UPDATE usuarios_nul SET contrasena = %s WHERE idUsuario = %s",
                        (hashed_password, user['idUsuario'])
                    )
                    logger.info(f"[LOGIN] Contraseña de usuario '{usuario}' actualizada a hash bcrypt")
                except Exception as e:
                    logger.error(f"[LOGIN] Error al actualizar contraseña a hash: {e}")
        
        if password_valid:
            rol = user.get('rol') or 'usuario'
            logger.info(f"[LOGIN] Login exitoso para usuario: {usuario}, rol: {rol}")
            
            # Registrar login exitoso
            action_logger.log_action(
                usuario=usuario,
                accion='login_exitoso',
                nivel='aviso',
                descripcion=f"Login exitoso para usuario '{usuario}' con rol '{rol}'"
            )
            
            token = generate_token(
                user_id=user['idUsuario'],
                usuario=user['usuario'],  # Usar usuario de la BD, no nombre
                rol=rol,
                nombre=user.get('nombre')
            )
            
            logger.info(f"[LOGIN] Token generado con rol: {rol}")
            logger.info(f"[LOGIN] Token (primeros 30 chars): {token[:30] if len(token) > 30 else token}")
            
            response = jsonify({
                "mensaje": "Inicio de sesión exitoso",
                "usuario": user.get('nombre') or user['usuario'],
                "nombre": user.get('nombre'),
                "rol": rol
            })
            
            # Obtener el origen de la petición para configurar la cookie correctamente
            origin = request.headers.get('Origin', '')
            logger.info(f"[LOGIN] Origen de la petición: {origin}")
            
            # Configurar cookie para que persista entre pestañas
            # IMPORTANTE: Las cookies se establecen en el dominio del servidor (localhost:5000)
            # El frontend (localhost:4321) puede enviar cookies cross-origin si están configuradas correctamente
            # Para que las cookies funcionen entre pestañas, necesitan:
            # 1. Mismo dominio (localhost en este caso)
            # 2. Mismo path (/)
            # 3. Configuración correcta de SameSite
            
            # Obtener el hostname de la petición para establecer el dominio correcto
            host = request.headers.get('Host', 'localhost:5000')
            hostname = host.split(':')[0] if ':' in host else host
            origin = request.headers.get('Origin', '')
            
            logger.info(f"[LOGIN] Host de la petición: {host}")
            logger.info(f"[LOGIN] Hostname extraído: {hostname}")
            logger.info(f"[LOGIN] Origin: {origin}")
            
            # Detectar si estamos usando Cloudflare Tunnel (dominios .trycloudflare.com)
            is_cloudflare = 'trycloudflare.com' in hostname or 'trycloudflare.com' in origin
            is_https = request.is_secure or origin.startswith('https://') or 'trycloudflare.com' in origin
            
            logger.info(f"[LOGIN] Es Cloudflare: {is_cloudflare}")
            logger.info(f"[LOGIN] Es HTTPS: {is_https}")
            
            # Configurar cookie según el entorno
            # Para Cloudflare Tunnel: usar secure=True y samesite='None'
            # Para localhost: usar secure=False y samesite='Lax'
            cookie_domain = None
            cookie_secure = is_https
            cookie_samesite = 'None' if is_cloudflare else 'Lax'
            
            # Si es Cloudflare, no establecer dominio específico (None funciona mejor)
            if is_cloudflare:
                cookie_domain = None
            else:
                cookie_domain = None  # Mantener None para localhost también
            
            response.set_cookie(
                'auth_token', 
                token, 
                max_age=86400,  # 24 horas
                httponly=True,  # HTTP-only para seguridad
                secure=cookie_secure,   # True para HTTPS (Cloudflare), False para HTTP (localhost)
                samesite=cookie_samesite, # 'None' para Cloudflare, 'Lax' para localhost
                path='/',       # Disponible en todo el path del dominio
                domain=cookie_domain     # None = dominio exacto del servidor
            )
            
            logger.info(f"[LOGIN] Cookie establecida correctamente")
            
            # Notificar a los observadores sobre el login (patrón Observer)
            auth_event_subject.user_logged_in({
                'usuario': user['usuario'],
                'rol': rol,
                'nombre': user.get('nombre')
            })
            logger.info(f"[LOGIN] Configuración: max_age=86400, httponly=True, secure={cookie_secure}, samesite={cookie_samesite}, path=/, domain={cookie_domain}")
            
            # Verificar que la cookie se estableció en los headers de respuesta
            # Nota: Flask no expone Set-Cookie directamente, pero podemos verificar si se estableció
            logger.info(f"[LOGIN] Cookie establecida para usuario: {usuario}")
            logger.info(f"[LOGIN] Response headers keys: {list(response.headers.keys())}")
            
            # Intentar obtener el valor de Set-Cookie del response (Flask lo maneja internamente)
            # Flask establece la cookie en el objeto response, pero no la muestra en headers hasta que se envía
            logger.info(f"[LOGIN] Cookie debería estar establecida en la respuesta")
            
            # Los headers CORS ya se agregan automáticamente por el decorador @app.after_request
            return response
        else:
            logger.warning(f"[LOGIN] Contraseña incorrecta para usuario: {usuario}")
            # Registrar intento de login fallido como ataque
            action_logger.log_action(
                usuario=usuario,
                accion='login_fallido',
                nivel='ataque',
                descripcion=f"Intento de login fallido: contraseña incorrecta para usuario '{usuario}'"
            )
            # Asegurar headers CORS para Cloudflare en respuesta de error
            response = jsonify({"error": "Credenciales incorrectas"})
            origin = request.headers.get('Origin', '')
            if origin and is_cloudflare_origin(origin):
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
            return response, 401
    except Exception as e:
        logger.error(f"[LOGIN] Error en login: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": "Error interno del servidor"}), 500


@app.route('/api/auth/logout', methods=['POST', 'GET'])
def logout():
    """Endpoint para cerrar sesión"""
    try:
        response = jsonify({
            "mensaje": "Sesión cerrada exitosamente"
        })
        
        # Detectar si estamos usando Cloudflare
        origin = request.headers.get('Origin', '')
        is_cloudflare = 'trycloudflare.com' in origin or 'trycloudflare.com' in request.headers.get('Host', '')
        is_https = request.is_secure or origin.startswith('https://') or is_cloudflare
        
        # Eliminar cookie - usar configuración según el entorno
        cookie_secure = is_https
        cookie_samesite = 'None' if is_cloudflare else 'Lax'
        
        response.set_cookie(
            'auth_token',
            '',
            max_age=0,
            httponly=True,
            secure=cookie_secure,
            samesite=cookie_samesite,
            path='/',
            domain=None
        )
        
        return response, 200
    except Exception as e:
        logger.error(f"Error en logout: {e}")
        return jsonify({"error": "Error al cerrar sesión"}), 500

@app.route('/api/news', methods=['GET'])
def get_news():
    """Obtener noticias desde MySQL (optimizado con caché, paginación, categorías y fijadas)"""
    try:
        # Obtener parámetros de paginación
        limit = request.args.get('limit', default=15, type=int)
        offset = request.args.get('offset', default=0, type=int)
        categoria_id = request.args.get('categoria', type=int)
        search = request.args.get('search', '').strip()
        
        # Clave de caché basada en parámetros
        cache_key = f"news_{limit}_{offset}_{categoria_id}_{search}"
        
        # Intentar obtener del caché (solo si no hay búsqueda)
        if not search:
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return jsonify(cached_result)
        
        # Construir query base
        where_clauses = []
        params = []
        
        # Filtro por categoría
        if categoria_id:
            where_clauses.append("n.id IN (SELECT noticia_id FROM noticias_categorias WHERE categoria_id = %s)")
            params.append(categoria_id)
        
        # Filtro por búsqueda
        if search:
            where_clauses.append("(n.titulo LIKE %s OR n.contenido LIKE %s OR n.autor LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # Query optimizada: ordenar por fecha descendente (más recientes primero)
        query = f"""SELECT n.id, n.titulo, n.contenido, n.autor, n.fecha, n.imagen_url as imagen,
                      COALESCE(u.nombre, n.autor) as nombre_autor,
                      COALESCE(u.rol, 'usuario') as rol_autor
               FROM noticias_nul n
               LEFT JOIN usuarios_nul u ON n.autor = u.usuario
               {where_sql}
               ORDER BY n.fecha DESC
               LIMIT %s OFFSET %s"""
        
        params.extend([limit, offset])
        
        noticias = db.execute_query(query, tuple(params), fetch_all=True)
        
        # Obtener categorías para cada noticia
        categorias_por_noticia = {}
        if noticias:
            noticia_ids = [n['id'] for n in noticias]
            if noticia_ids:
                # Usar parámetros preparados para seguridad
                placeholders = ','.join(['%s'] * len(noticia_ids))
                categorias_query = f"""SELECT nc.noticia_id, c.id, c.nombre, c.color
                                      FROM noticias_categorias nc
                                      JOIN categorias_nul c ON nc.categoria_id = c.id
                                      WHERE nc.noticia_id IN ({placeholders})"""
                categorias_data = db.execute_query(categorias_query, tuple(noticia_ids), fetch_all=True)
                
                # Agrupar categorías por noticia
                for cat in categorias_data:
                    noticia_id = cat['noticia_id']
                    if noticia_id not in categorias_por_noticia:
                        categorias_por_noticia[noticia_id] = []
                    categorias_por_noticia[noticia_id].append({
                        'id': cat['id'],
                        'nombre': cat['nombre'],
                        'color': cat['color']
                    })
        
        # Convertir fecha a string para JSON y agregar categorías
        for noticia in noticias:
            if noticia.get('fecha'):
                # Si la fecha ya es string (JSON), no convertir
                if isinstance(noticia['fecha'], str):
                    pass  # Ya es string, no hacer nada
                else:
                    # Si es datetime, convertir a string
                    noticia['fecha'] = noticia['fecha'].strftime("%Y-%m-%d %H:%M:%S")
            if not noticia.get('imagen'):
                noticia['imagen'] = ""
            noticia['categorias'] = categorias_por_noticia.get(noticia['id'], [])
        
        result = noticias if noticias else []
        
        # Guardar en caché solo si no hay búsqueda (TTL de 10 segundos para actualizaciones más rápidas)
        if not search:
            cache.set(cache_key, result, ttl=10)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error al obtener noticias: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": "Error al obtener noticias"}), 500

@app.route('/api/news/<int:news_id>', methods=['GET'])
@LoggingDecorator.log_operation("Obtener noticia por ID")
def get_news_by_id(news_id):
    """Obtener una noticia específica por ID desde MySQL (con caché) - Usando Facade Pattern"""
    try:
        # Usar la fachada para obtener la noticia (incluye caché automático)
        noticia = news_facade.get_news_by_id(news_id)
        
        if not noticia:
            return jsonify({"error": "Noticia no encontrada"}), 404
        
        return jsonify(noticia)
    except Exception as e:
        logger.error(f"Error al obtener noticia: {e}")
        return jsonify({"error": "Error al obtener la noticia"}), 500

@app.route('/api/news', methods=['POST'])
@require_permission('create')
@LoggingDecorator.log_operation("Crear noticia desde endpoint")
def create_news():
    """Crear una nueva noticia en MySQL (requiere permiso 'create': admin o maestro) - Usando Facade Pattern"""
    try:
        data = request.get_json() or {}
        titulo = data.get("titulo")
        contenido = data.get("contenido")
        autor = data.get("autor")
        imagen_url = data.get("imagen", "")  # URL de Firebase Storage o externa
        tipo_noticia = data.get("tipo", "general")  # Tipo de noticia (general, importante, evento, anuncio)
        categorias_ids = data.get("categorias", [])  # Lista de IDs de categorías
        
        # Validación básica de campos requeridos
        if not titulo or not contenido or not autor:
            return jsonify({"error": "Faltan campos requeridos: titulo, contenido, autor"}), 400
        
        # Obtener usuario actual que está creando la noticia
        current_user = get_user_from_token()
        creador_usuario = current_user.get('usuario', 'desconocido') if current_user else 'desconocido'
        creador_rol = current_user.get('rol', 'desconocido') if current_user else 'desconocido'
        
        # Usar la fachada para crear la noticia (encapsula validación, BD, categorías, caché)
        nueva_noticia = news_facade.create_news(
            titulo=titulo,
            contenido=contenido,
            autor=autor,
            imagen_url=imagen_url,
            tipo_noticia=tipo_noticia,
            categorias=categorias_ids
        )
        
        # Registrar acción de creación de noticia
        action_logger.log_action(
            usuario=creador_usuario,
            accion='crear_noticia',
            nivel='movimiento',
            descripcion=f"Noticia '{titulo}' (ID: {nueva_noticia.get('id')}) creada por '{creador_usuario}' (rol: {creador_rol})"
        )
        
        # Enviar evento de Pusher para notificar en tiempo real
        send_pusher_event('noticias', 'noticia-creada', {
            'id': nueva_noticia.get('id'),
            'titulo': titulo,
            'autor': autor
        })
        
        return jsonify({
            "mensaje": "Noticia creada exitosamente",
            "noticia": nueva_noticia
        }), 201
    except ValueError as e:
        # Error de validación
        logger.warning(f"Validación fallida: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error al crear noticia: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": "Error al crear la noticia"}), 500

@app.route('/api/news/<int:news_id>', methods=['PUT'])
@require_permission('edit')
@LoggingDecorator.log_operation("Actualizar noticia desde endpoint")
def update_news(news_id):
    """Actualizar una noticia existente (requiere permiso 'edit': solo admin) - Usando Facade Pattern"""
    try:
        data = request.get_json() or {}
        titulo = data.get("titulo")
        contenido = data.get("contenido")
        imagen_url = data.get("imagen")
        categorias_ids = data.get("categorias")
        
        # Verificar que hay al menos un campo para actualizar
        if titulo is None and contenido is None and imagen_url is None and categorias_ids is None:
            return jsonify({"error": "No se proporcionaron campos para actualizar"}), 400
        
        # Obtener usuario actual que está actualizando la noticia
        current_user = get_user_from_token()
        actualizador_usuario = current_user.get('usuario', 'desconocido') if current_user else 'desconocido'
        actualizador_rol = current_user.get('rol', 'desconocido') if current_user else 'desconocido'
        
        # Obtener título actual de la noticia para el log
        noticia_actual = news_facade.get_news_by_id(news_id)
        titulo_actual = noticia_actual.get('titulo', 'Sin título') if noticia_actual else 'Sin título'
        
        # Usar la fachada para actualizar la noticia (encapsula validación, BD, categorías, caché)
        noticia_actualizada = news_facade.update_news(
            news_id=news_id,
            titulo=titulo,
            contenido=contenido,
            imagen_url=imagen_url,
            categorias=categorias_ids
        )
        
        # Registrar acción de actualización de noticia
        action_logger.log_action(
            usuario=actualizador_usuario,
            accion='actualizar_noticia',
            nivel='movimiento',
            descripcion=f"Noticia '{titulo_actual}' (ID: {news_id}) actualizada por '{actualizador_usuario}' (rol: {actualizador_rol})"
        )
        
        # Enviar evento de Pusher para notificar en tiempo real
        send_pusher_event('noticias', 'noticia-actualizada', {
            'id': news_id,
            'titulo': noticia_actualizada.get('titulo', titulo_actual)
        })
        
        return jsonify({
            "mensaje": "Noticia actualizada exitosamente",
            "noticia": noticia_actualizada
        }), 200
    except ValueError as e:
        # Error de validación o noticia no encontrada
        logger.warning(f"Error de validación: {e}")
        return jsonify({"error": str(e)}), 404 if "no encontrada" in str(e) else 400
    except Exception as e:
        logger.error(f"Error al actualizar noticia: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": "Error al actualizar la noticia"}), 500

@app.route('/api/news/<int:news_id>', methods=['DELETE'])
@require_permission('delete')
@LoggingDecorator.log_operation("Eliminar noticia desde endpoint")
def delete_news(news_id):
    """Eliminar una noticia (requiere permiso 'delete': solo admin) - Usando Facade Pattern"""
    try:
        # Obtener usuario actual que está eliminando la noticia
        current_user = get_user_from_token()
        eliminador_usuario = current_user.get('usuario', 'desconocido') if current_user else 'desconocido'
        eliminador_rol = current_user.get('rol', 'desconocido') if current_user else 'desconocido'
        
        # Obtener título de la noticia antes de eliminarla para el log
        noticia_actual = news_facade.get_news_by_id(news_id)
        titulo_noticia = noticia_actual.get('titulo', 'Sin título') if noticia_actual else 'Sin título'
        
        # Usar la fachada para eliminar la noticia (encapsula Firebase, BD, caché)
        news_facade.delete_news(news_id)
        
        # Registrar acción de eliminación de noticia
        action_logger.log_action(
            usuario=eliminador_usuario,
            accion='eliminar_noticia',
            nivel='movimiento',
            descripcion=f"Noticia '{titulo_noticia}' (ID: {news_id}) eliminada por '{eliminador_usuario}' (rol: {eliminador_rol})"
        )
        
        # Enviar evento de Pusher para notificar en tiempo real
        send_pusher_event('noticias', 'noticia-eliminada', {
            'id': news_id,
            'titulo': titulo_noticia
        })
        
        return jsonify({
            "mensaje": "Noticia eliminada exitosamente"
        }), 200
    except ValueError as e:
        # Noticia no encontrada
        logger.warning(f"Noticia no encontrada: {e}")
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Error al eliminar noticia: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": "Error al eliminar la noticia"}), 500

@app.route('/api/notifications', methods=['GET'])
@require_auth
def get_notifications():
    """Obtener notificaciones recientes del sistema (patrón Observer)"""
    try:
        limit = request.args.get('limit', default=10, type=int)
        notifications = notification_observer.get_recent_notifications(limit=limit)
        return jsonify({
            "notifications": notifications,
            "total": len(notifications)
        }), 200
    except Exception as e:
        logger.error(f"Error al obtener notificaciones: {e}")
        return jsonify({"error": "Error al obtener notificaciones"}), 500

@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Obtener todas las categorías disponibles"""
    try:
        categorias = db.execute_query(
            "SELECT id, nombre, descripcion, color FROM categorias_nul ORDER BY nombre",
            fetch_all=True
        )
        
        return jsonify(categorias if categorias else []), 200
    except Exception as e:
        logger.error(f"Error al obtener categorías: {e}")
        return jsonify({"error": "Error al obtener categorías"}), 500

@app.route('/api/upload', methods=['POST'])
@require_permission('create')
def upload_image():
    """Endpoint para subir imágenes a Firebase Storage"""
    try:
        # Verificar que Firebase esté inicializado
        if not firebase._initialized:
            logger.error("Firebase no está inicializado")
            logger.error(f"Archivo de credenciales: {Config.FIREBASE_CREDENTIALS_PATH}")
            logger.error(f"¿Existe el archivo? {os.path.exists(Config.FIREBASE_CREDENTIALS_PATH)}")
            return jsonify({
                "error": "Firebase Storage no está configurado. Verifica que el archivo firebase-credentials.json exista en la carpeta backend/."
            }), 500
        
        if 'imagen' not in request.files:
            return jsonify({"error": "No se proporcionó ningún archivo"}), 400
        
        file = request.files['imagen']
        
        if file.filename == '':
            return jsonify({"error": "No se seleccionó ningún archivo"}), 400
        
        # Validar tipo de archivo
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        if file_ext not in allowed_extensions:
            return jsonify({"error": "Tipo de archivo no permitido. Solo se aceptan PNG, JPG, JPEG, GIF y WEBP."}), 400
        
        # Validar tamaño (máximo 10MB)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Resetear posición
        
        if file_size > 10 * 1024 * 1024:  # 10MB
            return jsonify({"error": "El archivo es demasiado grande. Máximo permitido: 10MB."}), 400
        
        # Generar nombre único para el archivo
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        destination_path = f"noticias/{unique_filename}"
        
        logger.info(f"Intentando subir imagen: {destination_path}")
        logger.info(f"Bucket configurado: {Config.FIREBASE_STORAGE_BUCKET}")
        
        # Subir a Firebase Storage
        image_url = firebase.upload_image_from_file_storage(file, destination_path)
        
        if not image_url:
            logger.error("Error: Firebase Storage no está disponible o hubo un error al subir")
            logger.error(f"Firebase inicializado: {firebase._initialized}")
            logger.error(f"Bucket configurado: {Config.FIREBASE_STORAGE_BUCKET}")
            return jsonify({
                "error": "Error al subir la imagen a Firebase Storage. Verifica los logs del servidor para más detalles."
            }), 500
        
        # Obtener usuario actual que está subiendo la imagen
        current_user = get_user_from_token()
        subidor_usuario = current_user.get('usuario', 'desconocido') if current_user else 'desconocido'
        subidor_rol = current_user.get('rol', 'desconocido') if current_user else 'desconocido'
        
        # Registrar acción de subida de imagen
        action_logger.log_action(
            usuario=subidor_usuario,
            accion='subir_imagen',
            nivel='movimiento',
            descripcion=f"Imagen '{destination_path}' subida exitosamente por '{subidor_usuario}' (rol: {subidor_rol}) - URL: {image_url}"
        )
        return jsonify({"url": image_url}), 200
        
    except Exception as e:
        logger.error(f"Error al subir imagen: {e}")
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(error_traceback)
        return jsonify({
            "error": f"Error interno al subir la imagen: {str(e)}",
            "details": error_traceback if Config.DEBUG else "Habilita DEBUG para ver más detalles"
        }), 500

@app.route('/api/config')
def get_config():
    config = ConfigSingleton()
    return jsonify(config.config)

@app.route('/api/firebase-status', methods=['GET'])
def firebase_status():
    """Endpoint para verificar el estado de Firebase"""
    try:
        creds_path = Config.FIREBASE_CREDENTIALS_PATH
        creds_exists = os.path.exists(creds_path)
        
        status = {
            "initialized": firebase._initialized,
            "credentials_path": creds_path,
            "credentials_exists": creds_exists,
            "bucket": Config.FIREBASE_STORAGE_BUCKET,
        }
        
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"Error al verificar estado de Firebase: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/pusher-config', methods=['GET'])
def pusher_config():
    """Endpoint para obtener la configuración de Pusher para el frontend"""
    try:
        if pusher_client and Config.PUSHER_KEY:
            return jsonify({
                "enabled": True,
                "key": Config.PUSHER_KEY,
                "cluster": Config.PUSHER_CLUSTER
            }), 200
        else:
            return jsonify({
                "enabled": False,
                "message": "Pusher no está configurado"
            }), 200
    except Exception as e:
        logger.error(f"Error al obtener configuración de Pusher: {e}")
        return jsonify({
            "enabled": False,
            "error": str(e)
        }), 500

@app.route('/api/permissions', methods=['GET'])
def get_permissions():
    """Obtener permisos del usuario actual basado en su rol"""
    try:
        user_role = request.headers.get('X-User-Role', 'usuario')
        permissions = get_user_permissions(user_role)
        
        return jsonify({
            "role": user_role,
            "permissions": permissions
        }), 200
    except Exception as e:
        logger.error(f"Error al obtener permisos: {e}")
        return jsonify({"error": "Error al obtener permisos"}), 500

@app.route('/api/cache/clear', methods=['POST', 'GET'])
def clear_cache():
    """Limpiar toda la caché del sistema (accesible por GET o POST para facilitar uso)"""
    try:
        cache.clear()
        logger.info("Caché limpiada manualmente")
        return jsonify({
            "mensaje": "Caché limpiada exitosamente",
            "success": True
        }), 200
    except Exception as e:
        logger.error(f"Error al limpiar caché: {e}")
        return jsonify({"error": "Error al limpiar caché"}), 500

@app.route('/api/auth/test-cookie', methods=['GET', 'POST'])
def test_cookie():
    """Endpoint de prueba para verificar que las cookies funcionen"""
    try:
        logger.info("[TEST-COOKIE] Endpoint llamado")
        logger.info(f"[TEST-COOKIE] Cookies recibidas: {dict(request.cookies)}")
        logger.info(f"[TEST-COOKIE] Headers recibidos: {dict(request.headers)}")
        logger.info(f"[TEST-COOKIE] Origen de la petición: {request.headers.get('Origin')}")
        
        # Intentar establecer una cookie de prueba
        response = jsonify({
            "message": "Cookie de prueba establecida",
            "cookies_received": dict(request.cookies),
            "origin": request.headers.get('Origin')
        })
        
        response.set_cookie(
            'test_cookie',
            'test_value_123',
            max_age=3600,
            httponly=False,  # No HTTP-only para poder verla en JavaScript
            secure=False,
            samesite='Lax',
            path='/'
        )
        
        logger.info("[TEST-COOKIE] Cookie de prueba establecida")
        return response, 200
    except Exception as e:
        logger.error(f"[TEST-COOKIE] Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/me', methods=['GET'])
def get_current_user():
    """Obtener información del usuario actual desde el token en la cookie"""
    try:
        logger.info("[AUTH/ME] Endpoint llamado")
        logger.info(f"[AUTH/ME] Origen: {request.headers.get('Origin', 'N/A')}")
        logger.info(f"[AUTH/ME] Cookies recibidas: {list(request.cookies.keys())}")
        
        # Intentar obtener el token
        token = get_token_from_request()
        if not token:
            logger.info("[AUTH/ME] No se encontró token")
            # Asegurar headers CORS para Cloudflare en respuesta de error
            response = jsonify({
                "authenticated": False,
                "message": "No hay sesión activa"
            })
            origin = request.headers.get('Origin', '')
            if origin and is_cloudflare_origin(origin):
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
            return response, 401
        
        # Verificar token y obtener datos del usuario
        user_data = get_user_from_token()
        if not user_data:
            logger.warning("[AUTH/ME] No user data found in token")
            # Asegurar headers CORS para Cloudflare en respuesta de error
            response = jsonify({"authenticated": False})
            origin = request.headers.get('Origin', '')
            if origin and is_cloudflare_origin(origin):
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
            return response, 401
        
        logger.info(f"[AUTH/ME] Usuario autenticado: {user_data.get('usuario')}, Rol: {user_data.get('rol')}")
        
        return jsonify({
            "authenticated": True,
            "usuario": user_data.get('usuario'),
            "nombre": user_data.get('nombre'),
            "rol": user_data.get('rol'),
            "user_id": user_data.get('user_id')
        }), 200
    except Exception as e:
        logger.error(f"[AUTH/ME] Error general al obtener usuario actual: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            "authenticated": False,
            "error": f"Error interno: {str(e)}"
        }), 500

@app.route('/api/actions', methods=['GET'])
@require_permission('manage_admins')
def get_actions():
    """Obtener acciones registradas desde la base de datos (solo superadmin)"""
    try:
        limit = request.args.get('limit', default=100, type=int)
        offset = request.args.get('offset', default=0, type=int)
        nivel = request.args.get('nivel', type=str)
        usuario = request.args.get('usuario', type=str)
        
        actions = action_logger.get_actions(
            limit=limit,
            offset=offset,
            nivel=nivel,
            usuario=usuario
        )
        
        total = action_logger.get_actions_count(nivel=nivel, usuario=usuario)
        
        return jsonify({
            'actions': actions,
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200
    except Exception as e:
        logger.error(f"Error al obtener acciones: {e}")
        return jsonify({"error": "Error al obtener acciones"}), 500

@app.route('/api/actions/levels', methods=['GET'])
@require_permission('manage_admins')
def get_action_levels():
    """Obtener información sobre los niveles de afectación disponibles"""
    try:
        return jsonify({
            'levels': NIVELES_AFECTACION,
            'available_levels': list(NIVELES_AFECTACION.keys())
        }), 200
    except Exception as e:
        logger.error(f"Error al obtener niveles: {e}")
        return jsonify({"error": "Error al obtener niveles"}), 500

@app.route('/api/logs/actions', methods=['GET'])
@require_permission('manage_admins')
def get_action_logs():
    """Obtener contenido del archivo de log de acciones (solo superadmin)"""
    try:
        limit = request.args.get('limit', default=500, type=int)
        log_file_path = os.path.join(log_dir, 'actions.log')
        
        if not os.path.exists(log_file_path):
            return jsonify({
                'logs': [],
                'message': 'El archivo de log no existe aún'
            }), 200
        
        # Leer las últimas líneas del archivo
        with open(log_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Obtener las últimas 'limit' líneas
        recent_lines = lines[-limit:] if len(lines) > limit else lines
        
        # Formatear las líneas
        logs = []
        for line in recent_lines:
            line = line.strip()
            if line:
                logs.append({
                    'line': line,
                    'timestamp': line.split(' - ')[0] if ' - ' in line else ''
                })
        
        return jsonify({
            'logs': logs,
            'total_lines': len(lines),
            'returned_lines': len(logs)
        }), 200
    except Exception as e:
        logger.error(f"Error al leer archivo de log: {e}")
        return jsonify({"error": f"Error al leer archivo de log: {str(e)}"}), 500

@app.route('/api/debug/tables', methods=['GET'])
def debug_tables():
    """Endpoint para debug: mostrar información de las tablas del proyecto"""
    try:
        project_tables = {
            'usuarios_nul': {
                'name': 'usuarios_nul',
                'description': 'Usuarios del sistema'
            },
            'noticias_nul': {
                'name': 'noticias_nul',
                'description': 'Noticias publicadas'
            },
            'categorias_nul': {
                'name': 'categorias_nul',
                'description': 'Categorías de noticias'
            },
            'noticias_categorias': {
                'name': 'noticias_categorias',
                'description': 'Relación noticias-categorías'
            }
        }
        
        tables_info = []
        
        for table_key, table_info in project_tables.items():
            table_name = table_info['name']
            
            # Contar registros
            count_result = db.execute_query(
                f"SELECT COUNT(*) as total FROM `{table_name}`",
                fetch_one=True
            )
            total = count_result.get('total', 0) if count_result else 0
            
            # Obtener estructura de la tabla
            columns_result = db.execute_query(
                f"DESCRIBE `{table_name}`",
                fetch_all=True
            )
            columns = columns_result if columns_result else []
            
            # Obtener algunos registros de ejemplo (máximo 5)
            sample_data = []
            if total > 0:
                try:
                    sample_result = db.execute_query(
                        f"SELECT * FROM `{table_name}` LIMIT 5",
                        fetch_all=True
                    )
                    if sample_result:
                        sample_data = sample_result
                except Exception as e:
                    logger.warning(f"No se pudieron obtener datos de muestra de {table_name}: {e}")
            
            tables_info.append({
                'name': table_name,
                'description': table_info['description'],
                'total_records': total,
                'columns': columns,
                'sample_data': sample_data
            })
        
        return jsonify({
            'success': True,
            'tables': tables_info,
            'database': Config.MYSQL_DATABASE,
            'host': Config.MYSQL_HOST
        }), 200
        
    except Exception as e:
        logger.error(f"Error en debug_tables: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# Database Manager Dashboard (tipo phpMyAdmin)
# ============================================

@app.route('/db-manager')
@require_permission('manage_admins')  # Solo superadmin puede acceder
def db_manager():
    """Página principal del Database Manager"""
    return """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DB Manager</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f5f5;
            color: #333;
        }
        .header {
            background: #4a5568;
            color: white;
            padding: 1rem 2rem;
            border-bottom: 2px solid #2d3748;
        }
        .header h1 { font-size: 1.5rem; }
        .container {
            max-width: 1400px;
            margin: 2rem auto;
            padding: 0 2rem;
        }
        .sidebar {
            background: white;
            border: 1px solid #ddd;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }
        .table-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 1rem;
        }
        .table-card {
            background: white;
            border: 1px solid #ddd;
            padding: 1rem;
            cursor: pointer;
        }
        .table-card:hover {
            border-color: #4a5568;
            background: #f7fafc;
        }
        .table-card.active {
            border-color: #4a5568;
            background: #4a5568;
            color: white;
        }
        .table-card h3 {
            font-size: 1rem;
            margin-bottom: 0.5rem;
        }
        .table-card .count {
            font-size: 0.85rem;
            opacity: 0.8;
        }
        .main-content {
            background: white;
            border: 1px solid #ddd;
            padding: 2rem;
        }
        .toolbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid #e9ecef;
        }
        .btn {
            background: #4a5568;
            color: white;
            border: none;
            padding: 0.6rem 1.2rem;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .btn:hover { background: #2d3748; }
        .btn-danger { background: #c53030; }
        .btn-danger:hover { background: #9b2c2c; }
        .btn-success { background: #38a169; }
        .btn-success:hover { background: #2f855a; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }
        th, td {
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid #e9ecef;
        }
        th {
            background: #f8f9fa;
            font-weight: 600;
            color: #495057;
            position: sticky;
            top: 0;
        }
        tr:hover { background: #f8f9fa; }
        .actions {
            display: flex;
            gap: 0.5rem;
        }
        .btn-sm {
            padding: 0.3rem 0.6rem;
            font-size: 0.8rem;
        }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: white;
            padding: 2rem;
            border: 1px solid #ddd;
            max-width: 600px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
        }
        .form-group {
            margin-bottom: 1rem;
        }
        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 500;
        }
        .form-group input,
        .form-group textarea,
        .form-group select {
            width: 100%;
            padding: 0.6rem;
            border: 1px solid #ccc;
            font-size: 0.9rem;
        }
        .form-group textarea {
            min-height: 100px;
            resize: vertical;
        }
        .loading {
            text-align: center;
            padding: 2rem;
            color: #667eea;
        }
        .empty-state {
            text-align: center;
            padding: 3rem;
            color: #6c757d;
        }
        .badge {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            font-size: 0.75rem;
            background: #e2e8f0;
            color: #2d3748;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>DB Manager</h1>
    </div>
    
    <div class="container">
        <div class="sidebar">
            <h2 style="margin-bottom: 1rem;">Tablas</h2>
            <div class="table-list" id="tableList">
                <div class="loading">Cargando tablas...</div>
            </div>
        </div>
        
        <div class="main-content" id="mainContent">
            <div class="empty-state">
                <h3>Selecciona una tabla para ver sus datos</h3>
            </div>
        </div>
    </div>
    
    <!-- Modal para editar/crear -->
    <div class="modal" id="editModal">
        <div class="modal-content">
            <h2 id="modalTitle">Editar Registro</h2>
            <form id="editForm">
                <div id="formFields"></div>
                <div style="display: flex; gap: 1rem; margin-top: 1.5rem;">
                    <button type="submit" class="btn btn-success">Guardar</button>
                    <button type="button" class="btn" onclick="closeModal()">Cancelar</button>
                </div>
            </form>
        </div>
    </div>
    
    <script>
        let currentTable = null;
        let currentData = [];
        
        // Cargar tablas al inicio
        async function loadTables() {
            try {
                const response = await fetch('/api/db/tables');
                const data = await response.json();
                
                const tableList = document.getElementById('tableList');
                tableList.innerHTML = '';
                
                data.tables.forEach(table => {
                    const card = document.createElement('div');
                    card.className = 'table-card';
                    card.onclick = () => loadTable(table.name);
                    card.innerHTML = `
                        <h3>${table.name}</h3>
                        <div class="count">${table.count} registros</div>
                    `;
                    tableList.appendChild(card);
                });
            } catch (error) {
                console.error('Error cargando tablas:', error);
            }
        }
        
        // Cargar datos de una tabla
        async function loadTable(tableName) {
            currentTable = tableName;
            
            // Actualizar UI
            document.querySelectorAll('.table-card').forEach(card => {
                card.classList.remove('active');
                if (card.querySelector('h3').textContent === tableName) {
                    card.classList.add('active');
                }
            });
            
            try {
                const response = await fetch(`/api/db/table/${tableName}`);
                const data = await response.json();
                
                currentData = data.records || [];
                renderTable(data.records || [], data.columns || []);
            } catch (error) {
                console.error('Error cargando tabla:', error);
                document.getElementById('mainContent').innerHTML = 
                    '<div class="empty-state"><h3>Error al cargar la tabla</h3></div>';
            }
        }
        
        // Renderizar tabla
        function renderTable(records, columns) {
            const mainContent = document.getElementById('mainContent');
            
            if (records.length === 0) {
                mainContent.innerHTML = `
                    <div class="toolbar">
                        <h2>${currentTable}</h2>
                        <button class="btn btn-success" onclick="openCreateModal()">+ Nuevo Registro</button>
                    </div>
                    <div class="empty-state">
                        <h3>No hay registros en esta tabla</h3>
                        <p>Haz clic en "Nuevo Registro" para agregar uno</p>
                    </div>
                `;
                return;
            }
            
            // Obtener columnas de los registros si no se proporcionan
            const tableColumns = columns.length > 0 ? columns : Object.keys(records[0]);
            
            let html = `
                <div class="toolbar">
                    <h2>${currentTable} <span class="badge">${records.length} registros</span></h2>
                    <button class="btn btn-success" onclick="openCreateModal()">+ Nuevo Registro</button>
                </div>
                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                ${tableColumns.map(col => `<th>${col}</th>`).join('')}
                                <th>Acciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${records.map((record, idx) => `
                                <tr>
                                    ${tableColumns.map(col => {
                                        let value = record[col];
                                        if (value === null || value === undefined) value = '<em>null</em>';
                                        else if (typeof value === 'object') value = JSON.stringify(value);
                                        else if (String(value).length > 50) value = String(value).substring(0, 50) + '...';
                                        return `<td>${value}</td>`;
                                    }).join('')}
                                    <td>
                                        <div class="actions">
                                            <button class="btn btn-sm" onclick="openEditModal(${idx})">Editar</button>
                                            <button class="btn btn-sm btn-danger" onclick="deleteRecord(${idx})">Eliminar</button>
                                        </div>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
            
            mainContent.innerHTML = html;
        }
        
        // Abrir modal de edición
        function openEditModal(index) {
            const record = currentData[index];
            const columns = Object.keys(record);
            
            document.getElementById('modalTitle').textContent = 'Editar Registro';
            const formFields = document.getElementById('formFields');
            formFields.innerHTML = columns.map(col => {
                let value = record[col];
                if (value === null || value === undefined) value = '';
                else if (typeof value === 'object') value = JSON.stringify(value);
                
                return `
                    <div class="form-group">
                        <label>${col}</label>
                        <input type="text" name="${col}" value="${String(value).replace(/"/g, '&quot;')}" ${col.includes('id') || col.includes('Id') ? 'readonly' : ''}>
                    </div>
                `;
            }).join('');
            
            document.getElementById('editForm').onsubmit = (e) => {
                e.preventDefault();
                saveRecord(index);
            };
            
            document.getElementById('editModal').classList.add('active');
        }
        
        // Abrir modal de creación
        function openCreateModal() {
            if (currentData.length > 0) {
                const columns = Object.keys(currentData[0]);
                document.getElementById('modalTitle').textContent = 'Nuevo Registro';
                const formFields = document.getElementById('formFields');
                formFields.innerHTML = columns.map(col => {
                    // Omitir campos ID auto-incrementales
                    if (col.toLowerCase().includes('id') && col !== 'idUsuario') {
                        return '';
                    }
                    return `
                        <div class="form-group">
                            <label>${col}</label>
                            <input type="text" name="${col}" value="">
                        </div>
                    `;
                }).filter(html => html).join('');
            } else {
                // Si no hay registros, pedir columnas manualmente
                document.getElementById('modalTitle').textContent = 'Nuevo Registro';
                document.getElementById('formFields').innerHTML = `
                    <div class="form-group">
                        <label>Columnas (separadas por comas)</label>
                        <input type="text" name="columns" placeholder="campo1, campo2, campo3">
                    </div>
                `;
            }
            
            document.getElementById('editForm').onsubmit = (e) => {
                e.preventDefault();
                createRecord();
            };
            
            document.getElementById('editModal').classList.add('active');
        }
        
        // Cerrar modal
        function closeModal() {
            document.getElementById('editModal').classList.remove('active');
        }
        
        // Guardar registro editado
        async function saveRecord(index) {
            const form = document.getElementById('editForm');
            const formData = new FormData(form);
            const data = {};
            
            for (let [key, value] of formData.entries()) {
                // Intentar parsear como JSON si parece ser un objeto
                if (value.startsWith('{') || value.startsWith('[')) {
                    try {
                        data[key] = JSON.parse(value);
                    } catch {
                        data[key] = value;
                    }
                } else {
                    data[key] = value;
                }
            }
            
            try {
                const response = await fetch(`/api/db/table/${currentTable}/record/${currentData[index].id || index}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                
                if (response.ok) {
                    closeModal();
                    loadTable(currentTable);
                } else {
                    alert('Error al guardar');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Error al guardar');
            }
        }
        
        // Crear nuevo registro
        async function createRecord() {
            const form = document.getElementById('editForm');
            const formData = new FormData(form);
            const data = {};
            
            for (let [key, value] of formData.entries()) {
                if (key === 'columns') continue;
                data[key] = value;
            }
            
            try {
                const response = await fetch(`/api/db/table/${currentTable}/record`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                
                if (response.ok) {
                    closeModal();
                    loadTable(currentTable);
                } else {
                    alert('Error al crear registro');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Error al crear registro');
            }
        }
        
        // Eliminar registro
        async function deleteRecord(index) {
            if (!confirm('¿Estás seguro de eliminar este registro?')) return;
            
            const record = currentData[index];
            const idField = Object.keys(record).find(k => k.toLowerCase().includes('id'));
            const recordId = record[idField] || index;
            
            try {
                const response = await fetch(`/api/db/table/${currentTable}/record/${recordId}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    loadTable(currentTable);
                } else {
                    alert('Error al eliminar');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Error al eliminar');
            }
        }
        
        // Inicializar
        loadTables();
    </script>
</body>
</html>
    """

@app.route('/api/db/tables', methods=['GET'])
@require_permission('manage_admins')
def get_db_tables():
    """Obtener lista de todas las tablas en la base de datos JSON"""
    try:
        if Config.DATABASE_TYPE != 'json':
            return jsonify({"error": "Este endpoint solo funciona con base de datos JSON"}), 400
        
        # Cargar datos directamente desde el archivo JSON
        db_file = os.path.join(os.path.dirname(__file__), 'database.json')
        with open(db_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        tables = []
        for table_name, records in data.items():
            if table_name != 'last_ids' and isinstance(records, list):
                tables.append({
                    'name': table_name,
                    'count': len(records),
                    'columns': list(records[0].keys()) if records else []
                })
        
        return jsonify({
            'success': True,
            'tables': tables
        }), 200
    except Exception as e:
        logger.error(f"Error al obtener tablas: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/db/table/<table_name>', methods=['GET'])
@require_permission('manage_admins')
def get_table_data(table_name):
    """Obtener todos los registros de una tabla específica"""
    try:
        if Config.DATABASE_TYPE != 'json':
            return jsonify({"error": "Este endpoint solo funciona con base de datos JSON"}), 400
        
        db_file = os.path.join(os.path.dirname(__file__), 'database.json')
        with open(db_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if table_name not in data:
            return jsonify({"error": f"Tabla '{table_name}' no encontrada"}), 404
        
        records = data[table_name]
        columns = list(records[0].keys()) if records else []
        
        return jsonify({
            'success': True,
            'table': table_name,
            'records': records,
            'columns': columns,
            'count': len(records)
        }), 200
    except Exception as e:
        logger.error(f"Error al obtener datos de tabla: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/db/table/<table_name>/record', methods=['POST'])
@require_permission('manage_admins')
def create_table_record(table_name):
    """Crear un nuevo registro en una tabla"""
    try:
        if Config.DATABASE_TYPE != 'json':
            return jsonify({"error": "Este endpoint solo funciona con base de datos JSON"}), 400
        
        db_file = os.path.join(os.path.dirname(__file__), 'database.json')
        with open(db_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if table_name not in data:
            return jsonify({"error": f"Tabla '{table_name}' no encontrada"}), 404
        
        new_record = request.get_json()
        
        # Generar ID si es necesario
        id_field = db.get_id_field(table_name) if hasattr(db, 'get_id_field') else None
        if id_field and id_field not in new_record:
            if 'last_ids' not in data:
                data['last_ids'] = {}
            if table_name not in data['last_ids']:
                data['last_ids'][table_name] = 0
            data['last_ids'][table_name] += 1
            new_record[id_field] = data['last_ids'][table_name]
        
        # Agregar fecha si existe el campo
        if 'fecha_creacion' in new_record or 'fecha' in new_record:
            if 'fecha_creacion' not in new_record:
                new_record['fecha_creacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if 'fecha' not in new_record and table_name == 'noticias_nul':
                new_record['fecha'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        data[table_name].append(new_record)
        
        with open(db_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True,
            'record': new_record
        }), 201
    except Exception as e:
        logger.error(f"Error al crear registro: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/db/table/<table_name>/record/<record_id>', methods=['PUT'])
@require_permission('manage_admins')
def update_table_record(table_name, record_id):
    """Actualizar un registro en una tabla"""
    try:
        if Config.DATABASE_TYPE != 'json':
            return jsonify({"error": "Este endpoint solo funciona con base de datos JSON"}), 400
        
        db_file = os.path.join(os.path.dirname(__file__), 'database.json')
        with open(db_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if table_name not in data:
            return jsonify({"error": f"Tabla '{table_name}' no encontrada"}), 404
        
        updated_data = request.get_json()
        id_field = db.get_id_field(table_name) if hasattr(db, 'get_id_field') else 'id'
        
        # Buscar y actualizar el registro
        for i, record in enumerate(data[table_name]):
            if str(record.get(id_field, i)) == str(record_id):
                data[table_name][i].update(updated_data)
                
                with open(db_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                return jsonify({
                    'success': True,
                    'record': data[table_name][i]
                }), 200
        
        return jsonify({"error": "Registro no encontrado"}), 404
    except Exception as e:
        logger.error(f"Error al actualizar registro: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/db/table/<table_name>/record/<record_id>', methods=['DELETE'])
@require_permission('manage_admins')
def delete_table_record(table_name, record_id):
    """Eliminar un registro de una tabla"""
    try:
        if Config.DATABASE_TYPE != 'json':
            return jsonify({"error": "Este endpoint solo funciona con base de datos JSON"}), 400
        
        db_file = os.path.join(os.path.dirname(__file__), 'database.json')
        with open(db_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if table_name not in data:
            return jsonify({"error": f"Tabla '{table_name}' no encontrada"}), 404
        
        id_field = db.get_id_field(table_name) if hasattr(db, 'get_id_field') else 'id'
        
        # Buscar y eliminar el registro
        for i, record in enumerate(data[table_name]):
            if str(record.get(id_field, i)) == str(record_id):
                deleted = data[table_name].pop(i)
                
                with open(db_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                return jsonify({
                    'success': True,
                    'message': 'Registro eliminado'
                }), 200
        
        return jsonify({"error": "Registro no encontrado"}), 404
    except Exception as e:
        logger.error(f"Error al eliminar registro: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info("🚀 Iniciando servidor Flask...")
    app.run(debug=True)

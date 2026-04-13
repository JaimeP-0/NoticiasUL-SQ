"""
Módulo para manejar autenticación JWT
"""
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify
from config import Config
import logging

logger = logging.getLogger(__name__)

# Clave secreta para firmar los tokens (en producción usar variable de entorno)
JWT_SECRET_KEY = getattr(Config, 'JWT_SECRET_KEY', 'tu-clave-secreta-super-segura-cambiar-en-produccion')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24  # Token válido por 24 horas

def generate_token(user_id, usuario, rol, nombre=None):
    """
    Generar un token JWT para un usuario
    
    Args:
        user_id: ID del usuario
        usuario: Nombre de usuario
        rol: Rol del usuario
        nombre: Nombre completo (opcional)
    
    Returns:
        str: Token JWT codificado
    """
    now = datetime.now(timezone.utc)
    payload = {
        'user_id': user_id,
        'usuario': usuario,
        'rol': rol,
        'nombre': nombre,
        'exp': now + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': now
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token

def verify_token(token):
    """
    Verificar y decodificar un token JWT
    
    Args:
        token: Token JWT a verificar
    
    Returns:
        dict: Payload del token si es válido, None si no lo es
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expirado")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Token inválido")
        return None

def get_token_from_request():
    """
    Extraer el token JWT del header Authorization o de la cookie
    
    Returns:
        str: Token si existe, None si no
    """
    try:
        # Primero intentar desde el header Authorization (para compatibilidad con API calls)
        auth_header = request.headers.get('Authorization')
        if auth_header:
            try:
                # Formato: "Bearer <token>"
                token = auth_header.split(' ')[1]
                logger.info("[JWT] Token obtenido desde header Authorization")
                return token
            except IndexError:
                logger.warning("[JWT] Formato incorrecto en header Authorization")
                # Continuar y probar la cookie auth_token
        
        # Si no está en el header, intentar desde la cookie (para navegador)
        token = request.cookies.get('auth_token')
        if token:
            logger.info("[JWT] Token obtenido desde cookie")
            return token
        logger.warning("[JWT] No se encontró token en cookie 'auth_token'")
        logger.info("[JWT] Petición sin token en cookie (número de cookies: %s)", len(request.cookies))
        
        return None
    except Exception as e:
        logger.error(f"[JWT] Error al obtener token: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def require_auth(f):
    """
    Decorador para proteger endpoints que requieren autenticación
    
    Usage:
        @app.route('/api/protected')
        @require_auth
        def protected_route():
            user = request.current_user  # Disponible después de la autenticación
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_token_from_request()
        
        if not token:
            return jsonify({
                "error": "Token de autenticación requerido",
                "message": "Debes iniciar sesión para acceder a este recurso"
            }), 401
        
        payload = verify_token(token)
        if not payload:
            return jsonify({
                "error": "Token inválido o expirado",
                "message": "Tu sesión ha expirado. Por favor, inicia sesión nuevamente"
            }), 401
        
        # Agregar información del usuario al request
        request.current_user = {
            'user_id': payload.get('user_id'),
            'usuario': payload.get('usuario'),
            'rol': payload.get('rol'),
            'nombre': payload.get('nombre')
        }
        
        return f(*args, **kwargs)
    return decorated_function

def get_user_from_token():
    """
    Obtener información del usuario desde el token (sin decorador)
    Útil para endpoints que pueden ser opcionales
    
    Returns:
        dict: Información del usuario o None
    """
    try:
        token = get_token_from_request()
        if token:
            logger.info("[JWT] Verificando token")
            payload = verify_token(token)
            if payload:
                user_info = {
                    'user_id': payload.get('user_id'),
                    'usuario': payload.get('usuario'),
                    'rol': payload.get('rol'),
                    'nombre': payload.get('nombre')
                }
                logger.info(
                    "[JWT] Token válido (user_id=%s, rol=%s)",
                    user_info.get('user_id'),
                    user_info.get('rol'),
                )
                return user_info
            else:
                logger.warning("[JWT] Token inválido o expirado")
        else:
            logger.warning("[JWT] No se encontró token en la petición")
        return None
    except Exception as e:
        logger.error(f"[JWT] Error en get_user_from_token: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


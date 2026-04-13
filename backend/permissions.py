"""
Sistema de permisos y autorización basado en roles
"""
from functools import wraps
from flask import request, jsonify
from jwt_auth import get_user_from_token
import logging

logger = logging.getLogger(__name__)

# Definición de permisos por rol
ROLE_PERMISSIONS = {
    'superadmin': {
        'view': True,
        'create': True,
        'edit': True,
        'delete': True,
        'manage_users': True,  # Puede gestionar usuarios y asignar roles
        'manage_admins': True   # Solo superadmin puede crear/editar admins y maestros
    },
    'admin': {
        'view': True,
        'create': True,
        'edit': True,
        'delete': True,
        'manage_users': False,  # Admin ya no puede gestionar usuarios
        'manage_admins': False
    },
    'maestro': {
        'view': True,
        'create': True,
        'edit': False,
        'delete': False,
        'manage_users': False,
        'manage_admins': False
    },
    'usuario': {
        'view': True,
        'create': False,
        'edit': False,
        'delete': False,
        'manage_users': False,
        'manage_admins': False
    }
}

def get_user_role_from_request():
    """
    Obtener el rol del usuario desde el token JWT o header de la petición
    Prioridad: Token JWT > Header X-User-Role > 'usuario' por defecto
    """
    # Intentar obtener del token JWT primero
    user = get_user_from_token()
    if user and user.get('rol'):
        return user['rol']
    
    # Fallback al header (para compatibilidad)
    return request.headers.get('X-User-Role', 'usuario')

def has_permission(role, permission):
    """
    Verificar si un rol tiene un permiso específico
    
    Args:
        role: Rol del usuario ('superadmin', 'admin', 'maestro', 'usuario')
        permission: Permiso a verificar ('view', 'create', 'edit', 'delete', 'manage_users', 'manage_admins')
    
    Returns:
        bool: True si el rol tiene el permiso, False en caso contrario
    """
    if role not in ROLE_PERMISSIONS:
        logger.warning("Rol desconocido en permisos; se usa rol 'usuario' por defecto")
        role = 'usuario'
    
    return ROLE_PERMISSIONS.get(role, {}).get(permission, False)

def require_permission(permission):
    """
    Decorador para proteger endpoints que requieren un permiso específico
    
    Args:
        permission: Permiso requerido ('view', 'create', 'edit', 'delete', 'manage_users', 'manage_admins')
    
    Usage:
        @app.route('/api/news', methods=['POST'])
        @require_permission('create')
        def create_news():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Obtener rol del usuario desde el header
            user_role = get_user_role_from_request()
            
            # Verificar si el usuario tiene el permiso
            if not has_permission(user_role, permission):
                logger.warning("Acceso denegado: permiso insuficiente para el recurso solicitado")
                return jsonify({
                    "error": "No tienes permisos para realizar esta acción",
                    "required_permission": permission,
                    "user_role": user_role
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_role(*allowed_roles):
    """
    Decorador para proteger endpoints que requieren roles específicos
    
    Args:
        *allowed_roles: Roles permitidos ('admin', 'maestro', 'usuario')
    
    Usage:
        @app.route('/api/admin/users', methods=['GET'])
        @require_role('admin')
        def get_users():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_role = get_user_role_from_request()
            
            if user_role not in allowed_roles:
                logger.warning("Acceso denegado: rol no autorizado para el recurso solicitado")
                return jsonify({
                    "error": "No tienes permisos para acceder a este recurso",
                    "required_roles": list(allowed_roles),
                    "user_role": user_role
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_user_permissions(role):
    """
    Obtener todos los permisos de un rol
    
    Args:
        role: Rol del usuario
    
    Returns:
        dict: Diccionario con todos los permisos del rol
    """
    return ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS['usuario'])


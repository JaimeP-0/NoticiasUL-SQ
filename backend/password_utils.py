"""
Utilidades para el manejo seguro de contraseñas usando bcrypt
"""
import bcrypt
import logging

logger = logging.getLogger(__name__)

def hash_password(password):
    """
    Generar hash de contraseña usando bcrypt
    
    Args:
        password: Contraseña en texto plano
    
    Returns:
        str: Hash de la contraseña (string codificado)
    """
    try:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error(f"Error al hashear contraseña: {e}")
        raise

def verify_password(password, hashed):
    """
    Verificar contraseña contra hash almacenado
    
    Args:
        password: Contraseña en texto plano a verificar
        hashed: Hash almacenado en la base de datos
    
    Returns:
        bool: True si la contraseña coincide, False en caso contrario
    """
    try:
        if not hashed:
            return False
        
        # Asegurar que hashed sea bytes
        if isinstance(hashed, str):
            hashed = hashed.encode('utf-8')
        
        # Verificar contraseña
        return bcrypt.checkpw(password.encode('utf-8'), hashed)
    except Exception as e:
        logger.error(f"Error al verificar contraseña: {e}")
        return False

def is_password_hashed(password_string):
    """
    Verificar si una cadena parece ser un hash bcrypt
    
    Args:
        password_string: Cadena a verificar
    
    Returns:
        bool: True si parece ser un hash bcrypt
    """
    # Los hashes bcrypt tienen un formato específico: $2b$ o $2a$ seguido de cost y salt
    if isinstance(password_string, str) and password_string.startswith('$2'):
        return True
    return False

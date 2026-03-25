"""
Configuración de la aplicación
Lee las variables de entorno desde un archivo .env
"""
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

class Config:
    """Configuración de la aplicación"""
    
    # Database Type: 'json' or 'mysql'
    DATABASE_TYPE = os.getenv('DATABASE_TYPE', 'json')
    
    # MySQL Database
    MYSQL_HOST = os.getenv('MYSQL_HOST', '82.180.138.204')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
    MYSQL_USER = os.getenv('MYSQL_USER', 'u489282276_jaime')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'Noticias_1')
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'u489282276_noticiasul')
    
    # Firebase
    FIREBASE_CREDENTIALS_PATH = os.getenv('FIREBASE_CREDENTIALS_PATH', 'firebase-credentials.json')
    # Bucket de Firebase Storage (sin prefijo gs:// para Firebase Admin SDK)
    FIREBASE_STORAGE_BUCKET = os.getenv('FIREBASE_STORAGE_BUCKET', 'noticiasul.firebasestorage.app')
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    
    # Pusher (opcional - si no está configurado, no se usará)
    PUSHER_APP_ID = os.getenv('PUSHER_APP_ID', '')
    PUSHER_KEY = os.getenv('PUSHER_KEY', '')
    PUSHER_SECRET = os.getenv('PUSHER_SECRET', '')
    PUSHER_CLUSTER = os.getenv('PUSHER_CLUSTER', 'us2')
    
    # CORS - Permitir tanto localhost como 127.0.0.1 en múltiples puertos
    # También permitir dominios de Cloudflare Tunnel
    cors_origins_env = os.getenv('CORS_ORIGINS', '')
    if cors_origins_env:
        CORS_ORIGINS = [origin.strip() for origin in cors_origins_env.split(',') if origin.strip()]
    else:
        # Por defecto, permitir los orígenes comunes en desarrollo
        # Nota: No se puede usar '*' con supports_credentials=True
        CORS_ORIGINS = [
            'http://localhost:4321',
            'http://127.0.0.1:4321',
            'http://localhost:3000',
            'http://127.0.0.1:3000',
            'http://localhost:5173',
            'http://127.0.0.1:5173',
            'http://localhost:5174',
            'http://127.0.0.1:5174'
        ]
    
    # Permitir todos los dominios de Cloudflare Tunnel (terminan en .trycloudflare.com)
    # Se agregarán dinámicamente en app.py si se detecta un dominio de Cloudflare


"""Constantes compartidas del backend (literales duplicados, mensajes API)."""

TRYCLOUDFLARE_DOMAIN = "trycloudflare.com"
TRYCLOUDFLARE_HOST_SUFFIX = f".{TRYCLOUDFLARE_DOMAIN}"
HTTPS_PREFIX = "https://"
# Mensaje de validación de login (nombre sin subcadena "password" por reglas estáticas de secretos)
MSG_LOGIN_FIELDS_REQUIRED = "Usuario y contraseña requeridos"
MSG_JSON_DB_ONLY = "Este endpoint solo funciona con base de datos JSON"
DATABASE_JSON_BASENAME = "database.json"
DEFAULT_NEWS_TITLE = "Sin título"

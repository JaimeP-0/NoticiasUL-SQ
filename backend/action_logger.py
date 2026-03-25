"""
Módulo para registrar acciones de usuarios en archivo log y base de datos
con clasificación por niveles de afectación.
"""
import logging
from datetime import datetime
from database import Database
from database_json import DatabaseJSON
from config import Config
from flask import request
from typing import Optional

logger = logging.getLogger(__name__)

# Niveles de afectación permitidos
NIVELES_AFECTACION = {
    'aviso': 'Avisos - Acciones informativas normales',
    'movimiento': 'Movimientos - Acciones de creación, edición o eliminación',
    'ataque': 'Ataques - Intentos de acceso no autorizado o acciones maliciosas'
}

class ActionLogger:
    """Clase para registrar acciones de usuarios en log y base de datos"""
    
    def __init__(self):
        # Usar DatabaseJSON si DATABASE_TYPE es 'json', sino usar Database (MySQL)
        if Config.DATABASE_TYPE == 'json':
            self.db = DatabaseJSON()
        else:
            self.db = Database()
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """Asegurar que la tabla acciones_usuarios existe"""
        try:
            self.db.execute_query(
                """CREATE TABLE IF NOT EXISTS acciones_usuarios (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    usuario VARCHAR(50) NOT NULL,
                    accion VARCHAR(100) NOT NULL,
                    nivel VARCHAR(20) NOT NULL DEFAULT 'movimiento',
                    descripcion TEXT,
                    ip VARCHAR(45),
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_usuario (usuario),
                    INDEX idx_fecha (fecha),
                    INDEX idx_nivel (nivel),
                    INDEX idx_accion (accion)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""
            )
        except Exception as e:
            logger.warning(f"No se pudo crear tabla acciones_usuarios (puede que ya exista): {e}")
    
    def _get_client_ip(self) -> str:
        """Obtener la IP del cliente desde la petición"""
        if request:
            # Intentar obtener IP real (puede estar detrás de proxy)
            if request.headers.get('X-Forwarded-For'):
                return request.headers.get('X-Forwarded-For').split(',')[0].strip()
            elif request.headers.get('X-Real-IP'):
                return request.headers.get('X-Real-IP')
            else:
                return request.remote_addr or 'desconocida'
        return 'desconocida'
    
    def log_action(self, 
                   usuario: str, 
                   accion: str, 
                   nivel: str = 'movimiento',
                   descripcion: Optional[str] = None,
                   ip: Optional[str] = None):
        """
        Registrar una acción de usuario en log y base de datos
        
        Args:
            usuario: Nombre del usuario que realiza la acción
            accion: Tipo de acción realizada (ej: 'login', 'crear_noticia', 'eliminar_usuario')
            nivel: Nivel de afectación ('aviso', 'movimiento', 'ataque')
            descripcion: Descripción detallada de la acción
            ip: Dirección IP del cliente (se obtiene automáticamente si no se proporciona)
        """
        # Validar nivel
        if nivel not in NIVELES_AFECTACION:
            logger.warning(f"Nivel '{nivel}' no válido, usando 'movimiento' por defecto")
            nivel = 'movimiento'
        
        # Obtener IP si no se proporciona
        if ip is None:
            ip = self._get_client_ip()
        
        # Construir mensaje para el log
        log_message = f"[ACCION] Usuario: {usuario} | Acción: {accion} | Nivel: {nivel}"
        if descripcion:
            log_message += f" | Descripción: {descripcion}"
        log_message += f" | IP: {ip}"
        
        # Registrar en archivo log
        logger.info(log_message)
        
        # Registrar en base de datos
        try:
            self.db.execute_query(
                """INSERT INTO acciones_usuarios (usuario, accion, nivel, descripcion, ip)
                   VALUES (%s, %s, %s, %s, %s)""",
                (usuario, accion, nivel, descripcion, ip)
            )
        except Exception as e:
            logger.error(f"Error al registrar acción en base de datos: {e}")
    
    def get_actions(self, 
                   limit: int = 100, 
                   offset: int = 0,
                   nivel: Optional[str] = None,
                   usuario: Optional[str] = None) -> list:
        """
        Obtener acciones registradas desde la base de datos
        
        Args:
            limit: Número máximo de registros a obtener
            offset: Número de registros a saltar (para paginación)
            nivel: Filtrar por nivel de afectación
            usuario: Filtrar por usuario
        
        Returns:
            Lista de acciones registradas
        """
        try:
            where_clauses = []
            params = []
            
            if nivel:
                where_clauses.append("nivel = %s")
                params.append(nivel)
            
            if usuario:
                where_clauses.append("usuario = %s")
                params.append(usuario)
            
            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            
            query = f"""SELECT id, usuario, accion, nivel, descripcion, ip, fecha
                       FROM acciones_usuarios
                       {where_sql}
                       ORDER BY fecha DESC
                       LIMIT %s OFFSET %s"""
            
            params.extend([limit, offset])
            
            actions = self.db.execute_query(
                query,
                tuple(params),
                fetch_all=True
            )
            
            # Convertir fecha a string para JSON
            for action in actions:
                if action.get('fecha'):
                    action['fecha'] = action['fecha'].strftime("%Y-%m-%d %H:%M:%S")
            
            return actions if actions else []
        except Exception as e:
            logger.error(f"Error al obtener acciones: {e}")
            return []
    
    def get_actions_count(self, nivel: Optional[str] = None, usuario: Optional[str] = None) -> int:
        """Obtener el total de acciones registradas (para paginación)"""
        try:
            where_clauses = []
            params = []
            
            if nivel:
                where_clauses.append("nivel = %s")
                params.append(nivel)
            
            if usuario:
                where_clauses.append("usuario = %s")
                params.append(usuario)
            
            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            
            query = f"SELECT COUNT(*) as total FROM acciones_usuarios {where_sql}"
            
            result = self.db.execute_query(
                query,
                tuple(params) if params else None,
                fetch_one=True
            )
            
            return result.get('total', 0) if result else 0
        except Exception as e:
            logger.error(f"Error al contar acciones: {e}")
            return 0

# Instancia global del logger de acciones
action_logger = ActionLogger()

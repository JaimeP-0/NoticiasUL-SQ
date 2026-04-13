"""
Módulo para manejar la conexión a MySQL con connection pooling
"""
import mysql.connector
from mysql.connector import Error, pooling
from config import Config
import logging
import time

logger = logging.getLogger(__name__)

class Database:
    """Clase singleton para manejar la conexión a MySQL con connection pooling"""
    
    _instance = None
    _pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance
    
    def _get_pool(self):
        """Obtener o crear el pool de conexiones"""
        if self._pool is None:
            try:
                pool_config = {
                    'pool_name': 'noticias_pool',
                    'pool_size': 5,  # Reducido a 5 para iniciar más rápido
                    'pool_reset_session': True,
                    'host': Config.MYSQL_HOST,
                    'port': Config.MYSQL_PORT,
                    'user': Config.MYSQL_USER,
                    'password': Config.MYSQL_PASSWORD,
                    'database': Config.MYSQL_DATABASE,
                    'autocommit': True,
                    'charset': 'utf8mb4',
                    'collation': 'utf8mb4_unicode_ci',
                    'use_unicode': True,
                    'connect_timeout': 10,  # 10 segundos para conexiones remotas
                    'buffered': True,
                    'compress': True,
                    'connection_timeout': 10  # Timeout adicional para la conexión
                }
                self._pool = pooling.MySQLConnectionPool(**pool_config)
            except Error as e:
                logger.error(f"Error al crear pool de conexiones: {e}")
                raise
        return self._pool
    
    def get_connection(self, use_pool=True):
        """
        Obtener una conexión a la base de datos
        
        Args:
            use_pool (bool): Si True usa pool (más eficiente), si False conexión directa (más simple)
        """
        if use_pool:
            try:
                pool = self._get_pool()
                connection = pool.get_connection()
                return connection
            except pooling.PoolError:
                logger.warning("Pool sin conexiones libres; segundo intento de obtener conexión")
                try:
                    return pool.get_connection()
                except pooling.PoolError:
                    logger.error("No se pudo obtener conexión del pool tras el reintento")
                    raise
            except Error as e:
                logger.error(f"Error al obtener conexión del pool: {e}")
                raise
        else:
            # Conexión directa (sin pool) - más simple pero menos eficiente
            try:
                connection = mysql.connector.connect(
                    host=Config.MYSQL_HOST,
                    port=Config.MYSQL_PORT,
                    user=Config.MYSQL_USER,
                    password=Config.MYSQL_PASSWORD,
                    database=Config.MYSQL_DATABASE,
                    autocommit=True,
                    charset='utf8mb4',
                    collation='utf8mb4_unicode_ci',
                    use_unicode=True,
                    connect_timeout=10,  # 10 segundos para conexiones remotas
                    buffered=True
                )
                return connection
            except Error as e:
                logger.error(f"Error al crear conexión directa: {e}")
                raise
    
    @staticmethod
    def _cursor_fetch_result(cursor, fetch_one, fetch_all):
        if fetch_one:
            return cursor.fetchone()
        if fetch_all:
            return cursor.fetchall()
        if cursor.rowcount is not None:
            result = cursor.lastrowid if cursor.lastrowid else cursor.rowcount
        else:
            result = None
        try:
            cursor.fetchall()
        except Error:
            pass
        return result

    @staticmethod
    def _rollback_silent(connection):
        if connection and not connection.autocommit:
            try:
                connection.rollback()
            except Error:
                pass

    @staticmethod
    def _close_cursor_silent(cursor):
        if not cursor:
            return
        try:
            cursor.close()
        except Error:
            pass

    @staticmethod
    def _close_connection_silent(connection):
        if not connection:
            return
        try:
            if connection.is_connected():
                connection.close()
        except Exception as ex:
            logger.warning("Error al cerrar conexión: %s", type(ex).__name__)

    def _run_sql(self, use_pool, query, params, fetch_one, fetch_all, log_label):
        connection = None
        cursor = None
        try:
            connection = self.get_connection(use_pool=use_pool)
            cursor = connection.cursor(dictionary=True, buffered=True)
            cursor.execute(query, params or ())
            result = Database._cursor_fetch_result(cursor, fetch_one, fetch_all)
            if not connection.autocommit:
                connection.commit()
            return result
        except Error as e:
            logger.error("Error al ejecutar %s: %s", log_label, e)
            Database._rollback_silent(connection)
            raise
        finally:
            Database._close_cursor_silent(cursor)
            Database._close_connection_silent(connection)

    def execute_query_direct(self, query, params=None, fetch_one=False, fetch_all=False):
        """
        Ejecutar consulta con conexión directa (sin pool) - más simple pero menos eficiente
        Útil para scripts o operaciones puntuales
        """
        return self._run_sql(False, query, params, fetch_one, fetch_all, "consulta directa")

    def execute_query(self, query, params=None, fetch_one=False, fetch_all=False):
        """Ejecutar una consulta SQL usando el pool de conexiones"""
        return self._run_sql(True, query, params, fetch_one, fetch_all, "consulta")
    
    def init_tables(self):
        """Inicializar tablas en la base de datos"""
        try:
            # Verificar si la tabla usuarios_nul existe y tiene la estructura correcta
            try:
                self.execute_query("SELECT idUsuario, usuario, contrasena FROM usuarios_nul LIMIT 1", fetch_one=True)
            except Error:
                # Crear tabla de usuarios_nul solo si no existe
                self.execute_query("""
                    CREATE TABLE IF NOT EXISTS usuarios_nul (
                        idUsuario INT AUTO_INCREMENT PRIMARY KEY,
                        usuario VARCHAR(50) UNIQUE NOT NULL,
                        contrasena VARCHAR(255) NOT NULL,
                        nombre VARCHAR(100),
                        email VARCHAR(100),
                        rol VARCHAR(20) DEFAULT 'usuario',
                        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            
            # Crear tabla de noticias_nul (sin clave foránea para compatibilidad)
            try:
                self.execute_query("SELECT id FROM noticias_nul LIMIT 1", fetch_one=True)
            except Error:
                # Crear tabla de noticias_nul sin clave foránea para evitar problemas
                self.execute_query("""
                    CREATE TABLE IF NOT EXISTS noticias_nul (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        titulo VARCHAR(255) NOT NULL,
                        contenido TEXT NOT NULL,
                        autor VARCHAR(100) NOT NULL,
                        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        imagen_url VARCHAR(500),
                        usuario_id INT,
                        INDEX idx_fecha (fecha),
                        INDEX idx_autor (autor),
                        INDEX idx_titulo (titulo)
                    )
                """)
            
            # Crear tabla de acciones de usuarios si no existe
            try:
                self.execute_query("SELECT id FROM acciones_usuarios LIMIT 1", fetch_one=True)
            except Error:
                # Crear tabla de acciones de usuarios
                self.execute_query("""
                    CREATE TABLE IF NOT EXISTS acciones_usuarios (
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
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
            
            # Insertar usuario admin por defecto si no existe
            try:
                existing_admin = self.execute_query(
                    "SELECT idUsuario FROM usuarios_nul WHERE usuario = %s",
                    ('admin',),
                    fetch_one=True
                )
                
                if not existing_admin:
                    # Crear superadmin por defecto
                    self.execute_query("""
                        INSERT INTO usuarios_nul (usuario, contrasena, nombre, rol)
                        VALUES (%s, %s, %s, %s)
                    """, ('superadmin', '1234', 'Super Administrador', 'superadmin'))
                    
                    # También crear un admin de ejemplo
                    try:
                        existing_admin_example = self.execute_query(
                            "SELECT idUsuario FROM usuarios_nul WHERE usuario = %s",
                            ('admin',),
                            fetch_one=True
                        )
                        if not existing_admin_example:
                            self.execute_query("""
                                INSERT INTO usuarios_nul (usuario, contrasena, nombre, rol)
                                VALUES (%s, %s, %s, %s)
                            """, ('admin', '1234', 'Administrador', 'admin'))
                    except Error:
                        pass
            except Exception as e:
                logger.warning(f"No se pudo crear usuario admin: {e}")
            
            return True
        except Error as e:
            logger.error(f"Error al inicializar tablas: {e}")
            return False


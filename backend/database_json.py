"""
Módulo para manejar la base de datos usando JSON como almacenamiento local
Simula una base de datos MySQL pero usando archivos JSON
"""
import json
import os
import logging
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import re

logger = logging.getLogger(__name__)

# Operador SQL en mayúsculas para parseo WHERE (espacios explícitos)
SQL_LIKE_TOKEN = " LIKE "
SQL_IN_TOKEN = " IN "

class DatabaseJSON:
    """
    Clase singleton para manejar la base de datos usando JSON
    Implementa la misma interfaz que Database para compatibilidad
    """
    
    _instance = None
    _lock = threading.Lock()  # Lock para operaciones thread-safe
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseJSON, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.db_file = os.path.join(os.path.dirname(__file__), 'database.json')
            self._data = None
            self._load_data()
            self._initialized = True
    
    def _load_data(self):
        """Cargar datos desde el archivo JSON"""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
                
                # Migración: Agregar campo "fecha" a noticias que no lo tengan
                if "noticias_nul" in self._data:
                    fecha_agregada = False
                    for noticia in self._data["noticias_nul"]:
                        if "fecha" not in noticia:
                            noticia["fecha"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            fecha_agregada = True
                    if fecha_agregada:
                        self._save_data()
                        logger.info("✅ Campo 'fecha' agregado a noticias existentes durante carga")
            else:
                # Inicializar estructura vacía
                self._data = {
                    "usuarios_nul": [],
                    "noticias_nul": [],
                    "categorias_nul": [],
                    "noticias_categorias": [],
                    "acciones_usuarios": [],
                    "last_ids": {
                        "usuarios_nul": 0,
                        "noticias_nul": 0,
                        "categorias_nul": 0,
                        "acciones_usuarios": 0
                    }
                }
                self._save_data()
        except Exception as e:
            logger.error(f"Error al cargar datos JSON: {e}")
            self._data = {
                "usuarios_nul": [],
                "noticias_nul": [],
                "categorias_categorias": [],
                "noticias_categorias": [],
                "acciones_usuarios": [],
                "last_ids": {}
            }
    
    def _save_data(self):
        """Guardar datos al archivo JSON"""
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error al guardar datos JSON: {e}")
            raise
    
    def _get_next_id(self, table_name: str) -> int:
        """Obtener el siguiente ID para una tabla"""
        if "last_ids" not in self._data:
            self._data["last_ids"] = {}
        if table_name not in self._data["last_ids"]:
            self._data["last_ids"][table_name] = 0
        
        self._data["last_ids"][table_name] += 1
        return self._data["last_ids"][table_name]
    
    def _parse_sql_query(self, query: str, params: Optional[Tuple] = None) -> Dict[str, Any]:
        """
        Parsear una consulta SQL simple y convertirla a operaciones JSON
        Soporta: SELECT, INSERT, UPDATE, DELETE, CREATE TABLE básicos
        """
        query = query.strip()
        query_upper = query.upper()
        
        # Normalizar espacios
        query = re.sub(r'\s+', ' ', query)
        
        # Manejar CREATE TABLE IF NOT EXISTS (simplemente retornar éxito)
        if query_upper.startswith('CREATE TABLE'):
            return {
                "operation": "CREATE_TABLE",
                "table": None
            }
        
        result = {
            "operation": None,
            "table": None,
            "where": [],
            "fields": [],
            "field_aliases": {},  # Mapeo de alias a campos reales
            "values": [],
            "set_fields": {},
            "order_by": None,
            "limit": None,
            "offset": None
        }
        
        # Detectar operación
        if query_upper.startswith('SELECT'):
            result["operation"] = "SELECT"
            # Extraer campos
            select_match = re.search(r'SELECT\s+(.*?)\s+FROM', query, re.IGNORECASE)
            if select_match:
                fields_str = select_match.group(1).strip()
                if fields_str == '*':
                    result["fields"] = ['*']
                elif 'COUNT' in fields_str.upper():
                    # Manejar COUNT(*)
                    result["fields"] = ['COUNT(*)']
                else:
                    # Limpiar campos (remover funciones, alias, backticks, prefijos de tabla, etc.)
                    fields = []
                    field_aliases = {}  # Mapear alias a campo real
                    for f in fields_str.split(','):
                        f = f.strip()
                        # Remover backticks y comillas
                        f = f.strip('`"')
                        
                        # Extraer alias si existe (campo AS alias)
                        alias = None
                        if ' AS ' in f.upper():
                            parts = f.split(' AS ', 1)
                            if len(parts) >= 2:
                                f = parts[0].strip()
                                alias = parts[1].strip().strip('`"')
                        
                        # Remover prefijo de tabla (n.id -> id, u.nombre -> nombre)
                        if '.' in f:
                            f = f.split('.')[-1]
                        
                        # Remover funciones básicas (COALESCE, etc.)
                        if '(' in f and ')' in f:
                            # Es una función (COALESCE, etc.)
                            # Extraer el campo dentro de la función
                            # COALESCE(u.nombre, n.autor) -> extraer el primer campo disponible
                            match = re.findall(r'(\w+)\.(\w+)', f)
                            if match:
                                # Si hay múltiples campos en la función, usar el primero disponible
                                # Buscar en la tabla principal primero (prefijo 'n')
                                for table_prefix, field_name in match:
                                    # Preferir campos de la tabla principal (prefijo 'n')
                                    if table_prefix.lower() == 'n':
                                        f = field_name
                                        break
                                else:
                                    # Si no hay de la tabla principal, usar el primero
                                    f = match[0][1]
                            else:
                                # Intentar extraer campo simple dentro de paréntesis
                                inner_match = re.search(r'\(([^)]+)\)', f)
                                if inner_match:
                                    inner = inner_match.group(1).strip()
                                    # Dividir por comas para COALESCE con múltiples argumentos
                                    inner_parts = [p.strip() for p in inner.split(',')]
                                    for part in inner_parts:
                                        if '.' in part:
                                            field_part = part.split('.')[-1].strip()
                                            # Preferir campos que no sean strings literales
                                            if not (field_part.startswith("'") or field_part.startswith('"')):
                                                f = field_part
                                                break
                                    else:
                                        # Si no se encontró, usar el primero sin prefijo
                                        if inner_parts:
                                            first = inner_parts[0].strip()
                                            if '.' in first:
                                                f = first.split('.')[-1]
                                            else:
                                                f = first.strip('`"\'')
                                else:
                                    # Si no se puede extraer, usar un campo por defecto común
                                    f = 'autor'  # Campo común en noticias
                        
                        # Guardar el campo real
                        field_name = f.strip('`"')
                        fields.append(field_name)
                        
                        # Si hay alias, mapearlo al campo real
                        if alias:
                            field_aliases[alias] = field_name
                    
                    result["fields"] = fields
                    result["field_aliases"] = field_aliases
                    
                    # Asegurar que 'id' siempre esté en los campos si se solicitó
                    # (necesario para operaciones posteriores que dependen de 'id')
                    if 'id' not in fields and any('id' in f.lower() for f in fields_str.split(',')):
                        fields.append('id')
                        result["fields"] = fields
            
            # Extraer tabla (manejar backticks y alias de tabla)
            # Ejemplo: FROM noticias_nul n -> extraer "noticias_nul"
            # También manejar: FROM `noticias_nul` n LEFT JOIN ...
            from_match = re.search(r'FROM\s+[`"]?(\w+)[`"]?\s*\w*', query, re.IGNORECASE)
            if from_match:
                result["table"] = from_match.group(1)
            
            # Extraer WHERE
            where_match = re.search(
                r'WHERE\s+(.+?)(?=\s+ORDER\s+BY|\s+LIMIT\b|$)',
                query,
                re.IGNORECASE | re.DOTALL,
            )
            if where_match:
                where_clause = where_match.group(1).strip()
                result["where"] = self._parse_where_clause(where_clause, params)
            
            # Extraer ORDER BY
            order_match = re.search(r'ORDER\s+BY\s+(\w+)(?:\s+(ASC|DESC))?(?:\s+LIMIT|$)', query, re.IGNORECASE)
            if order_match:
                result["order_by"] = {
                    "field": order_match.group(1),
                    "direction": order_match.group(2) if order_match.group(2) else "ASC"
                }
            
            # Extraer LIMIT y OFFSET
            limit_match = re.search(r'LIMIT\s+(\d+)(?:\s+OFFSET\s+(\d+))?', query, re.IGNORECASE)
            if limit_match:
                result["limit"] = int(limit_match.group(1))
                if limit_match.group(2):
                    result["offset"] = int(limit_match.group(2))
        
        elif query_upper.startswith('INSERT'):
            result["operation"] = "INSERT"
            # Extraer tabla (manejar backticks)
            insert_match = re.search(r'INSERT\s+INTO\s+[`"]?(\w+)[`"]?', query, re.IGNORECASE)
            if insert_match:
                result["table"] = insert_match.group(1)
            
            # Extraer campos (manejar backticks)
            fields_match = re.search(r'\(([^)]+)\)', query)
            if fields_match:
                fields_str = fields_match.group(1)
                # Remover backticks y comillas de los campos
                result["fields"] = [f.strip().strip('`"') for f in fields_str.split(',')]
            
            # Extraer valores (VALUES o usar params)
            if params:
                result["values"] = params
            else:
                values_match = re.search(r'VALUES\s*\(([^)]+)\)', query, re.IGNORECASE)
                if values_match:
                    # Parsear valores simples (sin comillas)
                    values_str = values_match.group(1)
                    result["values"] = [v.strip().strip("'\"") for v in values_str.split(',')]
        
        elif query_upper.startswith('UPDATE'):
            result["operation"] = "UPDATE"
            # Extraer tabla (manejar backticks)
            update_match = re.search(r'UPDATE\s+[`"]?(\w+)[`"]?', query, re.IGNORECASE)
            if update_match:
                result["table"] = update_match.group(1)
            
            # Extraer SET
            set_match = re.search(
                r'SET\s+(.+?)(?=\s+WHERE\b|$)',
                query,
                re.IGNORECASE | re.DOTALL,
            )
            if set_match:
                set_clause = set_match.group(1).strip()
                # Parsear SET campo = valor
                set_parts = set_clause.split(',')
                for part in set_parts:
                    if '=' in part:
                        field, value = part.split('=', 1)
                        result["set_fields"][field.strip()] = value.strip().strip("'\"")
            
            # Extraer WHERE
            where_match = re.search(r'WHERE\s+(.+)$', query, re.IGNORECASE | re.DOTALL)
            if where_match:
                where_clause = where_match.group(1).strip()
                result["where"] = self._parse_where_clause(where_clause, params)
        
        elif query_upper.startswith('DELETE'):
            result["operation"] = "DELETE"
            # Extraer tabla (manejar backticks)
            delete_match = re.search(r'FROM\s+[`"]?(\w+)[`"]?', query, re.IGNORECASE)
            if delete_match:
                result["table"] = delete_match.group(1)
            
            # Extraer WHERE
            where_match = re.search(r'WHERE\s+(.+)$', query, re.IGNORECASE | re.DOTALL)
            if where_match:
                where_clause = where_match.group(1).strip()
                result["where"] = self._parse_where_clause(where_clause, params)
        
        return result
    
    def _parse_where_clause(self, where_clause: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Parsear cláusula WHERE simple"""
        conditions = []
        param_index = 0
        
        # Dividir por AND (manejar AND en mayúsculas y minúsculas)
        and_parts = re.split(r'\s+AND\s+', where_clause, flags=re.IGNORECASE)
        for part in and_parts:
            part = part.strip()
            # Buscar operadores: =, !=, <, >, <=, >=, LIKE, IN
            for op in ['!=', '<=', '>=', '=', '<', '>', SQL_LIKE_TOKEN, SQL_IN_TOKEN]:
                op_clean = op.strip()
                if op_clean in part.upper() or op in part:
                    # Encontrar la posición del operador
                    if op == SQL_LIKE_TOKEN:
                        op_pos = part.upper().find(SQL_LIKE_TOKEN.upper())
                        op_used = 'LIKE'
                    elif op == SQL_IN_TOKEN:
                        op_pos = part.upper().find(SQL_IN_TOKEN.upper())
                        op_used = 'IN'
                    else:
                        op_pos = part.find(op)
                        op_used = op_clean
                    
                    if op_pos != -1:
                        field = part[:op_pos].strip()
                        # Remover backticks y comillas si existen
                        field = field.strip('`"')
                        # Remover prefijo de tabla (n.id -> id, u.nombre -> nombre)
                        if '.' in field:
                            field = field.split('.')[-1]
                        value = part[op_pos + len(op):].strip()
                        
                        # Si es %s, usar parámetro
                        if value == '%s' and params and param_index < len(params):
                            value = params[param_index]
                            param_index += 1
                        elif value.startswith('(') and value.endswith(')'):
                            # Manejar IN (val1, val2, ...)
                            value = value[1:-1].strip()
                            if params and param_index < len(params):
                                value = params[param_index]
                                param_index += 1
                            else:
                                # Parsear valores del IN
                                value = [v.strip().strip("'\"") for v in value.split(',')]
                        else:
                            # Remover comillas
                            value = value.strip("'\"")
                        
                        conditions.append({
                            "field": field,
                            "operator": op_used,
                            "value": value
                        })
                        break
        
        return conditions
    
    def _apply_where(self, records: List[Dict], conditions: List[Dict]) -> List[Dict]:
        """Aplicar condiciones WHERE a los registros"""
        if not conditions:
            return records
        
        filtered = []
        for record in records:
            match = True
            for condition in conditions:
                field = condition["field"]
                operator = condition["operator"]
                value = condition["value"]
                
                if field not in record:
                    match = False
                    break
                
                record_value = record[field]
                
                if operator == '=':
                    if str(record_value) != str(value):
                        match = False
                        break
                elif operator == '!=':
                    if str(record_value) == str(value):
                        match = False
                        break
                elif operator == 'LIKE':
                    # Convertir SQL LIKE a regex
                    pattern = value.replace('%', '.*').replace('_', '.')
                    if not re.search(pattern, str(record_value), re.IGNORECASE):
                        match = False
                        break
                elif operator == 'IN':
                    # Manejar IN (val1, val2, ...)
                    if isinstance(value, list):
                        if str(record_value) not in [str(v) for v in value]:
                            match = False
                            break
                    else:
                        if str(record_value) != str(value):
                            match = False
                            break
                elif operator == '<':
                    if record_value >= value:
                        match = False
                        break
                elif operator == '>':
                    if record_value <= value:
                        match = False
                        break
                elif operator == '<=':
                    if record_value > value:
                        match = False
                        break
                elif operator == '>=':
                    if record_value < value:
                        match = False
                        break
            
            if match:
                filtered.append(record)
        
        return filtered
    
    def execute_query(self, query: str, params: Optional[Tuple] = None, 
                     fetch_one: bool = False, fetch_all: bool = False):
        """
        Ejecutar una consulta SQL (simulada) usando JSON
        Mantiene la misma interfaz que Database.execute_query
        """
        with self._lock:
            try:
                parsed = self._parse_sql_query(query, params)
                operation = parsed["operation"]
                table = parsed["table"]
                
                if not table or table not in self._data:
                    logger.warning(f"Tabla {table} no encontrada")
                    return None if not fetch_one and not fetch_all else ([] if fetch_all else None)
                
                if operation == "SELECT":
                    # Verificar si hay JOIN en la consulta
                    if 'JOIN' in query.upper():
                        # Manejar JOINs básicos
                        records = self._handle_join_query(query, params, parsed)
                    else:
                        # Consulta normal sin JOIN
                        records = self._data[table].copy()
                        
                        # Aplicar WHERE
                        if parsed["where"]:
                            records = self._apply_where(records, parsed["where"])
                    
                    # Aplicar ORDER BY (tanto para JOIN como para consultas normales)
                    if parsed.get("order_by"):
                        field = parsed["order_by"]["field"]
                        # Remover prefijo de tabla si existe
                        if '.' in field:
                            field = field.split('.')[-1]
                        direction = parsed["order_by"]["direction"]
                        reverse = (direction.upper() == "DESC")
                        records.sort(key=lambda x: x.get(field, ''), reverse=reverse)
                    
                    # Aplicar LIMIT y OFFSET (tanto para JOIN como para consultas normales)
                    if parsed.get("offset"):
                        records = records[parsed["offset"]:]
                    if parsed.get("limit"):
                        records = records[:parsed["limit"]]
                    
                    # Manejar COUNT(*)
                    if parsed["fields"] and parsed["fields"][0] == 'COUNT(*)':
                        return len(records)
                    
                    # Filtrar campos si no es *
                    if parsed["fields"] and parsed["fields"] != ['*']:
                        filtered_records = []
                        field_aliases = parsed.get("field_aliases", {})
                        for record in records:
                            filtered_record = {}
                            # Agregar campos solicitados
                            for field in parsed["fields"]:
                                if field in record:
                                    filtered_record[field] = record[field]
                                else:
                                    # Si el campo no existe, intentar con None
                                    filtered_record[field] = None
                            
                            # Agregar alias si existen (el alias apunta al campo real)
                            for alias, real_field in field_aliases.items():
                                if real_field in record:
                                    filtered_record[alias] = record[real_field]
                                else:
                                    # Si el campo real no existe, usar None o valor por defecto
                                    # Para COALESCE, usar el primer valor disponible o None
                                    filtered_record[alias] = None
                            
                            # Asegurar que 'id' siempre esté presente si existe en el registro original
                            # (necesario para operaciones posteriores)
                            if 'id' in record and 'id' not in filtered_record:
                                filtered_record['id'] = record['id']
                            
                            filtered_records.append(filtered_record)
                        records = filtered_records
                    else:
                        # Si es *, asegurar que todos los campos estén presentes
                        # (ya están, no hacer nada)
                        pass
                    
                    if fetch_one:
                        return records[0] if records else None
                    elif fetch_all:
                        return records
                    else:
                        return records[0] if records else None
                
                elif operation == "INSERT":
                    # Crear nuevo registro
                    new_record = {}
                    
                    # Mapear campos con valores
                    if params:
                        for i, field in enumerate(parsed["fields"]):
                            if i < len(params):
                                new_record[field] = params[i]
                    else:
                        for i, field in enumerate(parsed["fields"]):
                            if i < len(parsed["values"]):
                                new_record[field] = parsed["values"][i]
                    
                    # Generar ID automático
                    id_field = self._get_id_field(table)
                    if id_field and id_field not in new_record:
                        new_record[id_field] = self._get_next_id(table)
                    
                    # Agregar timestamp si es fecha_creacion o fecha
                    # Para noticias_nul, siempre agregar fecha si no existe
                    if table == "noticias_nul":
                        if "fecha" not in new_record:
                            new_record["fecha"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    elif "fecha_creacion" not in new_record and "fecha_creacion" in self._get_table_structure(table):
                        new_record["fecha_creacion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    elif "fecha" not in new_record and "fecha" in self._get_table_structure(table):
                        new_record["fecha"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    self._data[table].append(new_record)
                    self._save_data()
                    
                    # Retornar ID del nuevo registro (o True si no hay ID field, como en noticias_categorias)
                    if id_field:
                        return new_record.get(id_field, len(self._data[table]))
                    else:
                        # Para tablas sin ID autoincremental (como noticias_categorias), retornar True
                        return True
                
                elif operation == "UPDATE":
                    records = self._data[table]
                    updated_count = 0
                    
                    # Aplicar WHERE para encontrar registros
                    if parsed["where"]:
                        matching_records = self._apply_where(records, parsed["where"])
                        indices = [i for i, r in enumerate(records) if r in matching_records]
                    else:
                        indices = list(range(len(records)))
                    
                    # Actualizar registros
                    for idx in indices:
                        for field, value in parsed["set_fields"].items():
                            # Si el valor es %s, usar parámetro
                            if value == '%s' and params:
                                value = params[0] if params else value
                            records[idx][field] = value
                        updated_count += 1
                    
                    self._save_data()
                    return updated_count
                
                elif operation == "DELETE":
                    records = self._data[table]
                    deleted_count = 0
                    
                    # Aplicar WHERE para encontrar registros
                    if parsed["where"]:
                        matching_records = self._apply_where(records, parsed["where"])
                        indices_to_delete = [i for i, r in enumerate(records) if r in matching_records]
                    else:
                        indices_to_delete = list(range(len(records)))
                    
                    # Eliminar en orden inverso para no afectar índices
                    for idx in sorted(indices_to_delete, reverse=True):
                        del records[idx]
                        deleted_count += 1
                    
                    self._save_data()
                    return deleted_count
                
                elif operation == "CREATE_TABLE":
                    # CREATE TABLE IF NOT EXISTS - solo verificar que la tabla existe
                    # Las tablas se crean automáticamente si no existen
                    return True
                
                else:
                    logger.warning(f"Operación no soportada: {operation}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error al ejecutar consulta JSON: {e}")
                import traceback
                logger.error(traceback.format_exc())
                raise
    
    def _get_id_field(self, table: str) -> Optional[str]:
        """Obtener el nombre del campo ID de una tabla"""
        id_fields = {
            "usuarios_nul": "idUsuario",
            "noticias_nul": "id",
            "categorias_nul": "id",
            "acciones_usuarios": "id"
        }
        return id_fields.get(table)
    
    def get_id_field(self, table: str) -> Optional[str]:
        """Método público para obtener el campo ID de una tabla"""
        return self._get_id_field(table)
    
    def _get_table_structure(self, table: str) -> List[str]:
        """Obtener estructura de una tabla (campos)"""
        if table in self._data and self._data[table]:
            return list(self._data[table][0].keys())
        return []
    
    def execute_query_direct(self, query: str, params: Optional[Tuple] = None,
                            fetch_one: bool = False, fetch_all: bool = False):
        """Mismo que execute_query, para compatibilidad"""
        return self.execute_query(query, params, fetch_one, fetch_all)
    
    def init_tables(self):
        """Inicializar tablas en la base de datos JSON"""
        try:
            # Asegurar que todas las tablas existen
            required_tables = ["usuarios_nul", "noticias_nul", "categorias_nul", 
                              "noticias_categorias", "acciones_usuarios"]
            
            for table in required_tables:
                if table not in self._data:
                    self._data[table] = []
            
            # Migración: Agregar campo "fecha" a noticias que no lo tengan
            if "noticias_nul" in self._data:
                for noticia in self._data["noticias_nul"]:
                    if "fecha" not in noticia:
                        noticia["fecha"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._save_data()
                logger.info("✅ Campo 'fecha' agregado a noticias existentes")
            
            # Crear usuarios por defecto si no existen
            usuarios = self._data.get("usuarios_nul", [])
            superadmin_exists = any(u.get("usuario") == "superadmin" for u in usuarios)
            admin_exists = any(u.get("usuario") == "admin" for u in usuarios)
            
            if not superadmin_exists:
                self._data["usuarios_nul"].append({
                    "idUsuario": self._get_next_id("usuarios_nul"),
                    "usuario": "superadmin",
                    "contrasena": "1234",  # En producción debería estar hasheado
                    "nombre": "Super Administrador",
                    "email": "superadmin@noticiasul.com",
                    "rol": "superadmin",
                    "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            
            if not admin_exists:
                self._data["usuarios_nul"].append({
                    "idUsuario": self._get_next_id("usuarios_nul"),
                    "usuario": "admin",
                    "contrasena": "1234",
                    "nombre": "Administrador",
                    "email": "admin@noticiasul.com",
                    "rol": "admin",
                    "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            
            self._save_data()
            return True
        except Exception as e:
            logger.error(f"Error al inicializar tablas JSON: {e}")
            return False
    
    def get_connection(self):
        """Método de compatibilidad - retorna self para simular conexión"""
        return self
    
    def _handle_join_query(self, query: str, params: Optional[Tuple], parsed: Dict) -> List[Dict]:
        """
        Manejar consultas con JOINs básicos (INNER JOIN y LEFT JOIN)
        Ejemplo 1: SELECT c.id, c.nombre, c.color FROM categorias_nul c JOIN noticias_categorias nc ON c.id = nc.categoria_id WHERE nc.noticia_id = %s
        Ejemplo 2: SELECT n.id, n.titulo FROM noticias_nul n LEFT JOIN usuarios_nul u ON n.autor = u.usuario WHERE n.id = %s
        """
        try:
            query_upper = query.upper()
            
            # Detectar JOIN (INNER o LEFT)
            if 'JOIN' in query_upper:
                is_left_join = 'LEFT JOIN' in query_upper
                
                # Extraer tablas del JOIN (manejar LEFT JOIN y JOIN normal)
                # FROM noticias_nul n LEFT JOIN usuarios_nul u ON n.autor = u.usuario WHERE n.id = %s
                # FROM categorias_nul c JOIN noticias_categorias nc ON c.id = nc.categoria_id WHERE nc.noticia_id = %s
                # Capturar hasta WHERE, ORDER BY, LIMIT o el final
                join_pattern = (
                    r'FROM\s+(\w+)\s+\w+\s+(?:LEFT\s+)?JOIN\s+(\w+)\s+\w+\s+ON\s+'
                    r'(.+)(?=\s+WHERE\b|\s+ORDER\s+BY\b|\s+LIMIT\b|$)'
                )
                join_match = re.search(join_pattern, query, re.IGNORECASE)
                if join_match:
                    logger.debug(f"[JOIN] Match encontrado: main_table={join_match.group(1)}, join_table={join_match.group(2)}, is_left={is_left_join}")
                    main_table = join_match.group(1)
                    join_table = join_match.group(2)
                    join_condition = join_match.group(3).strip()
                    
                    # Parsear condición del JOIN (ej: n.autor = u.usuario o c.id = nc.categoria_id)
                    join_parts = join_condition.split('=')
                    if len(join_parts) == 2:
                        # Determinar qué campo pertenece a cada tabla
                        left_part = join_parts[0].strip()
                        right_part = join_parts[1].strip()
                        
                        # Extraer prefijos de tabla
                        left_prefix = left_part.split('.')[0] if '.' in left_part else None
                        right_prefix = right_part.split('.')[0] if '.' in right_part else None
                        
                        # Determinar qué campo pertenece a la tabla principal
                        # La tabla principal es la primera en el FROM, así que su alias debería aparecer primero
                        # Pero también podemos verificar comparando con los alias comunes (n, c, etc.)
                        # Por ahora, asumimos que el primer campo es de la tabla principal
                        main_field_part = left_part
                        join_field_part = right_part
                        
                        # Si el prefijo derecho parece ser de la tabla principal, intercambiar
                        # (esto es una heurística, pero funciona para la mayoría de casos)
                        if right_prefix and right_prefix.lower() in ['n', 'c'] and left_prefix and left_prefix.lower() in ['u', 'nc']:
                            main_field_part = right_part
                            join_field_part = left_part
                        
                        # Determinar campos (remover prefijos de tabla)
                        main_field = main_field_part.split('.')[-1]  # n.autor -> autor
                        join_field = join_field_part.split('.')[-1]  # u.usuario -> usuario
                        
                        logger.debug(f"[JOIN] main_field={main_field}, join_field={join_field}, main_table={main_table}, join_table={join_table}")
                        
                        # Obtener registros de ambas tablas
                        main_records = self._data.get(main_table, [])
                        join_records = self._data.get(join_table, [])
                        
                        # Aplicar WHERE en la tabla principal primero
                        where_conditions = parsed.get("where", [])
                        filtered_main_records = main_records
                        if where_conditions:
                            # Ajustar WHERE para la tabla principal (n.id -> id)
                            adjusted_where = []
                            for cond in where_conditions:
                                adj_cond = cond.copy()
                                # Remover prefijo de tabla del campo
                                if '.' in adj_cond.get("field", ""):
                                    adj_cond["field"] = adj_cond["field"].split('.')[-1]
                                adjusted_where.append(adj_cond)
                            filtered_main_records = self._apply_where(main_records, adjusted_where)
                        
                        # Hacer el JOIN manualmente
                        result = []
                        logger.debug(f"[JOIN] Procesando {len(filtered_main_records)} registros de {main_table} con {len(join_records)} registros de {join_table}")
                        for main_rec in filtered_main_records:
                            # Obtener el valor del campo de la tabla principal
                            main_value = main_rec.get(main_field)
                            
                            # Buscar coincidencia en la tabla de unión
                            matched_join_rec = None
                            for join_rec in join_records:
                                if join_rec.get(join_field) == main_value:
                                    matched_join_rec = join_rec
                                    break
                            
                            # Para LEFT JOIN, incluir el registro principal incluso si no hay coincidencia
                            # Para INNER JOIN, solo incluir si hay coincidencia
                            if matched_join_rec or is_left_join:
                                combined = main_rec.copy()
                                
                                # Agregar campos de la tabla de unión si existe coincidencia
                                if matched_join_rec:
                                    # Agregar campos de la tabla de unión (u.nombre, u.rol, etc.)
                                    for key, value in matched_join_rec.items():
                                        # Solo agregar si no existe en el registro principal o si es necesario
                                        if key not in combined:
                                            combined[key] = value
                                
                                result.append(combined)
                        
                        logger.debug(f"[JOIN] Resultado: {len(result)} registros después del JOIN")
                        # Filtrar campos si se especificaron
                        if parsed.get("fields") and parsed["fields"] != ['*']:
                            filtered_result = []
                            field_aliases = parsed.get("field_aliases", {})
                            for record in result:
                                filtered_record = {}
                                for field in parsed["fields"]:
                                    # Remover prefijo de tabla si existe
                                    clean_field = field.split('.')[-1]
                                    if clean_field in record:
                                        filtered_record[clean_field] = record[clean_field]
                                    else:
                                        # Si el campo no existe, usar None (para COALESCE)
                                        filtered_record[clean_field] = None
                                
                                # Agregar alias si existen
                                for alias, real_field in field_aliases.items():
                                    clean_real_field = real_field.split('.')[-1] if '.' in real_field else real_field
                                    if clean_real_field in record:
                                        filtered_record[alias] = record[clean_real_field]
                                    else:
                                        # Para COALESCE, usar el primer valor disponible o None
                                        filtered_record[alias] = None
                                
                                filtered_result.append(filtered_record)
                            result = filtered_result
                        
                        logger.debug(f"[JOIN] Retornando {len(result)} registros finales")
                        return result
                else:
                    logger.warning("[JOIN] No se pudo analizar la cláusula JOIN de la consulta")
            
            # Si no se puede procesar, retornar vacío
            logger.warning("[JOIN] No se detectó JOIN en la consulta")
            return []
        except Exception as e:
            logger.error(f"Error al procesar JOIN: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
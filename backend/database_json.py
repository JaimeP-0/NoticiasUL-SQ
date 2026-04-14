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

    def _psc_split_as_alias(self, f: str) -> Tuple[str, Optional[str]]:
        alias = None
        if ' AS ' in f.upper():
            parts = f.split(' AS ', 1)
            if len(parts) >= 2:
                f = parts[0].strip()
                alias = parts[1].strip().strip('`"')
        return f, alias

    @staticmethod
    def _psc_simple_qualified_field(f: str) -> str:
        if '(' not in f and '.' in f:
            return f.split('.')[-1]
        return f

    @staticmethod
    def _psc_field_from_table_dot_matches(match: List[Tuple[str, str]]) -> str:
        for table_prefix, field_name in match:
            if table_prefix.lower() == 'n':
                return field_name
        return match[0][1]

    def _psc_field_from_inner_parts(self, inner_parts: List[str]) -> str:
        for part in inner_parts:
            if '.' in part:
                field_part = part.split('.')[-1].strip()
                if not (field_part.startswith("'") or field_part.startswith('"')):
                    return field_part
        if inner_parts:
            first = inner_parts[0].strip()
            return first.split('.')[-1] if '.' in first else first.strip('`"\'')
        return 'autor'

    def _psc_resolve_paren_field(self, f: str) -> str:
        if '(' not in f or ')' not in f:
            return f
        match = re.findall(r'(\w+)\.(\w+)', f)
        if match:
            return self._psc_field_from_table_dot_matches(match)
        inner_match = re.search(r'\(([^)]+)\)', f)
        if not inner_match:
            return 'autor'
        inner = inner_match.group(1).strip()
        inner_parts = [p.strip() for p in inner.split(',')]
        return self._psc_field_from_inner_parts(inner_parts)

    def _psc_normalize_one_raw_field(self, raw: str) -> Tuple[str, Optional[str]]:
        f = raw.strip().strip('`"')
        f, alias = self._psc_split_as_alias(f)
        f = self._psc_simple_qualified_field(f)
        if '(' in f and ')' in f:
            f = self._psc_resolve_paren_field(f)
        field_name = f.strip('`"')
        return field_name, alias

    def _parse_select_column_clause(self, result: Dict[str, Any], fields_str: str) -> None:
        """Rellena fields / field_aliases del resultado para SELECT."""
        if fields_str == '*':
            result["fields"] = ['*']
            return
        if 'COUNT' in fields_str.upper():
            result["fields"] = ['COUNT(*)']
            return
        fields: List[str] = []
        field_aliases: Dict[str, str] = {}
        for raw in fields_str.split(','):
            field_name, alias = self._psc_normalize_one_raw_field(raw)
            fields.append(field_name)
            if alias:
                field_aliases[alias] = field_name
        result["fields"] = fields
        result["field_aliases"] = field_aliases
        if 'id' not in fields and any('id' in x.lower() for x in fields_str.split(',')):
            fields.append('id')
            result["fields"] = fields
    
    def _parse_sql_query(self, query: str, params: Optional[Tuple] = None) -> Dict[str, Any]:
        """
        Parsear una consulta SQL simple y convertirla a operaciones JSON
        Soporta: SELECT, INSERT, UPDATE, DELETE, CREATE TABLE básicos
        """
        query = re.sub(r'\s+', ' ', query.strip())
        query_upper = query.upper()

        if query_upper.startswith('CREATE TABLE'):
            return {
                "operation": "CREATE_TABLE",
                "table": None
            }

        result: Dict[str, Any] = {
            "operation": None,
            "table": None,
            "where": [],
            "fields": [],
            "field_aliases": {},
            "values": [],
            "set_fields": {},
            "order_by": None,
            "limit": None,
            "offset": None
        }

        if query_upper.startswith('SELECT'):
            self._fill_parse_select(query, result, params)
        elif query_upper.startswith('INSERT'):
            self._fill_parse_insert(query, result, params)
        elif query_upper.startswith('UPDATE'):
            self._fill_parse_update(query, result, params)
        elif query_upper.startswith('DELETE'):
            self._fill_parse_delete(query, result, params)

        return result

    @staticmethod
    def _index_after_sql_keyword(query: str, keyword: str) -> Optional[int]:
        """Índice tras palabra clave SQL completa; evita (.+)$ y lookaheads con backtracking (ReDoS)."""
        m = re.search(rf'\b{re.escape(keyword)}\b', query, re.IGNORECASE)
        return m.end() if m else None

    @staticmethod
    def _trim_sql_tail_before_order_limit(tail: str) -> str:
        """Recorta antes del primer ORDER BY o LIMIT en tail (búsqueda lineal + un \bLIMIT\b acotado)."""
        if not tail:
            return tail
        upper = tail.upper()
        end = len(tail)
        pos_ob = upper.find('ORDER BY')
        if pos_ob != -1:
            end = min(end, pos_ob)
        segment = tail[:end]
        lm = re.search(r'\bLIMIT\b', segment, re.IGNORECASE)
        if lm:
            end = min(end, lm.start())
        return tail[:end].strip()

    def _fill_parse_select(self, query: str, result: Dict[str, Any], params: Optional[Tuple]) -> None:
        result["operation"] = "SELECT"
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', query, re.IGNORECASE)
        if select_match:
            self._parse_select_column_clause(result, select_match.group(1).strip())

        from_match = re.search(r'FROM\s+[`"]?(\w+)[`"]?\s*\w*', query, re.IGNORECASE)
        if from_match:
            result["table"] = from_match.group(1)

        where_start = self._index_after_sql_keyword(query, 'WHERE')
        if where_start is not None:
            tail = query[where_start:].lstrip()
            where_clause = self._trim_sql_tail_before_order_limit(tail)
            if where_clause:
                result["where"] = self._parse_where_clause(where_clause, params)

        order_match = re.search(r'ORDER\s+BY\s+(\w+)(?:\s+(ASC|DESC))?(?:\s+LIMIT|$)', query, re.IGNORECASE)
        if order_match:
            result["order_by"] = {
                "field": order_match.group(1),
                "direction": order_match.group(2) if order_match.group(2) else "ASC"
            }

        limit_match = re.search(r'LIMIT\s+(\d+)(?:\s+OFFSET\s+(\d+))?', query, re.IGNORECASE)
        if limit_match:
            result["limit"] = int(limit_match.group(1))
            if limit_match.group(2):
                result["offset"] = int(limit_match.group(2))

    def _fill_parse_insert(self, query: str, result: Dict[str, Any], params: Optional[Tuple]) -> None:
        result["operation"] = "INSERT"
        insert_match = re.search(r'INSERT\s+INTO\s+[`"]?(\w+)[`"]?', query, re.IGNORECASE)
        if insert_match:
            result["table"] = insert_match.group(1)

        fields_match = re.search(r'\(([^)]+)\)', query)
        if fields_match:
            fields_str = fields_match.group(1)
            result["fields"] = [f.strip().strip('`"') for f in fields_str.split(',')]

        if params:
            result["values"] = params
        else:
            values_match = re.search(r'VALUES\s*\(([^)]+)\)', query, re.IGNORECASE)
            if values_match:
                values_str = values_match.group(1)
                result["values"] = [v.strip().strip("'\"") for v in values_str.split(',')]

    def _fill_parse_update(self, query: str, result: Dict[str, Any], params: Optional[Tuple]) -> None:
        result["operation"] = "UPDATE"
        update_match = re.search(r'UPDATE\s+[`"]?(\w+)[`"]?', query, re.IGNORECASE)
        if update_match:
            result["table"] = update_match.group(1)

        set_start = self._index_after_sql_keyword(query, 'SET')
        if set_start is not None:
            rest = query[set_start:].lstrip()
            where_in_rest = re.search(r'\bWHERE\b', rest, re.IGNORECASE)
            if where_in_rest:
                set_clause = rest[:where_in_rest.start()].strip()
            else:
                set_clause = rest.strip()
            set_parts = set_clause.split(',')
            for part in set_parts:
                if '=' in part:
                    field, value = part.split('=', 1)
                    result["set_fields"][field.strip()] = value.strip().strip("'\"")

        where_start = self._index_after_sql_keyword(query, 'WHERE')
        if where_start is not None:
            where_clause = query[where_start:].strip()
            result["where"] = self._parse_where_clause(where_clause, params)

    def _fill_parse_delete(self, query: str, result: Dict[str, Any], params: Optional[Tuple]) -> None:
        result["operation"] = "DELETE"
        delete_match = re.search(r'FROM\s+[`"]?(\w+)[`"]?', query, re.IGNORECASE)
        if delete_match:
            result["table"] = delete_match.group(1)

        where_start = self._index_after_sql_keyword(query, 'WHERE')
        if where_start is not None:
            where_clause = query[where_start:].strip()
            result["where"] = self._parse_where_clause(where_clause, params)

    @staticmethod
    def _where_op_position(part: str, op: str) -> Tuple[int, str]:
        if op == SQL_LIKE_TOKEN:
            pos = part.upper().find(SQL_LIKE_TOKEN.upper())
            return pos, 'LIKE'
        if op == SQL_IN_TOKEN:
            pos = part.upper().find(SQL_IN_TOKEN.upper())
            return pos, 'IN'
        op_clean = op.strip()
        return part.find(op), op_clean

    @staticmethod
    def _where_bind_value(
        raw_value: str, params: Optional[Tuple], param_index: int
    ) -> Tuple[Any, int]:
        if raw_value == '%s' and params and param_index < len(params):
            return params[param_index], param_index + 1
        if raw_value.startswith('(') and raw_value.endswith(')'):
            inner = raw_value[1:-1].strip()
            if params and param_index < len(params):
                return params[param_index], param_index + 1
            return [v.strip().strip("'\"") for v in inner.split(',')], param_index
        return raw_value.strip("'\""), param_index

    def _parse_where_part(
        self, part: str, params: Optional[Tuple], param_index: int
    ) -> Tuple[Optional[Dict[str, Any]], int]:
        part = part.strip()
        for op in ['!=', '<=', '>=', '=', '<', '>', SQL_LIKE_TOKEN, SQL_IN_TOKEN]:
            op_clean = op.strip()
            if not (op_clean in part.upper() or op in part):
                continue
            op_pos, op_used = self._where_op_position(part, op)
            if op_pos == -1:
                continue
            field = part[:op_pos].strip().strip('`"')
            if '.' in field:
                field = field.split('.')[-1]
            value_tail = part[op_pos + len(op):].strip()
            value, param_index = self._where_bind_value(value_tail, params, param_index)
            return ({
                "field": field,
                "operator": op_used,
                "value": value
            }, param_index)
        return (None, param_index)

    def _parse_where_clause(self, where_clause: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Parsear cláusula WHERE simple"""
        conditions: List[Dict[str, Any]] = []
        param_index = 0
        and_parts = re.split(r'\s+AND\s+', where_clause, flags=re.IGNORECASE)
        for raw_part in and_parts:
            cond, param_index = self._parse_where_part(raw_part, params, param_index)
            if cond:
                conditions.append(cond)
        return conditions
    
    def _where_compare(self, operator: str, record_value, value) -> bool:
        if operator == '=':
            return str(record_value) == str(value)
        if operator == '!=':
            return str(record_value) != str(value)
        if operator == 'LIKE':
            pattern = str(value).replace('%', '.*').replace('_', '.')
            return bool(re.search(pattern, str(record_value), re.IGNORECASE))
        if operator == 'IN':
            if isinstance(value, list):
                return str(record_value) in [str(v) for v in value]
            return str(record_value) == str(value)
        if operator == '<':
            return record_value < value
        if operator == '>':
            return record_value > value
        if operator == '<=':
            return record_value <= value
        if operator == '>=':
            return record_value >= value
        return False

    def _record_matches_where(self, record: Dict, conditions: List[Dict]) -> bool:
        for condition in conditions:
            field = condition["field"]
            if field not in record:
                return False
            if not self._where_compare(
                condition["operator"], record[field], condition["value"]
            ):
                return False
        return True

    def _apply_where(self, records: List[Dict], conditions: List[Dict]) -> List[Dict]:
        """Aplicar condiciones WHERE a los registros"""
        if not conditions:
            return records
        return [r for r in records if self._record_matches_where(r, conditions)]

    def _json_missing_table(self, fetch_all: bool):
        logger.warning("Tabla no encontrada en almacén JSON")
        if fetch_all:
            return []
        return None

    def _json_select_order_limit(self, records: List[Dict], parsed: Dict) -> List[Dict]:
        if parsed.get("order_by"):
            field = parsed["order_by"]["field"]
            if '.' in field:
                field = field.split('.')[-1]
            reverse = parsed["order_by"]["direction"].upper() == "DESC"
            records.sort(key=lambda x: x.get(field, ''), reverse=reverse)
        if parsed.get("offset"):
            records = records[parsed["offset"]:]
        if parsed.get("limit"):
            records = records[:parsed["limit"]]
        return records

    def _json_select_project_fields(self, records: List[Dict], parsed: Dict) -> List[Dict]:
        if not parsed["fields"] or parsed["fields"] == ['*']:
            return records
        out = []
        aliases = parsed.get("field_aliases", {})
        for record in records:
            row = {f: record.get(f) for f in parsed["fields"]}
            for alias, real in aliases.items():
                row[alias] = record.get(real)
            if 'id' in record and 'id' not in row:
                row['id'] = record['id']
            out.append(row)
        return out

    def _json_select_return(self, records: List[Dict], fetch_one: bool, fetch_all: bool):
        if fetch_all:
            return records
        if fetch_one:
            return records[0] if records else None
        return records[0] if records else None

    def _json_op_select(
        self, query: str, table: str, parsed: Dict, _params: Optional[Tuple],
        fetch_one: bool, fetch_all: bool,
    ):
        if 'JOIN' in query.upper():
            records = self._handle_join_query(query, parsed)
        else:
            records = self._data[table].copy()
            if parsed["where"]:
                records = self._apply_where(records, parsed["where"])
        records = self._json_select_order_limit(records, parsed)
        if parsed["fields"] and parsed["fields"][0] == 'COUNT(*)':
            return len(records)
        records = self._json_select_project_fields(records, parsed)
        return self._json_select_return(records, fetch_one, fetch_all)

    def _json_build_insert_row(self, parsed: Dict, params: Optional[Tuple]) -> Dict:
        new_record = {}
        if params:
            for i, field in enumerate(parsed["fields"]):
                if i < len(params):
                    new_record[field] = params[i]
        else:
            for i, field in enumerate(parsed["fields"]):
                if i < len(parsed["values"]):
                    new_record[field] = parsed["values"][i]
        return new_record

    def _json_insert_timestamps(self, table: str, new_record: Dict) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if table == "noticias_nul":
            if "fecha" not in new_record:
                new_record["fecha"] = ts
            return
        struct = self._get_table_structure(table)
        if "fecha_creacion" not in new_record and "fecha_creacion" in struct:
            new_record["fecha_creacion"] = ts
        elif "fecha" not in new_record and "fecha" in struct:
            new_record["fecha"] = ts

    def _json_op_insert(self, table: str, parsed: Dict, params: Optional[Tuple]):
        new_record = self._json_build_insert_row(parsed, params)
        id_field = self._get_id_field(table)
        if id_field and id_field not in new_record:
            new_record[id_field] = self._get_next_id(table)
        self._json_insert_timestamps(table, new_record)
        self._data[table].append(new_record)
        self._save_data()
        if id_field:
            return new_record.get(id_field, len(self._data[table]))
        return True

    def _json_op_update(self, table: str, parsed: Dict, params: Optional[Tuple]) -> int:
        records = self._data[table]
        if parsed["where"]:
            matching = self._apply_where(records, parsed["where"])
            indices = [i for i, r in enumerate(records) if r in matching]
        else:
            indices = list(range(len(records)))
        for idx in indices:
            for field, value in parsed["set_fields"].items():
                if value == '%s' and params:
                    value = params[0]
                records[idx][field] = value
        self._save_data()
        return len(indices)

    def _json_op_delete(self, table: str, parsed: Dict) -> int:
        records = self._data[table]
        if parsed["where"]:
            matching = self._apply_where(records, parsed["where"])
            to_del = [i for i, r in enumerate(records) if r in matching]
        else:
            to_del = list(range(len(records)))
        for idx in sorted(to_del, reverse=True):
            del records[idx]
        self._save_data()
        return len(to_del)
    
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
                    return self._json_missing_table(fetch_all)
                
                if operation == "SELECT":
                    return self._json_op_select(
                        query, table, parsed, params, fetch_one, fetch_all
                    )
                if operation == "INSERT":
                    return self._json_op_insert(table, parsed, params)
                if operation == "UPDATE":
                    return self._json_op_update(table, parsed, params)
                if operation == "DELETE":
                    return self._json_op_delete(table, parsed)
                if operation == "CREATE_TABLE":
                    return True
                logger.warning("Operación no soportada: %s", operation)
                return None
                    
            except Exception as e:
                logger.error("Error al ejecutar consulta JSON: %s", e)
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

    def _join_match_pattern(self, query: str):
        join_pattern = (
            r'FROM\s+(\w+)\s+\w+\s+(?:LEFT\s+)?JOIN\s+(\w+)\s+\w+\s+ON\s+'
            r'(.+)(?=\s+WHERE\b|\s+ORDER\s+BY\b|\s+LIMIT\b|$)'
        )
        return re.search(join_pattern, query, re.IGNORECASE)

    def _join_resolve_main_join_fields(self, join_condition: str) -> Optional[Tuple[str, str]]:
        join_parts = join_condition.split('=')
        if len(join_parts) != 2:
            return None
        left_part = join_parts[0].strip()
        right_part = join_parts[1].strip()
        left_prefix = left_part.split('.')[0] if '.' in left_part else None
        right_prefix = right_part.split('.')[0] if '.' in right_part else None
        main_field_part = left_part
        join_field_part = right_part
        if right_prefix and right_prefix.lower() in ['n', 'c'] and left_prefix and left_prefix.lower() in ['u', 'nc']:
            main_field_part = right_part
            join_field_part = left_part
        main_field = main_field_part.split('.')[-1]
        join_field = join_field_part.split('.')[-1]
        return main_field, join_field

    def _join_filter_main_records(
        self, main_records: List[Dict], where_conditions: List[Dict]
    ) -> List[Dict]:
        if not where_conditions:
            return main_records
        adjusted_where = []
        for cond in where_conditions:
            adj_cond = cond.copy()
            if '.' in adj_cond.get("field", ""):
                adj_cond["field"] = adj_cond["field"].split('.')[-1]
            adjusted_where.append(adj_cond)
        return self._apply_where(main_records, adjusted_where)

    @staticmethod
    def _join_find_matching_record(
        join_records: List[Dict], join_field: str, main_value: Any
    ) -> Optional[Dict]:
        for join_rec in join_records:
            if join_rec.get(join_field) == main_value:
                return join_rec
        return None

    @staticmethod
    def _join_merge_single_row(main_rec: Dict, matched_join_rec: Optional[Dict]) -> Dict:
        combined = main_rec.copy()
        if matched_join_rec:
            for key, value in matched_join_rec.items():
                if key not in combined:
                    combined[key] = value
        return combined

    def _join_combine_rows(
        self,
        filtered_main: List[Dict],
        join_records: List[Dict],
        main_field: str,
        join_field: str,
        is_left_join: bool,
    ) -> List[Dict]:
        result = []
        for main_rec in filtered_main:
            main_value = main_rec.get(main_field)
            matched = self._join_find_matching_record(join_records, join_field, main_value)
            if not matched and not is_left_join:
                continue
            result.append(self._join_merge_single_row(main_rec, matched))
        return result

    def _join_project_one_record(self, record: Dict, parsed: Dict) -> Dict:
        filtered_record: Dict[str, Any] = {}
        for field in parsed["fields"]:
            clean_field = field.split('.')[-1]
            filtered_record[clean_field] = record.get(clean_field)
        field_aliases = parsed.get("field_aliases", {})
        for alias, real_field in field_aliases.items():
            clean_real = real_field.split('.')[-1] if '.' in real_field else real_field
            filtered_record[alias] = record.get(clean_real)
        return filtered_record

    def _join_project_join_fields(self, result: List[Dict], parsed: Dict) -> List[Dict]:
        if not parsed.get("fields") or parsed["fields"] == ['*']:
            return result
        return [self._join_project_one_record(r, parsed) for r in result]

    def _handle_join_query(self, query: str, parsed: Dict) -> List[Dict]:
        """
        Manejar consultas con JOINs básicos (INNER JOIN y LEFT JOIN)
        Ejemplo 1: SELECT c.id, c.nombre, c.color FROM categorias_nul c JOIN noticias_categorias nc ON c.id = nc.categoria_id WHERE nc.noticia_id = %s
        Ejemplo 2: SELECT n.id, n.titulo FROM noticias_nul n LEFT JOIN usuarios_nul u ON n.autor = u.usuario WHERE n.id = %s
        """
        try:
            query_upper = query.upper()
            if 'JOIN' not in query_upper:
                logger.warning("[JOIN] No se detectó JOIN en la consulta")
                return []
            is_left_join = 'LEFT JOIN' in query_upper
            join_match = self._join_match_pattern(query)
            if not join_match:
                logger.warning("[JOIN] No se pudo analizar la cláusula JOIN de la consulta")
                return []
            main_table = join_match.group(1)
            join_table = join_match.group(2)
            join_condition = join_match.group(3).strip()
            fields = self._join_resolve_main_join_fields(join_condition)
            if not fields:
                return []
            main_field, join_field = fields
            logger.debug(
                "[JOIN] tablas=%s,%s campos=%s,%s left=%s",
                main_table, join_table, main_field, join_field, is_left_join,
            )
            main_records = self._data.get(main_table, [])
            join_records = self._data.get(join_table, [])
            filtered_main = self._join_filter_main_records(main_records, parsed.get("where", []))
            logger.debug("[JOIN] filas tras WHERE: main=%s join=%s", len(filtered_main), len(join_records))
            result = self._join_combine_rows(
                filtered_main, join_records, main_field, join_field, is_left_join
            )
            result = self._join_project_join_fields(result, parsed)
            logger.debug("[JOIN] filas finales=%s", len(result))
            return result
        except Exception as e:
            logger.error("Error al procesar JOIN: %s", e)
            import traceback
            logger.error(traceback.format_exc())
            return []
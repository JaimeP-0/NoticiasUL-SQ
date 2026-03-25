"""
Sistema de caché simple en memoria con TTL
"""
import time
from threading import Lock
from typing import Any, Optional

class SimpleCache:
    """Caché simple en memoria con tiempo de vida (TTL)"""
    
    def __init__(self, default_ttl: int = 60):
        """
        Args:
            default_ttl: Tiempo de vida por defecto en segundos
        """
        self._cache = {}
        self._lock = Lock()
        self.default_ttl = default_ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Obtener valor del caché si existe y no ha expirado"""
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if time.time() < expiry:
                    return value
                else:
                    # Eliminar entrada expirada
                    del self._cache[key]
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Guardar valor en el caché con TTL"""
        ttl = ttl or self.default_ttl
        expiry = time.time() + ttl
        with self._lock:
            self._cache[key] = (value, expiry)
    
    def delete(self, key: str) -> None:
        """Eliminar entrada del caché"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
    
    def clear(self) -> None:
        """Limpiar todo el caché"""
        with self._lock:
            self._cache.clear()
    
    def cleanup_expired(self) -> None:
        """Limpiar entradas expiradas"""
        current_time = time.time()
        with self._lock:
            expired_keys = [
                key for key, (_, expiry) in self._cache.items()
                if current_time >= expiry
            ]
            for key in expired_keys:
                del self._cache[key]
    
    def delete_pattern(self, pattern: str) -> int:
        """
        Eliminar todas las entradas que coincidan con un patrón.
        Soporta wildcards simples: * para cualquier secuencia de caracteres.
        
        Args:
            pattern: Patrón con wildcards (ej: "news_*")
        
        Returns:
            Número de entradas eliminadas
        """
        import fnmatch
        deleted_count = 0
        with self._lock:
            keys_to_delete = [
                key for key in self._cache.keys()
                if fnmatch.fnmatch(key, pattern)
            ]
            for key in keys_to_delete:
                del self._cache[key]
                deleted_count += 1
        return deleted_count

# Instancia global del caché
cache = SimpleCache(default_ttl=10)  # 10 segundos por defecto (reducido para actualizaciones más rápidas)


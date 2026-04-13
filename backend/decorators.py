"""
Decoradores para agregar funcionalidades transversales usando el patrón Decorator.

Este módulo implementa el patrón Decorator para agregar funcionalidades
como logging, retry y caché a funciones sin modificar su código interno.

Valor para el usuario:
- Logging automático de operaciones críticas
- Reintentos automáticos en caso de fallos transitorios
- Caché automático para mejorar el rendimiento
- Código más limpio y mantenible
"""
import functools
import time
import logging
from typing import Callable, Any, Optional
from cache import cache

logger = logging.getLogger(__name__)


class LoggingDecorator:
    @staticmethod
    def log_operation(operation_name: str):

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                logger.info(f"[LOG] Iniciando operación: {operation_name}")
                logger.debug(f"[LOG] Parámetros: args={args}, kwargs={kwargs}")
                
                try:
                    result = func(*args, **kwargs)
                    elapsed_time = time.time() - start_time
                    logger.info(f"[LOG] Operación completada: {operation_name} (Tiempo: {elapsed_time:.2f}s)")
                    logger.debug(f"[LOG] Resultado: {result}")
                    return result
                except Exception as e:
                    elapsed_time = time.time() - start_time
                    logger.error(f"[LOG] Error en operación: {operation_name} (Tiempo: {elapsed_time:.2f}s)")
                    logger.error(f"[LOG] Error: {str(e)}")
                    import traceback
                    logger.error(f"[LOG] Traceback: {traceback.format_exc()}")
                    raise
            return wrapper
        return decorator
    
    @staticmethod
    def log_performance(threshold_seconds: float = 1.0):
        """
        Decorador para registrar operaciones lentas.
        
        Args:
            threshold_seconds: Umbral en segundos para considerar una operación lenta
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                result = func(*args, **kwargs)
                elapsed_time = time.time() - start_time
                
                if elapsed_time > threshold_seconds:
                    logger.warning(f"⚠️ [PERF] Operación lenta detectada: {func.__name__} ({elapsed_time:.2f}s > {threshold_seconds}s)")
                
                return result
            return wrapper
        return decorator


class RetryDecorator:
    """
    Decorador para reintentar operaciones que fallan.
    
    Útil para operaciones que pueden fallar por problemas transitorios
    como timeouts de red, errores de conexión, etc.
    
    Ejemplo:
        @RetryDecorator.retry_on_failure(max_retries=3, delay=1.0)
        def upload_image():
            ...
    """
    
    @staticmethod
    def _run_with_retries(func: Callable, max_retries: int, delay: float,
                          exceptions: tuple, args: tuple, kwargs: dict) -> Any:
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(
                        "🔄 [RETRY] Reintentando %s (intento %s/%s)",
                        func.__name__,
                        attempt + 1,
                        max_retries + 1,
                    )
                    time.sleep(delay * attempt)
                result = func(*args, **kwargs)
                if attempt > 0:
                    logger.info("✅ [RETRY] Operación exitosa después de %s intentos", attempt + 1)
                return result
            except exceptions as e:
                last_exception = e
                logger.warning("⚠️ [RETRY] Intento %s falló: %s", attempt + 1, type(e).__name__)
                if attempt == max_retries:
                    logger.error("❌ [RETRY] Todos los reintentos fallaron para %s", func.__name__)
                    raise
        if last_exception:
            raise last_exception
        return None

    @staticmethod
    def retry_on_failure(max_retries: int = 3, delay: float = 1.0, 
                         exceptions: tuple = (Exception,)):
        """
        Decorador para reintentar operaciones que fallan.
        
        Args:
            max_retries: Número máximo de reintentos
            delay: Tiempo de espera entre reintentos (segundos)
            exceptions: Tupla de excepciones que deben activar el reintento
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return RetryDecorator._run_with_retries(
                    func, max_retries, delay, exceptions, args, kwargs
                )
            return wrapper
        return decorator


class CacheDecorator:
    """
    Decorador para manejar caché automáticamente.
    
    Almacena resultados de funciones en caché para mejorar el rendimiento
    y reducir la carga en la base de datos.
    
    Ejemplo:
        @CacheDecorator.cache_result(key_prefix="news", ttl=60)
        def get_news():
            ...
    """
    
    @staticmethod
    def cache_result(key_prefix: str, ttl: int = 60, 
                     key_builder: Optional[Callable] = None):
        """
        Decorador para cachear resultados de funciones.
        
        Args:
            key_prefix: Prefijo para la clave de caché
            ttl: Tiempo de vida del caché en segundos
            key_builder: Función opcional para construir la clave de caché personalizada
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Construir clave de caché
                if key_builder:
                    cache_key = key_builder(*args, **kwargs)
                else:
                    # Construir clave basada en args y kwargs
                    key_parts = [key_prefix]
                    if args:
                        key_parts.append(str(args))
                    if kwargs:
                        # Ordenar kwargs para consistencia
                        sorted_kwargs = sorted(kwargs.items())
                        key_parts.append(str(sorted_kwargs))
                    cache_key = "_".join(key_parts)
                
                # Intentar obtener del caché
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"💾 [CACHE] Cache hit para: {cache_key}")
                    return cached_result
                
                # Ejecutar función y guardar en caché
                logger.debug(f"💾 [CACHE] Cache miss para: {cache_key}")
                result = func(*args, **kwargs)
                cache.set(cache_key, result, ttl=ttl)
                logger.debug(f"💾 [CACHE] Resultado guardado en caché: {cache_key}")
                
                return result
            return wrapper
        return decorator
    
    @staticmethod
    def invalidate_cache(key_pattern: str):
        """
        Decorador para invalidar caché después de operaciones de escritura.
        
        Args:
            key_pattern: Patrón de clave de caché a invalidar
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                
                # Invalidar caché (implementación simple: limpiar todo)
                # En producción, se podría implementar invalidación selectiva
                logger.info(f"🗑️ [CACHE] Invalidando caché para patrón: {key_pattern}")
                cache.delete(key_pattern)
                
                return result
            return wrapper
        return decorator


class ValidationDecorator:
    """
    Decorador para validar parámetros antes de ejecutar funciones.
    
    Ejemplo:
        @ValidationDecorator.validate_params(validate_title, validate_content)
        def create_news(title, content):
            ...
    """
    
    @staticmethod
    def validate_params(*validators: Callable):
        """
        Decorador para validar parámetros antes de ejecutar funciones.
        
        Args:
            validators: Funciones de validación que reciben los mismos parámetros que la función decorada
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Ejecutar validadores
                for validator in validators:
                    try:
                        validator(*args, **kwargs)
                    except Exception as e:
                        logger.error(f"❌ [VALIDATION] Validación falló: {str(e)}")
                        raise ValueError(f"Validación fallida: {str(e)}")
                
                # Si todas las validaciones pasan, ejecutar la función
                return func(*args, **kwargs)
            return wrapper
        return decorator


def combine_decorators(*decorators):
    """
    Función auxiliar para combinar múltiples decoradores.
    
    Ejemplo:
        @combine_decorators(
            LoggingDecorator.log_operation("Crear noticia"),
            RetryDecorator.retry_on_failure(max_retries=3),
            CacheDecorator.cache_result(key_prefix="news", ttl=60)
        )
        def create_news():
            ...
    """
    def decorator(func):
        for dec in reversed(decorators):
            func = dec(func)
        return func
    return decorator


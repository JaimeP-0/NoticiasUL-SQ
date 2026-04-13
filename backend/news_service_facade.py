"""
Fachada para operaciones de noticias usando el patrón Facade.

Este módulo implementa el patrón Facade para simplificar operaciones
complejas que involucran múltiples servicios (base de datos, Firebase,
validación, caché, etc.).

Valor para el usuario:
- Interfaz simple y clara para operaciones complejas
- Encapsulación de lógica de múltiples servicios
- Manejo centralizado de errores
- Transformación automática de datos
- Invalidación automática de caché
"""
import logging
import urllib.parse
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from database import Database
from firebase_service import FirebaseService
from validators import NoticiaValidatorFactory
from factory_noticias import NoticiaFactory
from cache import cache
from decorators import (
    LoggingDecorator,
    RetryDecorator,
    CacheDecorator,
    combine_decorators
)
from mediator_pattern import Mediator

logger = logging.getLogger(__name__)

MSG_NOTICIA_NO_ENCONTRADA = "Noticia no encontrada"


class NewsServiceFacade:    
    def __init__(self, db: Optional[Database] = None, 
                 firebase: Optional[FirebaseService] = None,
                 mediator: Optional[Mediator] = None):

        self._database_subsystem = db or Database()
        self._firebase_subsystem = firebase or FirebaseService()
        self._mediator = mediator

    @staticmethod
    def _validate_update_fields(titulo, contenido):
        if titulo is not None:
            if not titulo.strip() or len(titulo.strip()) < 5:
                raise ValueError("El título debe tener al menos 5 caracteres")
            if len(titulo.strip()) > 255:
                raise ValueError("El título no puede exceder 255 caracteres")
        if contenido is not None:
            if not contenido.strip() or len(contenido.strip()) < 50:
                raise ValueError("El contenido debe tener al menos 50 caracteres")
    
    @combine_decorators(
        LoggingDecorator.log_operation("Crear noticia"),
        RetryDecorator.retry_on_failure(max_retries=2, delay=0.5, 
                                       exceptions=(Exception,))
    )
    def create_news(self, titulo: str, contenido: str, autor: str,
                    imagen_url: Optional[str] = None,
                    tipo_noticia: str = "general",
                    categorias: Optional[List[int]] = None) -> Dict[str, Any]:
        validator = NoticiaValidatorFactory.create_validator(tipo_noticia)
        es_valido, error = validator.validate(titulo, contenido, autor, imagen_url)
        
        if not es_valido:
            logger.error("Validación fallida al crear noticia")
            raise ValueError(error)
        
        noticia_obj = NoticiaFactory.crear(tipo_noticia, titulo, contenido, autor, imagen_url)
        logger.debug(f"Objeto Noticia creado: {type(noticia_obj).__name__}")
        
        imagen_url_final = imagen_url if imagen_url else ""
        noticia_id = self._database_subsystem.execute_query(
            "INSERT INTO noticias_nul (titulo, contenido, autor, imagen_url) VALUES (%s, %s, %s, %s)",
            (titulo, contenido, autor, imagen_url_final)
        )
        logger.info(f"Noticia insertada en BD con ID: {noticia_id}")
        
        if categorias:
            self._associate_categories(noticia_id, categorias)
        
        self._invalidate_news_cache()
        
        # Intentar obtener la noticia con reintentos, pero sin volver a insertar
        max_retries = 3
        noticia = None
        for attempt in range(max_retries):
            try:
                noticia = self._get_news_with_details(noticia_id)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        "Reintento al leer noticia recién creada (intento %s/%s)",
                        attempt + 1,
                        max_retries,
                    )
                    import time
                    time.sleep(0.2 * (attempt + 1))  # Backoff corto
                else:
                    logger.error(
                        "No se pudo obtener noticia tras crearla (%s intentos): %s",
                        max_retries,
                        type(e).__name__,
                    )
                    # Si no se puede obtener, crear un objeto básico con los datos que tenemos
                    noticia = {
                        'id': noticia_id,
                        'titulo': titulo,
                        'contenido': contenido,
                        'autor': autor,
                        'imagen': imagen_url_final,
                        'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'nombre_autor': autor,
                        'rol_autor': 'usuario',
                        'categorias': []
                    }
        
        if self._mediator:
            self._mediator.notify(self, 'news_create', {
                'news': noticia,
                'result': True
            })
        return noticia
    
    @combine_decorators(
        LoggingDecorator.log_operation("Actualizar noticia"),
        RetryDecorator.retry_on_failure(max_retries=2, delay=0.5)
    )
    def update_news(self, news_id: int, titulo: Optional[str] = None,
                    contenido: Optional[str] = None,
                    imagen_url: Optional[str] = None,
                    categorias: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Actualizar una noticia existente.
        
        Este método encapsula todas las operaciones necesarias para actualizar una noticia:
        1. Verificar que la noticia existe
        2. Validar datos si se proporcionan
        3. Actualizar en base de datos
        4. Actualizar categorías si se proporcionan
        5. Invalidar caché
        6. Transformación de datos para respuesta
        
        Args:
            news_id: ID de la noticia a actualizar
            titulo: Nuevo título (opcional)
            contenido: Nuevo contenido (opcional)
            imagen_url: Nueva URL de imagen (opcional)
            categorias: Nueva lista de categorías (opcional)
        
        Returns:
            Dict con la noticia actualizada
        
        Raises:
            ValueError: Si la noticia no existe o la validación falla
            Exception: Si hay error en la base de datos
        """
        # Orquestación de múltiples subsistemas para actualizar una noticia
        
        # 1. Delegar verificación al subsistema de base de datos
        noticia_existente = self._database_subsystem.execute_query(
            "SELECT id, autor FROM noticias_nul WHERE id = %s",
            (news_id,),
            fetch_one=True
        )
        
        if not noticia_existente:
            raise ValueError(MSG_NOTICIA_NO_ENCONTRADA)
        
        self._validate_update_fields(titulo, contenido)
        
        # 3. Construir query de actualización dinámicamente
        updates = []
        params = []
        
        if titulo is not None:
            updates.append("titulo = %s")
            params.append(titulo.strip())
        
        if contenido is not None:
            updates.append("contenido = %s")
            params.append(contenido.strip())
        
        if imagen_url is not None:
            updates.append("imagen_url = %s")
            params.append(imagen_url if imagen_url else "")
        
        # 4. Delegar actualización al subsistema de base de datos
        if updates:
            params.append(news_id)
            query = f"UPDATE noticias_nul SET {', '.join(updates)} WHERE id = %s"
            self._database_subsystem.execute_query(query, tuple(params))
            logger.info(f"Noticia {news_id} actualizada en BD")
        
        # 5. Delegar actualización de categorías al subsistema de base de datos
        if categorias is not None:
            self._update_categories(news_id, categorias)
        
        # 6. Delegar invalidación de caché al subsistema de caché
        self._invalidate_news_cache(news_id)
        
        # 7. Obtener noticia actualizada con transformaciones (orquestación interna)
        noticia = self._get_news_with_details(news_id)
        
        # 8. Notificar al mediador sobre la actualización (patrón Mediator)
        if self._mediator:
            self._mediator.notify(self, 'news_update', {
                'news': noticia,
                'result': True
            })
        
        return noticia
    
    @combine_decorators(
        LoggingDecorator.log_operation("Eliminar noticia"),
        RetryDecorator.retry_on_failure(max_retries=2, delay=0.5)
    )
    def delete_news(self, news_id: int) -> bool:
        """
        Eliminar una noticia.
        
        Este método encapsula todas las operaciones necesarias para eliminar una noticia:
        1. Verificar que la noticia existe
        2. Eliminar imagen de Firebase si existe
        3. Eliminar de base de datos
        4. Invalidar caché
        
        Args:
            news_id: ID de la noticia a eliminar
        
        Returns:
            True si se eliminó correctamente
        
        Raises:
            ValueError: Si la noticia no existe
            Exception: Si hay error en la base de datos o Firebase
        """
        # Orquestación de múltiples subsistemas para eliminar una noticia
        
        # 1. Delegar verificación al subsistema de base de datos
        noticia_existente = self._database_subsystem.execute_query(
            "SELECT id, imagen_url FROM noticias_nul WHERE id = %s",
            (news_id,),
            fetch_one=True
        )
        
        if not noticia_existente:
            raise ValueError(MSG_NOTICIA_NO_ENCONTRADA)
        
        # 2. Delegar eliminación de imagen al subsistema de Firebase
        imagen_url = noticia_existente.get('imagen_url')
        if imagen_url and self._firebase_subsystem._initialized:
            try:
                if 'firebasestorage' in imagen_url or 'storage.googleapis.com' in imagen_url:
                    if '/o/' in imagen_url:
                        path_part = imagen_url.split('/o/')[1].split('?')[0]
                        blob_path = urllib.parse.unquote(path_part)
                        self._firebase_subsystem.delete_image(blob_path)
                        logger.info(f"Imagen de Firebase eliminada: {blob_path}")
            except Exception as e:
                logger.warning(f"No se pudo eliminar imagen de Firebase: {e}")
        
        # 3. Delegar eliminación de categorías al subsistema de base de datos
        self._database_subsystem.execute_query(
            "DELETE FROM noticias_categorias WHERE noticia_id = %s",
            (news_id,)
        )
        
        # 4. Delegar eliminación de noticia al subsistema de base de datos
        self._database_subsystem.execute_query(
            "DELETE FROM noticias_nul WHERE id = %s",
            (news_id,)
        )
        
        logger.info(f"Noticia {news_id} eliminada de BD")
        
        # 5. Delegar invalidación de caché al subsistema de caché
        self._invalidate_news_cache(news_id)
        
        # 6. Notificar al mediador sobre la eliminación (patrón Mediator)
        if self._mediator:
            title = noticia_existente.get('titulo', f'Noticia #{news_id}')
            self._mediator.notify(self, 'news_delete', {
                'news_id': news_id,
                'title': title,
                'result': True
            })
        
        return True
    
    def get_news_by_id(self, news_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtener una noticia por ID (con caché automático).
        
        Args:
            news_id: ID de la noticia
        
        Returns:
            Dict con la noticia o None si no existe
        """
        # Construir clave de caché
        cache_key = f"news_detail_{news_id}"
        
        # Intentar obtener del caché
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"[CACHE] Cache hit para noticia {news_id}")
            return cached_result
        
        logger.debug(f"[CACHE] Cache miss para noticia {news_id}")
        
        # Delegar consulta al subsistema de base de datos
        noticia = self._database_subsystem.execute_query(
            """SELECT n.id, n.titulo, n.contenido, n.autor, n.fecha, n.imagen_url as imagen,
                      COALESCE(u.nombre, n.autor) as nombre_autor,
                      COALESCE(u.rol, 'usuario') as rol_autor
               FROM noticias_nul n
               LEFT JOIN usuarios_nul u ON n.autor = u.usuario
               WHERE n.id = %s""",
            (news_id,),
            fetch_one=True
        )
        
        if not noticia:
            return None
        
        # Delegar consulta de categorías al subsistema de base de datos
        categorias = self._database_subsystem.execute_query(
            """SELECT c.id, c.nombre, c.color
               FROM categorias_nul c
               JOIN noticias_categorias nc ON c.id = nc.categoria_id
               WHERE nc.noticia_id = %s""",
            (news_id,),
            fetch_all=True
        )
        
        # Transformar datos (operación interna de la fachada)
        noticia_transformada = self._transform_news_data(noticia, categorias)
        
        # Delegar guardado en caché al subsistema de caché
        cache.set(cache_key, noticia_transformada, ttl=15)
        logger.debug(f"💾 [CACHE] Noticia {news_id} guardada en caché")
        
        return noticia_transformada
    
    def _get_news_with_details(self, news_id: int) -> Dict[str, Any]:
        """
        Obtener noticia con todos los detalles y transformaciones.
        
        Args:
            news_id: ID de la noticia
        
        Returns:
            Dict con la noticia transformada
        """
        # Delegar consulta al subsistema de base de datos
        noticia = self._database_subsystem.execute_query(
            """SELECT n.id, n.titulo, n.contenido, n.autor, n.fecha, n.imagen_url as imagen,
                      COALESCE(u.nombre, n.autor) as nombre_autor,
                      COALESCE(u.rol, 'usuario') as rol_autor
               FROM noticias_nul n
               LEFT JOIN usuarios_nul u ON n.autor = u.usuario
               WHERE n.id = %s""",
            (news_id,),
            fetch_one=True
        )
        
        if not noticia:
            raise ValueError(MSG_NOTICIA_NO_ENCONTRADA)
        
        # Delegar consulta de categorías al subsistema de base de datos
        categorias = self._database_subsystem.execute_query(
            """SELECT c.id, c.nombre, c.color
               FROM categorias_nul c
               JOIN noticias_categorias nc ON c.id = nc.categoria_id
               WHERE nc.noticia_id = %s""",
            (news_id,),
            fetch_all=True
        )
        
        # Transformar datos (operación interna de la fachada)
        return self._transform_news_data(noticia, categorias)
    
    def _transform_news_data(self, noticia: Dict[str, Any], 
                             categorias: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Transformar datos de noticia para respuesta.
        
        Args:
            noticia: Dict con datos de la noticia
            categorias: Lista de categorías
        
        Returns:
            Dict con la noticia transformada
        """
        # Convertir fecha a string
        if noticia.get('fecha'):
            if isinstance(noticia['fecha'], datetime):
                noticia['fecha'] = noticia['fecha'].strftime("%Y-%m-%d %H:%M:%S")
        
        # Asegurar que imagen existe
        if not noticia.get('imagen'):
            noticia['imagen'] = ""
        
        # Agregar categorías
        noticia['categorias'] = [
            {'id': c['id'], 'nombre': c['nombre'], 'color': c['color']} 
            for c in categorias
        ] if categorias else []
        
        return noticia
    
    def _associate_categories(self, noticia_id: int, categorias: List[int]) -> None:
        """
        Asociar categorías a una noticia.
        
        Args:
            noticia_id: ID de la noticia
            categorias: Lista de IDs de categorías
        """
        if not categorias:
            logger.debug(f"No hay categorías para asociar a la noticia {noticia_id}")
            return
        
        logger.info("Asociando %s categoría(s) a la noticia %s", len(categorias), noticia_id)
        
        # Delegar asociación de categorías al subsistema de base de datos
        for cat_id in categorias:
            try:
                self._database_subsystem.execute_query(
                    "INSERT INTO noticias_categorias (noticia_id, categoria_id) VALUES (%s, %s)",
                    (noticia_id, cat_id)
                )
                logger.debug("Categoría asociada a noticia %s", noticia_id)
            except Exception as e:
                logger.error(
                    "Error al asociar categoría a noticia %s: %s",
                    noticia_id,
                    type(e).__name__,
                )
                import traceback
                logger.error(traceback.format_exc())
    
    def _update_categories(self, noticia_id: int, categorias: List[int]) -> None:
        """
        Actualizar categorías de una noticia.
        
        Args:
            noticia_id: ID de la noticia
            categorias: Nueva lista de IDs de categorías
        """
        # Delegar eliminación de categorías al subsistema de base de datos
        self._database_subsystem.execute_query(
            "DELETE FROM noticias_categorias WHERE noticia_id = %s",
            (noticia_id,)
        )
        
        # Delegar agregado de nuevas categorías al subsistema de base de datos
        if categorias:
            self._associate_categories(noticia_id, categorias)
    
    def _invalidate_news_cache(self, news_id: Optional[int] = None) -> None:
        """
        Invalidar caché de noticias.
        
        Args:
            news_id: ID de la noticia específica (opcional)
        """
        # Invalidar todos los cachés de noticias usando el patrón
        # El caché puede tener diferentes formatos: news_15_0, news_15_0_None_, news_15_0_1_, etc.
        try:
            # Invalidar usando el método de invalidación por patrón
            deleted_count = cache.delete_pattern("news_*")
            logger.info(f"🗑️ Caché de noticias invalidado: {deleted_count} entradas eliminadas")
        except Exception as e:
            logger.warning(f"⚠️ Error al invalidar caché: {e}")
            # Fallback: invalidar cachés comunes manualmente
            for limit in [15, 20, 30, 50]:
                for offset in [0, 15, 30, 45]:
                    cache.delete(f"news_{limit}_{offset}")
                    cache.delete(f"news_{limit}_{offset}_None_")
                    cache.delete(f"news_{limit}_{offset}_None")
                    for cat_id in [1, 2, 3, 4, 5]:
                        cache.delete(f"news_{limit}_{offset}_{cat_id}_")
                        cache.delete(f"news_{limit}_{offset}_{cat_id}")
            logger.info("🗑️ Caché de noticias invalidado (fallback manual)")
        
        # Invalidar caché de noticia específica si se proporciona
        if news_id:
            cache_key = f"news_detail_{news_id}"
            cache.delete(cache_key)
            logger.info(f"🗑️ Caché invalidado para noticia {news_id}")


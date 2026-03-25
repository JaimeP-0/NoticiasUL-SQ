"""
Patrón Mediator - Implementación para coordinar interacciones entre componentes

Este módulo implementa el patrón Mediator para coordinar las interacciones
entre diferentes servicios del sistema (notificaciones, caché, logging, actualización de UI).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class Mediator(ABC):
    """Interfaz abstracta para el mediador"""
    
    @abstractmethod
    def notify(self, sender: object, event: str, data: Dict[str, Any]) -> None:
        """
        Notificar al mediador sobre un evento
        
        Args:
            sender: El objeto que envía la notificación
            event: Tipo de evento
            data: Datos del evento
        """
        pass


class Component(ABC):
    """Clase base para componentes que interactúan a través del mediador"""
    
    def __init__(self, mediator: Mediator = None):
        self._mediator = mediator
    
    @property
    def mediator(self) -> Mediator:
        return self._mediator
    
    @mediator.setter
    def mediator(self, mediator: Mediator) -> None:
        self._mediator = mediator


class NewsServiceMediator(Mediator):
    """
    Mediador concreto que coordina las interacciones cuando se realizan
    operaciones CRUD sobre noticias.
    """
    
    def __init__(self, cache_service=None, logging_service=None, notification_service=None, observer_subject=None):
        self._cache_service = cache_service
        self._logging_service = logging_service
        self._notification_service = notification_service
        self._observer_subject = observer_subject
        self._components: List[Component] = []
    
    def register_component(self, component: Component) -> None:
        """Registrar un componente con el mediador"""
        component.mediator = self
        self._components.append(component)
        logger.info(f"Componente {type(component).__name__} registrado en el mediador")
    
    def notify(self, sender: object, event: str, data: Dict[str, Any]) -> None:
        """
        Coordinar las acciones cuando ocurre un evento relacionado con noticias
        
        Args:
            sender: El objeto que envía la notificación (ej: NewsServiceFacade)
            event: Tipo de evento ('create', 'update', 'delete', 'get')
            data: Datos del evento (incluye la noticia, resultado, etc.)
        """
        logger.info(f"[MEDIATOR] Evento recibido: {event} de {type(sender).__name__}")
        
        if event == 'news_create':
            self._handle_news_create(data)
        elif event == 'news_update':
            self._handle_news_update(data)
        elif event == 'news_delete':
            self._handle_news_delete(data)
        elif event == 'news_get':
            self._handle_news_get(data)
        else:
            logger.warning(f"Evento desconocido: {event}")
    
    def _handle_news_create(self, data: Dict[str, Any]) -> None:
        """Coordinar acciones cuando se crea una noticia"""
        news_data = data.get('news', {})
        result = data.get('result')
        
        if result and self._observer_subject:
            # Notificar a los observadores
            self._observer_subject.news_created(news_data)
        
        if self._cache_service:
            # Invalidar caché de lista de noticias
            self._cache_service.delete('news_list')
            logger.info("[MEDIATOR] Caché invalidado después de crear noticia")
        
        if self._logging_service:
            self._logging_service.log_operation(
                f"Noticia creada: {news_data.get('titulo', 'Sin título')}",
                {'news_id': news_data.get('id'), 'author': news_data.get('autor')}
            )
    
    def _handle_news_update(self, data: Dict[str, Any]) -> None:
        """Coordinar acciones cuando se actualiza una noticia"""
        news_data = data.get('news', {})
        result = data.get('result')
        
        if result and self._observer_subject:
            # Notificar a los observadores
            self._observer_subject.news_updated(news_data)
        
        if self._cache_service:
            # Invalidar caché de lista y de la noticia específica
            self._cache_service.delete('news_list')
            news_id = news_data.get('id')
            if news_id:
                self._cache_service.delete(f"news_{news_id}")
            logger.info("[MEDIATOR] Caché invalidado después de actualizar noticia")
        
        if self._logging_service:
            self._logging_service.log_operation(
                f"Noticia actualizada: {news_data.get('titulo', 'Sin título')}",
                {'news_id': news_data.get('id'), 'author': news_data.get('autor')}
            )
    
    def _handle_news_delete(self, data: Dict[str, Any]) -> None:
        """Coordinar acciones cuando se elimina una noticia"""
        news_id = data.get('news_id')
        title = data.get('title')
        result = data.get('result')
        
        if result and self._observer_subject:
            # Notificar a los observadores
            self._observer_subject.news_deleted(news_id, title)
        
        if self._cache_service:
            # Invalidar caché de lista y de la noticia específica
            self._cache_service.delete('news_list')
            if news_id:
                self._cache_service.delete(f"news_{news_id}")
            logger.info("[MEDIATOR] Caché invalidado después de eliminar noticia")
        
        if self._logging_service:
            self._logging_service.log_operation(
                f"Noticia eliminada: {title or f'ID {news_id}'}",
                {'news_id': news_id}
            )
    
    def _handle_news_get(self, data: Dict[str, Any]) -> None:
        """Coordinar acciones cuando se obtiene una noticia (opcional, para logging)"""
        news_id = data.get('news_id')
        if self._logging_service and news_id:
            self._logging_service.log_operation(
                f"Noticia consultada: ID {news_id}",
                {'news_id': news_id}
            )


class LoggingService(Component):
    """Servicio de logging que actúa como componente del mediador"""
    
    def log_operation(self, message: str, context: Dict[str, Any] = None) -> None:
        """Registrar una operación"""
        context = context or {}
        logger.info(f"[LOGGING] {message} - Contexto: {context}")
    
    def log_error(self, message: str, error: Exception) -> None:
        """Registrar un error"""
        logger.error(f"[LOGGING] {message} - Error: {error}")


class NotificationService(Component):
    """Servicio de notificaciones que actúa como componente del mediador"""
    
    def __init__(self, mediator: Mediator = None):
        super().__init__(mediator)
        self._notifications: List[Dict[str, Any]] = []
    
    def send_notification(self, message: str, type: str = 'info', data: Dict[str, Any] = None) -> None:
        """Enviar una notificación"""
        notification = {
            'message': message,
            'type': type,
            'timestamp': datetime.now().isoformat(),
            'data': data or {}
        }
        self._notifications.append(notification)
        logger.info(f"[NOTIFICATION] {message}")
    
    def get_notifications(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtener notificaciones recientes"""
        return self._notifications[-limit:]


# Singleton para el mediador de noticias
_news_mediator = None

def get_news_mediator(cache_service=None, observer_subject=None) -> NewsServiceMediator:
    """Obtener instancia singleton del mediador de noticias"""
    global _news_mediator
    if _news_mediator is None:
        logging_service = LoggingService()
        notification_service = NotificationService()
        _news_mediator = NewsServiceMediator(
            cache_service=cache_service,
            logging_service=logging_service,
            notification_service=notification_service,
            observer_subject=observer_subject
        )
        # Registrar componentes
        _news_mediator.register_component(logging_service)
        _news_mediator.register_component(notification_service)
    return _news_mediator




class NewsMediator:
	def __init__(self):
		self.cache = {}
		self.logs = []
	def notify(self, ev, data=None):
		if ev in ("create","update","delete"): self.cache.clear()
		self.logs.append(f"{ev}: {data}")

mediator = NewsMediator()

def create_news(n):
	mediator.notify("create", n)
	return "created"

def update_news(n):
	mediator.notify("update", n)
	return "updated"

def delete_news(n):
	mediator.notify("delete", n)
	return "deleted"

def get_news():
	mediator.notify("get")
	return "list"



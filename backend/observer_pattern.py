"""
Patrón Observer - Implementación para notificaciones de eventos del sistema

Este módulo implementa el patrón Observer para notificar a múltiples observadores
sobre cambios en el estado del sistema (creación, actualización, eliminación de noticias).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Callable
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Observer(ABC):
    """Interfaz abstracta para observadores"""
    
    @abstractmethod
    def update(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Método que se llama cuando ocurre un evento
        
        Args:
            event_type: Tipo de evento ('news_created', 'news_updated', 'news_deleted', 'user_logged_in', etc.)
            data: Datos del evento
        """
        pass


class Subject(ABC):
    """Interfaz abstracta para sujetos observables"""
    
    def __init__(self):
        self._observers: List[Observer] = []
    
    def attach(self, observer: Observer) -> None:
        """Agregar un observador"""
        if observer not in self._observers:
            self._observers.append(observer)
            logger.info(f"Observer {type(observer).__name__} agregado")
    
    def detach(self, observer: Observer) -> None:
        """Remover un observador"""
        if observer in self._observers:
            self._observers.remove(observer)
            logger.info(f"Observer {type(observer).__name__} removido")
    
    def notify(self, event_type: str, data: Dict[str, Any]) -> None:
        """Notificar a todos los observadores sobre un evento"""
        logger.info(f"Notificando evento '{event_type}' a {len(self._observers)} observadores")
        for observer in self._observers:
            try:
                observer.update(event_type, data)
            except Exception as e:
                logger.error(f"Error al notificar a {type(observer).__name__}: {e}")


# Implementaciones concretas de Observers

class CacheInvalidationObserver(Observer):
    """Observer que invalida el caché cuando ocurren cambios en noticias"""
    
    def __init__(self, cache_instance):
        self.cache = cache_instance
    
    def update(self, event_type: str, data: Dict[str, Any]) -> None:
        """Invalidar caché cuando se crea, actualiza o elimina una noticia"""
        if event_type in ['news_created', 'news_updated', 'news_deleted']:
            # Invalidar caché de lista de noticias
            self.cache.delete('news_list')
            logger.info(f"Caché invalidado por evento: {event_type}")
            
            # Si hay un ID específico, invalidar también el caché de esa noticia
            if 'news_id' in data:
                self.cache.delete(f"news_{data['news_id']}")


class LoggingObserver(Observer):
    """Observer que registra eventos en el log"""
    
    def update(self, event_type: str, data: Dict[str, Any]) -> None:
        """Registrar evento en el log"""
        logger.info(f"📢 Evento: {event_type} - Datos: {data}")


class NotificationObserver(Observer):
    """Observer que prepara notificaciones para usuarios (puede extenderse para notificaciones push, email, etc.)"""
    
    def __init__(self):
        self.notifications: List[Dict[str, Any]] = []
    
    def update(self, event_type: str, data: Dict[str, Any]) -> None:
        """Preparar notificación según el tipo de evento"""
        notification = {
            'type': event_type,
            'message': self._get_message(event_type, data),
            'timestamp': data.get('timestamp'),
            'data': data
        }
        self.notifications.append(notification)
        logger.info(f"Notificación preparada: {notification['message']}")
    
    def _get_message(self, event_type: str, data: Dict[str, Any]) -> str:
        """Generar mensaje de notificación según el tipo de evento"""
        messages = {
            'news_created': f"Nueva noticia publicada: {data.get('title', 'Sin título')}",
            'news_updated': f"Noticia actualizada: {data.get('title', 'Sin título')}",
            'news_deleted': f"Noticia eliminada: {data.get('title', 'Sin título')}",
            'user_logged_in': f"Usuario {data.get('usuario', 'desconocido')} inició sesión",
            'user_logged_out': f"Usuario {data.get('usuario', 'desconocido')} cerró sesión"
        }
        return messages.get(event_type, f"Evento: {event_type}")
    
    def get_recent_notifications(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtener notificaciones recientes"""
        return self.notifications[-limit:]


class NewsEventSubject(Subject):
    """Sujeto observable para eventos relacionados con noticias"""
    
    def news_created(self, news_data: Dict[str, Any]) -> None:
        """Notificar que se creó una noticia"""
        self.notify('news_created', {
            'news_id': news_data.get('id'),
            'title': news_data.get('titulo'),
            'author': news_data.get('autor'),
            'timestamp': news_data.get('fecha'),
            **news_data
        })
    
    def news_updated(self, news_data: Dict[str, Any]) -> None:
        """Notificar que se actualizó una noticia"""
        self.notify('news_updated', {
            'news_id': news_data.get('id'),
            'title': news_data.get('titulo'),
            'author': news_data.get('autor'),
            'timestamp': news_data.get('fecha'),
            **news_data
        })
    
    def news_deleted(self, news_id: int, title: str = None) -> None:
        """Notificar que se eliminó una noticia"""
        self.notify('news_deleted', {
            'news_id': news_id,
            'title': title or f'Noticia #{news_id}',
            'timestamp': datetime.now().isoformat()
        })


class AuthEventSubject(Subject):
    """Sujeto observable para eventos relacionados con autenticación"""
    
    def user_logged_in(self, user_data: Dict[str, Any]) -> None:
        """Notificar que un usuario inició sesión"""
        self.notify('user_logged_in', {
            'usuario': user_data.get('usuario'),
            'rol': user_data.get('rol'),
            'nombre': user_data.get('nombre'),
            'timestamp': datetime.now().isoformat()
        })
    
    def user_logged_out(self, user_data: Dict[str, Any]) -> None:
        """Notificar que un usuario cerró sesión"""
        self.notify('user_logged_out', {
            'usuario': user_data.get('usuario'),
            'timestamp': datetime.now().isoformat()
        })


# Singleton para el sujeto de eventos de noticias
_news_event_subject = None

def get_news_event_subject() -> NewsEventSubject:
    """Obtener instancia singleton del sujeto de eventos de noticias"""
    global _news_event_subject
    if _news_event_subject is None:
        _news_event_subject = NewsEventSubject()
    return _news_event_subject


# Singleton para el sujeto de eventos de autenticación
_auth_event_subject = None

def get_auth_event_subject() -> AuthEventSubject:
    """Obtener instancia singleton del sujeto de eventos de autenticación"""
    global _auth_event_subject
    if _auth_event_subject is None:
        _auth_event_subject = AuthEventSubject()
    return _auth_event_subject


"""
Factory Pattern mejorado para crear objetos de noticias según su tipo
"""
from datetime import datetime

class Noticia:
    """Clase base para representar una noticia"""
    def __init__(self, titulo, contenido, autor, tipo='general', imagen_url=None):
        self.titulo = titulo
        self.contenido = contenido
        self.autor = autor
        self.tipo = tipo
        self.imagen_url = imagen_url
        self.fecha = datetime.now()
    
    def to_dict(self):
        """Convertir noticia a diccionario para JSON"""
        return {
            'titulo': self.titulo,
            'contenido': self.contenido,
            'autor': self.autor,
            'tipo': self.tipo,
            'imagen_url': self.imagen_url,
            'fecha': self.fecha.strftime("%Y-%m-%d %H:%M:%S")
        }


class NoticiaImportante(Noticia):
    """Noticia importante con características especiales"""
    def __init__(self, titulo, contenido, autor, imagen_url=None):
        super().__init__(titulo, contenido, autor, tipo='importante', imagen_url=imagen_url)
        self.prioridad = 'alta'
        self.requiere_confirmacion = True


class NoticiaEvento(Noticia):
    """Noticia de evento con información adicional"""
    def __init__(self, titulo, contenido, autor, fecha_evento=None, imagen_url=None):
        super().__init__(titulo, contenido, autor, tipo='evento', imagen_url=imagen_url)
        self.fecha_evento = fecha_evento
        self.es_evento = True


class NoticiaAnuncio(Noticia):
    """Anuncio corto y conciso"""
    def __init__(self, titulo, contenido, autor, imagen_url=None):
        super().__init__(titulo, contenido, autor, tipo='anuncio', imagen_url=imagen_url)
        self.es_anuncio = True


class NoticiaFactory:
    """
    Factory Pattern para crear objetos Noticia según su tipo
    
    Este patrón permite:
    - Crear objetos especializados según el tipo de noticia
    - Encapsular la lógica de creación
    - Extensibilidad fácil para nuevos tipos
    - Validación centralizada antes de crear
    
    Usage:
        noticia = NoticiaFactory.crear('importante', titulo, contenido, autor)
    """
    
    @staticmethod
    def crear(tipo, titulo, contenido, autor, imagen_url=None, **kwargs):
        """
        Crear una noticia según su tipo
        
        Args:
            tipo: Tipo de noticia ('general', 'importante', 'evento', 'anuncio')
            titulo: Título de la noticia
            contenido: Contenido de la noticia
            autor: Usuario autor de la noticia
            imagen_url: URL de la imagen (opcional)
            **kwargs: Argumentos adicionales según el tipo
        
        Returns:
            Noticia: Instancia del tipo de noticia apropiado
        """
        tipo = tipo.lower() if tipo else 'general'
        
        if tipo == 'importante':
            return NoticiaImportante(titulo, contenido, autor, imagen_url)
        elif tipo == 'evento':
            fecha_evento = kwargs.get('fecha_evento')
            return NoticiaEvento(titulo, contenido, autor, fecha_evento, imagen_url)
        elif tipo == 'anuncio':
            return NoticiaAnuncio(titulo, contenido, autor, imagen_url)
        else:
            return Noticia(titulo, contenido, autor, tipo='general', imagen_url=imagen_url)
    
    @staticmethod
    def get_available_types():
        """Obtener lista de tipos de noticias disponibles"""
        return ['general', 'importante', 'evento', 'anuncio']

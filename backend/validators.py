"""
Módulo con validadores de noticias usando el patrón Factory
"""
from abc import ABC, abstractmethod
import re

class NoticiaValidator(ABC):
    """Clase abstracta base para validadores de noticias"""
    
    @abstractmethod
    def validate(self, titulo, contenido, autor, imagen_url=None):
        """
        Valida los datos de una noticia
        
        Returns:
            tuple: (es_valido: bool, error: str o None)
        """
        pass
    
    def _validate_basic_fields(self, titulo, contenido, autor):
        """Validación básica común a todos los validadores"""
        if not titulo or not titulo.strip():
            return False, "El título es requerido"
        
        if len(titulo.strip()) < 5:
            return False, "El título debe tener al menos 5 caracteres"
        
        if len(titulo.strip()) > 255:
            return False, "El título no puede exceder 255 caracteres"
        
        if not contenido or not contenido.strip():
            return False, "El contenido es requerido"
        
        if len(contenido.strip()) < 20:
            return False, "El contenido debe tener al menos 20 caracteres"
        
        if not autor or not autor.strip():
            return False, "El autor es requerido"
        
        return True, None


class NoticiaGeneralValidator(NoticiaValidator):
    """Validador para noticias generales (estándar)"""
    
    def validate(self, titulo, contenido, autor, imagen_url=None):
        valido, error = self._validate_basic_fields(titulo, contenido, autor)
        if not valido:
            return valido, error
        
        # Validaciones adicionales para noticias generales
        if len(contenido.strip()) < 50:
            return False, "El contenido de una noticia general debe tener al menos 50 caracteres"
        
        return True, None


class NoticiaImportanteValidator(NoticiaValidator):
    """Validador para noticias importantes (requiere más validación)"""
    
    def validate(self, titulo, contenido, autor, imagen_url=None):
        valido, error = self._validate_basic_fields(titulo, contenido, autor)
        if not valido:
            return valido, error
        
        # Las noticias importantes requieren más contenido
        if len(contenido.strip()) < 100:
            return False, "Las noticias importantes deben tener al menos 100 caracteres de contenido"
        
        # Deben tener una imagen
        if not imagen_url or not imagen_url.strip():
            return False, "Las noticias importantes deben incluir una imagen"
        
        # El título debe indicar importancia
        palabras_importantes = ['importante', 'urgente', 'anuncio', 'aviso', 'notificación']
        titulo_lower = titulo.lower()
        if not any(palabra in titulo_lower for palabra in palabras_importantes):
            return False, "Las noticias importantes deben incluir palabras clave como 'importante', 'urgente', 'anuncio', etc."
        
        return True, None


class NoticiaEventoValidator(NoticiaValidator):
    """Validador para noticias de eventos"""
    
    def validate(self, titulo, contenido, autor, imagen_url=None):
        valido, error = self._validate_basic_fields(titulo, contenido, autor)
        if not valido:
            return valido, error
        
        # Los eventos deben mencionar fecha/hora
        patrones_fecha = [
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # Fechas como 15/12/2024
            r'\d{1,2}\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)',
            r'(lunes|martes|miércoles|jueves|viernes|sábado|domingo)',
            r'\d{1,2}:\d{2}',  # Horas como 14:30
        ]
        
        contenido_completo = f"{titulo} {contenido}".lower()
        tiene_fecha = any(re.search(patron, contenido_completo, re.IGNORECASE) for patron in patrones_fecha)
        
        if not tiene_fecha:
            return False, "Las noticias de eventos deben incluir fecha y/o hora del evento"
        
        # Deben tener una imagen
        if not imagen_url or not imagen_url.strip():
            return False, "Las noticias de eventos deben incluir una imagen"
        
        return True, None


class NoticiaAnuncioValidator(NoticiaValidator):
    """Validador para anuncios cortos"""
    
    def validate(self, titulo, contenido, autor, imagen_url=None):
        valido, error = self._validate_basic_fields(titulo, contenido, autor)
        if not valido:
            return valido, error
        
        # Los anuncios pueden ser más cortos pero deben ser concisos
        if len(contenido.strip()) > 500:
            return False, "Los anuncios deben ser concisos (máximo 500 caracteres)"
        
        return True, None


class NoticiaValidatorFactory:
    """
    Factory Pattern para crear validadores de noticias según el tipo
    
    Este patrón permite:
    - Extensibilidad: Fácil agregar nuevos tipos de validadores
    - Separación de responsabilidades: Cada validador maneja su propia lógica
    - Mantenibilidad: Cambios en un tipo no afectan otros
    """
    
    _validators = {
        'general': NoticiaGeneralValidator,
        'importante': NoticiaImportanteValidator,
        'evento': NoticiaEventoValidator,
        'anuncio': NoticiaAnuncioValidator,
    }
    
    @classmethod
    def create_validator(cls, tipo_noticia='general'):
        """
        Crea un validador según el tipo de noticia
        
        Args:
            tipo_noticia: Tipo de noticia ('general', 'importante', 'evento', 'anuncio')
        
        Returns:
            NoticiaValidator: Instancia del validador apropiado
        """
        validator_class = cls._validators.get(tipo_noticia.lower(), NoticiaGeneralValidator)
        return validator_class()
    
    @classmethod
    def register_validator(cls, tipo_noticia, validator_class):
        """
        Registrar un nuevo tipo de validador (extensibilidad)
        
        Args:
            tipo_noticia: Nombre del tipo de noticia
            validator_class: Clase que hereda de NoticiaValidator
        """
        if not issubclass(validator_class, NoticiaValidator):
            raise ValueError("El validador debe heredar de NoticiaValidator")
        cls._validators[tipo_noticia.lower()] = validator_class
    
    @classmethod
    def get_available_types(cls):
        """Obtener lista de tipos de validadores disponibles"""
        return list(cls._validators.keys())


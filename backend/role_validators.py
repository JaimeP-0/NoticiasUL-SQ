"""
Módulo con validadores según el rol del usuario usando el patrón Factory
"""
from abc import ABC, abstractmethod
from permissions import get_user_role_from_request

class RoleBasedValidator(ABC):
    """Clase abstracta base para validadores basados en rol"""
    
    @abstractmethod
    def can_create_news(self, user_role):
        """Verificar si el rol puede crear noticias"""
        pass
    
    @abstractmethod
    def can_edit_news(self, user_role, news_author, current_user):
        """Verificar si el rol puede editar una noticia específica"""
        pass
    
    @abstractmethod
    def can_delete_news(self, user_role, news_author, current_user):
        """Verificar si el rol puede eliminar una noticia específica"""
        pass
    
    @abstractmethod
    def get_validation_rules(self, user_role):
        """Obtener reglas de validación específicas para el rol"""
        pass


class SuperAdminValidator(RoleBasedValidator):
    """Validador para superadministradores (máximos privilegios)"""
    
    def can_create_news(self, user_role):
        return True
    
    def can_edit_news(self, user_role, news_author, current_user):
        return True  # Puede editar cualquier noticia
    
    def can_delete_news(self, user_role, news_author, current_user):
        return True  # Puede eliminar cualquier noticia
    
    def get_validation_rules(self, user_role):
        return {
            'min_titulo_length': 3,  # Más permisivo
            'min_contenido_length': 10,  # Más permisivo
            'require_image': False,
            'max_titulo_length': 500,  # Más permisivo
        }


class AdminValidator(RoleBasedValidator):
    """Validador para administradores"""
    
    def can_create_news(self, user_role):
        return True
    
    def can_edit_news(self, user_role, news_author, current_user):
        return True  # Puede editar cualquier noticia
    
    def can_delete_news(self, user_role, news_author, current_user):
        return True  # Puede eliminar cualquier noticia
    
    def get_validation_rules(self, user_role):
        return {
            'min_titulo_length': 5,
            'min_contenido_length': 20,
            'require_image': False,
            'max_titulo_length': 255,
        }


class MaestroValidator(RoleBasedValidator):
    """Validador para maestros"""
    
    def can_create_news(self, user_role):
        return True
    
    def can_edit_news(self, user_role, news_author, current_user):
        # Solo puede editar sus propias noticias
        return news_author == current_user
    
    def can_delete_news(self, user_role, news_author, current_user):
        # Solo puede eliminar sus propias noticias
        return news_author == current_user
    
    def get_validation_rules(self, user_role):
        return {
            'min_titulo_length': 5,
            'min_contenido_length': 30,  # Requiere más contenido
            'require_image': False,  # Opcional pero recomendado
            'max_titulo_length': 255,
        }


class UsuarioValidator(RoleBasedValidator):
    """Validador para usuarios regulares (sin permisos de creación)"""
    
    def can_create_news(self, user_role):
        return False
    
    def can_edit_news(self, user_role, news_author, current_user):
        return False
    
    def can_delete_news(self, user_role, news_author, current_user):
        return False
    
    def get_validation_rules(self, user_role):
        return {
            'min_titulo_length': 5,
            'min_contenido_length': 20,
            'require_image': False,
            'max_titulo_length': 255,
        }


class RoleValidatorFactory:
    """
    Factory Pattern para crear validadores según el rol del usuario
    
    Este patrón permite:
    - Centralizar la lógica de permisos por rol
    - Fácil extensión para nuevos roles
    - Separación clara de reglas de negocio por rol
    - Testing más fácil (mock de validadores)
    """
    
    _validators = {
        'superadmin': SuperAdminValidator,
        'admin': AdminValidator,
        'maestro': MaestroValidator,
        'usuario': UsuarioValidator,
    }
    
    @classmethod
    def create_validator(cls, user_role=None):
        """
        Crea un validador según el rol del usuario
        
        Args:
            user_role: Rol del usuario. Si es None, se obtiene del request actual
        
        Returns:
            RoleBasedValidator: Instancia del validador apropiado
        """
        if user_role is None:
            user_role = get_user_role_from_request()
        
        validator_class = cls._validators.get(user_role.lower(), UsuarioValidator)
        return validator_class()
    
    @classmethod
    def register_validator(cls, role, validator_class):
        """
        Registrar un nuevo validador de rol (extensibilidad)
        
        Args:
            role: Nombre del rol
            validator_class: Clase que hereda de RoleBasedValidator
        """
        if not issubclass(validator_class, RoleBasedValidator):
            raise ValueError("El validador debe heredar de RoleBasedValidator")
        cls._validators[role.lower()] = validator_class
    
    @classmethod
    def get_available_roles(cls):
        """Obtener lista de roles con validadores disponibles"""
        return list(cls._validators.keys())


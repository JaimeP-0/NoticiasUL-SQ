/**
 * NewsModel - Modelo MVVM para Noticias
 * Maneja la comunicación con la API del backend
 * 
 * Responsabilidades:
 * - Obtener noticias desde el servidor
 * - Crear nuevas noticias
 * - Actualizar noticias existentes
 * - Eliminar noticias
 * - Obtener una noticia individual
 * - Obtener categorías
 */
class NewsModel {
    constructor() {
        this.baseUrl = '/api';
    }

    /**
     * Obtener lista de noticias con filtros y paginación
     * @param {Object} params - Parámetros de búsqueda
     * @param {number} params.limit - Número de noticias por página
     * @param {number} params.offset - Desplazamiento para paginación
     * @param {string} params.search - Término de búsqueda
     * @param {number|null} params.categoria - ID de categoría para filtrar
     * @returns {Promise<Array>} Lista de noticias
     */
    async getNews(params = {}) {
        try {
            const { limit = 15, offset = 0, search = '', categoria = null } = params;
            
            let url = `${this.baseUrl}/news?limit=${limit}&offset=${offset}`;
            
            if (search) {
                url += `&search=${encodeURIComponent(search)}`;
            }
            
            if (categoria !== null) {
                url += `&categoria=${categoria}`;
            }

            const response = await fetch(url, {
                credentials: 'include'
            });

            if (!response.ok) {
                throw new Error(`Error al obtener noticias: ${response.status}`);
            }

            const news = await response.json();
            return Array.isArray(news) ? news : [];
        } catch (error) {
            console.error('[NewsModel] Error al obtener noticias:', error);
            throw error;
        }
    }

    /**
     * Obtener una noticia individual por ID
     * @param {number} newsId - ID de la noticia
     * @returns {Promise<Object>} Noticia
     */
    async getNewsById(newsId) {
        try {
            const response = await fetch(`${this.baseUrl}/news/${newsId}`, {
                credentials: 'include'
            });

            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('Noticia no encontrada');
                }
                throw new Error(`Error al obtener noticia: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('[NewsModel] Error al obtener noticia:', error);
            throw error;
        }
    }

    /**
     * Crear una nueva noticia
     * @param {Object} newsData - Datos de la noticia
     * @param {string} newsData.titulo - Título de la noticia
     * @param {string} newsData.contenido - Contenido de la noticia
     * @param {string} newsData.autor - Autor de la noticia
     * @param {string} newsData.imagen - URL de la imagen (opcional)
     * @param {Array<number>} newsData.categorias - IDs de categorías (opcional)
     * @returns {Promise<Object>} Noticia creada
     */
    async createNews(newsData) {
        try {
            const response = await fetch(`${this.baseUrl}/news`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(newsData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Error al crear noticia');
            }

            const responseData = await response.json();
            return responseData.noticia || responseData;
        } catch (error) {
            console.error('[NewsModel] Error al crear noticia:', error);
            throw error;
        }
    }

    /**
     * Actualizar una noticia existente
     * @param {number} newsId - ID de la noticia
     * @param {Object} newsData - Datos actualizados
     * @returns {Promise<Object>} Noticia actualizada
     */
    async updateNews(newsId, newsData) {
        try {
            const response = await fetch(`${this.baseUrl}/news/${newsId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(newsData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Error al actualizar noticia');
            }

            const responseData = await response.json();
            return responseData.noticia || responseData;
        } catch (error) {
            console.error('[NewsModel] Error al actualizar noticia:', error);
            throw error;
        }
    }

    /**
     * Eliminar una noticia
     * @param {number} newsId - ID de la noticia
     * @returns {Promise<void>}
     */
    async deleteNews(newsId) {
        try {
            const response = await fetch(`${this.baseUrl}/news/${newsId}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include'
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Error al eliminar noticia');
            }
        } catch (error) {
            console.error('[NewsModel] Error al eliminar noticia:', error);
            throw error;
        }
    }

    /**
     * Obtener todas las categorías disponibles
     * @returns {Promise<Array>} Lista de categorías
     */
    async getCategories() {
        try {
            const response = await fetch(`${this.baseUrl}/categories`, {
                credentials: 'include'
            });

            if (!response.ok) {
                throw new Error(`Error al obtener categorías: ${response.status}`);
            }

            const categories = await response.json();
            return Array.isArray(categories) ? categories : [];
        } catch (error) {
            console.error('[NewsModel] Error al obtener categorías:', error);
            throw error;
        }
    }

    /**
     * Subir una imagen
     * @param {File} imageFile - Archivo de imagen
     * @returns {Promise<string>} URL de la imagen subida
     */
    async uploadImage(imageFile) {
        try {
            const formData = new FormData();
            formData.append('imagen', imageFile);

            const response = await fetch(`${this.baseUrl}/upload`, {
                method: 'POST',
                credentials: 'include',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Error al subir la imagen');
            }

            const uploadData = await response.json();
            return uploadData.url || '';
        } catch (error) {
            console.error('[NewsModel] Error al subir imagen:', error);
            throw error;
        }
    }
}

// Exportar para uso global
if (typeof window !== 'undefined') {
    window.NewsModel = NewsModel;
}

// Exportar para módulos ES6
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NewsModel;
}


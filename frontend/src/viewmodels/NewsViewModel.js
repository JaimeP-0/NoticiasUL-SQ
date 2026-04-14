/**
 * NewsViewModel - ViewModel MVVM para Noticias
 * Maneja el estado y la lógica de presentación
 * 
 * Responsabilidades:
 * - Gestionar el estado de las noticias (lista, filtros, paginación)
 * - Procesar y transformar datos del Model para la View
 * - Manejar eventos de usuario (búsqueda, filtros, paginación)
 * - Notificar cambios a la View mediante callbacks
 * - Validar datos antes de enviarlos al Model
 */
class NewsViewModel {
    constructor(newsModel) {
        this.model = newsModel;
        
        // Estado del ViewModel
        this.state = {
            news: [],
            categories: [],
            loading: false,
            error: null,
            
            // Filtros y búsqueda
            searchTerm: '',
            selectedCategory: null,
            
            // Paginación
            currentPage: 0,
            pageSize: 15,
            hasMore: false,
            
            // Noticia individual
            currentNews: null
        };
        
        // Callbacks para notificar cambios a la View
        this.callbacks = {
            onNewsChanged: null,
            onLoadingChanged: null,
            onErrorChanged: null,
            onCategoriesChanged: null,
            onCurrentNewsChanged: null
        };
    }

    /**
     * Registrar callback para cambios en las noticias
     */
    onNewsChanged(callback) {
        this.callbacks.onNewsChanged = callback;
    }

    /**
     * Registrar callback para cambios en el estado de carga
     */
    onLoadingChanged(callback) {
        this.callbacks.onLoadingChanged = callback;
    }

    /**
     * Registrar callback para errores
     */
    onErrorChanged(callback) {
        this.callbacks.onErrorChanged = callback;
    }

    /**
     * Registrar callback para cambios en categorías
     */
    onCategoriesChanged(callback) {
        this.callbacks.onCategoriesChanged = callback;
    }

    /**
     * Registrar callback para cambios en noticia individual
     */
    onCurrentNewsChanged(callback) {
        this.callbacks.onCurrentNewsChanged = callback;
    }

    /**
     * Notificar cambios a los callbacks registrados
     */
    notify(callbackName, data) {
        if (this.callbacks[callbackName]) {
            this.callbacks[callbackName](data);
        }
    }

    /**
     * Actualizar estado y notificar cambios
     */
    setState(updates) {
        this.state = { ...this.state, ...updates };
        
        // Notificar cambios específicos
        if (updates.news !== undefined) {
            this.notify('onNewsChanged', this.state.news);
        }
        if (updates.loading !== undefined) {
            this.notify('onLoadingChanged', this.state.loading);
        }
        if (updates.error !== undefined) {
            this.notify('onErrorChanged', this.state.error);
        }
        if (updates.categories !== undefined) {
            this.notify('onCategoriesChanged', this.state.categories);
        }
        if (updates.currentNews !== undefined) {
            this.notify('onCurrentNewsChanged', this.state.currentNews);
        }
    }

    /**
     * Cargar noticias desde el modelo
     */
    async loadNews() {
        this.setState({ loading: true, error: null });

        try {
            const params = {
                limit: this.state.pageSize,
                offset: this.state.currentPage * this.state.pageSize,
                search: this.state.searchTerm,
                categoria: this.state.selectedCategory
            };

            const news = await this.model.getNews(params);
            
            // Determinar si hay más noticias
            const hasMore = news.length === this.state.pageSize;

            this.setState({
                news: news,
                loading: false,
                hasMore: hasMore,
                error: null
            });
        } catch (error) {
            this.setState({
                loading: false,
                error: error.message || 'Error al cargar noticias'
            });
        }
    }

    /**
     * Cargar categorías desde el modelo
     */
    async loadCategories() {
        try {
            const categories = await this.model.getCategories();
            this.setState({ categories: categories });
        } catch (error) {
            console.error('[NewsViewModel] Error al cargar categorías:', error);
            this.setState({ categories: [] });
        }
    }

    /**
     * Establecer término de búsqueda
     */
    setSearchTerm(searchTerm) {
        this.setState({
            searchTerm: searchTerm,
            currentPage: 0 // Resetear a primera página
        });
        this.loadNews();
    }

    /**
     * Establecer categoría seleccionada
     */
    setSelectedCategory(categoryId) {
        this.setState({
            selectedCategory: categoryId,
            currentPage: 0 // Resetear a primera página
        });
        this.loadNews();
    }

    /**
     * Ir a la página siguiente
     */
    nextPage() {
        if (this.state.hasMore) {
            this.setState({ currentPage: this.state.currentPage + 1 });
            this.loadNews();
        }
    }

    /**
     * Ir a la página anterior
     */
    previousPage() {
        if (this.state.currentPage > 0) {
            this.setState({ currentPage: this.state.currentPage - 1 });
            this.loadNews();
        }
    }

    /**
     * Ir a una página específica
     */
    goToPage(page) {
        if (page >= 0) {
            this.setState({ currentPage: page });
            this.loadNews();
        }
    }

    /**
     * Cargar una noticia individual
     */
    async loadNewsById(newsId) {
        this.setState({ loading: true, error: null, currentNews: null });

        try {
            const news = await this.model.getNewsById(newsId);
            this.setState({
                currentNews: news,
                loading: false,
                error: null
            });
        } catch (error) {
            this.setState({
                loading: false,
                error: error.message || 'Error al cargar noticia',
                currentNews: null
            });
        }
    }

    /**
     * Crear una nueva noticia
     */
    async createNews(newsData) {
        // Validar datos antes de enviar
        if (!this.validateNewsData(newsData)) {
            throw new Error('Datos de noticia inválidos');
        }

        this.setState({ loading: true, error: null });

        try {
            // Si hay imagen, subirla primero
            let imageUrl = newsData.imagen || '';
            if (newsData.imageFile) {
                imageUrl = await this.model.uploadImage(newsData.imageFile);
            }

            const newsToCreate = {
                titulo: newsData.titulo,
                contenido: newsData.contenido,
                autor: newsData.autor,
                imagen: imageUrl,
                categorias: newsData.categorias || []
            };

            const createdNews = await this.model.createNews(newsToCreate);
            
            this.setState({ loading: false });
            
            // Recargar lista de noticias
            this.loadNews();
            
            return createdNews;
        } catch (error) {
            this.setState({
                loading: false,
                error: error.message || 'Error al crear noticia'
            });
            throw error;
        }
    }

    /**
     * Actualizar una noticia existente
     */
    async updateNews(newsId, newsData) {
        // Validar datos antes de enviar
        if (!this.validateNewsData(newsData)) {
            throw new Error('Datos de noticia inválidos');
        }

        this.setState({ loading: true, error: null });

        try {
            // Si hay nueva imagen, subirla primero
            let imageUrl = newsData.imagen;
            if (newsData.imageFile) {
                imageUrl = await this.model.uploadImage(newsData.imageFile);
            }

            const newsToUpdate = {
                titulo: newsData.titulo,
                contenido: newsData.contenido,
                categorias: newsData.categorias || []
            };

            if (imageUrl !== undefined) {
                newsToUpdate.imagen = imageUrl;
            }

            const updatedNews = await this.model.updateNews(newsId, newsToUpdate);
            
            this.setState({ loading: false });
            
            // Actualizar noticia actual si es la misma
            if (this.state.currentNews && this.state.currentNews.id === newsId) {
                this.setState({ currentNews: updatedNews });
            }
            
            // Recargar lista de noticias
            this.loadNews();
            
            return updatedNews;
        } catch (error) {
            this.setState({
                loading: false,
                error: error.message || 'Error al actualizar noticia'
            });
            throw error;
        }
    }

    /**
     * Eliminar una noticia
     */
    async deleteNews(newsId) {
        this.setState({ loading: true, error: null });

        try {
            await this.model.deleteNews(newsId);
            this.setState({ loading: false });
            
            // Si es la noticia actual, limpiarla
            if (this.state.currentNews && this.state.currentNews.id === newsId) {
                this.setState({ currentNews: null });
            }
            
            // Recargar lista de noticias
            this.loadNews();
        } catch (error) {
            this.setState({
                loading: false,
                error: error.message || 'Error al eliminar noticia'
            });
            throw error;
        }
    }

    validateNewsData(newsData) {
        if (!newsData.titulo || newsData.titulo.trim().length === 0) {
            return false;
        }
        
        if (!newsData.contenido || newsData.contenido.trim().length < 50) {
            return false;
        }
        
        return true;
    }

    formatDate(dateString) {
        if (!dateString) {
            return 'Fecha no disponible';
        }
        try {
            const date = new Date(dateString);
            // Verificar si la fecha es válida
            if (Number.isNaN(date.getTime())) {
                return 'Fecha no disponible';
            }
            return date.toLocaleDateString('es-ES', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
        } catch (e) {
            console.error('Error al formatear fecha:', e, dateString);
            return 'Fecha no disponible';
        }
    }

    /**
     * Formatear fecha con hora
     */
    formatDateTime(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('es-ES', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    /**
     * Generar slug a partir de un texto
     */
    generateSlug(text) {
        if (!text) return '';
        let s = text.toString().toLowerCase().trim();
        s = s.replaceAll(/\s/g, '-');
        s = s.normalize('NFD');
        s = s.replaceAll(/[\u0300-\u036f]/g, '');
        s = s.replaceAll(/[^a-z0-9-]/g, '');
        s = s.split('-').filter(Boolean).join('-');
        if (s.length > 100) {
            s = s.slice(0, 100);
        }
        while (s.endsWith('-')) {
            s = s.slice(0, -1);
        }
        return s;
    }

    /**
     * Obtener estado actual (para debugging o acceso externo)
     */
    getState() {
        return { ...this.state };
    }

    /**
     * Resetear estado a valores iniciales
     */
    reset() {
        this.setState({
            news: [],
            currentNews: null,
            searchTerm: '',
            selectedCategory: null,
            currentPage: 0,
            error: null
        });
    }
}

// Exportar para uso global
if (globalThis.window !== undefined) {
    globalThis.NewsViewModel = NewsViewModel;
}

// Exportar para módulos ES6
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NewsViewModel;
}


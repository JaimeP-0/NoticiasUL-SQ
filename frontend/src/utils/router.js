/**
 * Router del lado del cliente para SPA (Single Page Application)
 * Maneja las rutas sin recargar la página usando History API
 */
class Router {
	constructor() {
		this.routes = new Map();
		this.currentRoute = null;
		this.beforeRouteChange = null;
		this.afterRouteChange = null;
		this.initialized = false;
	}

	/**
	 * Inicializar el router
	 */
	init() {
		if (this.initialized) return;
		this.initialized = true;

		// Escuchar cambios en el historial del navegador
		window.addEventListener('popstate', (e) => {
			this.handleRoute(window.location.pathname);
		});

		// Manejar clics en links (usar delegación de eventos)
		document.addEventListener('click', (e) => {
			const link = e.target.closest('a[data-router]');
			if (link) {
				e.preventDefault();
				const href = link.getAttribute('href');
				this.navigate(href);
			}
		});
	}

	/**
	 * Registrar una ruta
	 * @param {string} path - Ruta a registrar
	 * @param {Function} handler - Función que maneja la ruta
	 */
	route(path, handler) {
		this.routes.set(path, handler);
	}

	/**
	 * Navegar a una ruta
	 * @param {string} path - Ruta a navegar
	 */
	navigate(path) {
		if (this.beforeRouteChange) {
			this.beforeRouteChange(path);
		}

		// Actualizar la URL sin recargar la página
		window.history.pushState({}, '', path);
		this.handleRoute(path);

		if (this.afterRouteChange) {
			this.afterRouteChange(path);
		}
	}

	/**
	 * Manejar una ruta
	 * @param {string} path - Ruta a manejar
	 */
	handleRoute(path) {
		// Limpiar la ruta (eliminar query params y hash)
		const cleanPath = path.split('?')[0].split('#')[0];

		// Buscar ruta exacta
		if (this.routes.has(cleanPath)) {
			this.currentRoute = cleanPath;
			const handler = this.routes.get(cleanPath);
			handler();
			this.updateActiveLink(cleanPath);
			return;
		}

		// Buscar rutas con parámetros dinámicos
		for (const [routePath, handler] of this.routes.entries()) {
			const params = this.matchRoute(routePath, cleanPath);
			if (params !== null) {
				this.currentRoute = cleanPath;
				handler(params);
				this.updateActiveLink(cleanPath);
				return;
			}
		}

		// Ruta no encontrada - redirigir a home
		if (cleanPath !== '/') {
			this.navigate('/');
		}
	}

	/**
	 * Comparar una ruta con un patrón
	 * @param {string} pattern - Patrón de ruta (ej: /noticia/:id)
	 * @param {string} path - Ruta actual
	 * @returns {Object|null} - Parámetros o null si no coincide
	 */
	matchRoute(pattern, path) {
		const patternParts = pattern.split('/');
		const pathParts = path.split('/');

		if (patternParts.length !== pathParts.length) {
			return null;
		}

		const params = {};
		for (let i = 0; i < patternParts.length; i++) {
			const patternPart = patternParts[i];
			const pathPart = pathParts[i];

			if (patternPart.startsWith(':')) {
				// Es un parámetro
				const paramName = patternPart.slice(1);
				params[paramName] = pathPart;
			} else if (patternPart !== pathPart) {
				// No coincide
				return null;
			}
		}

		return params;
	}

	/**
	 * Actualizar el link activo en la navegación
	 * @param {string} path - Ruta actual
	 */
	updateActiveLink(path) {
		// Remover clase activa de todos los links
		document.querySelectorAll('.nav-link').forEach(link => {
			link.classList.remove('border-blue-600', 'dark:border-blue-400', 'text-blue-600', 'dark:text-blue-400');
			link.classList.add('border-transparent');
		});

		// Agregar clase activa al link correspondiente
		const activeLink = document.querySelector(`a[data-router][href="${path}"]`);
		if (activeLink) {
			activeLink.classList.add('border-blue-600', 'dark:border-blue-400', 'text-blue-600', 'dark:text-blue-400');
			activeLink.classList.remove('border-transparent');
		}
	}

	/**
	 * Obtener parámetros de la URL actual
	 * @returns {Object} - Parámetros de la URL
	 */
	getQueryParams() {
		const params = new URLSearchParams(window.location.search);
		const result = {};
		for (const [key, value] of params.entries()) {
			result[key] = value;
		}
		return result;
	}

	/**
	 * Obtener el hash de la URL
	 * @returns {string} - Hash de la URL
	 */
	getHash() {
		return window.location.hash.slice(1);
	}
}

// Instancia global del router
if (typeof window !== 'undefined') {
	window.router = new Router();
	
	// Inicializar cuando el DOM esté listo
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', () => {
			window.router.init();
		});
	} else {
		window.router.init();
	}
}


/**
 * Aplicación principal SPA (Single Page Application)
 * Maneja el enrutamiento y la carga de vistas dinámicamente
 */

// Contenedor principal donde se renderizan las vistas
let currentView = null;
let appContainer = null;

/** Slug URL (implementación en utils/newsShared.js → buildNewsSlug). */
function generarSlug(texto) {
	return globalThis.buildNewsSlug(texto);
}

async function obtenerUsuarioActualDesdeApi() {
	try {
		const res = await fetch('/api/auth/me', { credentials: 'include' });
		if (!res.ok) return null;
		const data = await res.json();
		if (!data.authenticated) return null;
		return { usuario: data.usuario, rol: data.rol || 'usuario' };
	} catch (err) {
		console.debug('[auth] No se pudo leer sesión (/api/auth/me):', err instanceof Error ? err.name : 'error');
		return null;
	}
}

async function obtenerNombreUsuarioSesion() {
	const info = await obtenerUsuarioActualDesdeApi();
	return info?.usuario ?? null;
}

/** Admin/superadmin pueden eliminar noticias (ámbito módulo; evita función async anidada repetida). */
async function usuarioPuedeEliminarNoticia() {
	const userInfo = await obtenerUsuarioActualDesdeApi();
	if (!userInfo) return false;
	const role = userInfo.rol;
	return role === 'admin' || role === 'superadmin';
}

function getRoleBadgeClass(rol) {
	const classes = {
		superadmin: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
		admin: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
		maestro: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
		usuario: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200',
	};
	return classes[rol] || classes.usuario;
}

function getRoleLabel(rol) {
	const labels = {
		superadmin: 'Super Admin',
		admin: 'Admin',
		maestro: 'Maestro',
		usuario: 'Usuario',
	};
	return labels[rol] || rol;
}

/**
 * Inicializar la aplicación SPA
 */
function initApp() {
	appContainer = document.getElementById('app-container');
	if (!appContainer) {
		console.error('No se encontró el contenedor de la aplicación');
		return;
	}

	// Asegurar que el router esté inicializado
	if (globalThis.router) {
		if (!globalThis.router.initialized) {
			globalThis.router.init();
		}
		setupRoutes();
	} else {
		console.error('Router no está disponible');
	}
}

/**
 * Configurar rutas
 */
function setupRoutes() {
	const router = globalThis.router;

	// Ruta home - redirige a noticias
	router.route('/', () => {
		router.navigate('/noticias');
	});

	// Ruta noticias
	router.route('/noticias', () => {
		loadNoticiasView();
	});

	// Ruta noticia individual (con slug opcional)
	router.route('/noticia/:id', (params) => {
		loadNoticiaView(params.id);
	});

	// Ruta noticia con slug
	router.route('/noticia/:id/:slug', (params) => {
		loadNoticiaView(params.id);
	});

	// Ruta patrones de diseño
	router.route('/patrones', () => {
		loadPatronesView();
	});

	// Ruta admin
	router.route('/admin', () => {
		loadAdminView();
	});

	// Ruta agregar
	router.route('/agregar', () => {
		loadAgregarView();
	});

	// Ruta debug
	router.route('/debug', () => {
		loadDebugView();
	});

	// Ruta login
	router.route('/login', () => {
		loadLoginView();
	});

	// Ruta registro
	router.route('/registro', () => {
		loadRegistroView();
	});

	// No manejar la ruta inicial aquí, se manejará después de registrar todas las rutas
	setTimeout(() => {
		const currentPath = globalThis.location.pathname;
		if (currentPath === '/') {
			router.navigate('/noticias');
		} else {
			router.handleRoute(currentPath);
		}
	}, 0);
}

/**
 * Cargar vista de noticias
 */
async function loadNoticiasView() {
	if (!appContainer) return;

	appContainer.innerHTML = `
		<section class="mb-12">
			<h2 class="text-3xl font-bold text-gray-900 dark:text-white mb-6">Últimas Noticias</h2>
			
			<!-- Barra de búsqueda -->
			<div class="mb-6">
				<div class="relative">
					<input
						type="text"
						id="busqueda-noticias"
						placeholder="Buscar noticias por título, autor o contenido..."
						class="w-full px-4 py-3 pl-12 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
					/>
					<i class="bi bi-search absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-gray-500 text-lg"></i>
					<button
						id="limpiar-busqueda"
						class="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hidden"
						title="Limpiar búsqueda"
					>
						<i class="bi bi-x-circle text-xl"></i>
					</button>
				</div>
				<div id="resultados-busqueda" class="mt-2 text-sm text-gray-600 dark:text-gray-400 hidden"></div>
			</div>

			<!-- Filtros de categorías -->
			<div id="filtros-categorias" class="mb-6"></div>

			<div id="contenedor-noticias" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
				<p class="text-gray-600 dark:text-gray-400 col-span-full">Cargando noticias...</p>
			</div>

			<!-- Controles de paginación -->
			<div id="paginacion" class="mt-6"></div>
		</section>
	`;

	// Cargar noticias
	await initNoticiasView();
}

/**
 * Inicializar vista de noticias usando MVVM
 */
let newsViewModel = null;

async function initNoticiasView() {
	// Inicializar MVVM: Model y ViewModel
	if (!globalThis.NewsModel || !globalThis.NewsViewModel) {
		console.error('[MVVM] NewsModel o NewsViewModel no están disponibles');
		return;
	}

	// Si el ViewModel ya existe, solo recargar noticias
	if (newsViewModel) {
		await newsViewModel.loadNews();
		return;
	}

	// Crear nuevo ViewModel solo si no existe
	const newsModel = new globalThis.NewsModel();
	newsViewModel = new globalThis.NewsViewModel(newsModel);

	// Configurar callbacks del ViewModel para actualizar la View
	newsViewModel.onNewsChanged((news) => {
		renderNews(news);
	});

	newsViewModel.onLoadingChanged((loading) => {
		const container = document.getElementById('contenedor-noticias');
		if (container && loading) {
			container.innerHTML = '<p class="text-gray-600 dark:text-gray-400 col-span-full text-center py-8">Cargando noticias...</p>';
		}
	});

	newsViewModel.onErrorChanged((error) => {
		if (error) {
			const container = document.getElementById('contenedor-noticias');
			if (container) {
				container.innerHTML = `<p class="text-red-600 dark:text-red-400 col-span-full text-center py-8">${escapeHTML(error)}</p>`;
			}
		}
	});

	newsViewModel.onCategoriesChanged((categories) => {
		renderCategories(categories);
	});

	// Inicializar Observer Pattern para sincronización de UI (solo una vez)
	if (!globalThis._observersInitialized && globalThis.NewsObserver?.getNewsEventSubject) {
		const newsSubject = globalThis.NewsObserver.getNewsEventSubject();
		
		// Observer para recargar la lista cuando cambian las noticias
		const newsListObserver = new globalThis.NewsObserver.NewsListObserver(() => {
			if (newsViewModel) {
				newsViewModel.loadNews();
			}
		});
		
		// Observer para mostrar notificaciones
		const notificationObserver = new globalThis.NewsObserver.NotificationObserver();
		
		// Observer para sincronización entre pestañas (solo uno global)
		if (!globalThis._tabSyncObserver) {
			globalThis._tabSyncObserver = new globalThis.NewsObserver.TabSyncObserver();
		}
		
		// Registrar observadores (solo si no están ya registrados)
		if (!globalThis._newsListObserverAttached) {
			newsSubject.attach(newsListObserver);
			globalThis._newsListObserverAttached = true;
		}
		if (!globalThis._notificationObserverAttached) {
			newsSubject.attach(notificationObserver);
			globalThis._notificationObserverAttached = true;
		}
		if (!globalThis._tabSyncObserverAttached) {
			newsSubject.attach(globalThis._tabSyncObserver);
			globalThis._tabSyncObserverAttached = true;
		}
		
		globalThis._observersInitialized = true;
	}
	
	// Cargar categorías usando el ViewModel
	await newsViewModel.loadCategories();
	
	// Recargar noticias para asegurar que se muestren las más recientes
	await newsViewModel.loadNews();

	// Configurar búsqueda
	const searchInput = document.getElementById('busqueda-noticias');
	const clearBtn = document.getElementById('limpiar-busqueda');

	if (searchInput) {
		let searchTimeout;
		searchInput.addEventListener('input', (e) => {
			clearTimeout(searchTimeout);
			searchTimeout = setTimeout(() => {
				const searchTerm = e.target.value.trim();
				if (newsViewModel) {
					newsViewModel.setSearchTerm(searchTerm);
					updateSearchUI(searchTerm);
				}
			}, 200);
		});
	}

	if (clearBtn) {
		clearBtn.addEventListener('click', () => {
			if (searchInput) {
				searchInput.value = '';
			}
			if (newsViewModel) {
				newsViewModel.setSearchTerm('');
				updateSearchUI('');
			}
		});
	}

	// Cargar noticias usando el ViewModel
	await newsViewModel.loadNews();
	
	// No verificar autenticación aquí, ya se hace en Layout.astro
	// Esto evita verificaciones duplicadas
	
	// Inicializar Pusher para notificaciones en tiempo real
	initPusher();
}

/**
 * Inicializar Pusher para recibir notificaciones en tiempo real (solo una vez)
 */
async function initPusher() {
	// Evitar múltiples inicializaciones
	if (globalThis._pusherInitialized) {
		return;
	}
	
	try {
		// Obtener configuración de Pusher desde el backend
		const response = await fetch('/api/pusher-config', {
			credentials: 'include'
		});
		
		if (!response.ok) {
			return;
		}
		
		const config = await response.json();
		
		if (!config.enabled || !globalThis.Pusher) {
			return;
		}
		
		// Inicializar Pusher
		const pusher = new globalThis.Pusher(config.key, {
			cluster: config.cluster,
			encrypted: true
		});
		
		// Suscribirse al canal de noticias
		const channel = pusher.subscribe('noticias');
		
		// Escuchar eventos de noticias creadas
		channel.bind('noticia-creada', (data) => {
			if (newsViewModel) {
				newsViewModel.loadNews();
			}
		});
		
		// Escuchar eventos de noticias actualizadas
		channel.bind('noticia-actualizada', (data) => {
			if (newsViewModel) {
				newsViewModel.loadNews();
			}
		});
		
		// Escuchar eventos de noticias eliminadas
		channel.bind('noticia-eliminada', (data) => {
			if (newsViewModel) {
				newsViewModel.loadNews();
			}
		});
		
		globalThis._pusherInitialized = true;
	} catch (error) {
		console.error('[PUSHER] Error al inicializar Pusher:', error);
	}
}

function updateSearchUI(searchTerm) {
	const clearBtn = document.getElementById('limpiar-busqueda');
	const resultsDiv = document.getElementById('resultados-busqueda');

	if (searchTerm) {
		clearBtn?.classList.remove('hidden');
		if (resultsDiv) {
			resultsDiv.textContent = `Buscando: "${searchTerm}"`;
			resultsDiv.classList.remove('hidden');
		}
	} else {
		clearBtn?.classList.add('hidden');
		resultsDiv?.classList.add('hidden');
	}
}

function renderCategories(categories) {
	const container = document.getElementById('filtros-categorias');
	if (!container || !newsViewModel) return;

	const state = newsViewModel.getState();
	const selectedCategory = state.selectedCategory;

	let html = '<div class="flex flex-wrap gap-2">';
	html += `<button class="category-filter px-4 py-2 rounded-full border-2 ${
		selectedCategory === null 
			? 'border-blue-600 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300' 
			: 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300'
	} hover:border-blue-500 transition-colors" data-category="null">Todas</button>`;

	if (categories && categories.length > 0) {
		categories.forEach(cat => {
			html += `<button class="category-filter px-4 py-2 rounded-full border-2 ${
				selectedCategory === cat.id
					? 'border-blue-600 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
					: 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300'
			} hover:border-blue-500 transition-colors" data-category="${cat.id}" style="border-color: ${cat.color};">${escapeHTML(cat.nombre)}</button>`;
		});
	}

	html += '</div>';
	container.innerHTML = html;

	// Event listeners
	container.querySelectorAll('.category-filter').forEach(btn => {
		btn.addEventListener('click', (e) => {
			const catId = e.target.dataset.category;
			const categoryId = catId === 'null' ? null : Number.parseInt(catId, 10);
			if (newsViewModel) {
				newsViewModel.setSelectedCategory(categoryId);
			}
		});
	});
}

function renderNews(news) {
	const container = document.getElementById('contenedor-noticias');
	if (!container || !newsViewModel) return;

	if (!news || news.length === 0) {
		container.innerHTML = '<p class="text-gray-600 dark:text-gray-400 col-span-full text-center py-8">No se encontraron noticias.</p>';
		renderPagination();
		return;
	}

	// Usar el ViewModel para formatear fechas
	container.innerHTML = news.map(noticia => {
		const fecha = newsViewModel.formatDate(noticia.fecha);

		const categoriasHTML = noticia.categorias && noticia.categorias.length > 0
			? noticia.categorias.map(cat => `
				<span class="px-2 py-1 text-xs rounded-full text-white font-medium" style="background-color: ${cat.color};">
					${escapeHTML(cat.nombre)}
				</span>
			`).join('')
			: '';

		return `
			<article class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden hover:shadow-lg transition-shadow cursor-pointer news-card" data-news-id="${noticia.id}">
				${noticia.imagen ? `
					<img src="${noticia.imagen}" alt="${escapeHTML(noticia.titulo)}" class="w-full h-48 object-cover" />
				` : `
					<div class="w-full h-48 bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center">
						<i class="bi bi-newspaper text-white text-6xl"></i>
					</div>
				`}
				<div class="p-4">
					<h3 class="text-xl font-bold text-gray-900 dark:text-white mb-2 line-clamp-2">
						${escapeHTML(noticia.titulo)}
					</h3>
					<p class="text-gray-600 dark:text-gray-400 text-sm mb-4 line-clamp-3">
						${escapeHTML(noticia.contenido)}
					</p>
					${categoriasHTML ? `<div class="flex flex-wrap gap-2 mb-4">${categoriasHTML}</div>` : ''}
					<div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400">
						<span>${escapeHTML(noticia.nombre_autor || noticia.autor)}</span>
						<span>${fecha}</span>
					</div>
				</div>
			</article>
		`;
	}).join('');

	// Hacer las tarjetas clickeables
	container.querySelectorAll('.news-card').forEach(card => {
		card.addEventListener('click', (e) => {
			if (e.target.closest('button') || e.target.closest('.dropdown')) return;
			const newsId = card.dataset.newsId;
			if (globalThis.router) {
				globalThis.router.navigate(`/noticia/${newsId}`);
			}
		});
	});

	// Renderizar paginación
	renderPagination();
}

function renderPagination() {
	const container = document.getElementById('paginacion');
	if (!container || !newsViewModel) return;

	const state = newsViewModel.getState();
	const currentPage = state.currentPage;
	const hasMore = state.hasMore;

	if (!hasMore && currentPage === 0) {
		container.innerHTML = '';
		return;
	}

	const prevDisabled = currentPage === 0;
	const nextDisabled = !hasMore;

	const html = `
		<div class="flex justify-center gap-2">
			<button
				class="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg ${prevDisabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-gray-100 dark:hover:bg-gray-700'}"
				${prevDisabled ? 'disabled' : ''}
				data-page="prev"
			>
				Anterior
			</button>
			<span class="px-4 py-2 text-gray-700 dark:text-gray-300">
				Página ${currentPage + 1}
			</span>
			<button
				class="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg ${nextDisabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-gray-100 dark:hover:bg-gray-700'}"
				${nextDisabled ? 'disabled' : ''}
				data-page="next"
			>
				Siguiente
			</button>
		</div>
	`;

	container.innerHTML = html;

	container.querySelectorAll('button[data-page]').forEach(btn => {
		btn.addEventListener('click', (e) => {
			const page = e.target.dataset.page;
			if (newsViewModel) {
				if (page === 'prev') {
					newsViewModel.previousPage();
				} else if (page === 'next') {
					newsViewModel.nextPage();
				}
			}
		});
	});
}

/**
 * Cargar vista de noticia individual
 */
async function loadNoticiaView(newsId) {
	if (!appContainer) return;

	appContainer.innerHTML = '<div class="text-center py-8"><p class="text-gray-600 dark:text-gray-400">Cargando noticia...</p></div>';

	try {
		const response = await fetch(`/api/news/${newsId}`, {
			credentials: 'include'
		});

		if (!response.ok) {
			throw new Error('Noticia no encontrada');
		}

		const noticia = await response.json();
		renderNoticiaView(noticia);
	} catch (error) {
		appContainer.innerHTML = `
			<div class="text-center py-12">
				<h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-4">Noticia no encontrada</h1>
				<p class="text-gray-600 dark:text-gray-400 mb-6">${error.message}</p>
				<button 
					onclick="globalThis.router.navigate('/noticias')"
					class="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
				>
					Volver a noticias
				</button>
			</div>
		`;
	}
}

/**
 * Renderizar vista de noticia
 */
function renderNoticiaView(noticia) {
	if (!appContainer) return;

	const fecha = globalThis.formatNewsDateTimeDisplay(noticia.fecha);

	const categoriasHTML = noticia.categorias && noticia.categorias.length > 0
		? noticia.categorias.map(cat => `
			<span class="text-xs px-2 py-1 rounded-full text-white font-medium" style="background-color: ${cat.color};">
				${escapeHTML(cat.nombre)}
			</span>
		`).join('')
		: '';

	const slug = generarSlug(noticia.titulo);

	appContainer.innerHTML = `
		<article class="mb-12">
			<button 
				onclick="globalThis.router.navigate('/noticias')"
				class="inline-flex items-center gap-2 text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 mb-4 transition-colors"
			>
				<i class="bi bi-arrow-left"></i>
				<span>Volver a noticias</span>
			</button>

			<div id="titulo-container" class="mb-4 flex items-start justify-between gap-4">
				<h1 id="titulo-texto" class="text-4xl font-bold text-gray-900 dark:text-white flex-1">${escapeHTML(noticia.titulo)}</h1>
				<input 
					id="titulo-edit" 
					type="text"
					class="hidden flex-1 px-4 py-2 text-4xl font-bold border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
					value="${escapeHTML(noticia.titulo)}"
				/>
				<!-- Menú de 3 puntos (solo para admins) -->
				<div id="menu-acciones-noticia" class="hidden flex-shrink-0">
					<div class="relative">
						<button 
							id="btn-menu-acciones"
							class="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-gray-600 dark:text-gray-400"
							title="Opciones"
						>
							<i class="bi bi-three-dots-vertical text-xl"></i>
						</button>
						<div id="dropdown-menu-acciones" class="hidden absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-2 z-20">
							<button 
								id="btn-editar-noticia-menu"
								class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
							>
								<i class="bi bi-pencil"></i>
								<span>Editar</span>
							</button>
							<button 
								id="btn-eliminar-noticia-menu"
								class="w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
							>
								<i class="bi bi-trash"></i>
								<span>Eliminar</span>
							</button>
						</div>
					</div>
				</div>
			</div>

			${noticia.imagen ? `
				<div class="w-full mb-6 rounded-lg overflow-hidden bg-gray-200 dark:bg-gray-700">
					<img src="${noticia.imagen}" alt="${escapeHTML(noticia.titulo)}" class="w-full h-auto max-h-[600px] object-contain rounded-lg" />
				</div>
			` : ''}

			<div id="contenido-noticia" class="mb-8">
				<div id="contenido-texto" class="max-w-4xl mx-auto px-6 py-8 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
					<div class="prose prose-lg dark:prose-invert max-w-none text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words overflow-wrap-anywhere leading-relaxed text-justify" style="word-wrap: break-word; overflow-wrap: break-word; max-width: 100%;">
						${escapeHTML(noticia.contenido)}
					</div>
				</div>
				<div id="formulario-edicion" class="hidden space-y-4 max-w-4xl mx-auto px-6 mt-4">
					<div>
						<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
							Contenido:
						</label>
						<textarea 
							id="contenido-edit" 
							rows="10"
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
						>${escapeHTML(noticia.contenido)}</textarea>
					</div>
					<div class="flex gap-2">
						<button 
							id="btn-guardar-edicion"
							class="px-4 py-2 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-lg transition-colors"
						>
							Guardar cambios
						</button>
						<button 
							id="btn-cancelar-edicion"
							class="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white font-semibold rounded-lg transition-colors"
						>
							Cancelar
						</button>
					</div>
				</div>
			</div>

			<div class="max-w-4xl mx-auto mb-8">
				<div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pt-4 border-t border-gray-200 dark:border-gray-700">
					<div class="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
						<span class="flex items-center gap-2">
							<i class="bi bi-person"></i>
							<span>Por: ${escapeHTML(noticia.nombre_autor || noticia.autor)}</span>
						</span>
						<span class="flex items-center gap-1">
							<i class="bi bi-calendar"></i>
							<span>${fecha}</span>
						</span>
						${categoriasHTML ? `<span class="flex items-center gap-2 flex-wrap">${categoriasHTML}</span>` : ''}
					</div>
				</div>
			</div>

			<div id="categorias-container" class="mb-6 hidden">
				<div id="categorias-vista" class="mb-2">
					${categoriasHTML ? `<div class="flex flex-wrap gap-2">${categoriasHTML}</div>` : ''}
				</div>
				<div id="categorias-edit" class="hidden">
					<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
						Categorías:
					</label>
					<div id="categorias-checkboxes" class="flex flex-wrap gap-2">
						<p class="text-sm text-gray-500 dark:text-gray-400">Cargando categorías...</p>
					</div>
				</div>
			</div>
				<div id="formulario-edicion" class="hidden space-y-4 max-w-4xl mx-auto px-6">
					<div>
						<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
							Contenido:
						</label>
						<textarea 
							id="contenido-edit" 
							rows="10"
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
						>${escapeHTML(noticia.contenido)}</textarea>
					</div>
					<div class="flex gap-2">
						<button 
							id="btn-guardar-edicion"
							class="px-4 py-2 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-lg transition-colors"
						>
							Guardar cambios
						</button>
						<button 
							id="btn-cancelar-edicion"
							class="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white font-semibold rounded-lg transition-colors"
						>
							Cancelar
						</button>
					</div>
				</div>
			</div>

			<div class="comentarios-section mt-12 pt-8 border-t border-gray-200 dark:border-gray-700">
				<h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-4">Comentarios</h2>
				<div 
					id="disqus_thread" 
					data-disqus-identifier="noticia-${noticia.id}"
					data-disqus-title="${escapeHTML(noticia.titulo)}"
					data-disqus-url="${globalThis.location.origin}/noticia/${noticia.id}/${slug}"
					class="disqus-container"
				></div>
				<noscript>
					Por favor, habilita JavaScript para ver los comentarios de Disqus.
				</noscript>
			</div>
		</article>

		<!-- Modal de confirmación para eliminar noticia -->
		<div id="modal-eliminar-noticia" class="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 z-50 hidden flex items-center justify-center">
			<div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4 transform transition-all">
				<div class="p-6">
					<div class="flex items-center gap-3 mb-4">
						<div class="flex-shrink-0 w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
							<i class="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400 text-2xl"></i>
						</div>
						<h3 class="text-xl font-bold text-gray-900 dark:text-white">
							Confirmar eliminación
						</h3>
					</div>
					
					<p class="text-gray-600 dark:text-gray-300 mb-2">
						¿Estás seguro de que deseas eliminar la noticia?
					</p>
					<p id="modal-titulo-noticia" class="text-gray-900 dark:text-white font-semibold mb-6 line-clamp-2"></p>
					<p class="text-sm text-red-600 dark:text-red-400 mb-6">
						<i class="bi bi-info-circle"></i> Esta acción no se puede deshacer.
					</p>
					
					<div class="flex gap-3 justify-end">
						<button
							id="btn-cancelar-eliminar-noticia"
							class="px-4 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-900 dark:text-white font-semibold rounded-lg transition-colors"
						>
							Cancelar
						</button>
						<button
							id="btn-confirmar-eliminar-noticia"
							class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg transition-colors flex items-center gap-2"
						>
							<i class="bi bi-trash"></i>
							Eliminar
						</button>
					</div>
				</div>
			</div>
		</div>

		<!-- Modal de mensaje genérico -->
		<div id="modal-mensaje-noticia" class="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 z-50 hidden flex items-center justify-center">
			<div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4 transform transition-all">
				<div class="p-6">
					<div class="flex items-center gap-3 mb-4">
						<div id="modal-icono-noticia" class="flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center">
							<i id="modal-icono-clase-noticia" class="text-2xl"></i>
						</div>
						<h3 id="modal-titulo-mensaje-noticia" class="text-xl font-bold text-gray-900 dark:text-white">
						</h3>
					</div>
					
					<p id="modal-contenido-mensaje-noticia" class="text-gray-600 dark:text-gray-300 mb-6">
					</p>
					
					<div class="flex gap-3 justify-end">
						<button
							id="btn-cerrar-mensaje-noticia"
							class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
						>
							Aceptar
						</button>
					</div>
				</div>
			</div>
		</div>
	`;

	// Inicializar funcionalidad de noticia
	initNoticiaView(noticia);
}

/**
 * Inicializar vista de noticia individual
 */
function initNoticiaView(noticia) {
	let noticiaData = noticia;
	let modoEdicion = false;

	// Obtener información del usuario
	async function puedeEditar() {
		const userInfo = await obtenerUsuarioActualDesdeApi();
		if (!userInfo) return false;
		const role = userInfo.rol;
		const currentUser = userInfo.usuario;
		if (role === 'admin' || role === 'superadmin') return true;
		if (role === 'maestro' && noticiaData && noticiaData.autor === currentUser) return true;
		return false;
	}

	async function configurarBotones() {
		const menuAcciones = document.getElementById('menu-acciones-noticia');
		if (!menuAcciones) return;

		const puedeEditarNoticia = await puedeEditar();
		const puedeEliminarNoticia = await usuarioPuedeEliminarNoticia();

		// Mostrar el menú solo si el usuario tiene permisos
		if (puedeEditarNoticia || puedeEliminarNoticia) {
			menuAcciones.classList.remove('hidden');
		} else {
			menuAcciones.classList.add('hidden');
			return;
		}

		// Configurar botones del menú
		const btnEditarMenu = document.getElementById('btn-editar-noticia-menu');
		const btnEliminarMenu = document.getElementById('btn-eliminar-noticia-menu');
		const btnMenuAcciones = document.getElementById('btn-menu-acciones');
		const dropdownMenu = document.getElementById('dropdown-menu-acciones');

		// Mostrar/ocultar opciones según permisos
		if (btnEditarMenu) {
			if (puedeEditarNoticia) {
				btnEditarMenu.classList.remove('hidden');
				btnEditarMenu.addEventListener('click', () => {
					dropdownMenu.classList.add('hidden');
					if (modoEdicion) {
						cancelarEdicion();
					} else {
						entrarModoEdicion();
					}
				});
			} else {
				btnEditarMenu.classList.add('hidden');
			}
		}

		if (btnEliminarMenu) {
			if (puedeEliminarNoticia) {
				btnEliminarMenu.classList.remove('hidden');
				btnEliminarMenu.addEventListener('click', () => {
					dropdownMenu.classList.add('hidden');
					mostrarModalEliminar();
				});
			} else {
				btnEliminarMenu.classList.add('hidden');
			}
		}

		// Toggle del menú dropdown
		if (btnMenuAcciones && dropdownMenu) {
			btnMenuAcciones.addEventListener('click', (e) => {
				e.stopPropagation();
				dropdownMenu.classList.toggle('hidden');
			});

			// Cerrar el menú al hacer clic fuera
			document.addEventListener('click', (e) => {
				if (!menuAcciones.contains(e.target)) {
					dropdownMenu.classList.add('hidden');
				}
			});
		}
	}

	function entrarModoEdicion() {
		modoEdicion = true;
		const tituloTexto = document.getElementById('titulo-texto');
		const tituloEdit = document.getElementById('titulo-edit');
		const contenidoTexto = document.getElementById('contenido-texto');
		const formularioEdicion = document.getElementById('formulario-edicion');
		const categoriasVista = document.getElementById('categorias-vista');
		const categoriasEdit = document.getElementById('categorias-edit');
		const btnEditar = document.getElementById('btn-editar');

		if (tituloTexto) tituloTexto.classList.add('hidden');
		if (tituloEdit) tituloEdit.classList.remove('hidden');
		if (contenidoTexto) contenidoTexto.classList.add('hidden');
		if (formularioEdicion) formularioEdicion.classList.remove('hidden');
		if (categoriasVista) categoriasVista.classList.add('hidden');
		if (categoriasEdit) categoriasEdit.classList.remove('hidden');
		if (btnEditar) {
			btnEditar.innerHTML = '<i class="bi bi-x-circle text-lg"></i>';
			btnEditar.title = 'Cancelar edición';
		}

		cargarCategoriasParaEdicion();
	}

	function cancelarEdicion() {
		modoEdicion = false;
		const tituloTexto = document.getElementById('titulo-texto');
		const tituloEdit = document.getElementById('titulo-edit');
		const contenidoTexto = document.getElementById('contenido-texto');
		const formularioEdicion = document.getElementById('formulario-edicion');
		const categoriasVista = document.getElementById('categorias-vista');
		const categoriasEdit = document.getElementById('categorias-edit');
		const btnEditar = document.getElementById('btn-editar');

		if (tituloTexto) tituloTexto.classList.remove('hidden');
		if (tituloEdit) tituloEdit.classList.add('hidden');
		if (contenidoTexto) contenidoTexto.classList.remove('hidden');
		if (formularioEdicion) formularioEdicion.classList.add('hidden');
		if (categoriasVista) categoriasVista.classList.remove('hidden');
		if (categoriasEdit) categoriasEdit.classList.add('hidden');
		if (btnEditar) {
			btnEditar.innerHTML = '<i class="bi bi-pencil text-lg"></i>';
			btnEditar.title = 'Editar';
		}

		// Restaurar valores originales
		if (tituloEdit) tituloEdit.value = noticiaData.titulo;
		if (document.getElementById('contenido-edit')) {
			document.getElementById('contenido-edit').value = noticiaData.contenido;
		}
	}

	async function cargarCategoriasParaEdicion() {
		const container = document.getElementById('categorias-checkboxes');
		if (!container) return;

		try {
			const response = await fetch('/api/categories', {
				credentials: 'include'
			});
			if (response.ok) {
				const categorias = await response.json();
				const categoriasActuales = noticiaData.categorias ? noticiaData.categorias.map(c => c.id) : [];
				
				container.innerHTML = categorias.map(cat => `
					<label class="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
						<input 
							type="checkbox" 
							value="${cat.id}" 
							class="categoria-checkbox-edit w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700"
							${categoriasActuales.includes(cat.id) ? 'checked' : ''}
						/>
						<span class="text-sm font-medium text-gray-700 dark:text-gray-300" style="color: ${cat.color}">
							${escapeHTML(cat.nombre)}
						</span>
					</label>
				`).join('');
			}
		} catch (error) {
			console.error('Error al cargar categorías:', error);
		}
	}

	async function guardarEdicion() {
		const tituloEdit = document.getElementById('titulo-edit');
		const contenidoEdit = document.getElementById('contenido-edit');
		
		if (!tituloEdit || !contenidoEdit) return;

		const nuevoTitulo = tituloEdit.value.trim();
		const nuevoContenido = contenidoEdit.value.trim();

		if (!nuevoTitulo || !nuevoContenido) {
			mostrarModalMensajeNoticia('Campos incompletos', 'Por favor, completa todos los campos', 'warning');
			return;
		}

		if (nuevoContenido.trim().length < 50) {
			mostrarModalMensajeNoticia('Contenido muy corto', 'El contenido debe tener al menos 50 caracteres', 'warning');
			return;
		}

		const categoriasSeleccionadas = Array.from(document.querySelectorAll('.categoria-checkbox-edit:checked'))
			.map(cb => Number.parseInt(cb.value, 10));

		try {
			const response = await fetch(`/api/news/${noticiaData.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				credentials: 'include',
				body: JSON.stringify({
					titulo: nuevoTitulo,
					contenido: nuevoContenido,
					categorias: categoriasSeleccionadas
				})
			});

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.error || 'Error al actualizar noticia');
			}

			const responseData = await response.json();
			const noticiaActualizada = responseData.noticia || responseData;
			noticiaData = noticiaActualizada;

			// Notificar al observer sobre la actualización (patrón Observer)
			globalThis.NewsObserver?.getNewsEventSubject?.()?.newsUpdated(noticiaActualizada);

			// Actualizar UI
			const tituloTexto = document.getElementById('titulo-texto');
			const contenidoTexto = document.getElementById('contenido-texto');
			if (tituloTexto) tituloTexto.textContent = nuevoTitulo;
			if (contenidoTexto) {
				// Buscar el div interno que contiene el contenido
				const contenidoDiv = contenidoTexto.querySelector('.prose');
				if (contenidoDiv) {
					contenidoDiv.innerHTML = escapeHTML(nuevoContenido.trim());
				} else {
					contenidoTexto.textContent = nuevoContenido.trim();
				}
			}

			// Actualizar categorías
			const categoriasVista = document.getElementById('categorias-vista');
			if (categoriasVista && noticiaActualizada.categorias) {
				const categoriasHTML = noticiaActualizada.categorias.map(cat => `
					<span class="text-xs px-2 py-1 rounded-full text-white font-medium" style="background-color: ${cat.color};">
						${escapeHTML(cat.nombre)}
					</span>
				`).join('');
				categoriasVista.innerHTML = `<div class="flex flex-wrap gap-2">${categoriasHTML}</div>`;
			}

			cancelarEdicion();
			mostrarModalMensajeNoticia('Éxito', 'Noticia actualizada exitosamente', 'success');
		} catch (error) {
			mostrarModalMensajeNoticia('Error', 'Error al actualizar: ' + error.message, 'error');
		}
	}

	function mostrarModalEliminar() {
		const modal = document.getElementById('modal-eliminar-noticia');
		const tituloElement = document.getElementById('modal-titulo-noticia');
		if (modal && tituloElement) {
			tituloElement.textContent = noticiaData.titulo;
			modal.classList.remove('hidden');
		}
	}

	function cerrarModalEliminar() {
		const modal = document.getElementById('modal-eliminar-noticia');
		if (modal) {
			modal.classList.add('hidden');
		}
	}

	async function confirmarEliminar() {
		try {
			const response = await fetch(`/api/news/${noticiaData.id}`, {
				method: 'DELETE',
				headers: { 'Content-Type': 'application/json' },
				credentials: 'include'
			});

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.error || 'Error al eliminar noticia');
			}

			// Notificar al observer sobre la eliminación (patrón Observer)
			globalThis.NewsObserver?.getNewsEventSubject?.()?.newsDeleted(noticiaData.id);

			cerrarModalEliminar();
			mostrarModalMensajeNoticia('Éxito', 'Noticia eliminada exitosamente', 'success');
			
			// Redirigir después de cerrar el modal
			setTimeout(() => {
				if (globalThis.router) {
					globalThis.router.navigate('/noticias');
				}
			}, 1500);
		} catch (error) {
			cerrarModalEliminar();
			mostrarModalMensajeNoticia('Error', 'Error al eliminar: ' + error.message, 'error');
		}
	}

	// Event listeners
	const btnGuardar = document.getElementById('btn-guardar-edicion');
	const btnCancelar = document.getElementById('btn-cancelar-edicion');
	const btnCancelarEliminar = document.getElementById('btn-cancelar-eliminar-noticia');
	const btnConfirmarEliminar = document.getElementById('btn-confirmar-eliminar-noticia');

	if (btnGuardar) {
		btnGuardar.addEventListener('click', guardarEdicion);
	}

	if (btnCancelar) {
		btnCancelar.addEventListener('click', cancelarEdicion);
	}

	if (btnCancelarEliminar) {
		btnCancelarEliminar.addEventListener('click', cerrarModalEliminar);
	}

	if (btnConfirmarEliminar) {
		btnConfirmarEliminar.addEventListener('click', confirmarEliminar);
	}

	const modalEliminar = document.getElementById('modal-eliminar-noticia');
	if (modalEliminar) {
		modalEliminar.addEventListener('click', (e) => {
			if (e.target === modalEliminar) {
				cerrarModalEliminar();
			}
		});
	}

	// Función para mostrar modal de mensaje
	function mostrarModalMensajeNoticia(titulo, mensaje, tipo = 'info') {
		const modal = document.getElementById('modal-mensaje-noticia');
		const tituloElement = document.getElementById('modal-titulo-mensaje-noticia');
		const contenidoElement = document.getElementById('modal-contenido-mensaje-noticia');
		const iconoElement = document.getElementById('modal-icono-noticia');
		const iconoClaseElement = document.getElementById('modal-icono-clase-noticia');
		
		if (!modal || !tituloElement || !contenidoElement) return;
		
		let bgColor, icono, iconoColor;
		switch(tipo) {
			case 'error':
				bgColor = 'bg-red-100 dark:bg-red-900/30';
				icono = 'bi-exclamation-circle-fill';
				iconoColor = 'text-red-600 dark:text-red-400';
				break;
			case 'success':
				bgColor = 'bg-green-100 dark:bg-green-900/30';
				icono = 'bi-check-circle-fill';
				iconoColor = 'text-green-600 dark:text-green-400';
				break;
			case 'warning':
				bgColor = 'bg-yellow-100 dark:bg-yellow-900/30';
				icono = 'bi-exclamation-triangle-fill';
				iconoColor = 'text-yellow-600 dark:text-yellow-400';
				break;
			default:
				bgColor = 'bg-blue-100 dark:bg-blue-900/30';
				icono = 'bi-info-circle-fill';
				iconoColor = 'text-blue-600 dark:text-blue-400';
		}
		
		iconoElement.className = `flex-shrink-0 w-12 h-12 ${bgColor} rounded-full flex items-center justify-center`;
		iconoClaseElement.className = `${icono} ${iconoColor} text-2xl`;
		tituloElement.textContent = titulo;
		contenidoElement.textContent = mensaje;
		modal.classList.remove('hidden');
	}

	// Configurar modal de mensaje
	const btnCerrarMensaje = document.getElementById('btn-cerrar-mensaje-noticia');
	if (btnCerrarMensaje) {
		btnCerrarMensaje.addEventListener('click', () => {
			document.getElementById('modal-mensaje-noticia').classList.add('hidden');
		});
	}

	const modalMensaje = document.getElementById('modal-mensaje-noticia');
	if (modalMensaje) {
		modalMensaje.addEventListener('click', (e) => {
			if (e.target === modalMensaje) {
				modalMensaje.classList.add('hidden');
			}
		});
	}

	// Configurar botones
	configurarBotones();

	// Cargar Disqus
	const DISQUS_SHORTNAME = 'noticiasul';
	const noticiaId = noticia.id;
	const pageTitle = noticia.titulo;
	const slug = generarSlug(noticia.titulo);
	const pageUrl = `${globalThis.location.origin}/noticia/${noticia.id}/${slug}`;

	if (DISQUS_SHORTNAME && noticiaId) {
		globalThis.disqus_config = function() {
			this.page.identifier = `noticia-${noticiaId}`;
			this.page.url = pageUrl;
			this.page.title = pageTitle || 'Noticia';
		};

		(function() {
			const d = document;
			const s = d.createElement('script');
			s.id = 'disqus-script';
			s.src = `https://${DISQUS_SHORTNAME}.disqus.com/embed.js`;
			s.dataset.timestamp = String(Date.now());
			s.async = true;
			(d.head || d.body).appendChild(s);
		})();
	}
}

/**
 * Cargar vista de admin
 */
async function loadAdminView() {
	if (!appContainer) return;

	appContainer.innerHTML = `
		<section class="mb-12">
			<h2 class="text-3xl font-bold text-gray-900 dark:text-white mb-6">Administración de Usuarios</h2>
			
			<div class="mb-4 flex justify-between items-center">
				<p class="text-gray-600 dark:text-gray-400">Gestiona los usuarios del sistema y asigna roles.</p>
				<button id="btn-nuevo-usuario" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors">
					<i class="bi bi-person-plus"></i> Nuevo Usuario
				</button>
			</div>

			<div class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
				<table class="w-full">
					<thead class="bg-gray-50 dark:bg-gray-700">
						<tr>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Usuario</th>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Nombre</th>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Email</th>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Rol</th>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Fecha Creación</th>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Acciones</th>
						</tr>
					</thead>
					<tbody id="tabla-usuarios" class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
						<tr>
							<td colspan="6" class="px-6 py-4 text-center text-gray-600 dark:text-gray-400">Cargando usuarios...</td>
						</tr>
					</tbody>
				</table>
			</div>
		</section>

		<!-- Modal para crear/editar usuario -->
		<div id="modal-usuario" class="hidden fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
			<div class="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4">
				<div class="flex justify-between items-center mb-4">
					<h3 id="modal-titulo" class="text-xl font-bold text-gray-900 dark:text-white">Nuevo Usuario</h3>
					<button id="btn-cerrar-modal" class="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
						<i class="bi bi-x-lg"></i>
					</button>
				</div>
				
				<form id="formulario-usuario" class="space-y-4">
					<input type="hidden" id="usuario-id" />
					
					<div>
						<label for="usuario-nombre" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Usuario: <span id="usuario-nombre-required" class="text-red-500">*</span>
						</label>
						<input
							type="text"
							id="usuario-nombre"
							name="usuario"
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
						/>
					</div>

					<div id="div-password">
						<label for="usuario-password" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Contraseña: <span id="usuario-password-required" class="text-red-500">*</span>
						</label>
						<input
							type="password"
							id="usuario-password"
							name="password"
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
						/>
						<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">Solo requerida para nuevos usuarios</p>
					</div>

					<div id="div-nombre-completo">
						<label for="usuario-nombre-completo" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Nombre Completo (opcional):
						</label>
						<input
							type="text"
							id="usuario-nombre-completo"
							name="nombre"
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
						/>
					</div>

					<div id="div-email">
						<label for="usuario-email" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Email (opcional):
						</label>
						<input
							type="email"
							id="usuario-email"
							name="email"
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
						/>
					</div>

					<div>
						<label for="usuario-rol" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Rol: <span class="text-red-500">*</span>
						</label>
						<select
							id="usuario-rol"
							name="rol"
							required
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
						>
							<option value="">Selecciona un rol</option>
							<option value="usuario">Usuario</option>
							<option value="maestro">Maestro</option>
							<option value="admin">Administrador</option>
							<option value="superadmin">Super Administrador</option>
						</select>
					</div>

					<div id="usuario-error" class="text-red-600 dark:text-red-400 text-sm hidden"></div>

					<div class="flex gap-2 justify-end">
						<button
							type="button"
							id="btn-cancelar"
							class="px-4 py-2 bg-gray-300 dark:bg-gray-600 hover:bg-gray-400 dark:hover:bg-gray-500 text-gray-900 dark:text-white font-semibold rounded-lg transition-colors"
						>
							Cancelar
						</button>
						<button
							type="submit"
							class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
						>
							Guardar
						</button>
					</div>
				</form>
			</div>
		</div>

		<!-- Modal para editar usuario (solo cambiar rol) -->
		<div id="modal-editar-usuario" class="hidden fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
			<div class="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4">
				<div class="flex justify-between items-center mb-4">
					<h3 id="modal-titulo-editar" class="text-xl font-bold text-gray-900 dark:text-white">Cambiar Rol de Usuario</h3>
					<button id="btn-cerrar-modal-editar" class="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
						<i class="bi bi-x-lg"></i>
					</button>
				</div>
				
				<form id="formulario-editar-usuario" class="space-y-4" novalidate>
					<input type="hidden" id="usuario-id-editar" />
					
					<div>
						<label for="usuario-nombre-editar" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Usuario:
						</label>
						<input
							type="text"
							id="usuario-nombre-editar"
							name="usuario"
							readonly
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white cursor-not-allowed"
						/>
						<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">El nombre de usuario no se puede modificar</p>
					</div>

					<div>
						<label for="usuario-rol-editar" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Rol: <span class="text-red-500">*</span>
						</label>
						<select
							id="usuario-rol-editar"
							name="rol"
							required
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
						>
							<option value="">Selecciona un rol</option>
							<option value="usuario">Usuario</option>
							<option value="maestro">Maestro</option>
							<option value="admin">Administrador</option>
							<option value="superadmin">Super Administrador</option>
						</select>
					</div>

					<div id="usuario-error-editar" class="text-red-600 dark:text-red-400 text-sm hidden"></div>

					<div class="flex gap-2 justify-end">
						<button
							type="button"
							id="btn-cancelar-editar"
							class="px-4 py-2 bg-gray-300 dark:bg-gray-600 hover:bg-gray-400 dark:hover:bg-gray-500 text-gray-900 dark:text-white font-semibold rounded-lg transition-colors"
						>
							Cancelar
						</button>
						<button
							type="submit"
							class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
						>
							Guardar Cambios
						</button>
					</div>
				</form>
			</div>
		</div>

		<!-- Modal de confirmación para eliminar usuario -->
		<div id="modal-eliminar-usuario" class="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 z-50 hidden flex items-center justify-center">
			<div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4 transform transition-all">
				<div class="p-6">
					<div class="flex items-center gap-3 mb-4">
						<div class="flex-shrink-0 w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
							<i class="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400 text-2xl"></i>
						</div>
						<h3 class="text-xl font-bold text-gray-900 dark:text-white">
							Confirmar eliminación
						</h3>
					</div>
					
					<p class="text-gray-600 dark:text-gray-300 mb-2">
						¿Estás seguro de que deseas eliminar al usuario?
					</p>
					<p id="modal-usuario-nombre" class="text-gray-900 dark:text-white font-semibold mb-6"></p>
					<p class="text-sm text-red-600 dark:text-red-400 mb-6">
						<i class="bi bi-info-circle"></i> Esta acción no se puede deshacer.
					</p>
					
					<div class="flex gap-3 justify-end">
						<button
							id="btn-cancelar-eliminar-usuario"
							class="px-4 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-900 dark:text-white font-semibold rounded-lg transition-colors"
						>
							Cancelar
						</button>
						<button
							id="btn-confirmar-eliminar-usuario"
							class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg transition-colors flex items-center gap-2"
						>
							<i class="bi bi-trash"></i>
							Eliminar
						</button>
					</div>
				</div>
			</div>
		</div>

		<!-- Modal de mensaje genérico -->
		<div id="modal-mensaje-admin" class="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 z-50 hidden flex items-center justify-center">
			<div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4 transform transition-all">
				<div class="p-6">
					<div class="flex items-center gap-3 mb-4">
						<div id="modal-icono-admin" class="flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center">
							<i id="modal-icono-clase-admin" class="text-2xl"></i>
						</div>
						<h3 id="modal-titulo-mensaje-admin" class="text-xl font-bold text-gray-900 dark:text-white">
						</h3>
					</div>
					
					<p id="modal-contenido-mensaje-admin" class="text-gray-600 dark:text-gray-300 mb-6">
					</p>
					
					<div class="flex gap-3 justify-end">
						<button
							id="btn-cerrar-mensaje-admin"
							class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
						>
							Aceptar
						</button>
					</div>
				</div>
			</div>
		</div>
	`;

	// Inicializar funcionalidad de admin
	initAdminView();
}

/**
 * Inicializar vista de admin
 */
function initAdminView() {
	cargarUsuariosAdmin();

	// Configurar modales
	const btnCerrarMensaje = document.getElementById('btn-cerrar-mensaje-admin');
	if (btnCerrarMensaje) {
		btnCerrarMensaje.addEventListener('click', () => {
			document.getElementById('modal-mensaje-admin').classList.add('hidden');
		});
	}

	const modalMensaje = document.getElementById('modal-mensaje-admin');
	if (modalMensaje) {
		modalMensaje.addEventListener('click', (e) => {
			if (e.target === modalMensaje) {
				modalMensaje.classList.add('hidden');
			}
		});
	}

	// Modal de eliminar usuario
	let usuarioAEliminar = null;

	function mostrarModalEliminarUsuario(id, usuario) {
		usuarioAEliminar = { id, usuario };
		const modal = document.getElementById('modal-eliminar-usuario');
		const nombreElement = document.getElementById('modal-usuario-nombre');
		if (modal && nombreElement) {
			nombreElement.textContent = `"${usuario}"`;
			modal.classList.remove('hidden');
		}
	}

	function cerrarModalEliminarUsuario() {
		const modal = document.getElementById('modal-eliminar-usuario');
		if (modal) {
			modal.classList.add('hidden');
			usuarioAEliminar = null;
		}
	}

	async function confirmarEliminarUsuario() {
		if (!usuarioAEliminar) return;
		const { id } = usuarioAEliminar;
		try {
			const response = await fetch(`/api/users/${id}`, {
				method: 'DELETE',
				headers: { 'Content-Type': 'application/json' },
				credentials: 'include'
			});
			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.error || 'Error al eliminar usuario');
			}
			cerrarModalEliminarUsuario();
			mostrarModalMensajeAdmin('Usuario eliminado', 'Usuario eliminado exitosamente', 'success');
			cargarUsuariosAdmin();
		} catch (error) {
			cerrarModalEliminarUsuario();
			mostrarModalMensajeAdmin('Error', error.message, 'error');
		}
	}

	const btnCancelarEliminar = document.getElementById('btn-cancelar-eliminar-usuario');
	const btnConfirmarEliminar = document.getElementById('btn-confirmar-eliminar-usuario');
	const modalEliminarUsuario = document.getElementById('modal-eliminar-usuario');

	if (btnCancelarEliminar) {
		btnCancelarEliminar.addEventListener('click', cerrarModalEliminarUsuario);
	}
	if (btnConfirmarEliminar) {
		btnConfirmarEliminar.addEventListener('click', confirmarEliminarUsuario);
	}
	if (modalEliminarUsuario) {
		modalEliminarUsuario.addEventListener('click', (e) => {
			if (e.target === modalEliminarUsuario) {
				cerrarModalEliminarUsuario();
			}
		});
	}

	// Funciones globales para editar/eliminar
	globalThis.editarUsuario = function(id, usuario, rol) {
		console.log(`[ADMIN] Editando usuario - ID: ${id}, Usuario: ${usuario}, Rol: ${rol}`);
		
		const modal = document.getElementById('modal-editar-usuario');
		const usuarioIdInput = document.getElementById('usuario-id-editar');
		const usuarioNombreInput = document.getElementById('usuario-nombre-editar');
		const usuarioRolInput = document.getElementById('usuario-rol-editar');
		const errorDiv = document.getElementById('usuario-error-editar');
		
		if (!modal || !usuarioIdInput || !usuarioNombreInput || !usuarioRolInput) {
			console.error('[ADMIN] Error: No se encontraron elementos del modal de edición');
			return;
		}
		
		// Establecer valores
		usuarioIdInput.value = String(id);
		usuarioNombreInput.value = String(usuario || '');
		usuarioRolInput.value = String(rol || '');
		
		// Limpiar mensaje de error
		if (errorDiv) {
			errorDiv.classList.add('hidden');
			errorDiv.textContent = '';
		}
		
		// Abrir el modal
		modal.classList.remove('hidden');
		
		console.log('[ADMIN] Modal de edición abierto correctamente');
	};

	globalThis.eliminarUsuario = function(id, usuario) {
		mostrarModalEliminarUsuario(id, usuario);
	};

	// Modal de usuario (solo para crear nuevos usuarios)
	function abrirModalAdmin() {
		const modal = document.getElementById('modal-usuario');
		const titulo = document.getElementById('modal-titulo');
		const formulario = document.getElementById('formulario-usuario');
		
		if (modal) modal.classList.remove('hidden');
		if (titulo) titulo.textContent = 'Nuevo Usuario';
		
		// Resetear formulario
		if (formulario) {
			formulario.reset();
			formulario.removeAttribute('novalidate');
		}
		
		// Asegurar que todos los campos estén visibles y habilitados
		const usuarioIdInput = document.getElementById('usuario-id');
		const usuarioNombreInput = document.getElementById('usuario-nombre');
		const usuarioPasswordInput = document.getElementById('usuario-password');
		const usuarioNombreRequired = document.getElementById('usuario-nombre-required');
		const usuarioPasswordRequired = document.getElementById('usuario-password-required');
		
		if (usuarioIdInput) usuarioIdInput.value = '';
		
		if (usuarioPasswordInput) {
			usuarioPasswordInput.required = true;
			usuarioPasswordInput.disabled = false;
			usuarioPasswordInput.value = '';
		}
		
		if (usuarioNombreInput) {
			usuarioNombreInput.readOnly = false;
			usuarioNombreInput.removeAttribute('readonly');
			usuarioNombreInput.required = true;
			usuarioNombreInput.value = '';
		}
		
		// Mostrar asteriscos de requerido
		if (usuarioNombreRequired) usuarioNombreRequired.style.display = 'inline';
		if (usuarioPasswordRequired) usuarioPasswordRequired.style.display = 'inline';
		
		// Mostrar todos los campos
		const divPassword = document.getElementById('div-password');
		const divNombreCompleto = document.getElementById('div-nombre-completo');
		const divEmail = document.getElementById('div-email');
		
		if (divPassword) divPassword.style.display = 'block';
		if (divNombreCompleto) divNombreCompleto.style.display = 'block';
		if (divEmail) divEmail.style.display = 'block';
		
		// Limpiar mensaje de error
		const errorDiv = document.getElementById('usuario-error');
		if (errorDiv) {
			errorDiv.classList.add('hidden');
			errorDiv.textContent = '';
		}
	}

	function cerrarModalAdmin() {
		const modal = document.getElementById('modal-usuario');
		if (modal) modal.classList.add('hidden');
		const errorDiv = document.getElementById('usuario-error');
		if (errorDiv) {
			errorDiv.classList.add('hidden');
			errorDiv.textContent = '';
		}
	}

	async function cargarUsuariosAdmin() {
		try {
			const response = await fetch('/api/users', {
				method: 'GET',
				headers: { 'Content-Type': 'application/json' },
				credentials: 'include'
			});
			if (!response.ok) {
				throw new Error(`Error: ${response.status}`);
			}
			const usuarios = await response.json();
			renderizarUsuariosAdmin(usuarios);
		} catch (error) {
			const tbody = document.getElementById('tabla-usuarios');
			if (tbody) {
				tbody.innerHTML = `<tr><td colspan="6" class="px-6 py-4 text-center text-red-600 dark:text-red-400">Error al cargar usuarios: ${error.message}</td></tr>`;
			}
		}
	}

	function renderizarUsuariosAdmin(usuarios) {
		const tbody = document.getElementById('tabla-usuarios');
		if (!tbody) return;
		if (!usuarios || usuarios.length === 0) {
			tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-4 text-center text-gray-600 dark:text-gray-400">No hay usuarios registrados.</td></tr>';
			return;
		}

		tbody.innerHTML = usuarios.map(usuario => {
			const usuarioEscapado = escapeHTML(usuario.usuario).replaceAll("'", String.raw`\'`).replaceAll('"', '&quot;');
			return `
			<tr class="hover:bg-gray-50 dark:hover:bg-gray-700">
				<td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
					${escapeHTML(usuario.usuario)}
				</td>
				<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600 dark:text-gray-400">
					${escapeHTML(usuario.nombre || '-')}
				</td>
				<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600 dark:text-gray-400">
					${escapeHTML(usuario.email || '-')}
				</td>
				<td class="px-6 py-4 whitespace-nowrap">
					<span class="px-2 py-1 text-xs font-semibold rounded-full ${getRoleBadgeClass(usuario.rol)}">
						${getRoleLabel(usuario.rol)}
					</span>
				</td>
				<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600 dark:text-gray-400">
					${usuario.fecha_creacion ? new Date(usuario.fecha_creacion).toLocaleDateString('es-ES') : '-'}
				</td>
				<td class="px-6 py-4 whitespace-nowrap text-sm">
					<div class="flex gap-3">
						<button 
							onclick="editarUsuario(${usuario.idUsuario}, '${usuarioEscapado}', '${usuario.rol}')"
							class="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
							title="Cambiar rol"
						>
							<i class="bi bi-pencil"></i>
						</button>
						<button 
							onclick="eliminarUsuario(${usuario.idUsuario}, '${usuarioEscapado}')"
							class="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
							title="Eliminar usuario"
						>
							<i class="bi bi-trash"></i>
						</button>
					</div>
				</td>
			</tr>
		`;
		}).join('');
	}

	function mostrarModalMensajeAdmin(titulo, mensaje, tipo = 'info') {
		const modal = document.getElementById('modal-mensaje-admin');
		const tituloElement = document.getElementById('modal-titulo-mensaje-admin');
		const contenidoElement = document.getElementById('modal-contenido-mensaje-admin');
		const iconoElement = document.getElementById('modal-icono-admin');
		const iconoClaseElement = document.getElementById('modal-icono-clase-admin');
		
		if (!modal || !tituloElement || !contenidoElement) return;
		
		let bgColor, icono, iconoColor;
		switch(tipo) {
			case 'error':
				bgColor = 'bg-red-100 dark:bg-red-900/30';
				icono = 'bi-exclamation-circle-fill';
				iconoColor = 'text-red-600 dark:text-red-400';
				break;
			case 'success':
				bgColor = 'bg-green-100 dark:bg-green-900/30';
				icono = 'bi-check-circle-fill';
				iconoColor = 'text-green-600 dark:text-green-400';
				break;
			case 'warning':
				bgColor = 'bg-yellow-100 dark:bg-yellow-900/30';
				icono = 'bi-exclamation-triangle-fill';
				iconoColor = 'text-yellow-600 dark:text-yellow-400';
				break;
			default:
				bgColor = 'bg-blue-100 dark:bg-blue-900/30';
				icono = 'bi-info-circle-fill';
				iconoColor = 'text-blue-600 dark:text-blue-400';
		}
		
		iconoElement.className = `flex-shrink-0 w-12 h-12 ${bgColor} rounded-full flex items-center justify-center`;
		iconoClaseElement.className = `${icono} ${iconoColor} text-2xl`;
		tituloElement.textContent = titulo;
		contenidoElement.textContent = mensaje;
		modal.classList.remove('hidden');
	}

	async function manejarEnvioFormularioAdmin(event) {
		event.preventDefault();
		const errorDiv = document.getElementById('usuario-error');
		const usuarioInput = document.getElementById('usuario-nombre');
		const usuario = usuarioInput ? usuarioInput.value.trim() : '';
		const passwordInput = document.getElementById('usuario-password');
		const password = passwordInput ? passwordInput.value : '';
		const rolInput = document.getElementById('usuario-rol');
		const rol = rolInput ? rolInput.value : '';

		// Ocultar mensaje de error previo
		if (errorDiv) {
			errorDiv.classList.add('hidden');
			errorDiv.textContent = '';
		}

		// Validar campos requeridos para nuevo usuario
		if (!rol) {
			if (errorDiv) {
				errorDiv.textContent = 'Por favor, selecciona un rol.';
				errorDiv.classList.remove('hidden');
			}
			return;
		}
		
		if (!usuario || !password) {
			if (errorDiv) {
				errorDiv.textContent = 'Por favor, completa todos los campos requeridos (usuario y contraseña).';
				errorDiv.classList.remove('hidden');
			}
			return;
		}
		
		try {
			const nombre = document.getElementById('usuario-nombre-completo')?.value.trim() || '';
			const email = document.getElementById('usuario-email')?.value.trim() || '';
			const response = await fetch('/api/users', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				credentials: 'include',
				body: JSON.stringify({ usuario, password, nombre, email, rol }),
			});
			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.error || 'Error al crear usuario');
			}
			cerrarModalAdmin();
			mostrarModalMensajeAdmin('Éxito', 'Usuario creado exitosamente', 'success');
			cargarUsuariosAdmin();
		} catch (error) {
			if (errorDiv) {
				errorDiv.textContent = error.message || 'Error al crear usuario';
				errorDiv.classList.remove('hidden');
			}
		}
	}

	// Configurar modal de editar usuario
	const modalEditar = document.getElementById('modal-editar-usuario');
	const formularioEditar = document.getElementById('formulario-editar-usuario');
	const btnCerrarEditar = document.getElementById('btn-cerrar-modal-editar');
	const btnCancelarEditar = document.getElementById('btn-cancelar-editar');
	
	if (formularioEditar) {
		formularioEditar.addEventListener('submit', async (e) => {
			e.preventDefault();
			const errorDiv = document.getElementById('usuario-error-editar');
			const usuarioIdInput = document.getElementById('usuario-id-editar');
			const usuarioRolInput = document.getElementById('usuario-rol-editar');
			
			const usuarioId = usuarioIdInput ? usuarioIdInput.value.trim() : '';
			const rol = usuarioRolInput ? usuarioRolInput.value : '';
			
			// Ocultar mensaje de error previo
			if (errorDiv) {
				errorDiv.classList.add('hidden');
				errorDiv.textContent = '';
			}
			
			// Validar que haya un rol seleccionado
			if (!rol) {
				if (errorDiv) {
					errorDiv.textContent = 'Por favor, selecciona un rol.';
					errorDiv.classList.remove('hidden');
				}
				return;
			}
			
			try {
				console.log(`[ADMIN] Actualizando usuario ID: ${usuarioId} con rol: ${rol}`);
				const response = await fetch(`/api/users/${usuarioId}`, {
					method: 'PUT',
					headers: { 'Content-Type': 'application/json' },
					credentials: 'include',
					body: JSON.stringify({ rol }),
				});
				
				const responseData = await response.json();
				
				if (!response.ok) {
					throw new Error(responseData.error || 'Error al actualizar rol');
				}
				
				console.log('[ADMIN] Usuario actualizado exitosamente:', responseData);
				cerrarModalEditar();
				mostrarModalMensajeAdmin('Éxito', 'Rol de usuario actualizado exitosamente', 'success');
				cargarUsuariosAdmin();
			} catch (error) {
				console.error('[ADMIN] Error al actualizar usuario:', error);
				if (errorDiv) {
					errorDiv.textContent = error.message || 'Error al actualizar rol';
					errorDiv.classList.remove('hidden');
				}
			}
		});
	}
	
	function cerrarModalEditar() {
		const modal = document.getElementById('modal-editar-usuario');
		if (modal) modal.classList.add('hidden');
		const errorDiv = document.getElementById('usuario-error-editar');
		if (errorDiv) {
			errorDiv.classList.add('hidden');
			errorDiv.textContent = '';
		}
	}
	
	if (btnCerrarEditar) {
		btnCerrarEditar.addEventListener('click', cerrarModalEditar);
	}
	
	if (btnCancelarEditar) {
		btnCancelarEditar.addEventListener('click', cerrarModalEditar);
	}
	
	if (modalEditar) {
		modalEditar.addEventListener('click', (e) => {
			if (e.target === modalEditar) {
				cerrarModalEditar();
			}
		});
	}

	const btnNuevo = document.getElementById('btn-nuevo-usuario');
	const btnCerrar = document.getElementById('btn-cerrar-modal');
	const btnCancelar = document.getElementById('btn-cancelar');
	const formulario = document.getElementById('formulario-usuario');

		if (btnNuevo) {
			btnNuevo.addEventListener('click', () => {
				abrirModalAdmin();
			});
		}

	if (btnCerrar) btnCerrar.addEventListener('click', cerrarModalAdmin);
	if (btnCancelar) btnCancelar.addEventListener('click', cerrarModalAdmin);
	if (formulario) formulario.addEventListener('submit', manejarEnvioFormularioAdmin);

	const modal = document.getElementById('modal-usuario');
	if (modal) {
		modal.addEventListener('click', (e) => {
			if (e.target === modal) cerrarModalAdmin();
		});
	}
}

/**
 * Cargar vista de agregar
 */
async function loadAgregarView() {
	if (!appContainer) return;

	appContainer.innerHTML = `
		<section class="mb-12">
			<form id="formulario-noticia" class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 shadow-sm">
				<h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-4">Agregar Nueva Noticia</h2>
				
				<div class="space-y-4">
					<div>
						<label for="titulo" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Título:
						</label>
						<input 
							type="text" 
							id="titulo" 
							name="titulo" 
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
							required 
						/>
					</div>
					
					<div>
						<label for="contenido" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Contenido:
						</label>
						<textarea 
							id="contenido" 
							name="contenido" 
							rows="5"
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
							required
						></textarea>
					</div>
					
					<div>
						<label for="autor" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Autor:
						</label>
						<input 
							type="text" 
							id="autor" 
							name="autor" 
							readonly
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white cursor-not-allowed"
							required 
						/>
						<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
							El autor se asigna automáticamente con tu usuario
						</p>
					</div>
					
					<div>
						<label for="imagen" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Imagen (PNG, JPG, GIF, WEBP):
						</label>
						<input 
							type="file" 
							id="imagen" 
							name="imagen" 
							accept="image/png,image/jpeg,image/jpg,image/gif,image/webp"
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-gray-600 dark:file:text-gray-200"
						/>
						<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
							Formatos permitidos: PNG, JPG, JPEG, GIF, WEBP (máx. 10MB)
						</p>
						<div id="preview-container" class="mt-3 hidden">
							<img id="preview-imagen" src="" alt="Vista previa" class="max-w-xs max-h-48 rounded-lg border border-gray-300 dark:border-gray-600">
						</div>
					</div>

					<div>
						<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
							Categorías:
						</label>
						<div id="categorias-container" class="flex flex-wrap gap-2">
							<p class="text-sm text-gray-500 dark:text-gray-400">Cargando categorías...</p>
						</div>
						<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
							Selecciona una o más categorías (opcional)
						</p>
					</div>

					<button 
						type="submit"
						class="w-full px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
					>
						Publicar Noticia
					</button>
				</div>
			</form>
		</section>

		<!-- Modal de mensaje genérico -->
		<div id="modal-mensaje-agregar" class="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 z-50 hidden flex items-center justify-center">
			<div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4 transform transition-all">
				<div class="p-6">
					<div class="flex items-center gap-3 mb-4">
						<div id="modal-icono-agregar" class="flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center">
							<i id="modal-icono-clase-agregar" class="text-2xl"></i>
						</div>
						<h3 id="modal-titulo-mensaje-agregar" class="text-xl font-bold text-gray-900 dark:text-white">
						</h3>
					</div>
					
					<p id="modal-contenido-mensaje-agregar" class="text-gray-600 dark:text-gray-300 mb-6">
					</p>
					
					<div class="flex gap-3 justify-end">
						<button
							id="btn-cerrar-mensaje-agregar"
							class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
						>
							Aceptar
						</button>
					</div>
				</div>
			</div>
		</div>
	`;

	// Inicializar funcionalidad de agregar
	initAgregarView();
}

/**
 * Inicializar vista de agregar
 */
function initAgregarView() {
	// Llenar autor
	obtenerNombreUsuarioSesion().then(usuario => {
		const autorInput = document.getElementById('autor');
		if (autorInput && usuario) {
			autorInput.value = usuario;
		} else if (!usuario) {
			if (globalThis.router) {
				globalThis.router.navigate('/login');
			}
		}
	});

	// Cargar categorías
	async function cargarCategorias() {
		try {
			const response = await fetch('/api/categories', {
				credentials: 'include'
			});
			if (response.ok) {
				const categorias = await response.json();
				renderizarCategorias(categorias);
			}
		} catch (error) {
			console.error('Error al cargar categorías:', error);
		}
	}

	function renderizarCategorias(categorias) {
		const container = document.getElementById('categorias-container');
		if (!container) return;
		if (!categorias || categorias.length === 0) {
			container.innerHTML = '<p class="text-sm text-gray-500 dark:text-gray-400">No hay categorías disponibles</p>';
			return;
		}

		container.innerHTML = categorias.map(cat => `
			<label class="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
				<input 
					type="checkbox" 
					value="${cat.id}" 
					class="categoria-checkbox w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700"
				/>
				<span class="text-sm font-medium text-gray-700 dark:text-gray-300" style="color: ${cat.color}">
					${escapeHTML(cat.nombre)}
				</span>
			</label>
		`).join('');
	}

	cargarCategorias();

	// Vista previa de imagen
	const imagenInput = document.getElementById('imagen');
	if (imagenInput) {
		imagenInput.addEventListener('change', (e) => {
			const archivo = e.target.files[0];
			if (archivo) {
				const reader = new FileReader();
				reader.onload = (e) => {
					const previewImagen = document.getElementById('preview-imagen');
					const previewContainer = document.getElementById('preview-container');
					if (previewImagen && previewContainer) {
						previewImagen.src = e.target.result;
						previewContainer.classList.remove('hidden');
					}
				};
				reader.readAsDataURL(archivo);
			} else {
				const previewContainer = document.getElementById('preview-container');
				if (previewContainer) {
					previewContainer.classList.add('hidden');
				}
			}
		});
	}

	// Formulario - Usar ViewModel para crear noticia
	const formulario = document.getElementById('formulario-noticia');
	if (formulario) {
		formulario.addEventListener('submit', async (e) => {
			e.preventDefault();
			
			// Verificar que el ViewModel esté disponible
			if (!globalThis.NewsModel || !globalThis.NewsViewModel) {
				mostrarModalMensajeAgregar('Error', 'Sistema MVVM no disponible', 'error');
				return;
			}

			const titulo = document.getElementById('titulo').value.trim();
			const contenido = document.getElementById('contenido').value.trim();
			const autorInput = document.getElementById('autor');
			const autor = autorInput ? autorInput.value : '';
			const imagenInput = document.getElementById('imagen');
			const archivo = imagenInput ? imagenInput.files[0] : null;

			const submitButton = formulario.querySelector('button[type="submit"]');
			const textoOriginal = submitButton.textContent;
			submitButton.disabled = true;
			submitButton.textContent = 'Publicando...';

			try {
				// Crear instancia del ViewModel si no existe
				let agregarViewModel = globalThis.agregarNewsViewModel;
				if (!agregarViewModel) {
					const newsModel = new globalThis.NewsModel();
					agregarViewModel = new globalThis.NewsViewModel(newsModel);
					globalThis.agregarNewsViewModel = agregarViewModel;
				}

				const categoriasSeleccionadas = Array.from(document.querySelectorAll('.categoria-checkbox:checked'))
					.map(cb => Number.parseInt(cb.value, 10));

				const datosNoticia = {
					titulo,
					contenido,
					autor,
					imageFile: archivo,
					categorias: categoriasSeleccionadas
				};

				// Usar el ViewModel para crear la noticia
				const nuevaNoticia = await agregarViewModel.createNews(datosNoticia);
				
				// Notificar al observer sobre la creación (patrón Observer)
				globalThis.NewsObserver?.getNewsEventSubject?.()?.newsCreated(nuevaNoticia);
				
				mostrarModalMensajeAgregar('¡Éxito!', 'Noticia creada exitosamente!', 'success');
				formulario.reset();
				const previewContainer = document.getElementById('preview-container');
				if (previewContainer) previewContainer.classList.add('hidden');
				document.querySelectorAll('.categoria-checkbox').forEach(cb => cb.checked = false);

				setTimeout(() => {
					if (globalThis.router) {
						globalThis.router.navigate('/noticias');
					}
				}, 1500);
			} catch (error) {
				mostrarModalMensajeAgregar('Error', error.message || 'Error al crear noticia', 'error');
			} finally {
				submitButton.disabled = false;
				submitButton.textContent = textoOriginal;
			}
		});
	}

	function mostrarModalMensajeAgregar(titulo, mensaje, tipo = 'info') {
		const modal = document.getElementById('modal-mensaje-agregar');
		const tituloElement = document.getElementById('modal-titulo-mensaje-agregar');
		const contenidoElement = document.getElementById('modal-contenido-mensaje-agregar');
		const iconoElement = document.getElementById('modal-icono-agregar');
		const iconoClaseElement = document.getElementById('modal-icono-clase-agregar');
		
		if (!modal || !tituloElement || !contenidoElement) return;
		
		let bgColor, icono, iconoColor;
		switch(tipo) {
			case 'error':
				bgColor = 'bg-red-100 dark:bg-red-900/30';
				icono = 'bi-exclamation-circle-fill';
				iconoColor = 'text-red-600 dark:text-red-400';
				break;
			case 'success':
				bgColor = 'bg-green-100 dark:bg-green-900/30';
				icono = 'bi-check-circle-fill';
				iconoColor = 'text-green-600 dark:text-green-400';
				break;
			case 'warning':
				bgColor = 'bg-yellow-100 dark:bg-yellow-900/30';
				icono = 'bi-exclamation-triangle-fill';
				iconoColor = 'text-yellow-600 dark:text-yellow-400';
				break;
			default:
				bgColor = 'bg-blue-100 dark:bg-blue-900/30';
				icono = 'bi-info-circle-fill';
				iconoColor = 'text-blue-600 dark:text-blue-400';
		}
		
		iconoElement.className = `flex-shrink-0 w-12 h-12 ${bgColor} rounded-full flex items-center justify-center`;
		iconoClaseElement.className = `${icono} ${iconoColor} text-2xl`;
		tituloElement.textContent = titulo;
		contenidoElement.textContent = mensaje;
		modal.classList.remove('hidden');
	}

	const btnCerrarMensaje = document.getElementById('btn-cerrar-mensaje-agregar');
	if (btnCerrarMensaje) {
		btnCerrarMensaje.addEventListener('click', () => {
			document.getElementById('modal-mensaje-agregar').classList.add('hidden');
		});
	}

	const modalMensaje = document.getElementById('modal-mensaje-agregar');
	if (modalMensaje) {
		modalMensaje.addEventListener('click', (e) => {
			if (e.target === modalMensaje) {
				modalMensaje.classList.add('hidden');
			}
		});
	}
}

/**
 * Cargar vista de debug
 */
async function loadDebugView() {
	if (!appContainer) return;

	appContainer.innerHTML = `
		<section class="mb-12">
			<h2 class="text-3xl font-bold text-gray-900 dark:text-white mb-6">🔍 Debug de Base de Datos</h2>
			
			<div class="mb-4 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
				<p class="text-sm text-blue-800 dark:text-blue-200">
					<strong>Base de datos:</strong> <span id="db-name">-</span> | 
					<strong>Host:</strong> <span id="db-host">-</span>
				</p>
			</div>

			<div class="mb-4 flex justify-end">
				<button id="btn-refresh" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors">
					🔄 Actualizar
				</button>
			</div>

			<div id="tables-container" class="space-y-6">
				<div class="text-center text-gray-600 dark:text-gray-400 py-8">
					Cargando información de las tablas...
				</div>
			</div>
		</section>
	`;

	// Inicializar funcionalidad de debug
	initDebugView();
}

/**
 * Cargar vista de patrones de diseño
 * La página de patrones es una página Astro estática, así que redirigimos directamente
 */
function loadPatronesView() {
	// Redirigir a la página completa de patrones (página Astro estática)
	globalThis.location.href = '/patrones';
}

function formatDebugSampleCellHtml(val) {
	if (val === null) {
		return '<span class="text-gray-400">NULL</span>';
	}
	if (typeof val === 'object') {
		return escapeHTML(JSON.stringify(val));
	}
	const str = String(val);
	if (str.length > 50) {
		return escapeHTML(str.substring(0, 50)) + '...';
	}
	return escapeHTML(str);
}

function formatDebugColumnDefaultHtml(col) {
	if (col.Default !== null) {
		return escapeHTML(String(col.Default || col.default || 'NULL'));
	}
	return 'NULL';
}

function buildDebugTableSampleSection(table) {
	if (!table.sample_data || table.sample_data.length === 0) {
		return `
								<div class="text-gray-500 dark:text-gray-400 italic">
									No hay datos de ejemplo (tabla vacía)
								</div>`;
	}
	const keys = Object.keys(table.sample_data[0]);
	const headerRow = keys.map(key => `
														<th class="px-4 py-2 text-left text-gray-700 dark:text-gray-300 border-r border-gray-200 dark:border-gray-600">${escapeHTML(key)}</th>
													`).join('');
	const bodyRows = table.sample_data.map(row => {
		const cells = Object.values(row).map(val => `
														<td class="px-4 py-2 text-gray-600 dark:text-gray-400 border-r border-gray-200 dark:border-gray-600">${formatDebugSampleCellHtml(val)}</td>
													`).join('');
		return `
													<tr class="hover:bg-gray-50 dark:hover:bg-gray-700">${cells}
													</tr>`;
	}).join('');
	const footer = table.total_records > 5 ? `
										<p class="text-sm text-gray-500 dark:text-gray-400 mt-2">
											Mostrando 5 de ${table.total_records} registros
										</p>
									` : '';
	return `
								<div>
									<h4 class="text-lg font-semibold text-gray-900 dark:text-white mb-3">Datos de Ejemplo (${table.sample_data.length} registros)</h4>
									<div class="overflow-x-auto">
										<table class="w-full text-sm border border-gray-200 dark:border-gray-600">
											<thead class="bg-gray-100 dark:bg-gray-700">
												<tr>
													${headerRow}
												</tr>
											</thead>
											<tbody class="divide-y divide-gray-200 dark:divide-gray-600">
												${bodyRows}
											</tbody>
										</table>
									</div>${footer}
								</div>`;
}

function buildDebugTableCardHtml(table) {
	const columnsRows = table.columns.map(col => `
											<tr class="hover:bg-gray-50 dark:hover:bg-gray-700">
													<td class="px-4 py-2 font-mono text-gray-900 dark:text-white">${escapeHTML(col.Field || col.field || '')}</td>
													<td class="px-4 py-2 text-gray-600 dark:text-gray-400">${escapeHTML(col.Type || col.type || '')}</td>
													<td class="px-4 py-2 text-gray-600 dark:text-gray-400">${escapeHTML(col.Null || col.null || 'NO')}</td>
													<td class="px-4 py-2 text-gray-600 dark:text-gray-400">${escapeHTML(col.Key || col.key || '-')}</td>
													<td class="px-4 py-2 text-gray-600 dark:text-gray-400">${formatDebugColumnDefaultHtml(col)}</td>
												</tr>
											`).join('');
	return `
					<div class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
						<div class="bg-gray-50 dark:bg-gray-700 px-6 py-4 border-b border-gray-200 dark:border-gray-600">
							<h3 class="text-xl font-bold text-gray-900 dark:text-white">
								📊 ${escapeHTML(table.name)}
							</h3>
							<p class="text-sm text-gray-600 dark:text-gray-400 mt-1">${escapeHTML(table.description || '')}</p>
							<p class="text-sm text-blue-600 dark:text-blue-400 mt-2">
								<strong>Total de registros:</strong> ${table.total_records}
							</p>
						</div>
						
						<div class="p-6">
							<div class="mb-6">
								<h4 class="text-lg font-semibold text-gray-900 dark:text-white mb-3">Estructura de Columnas</h4>
								<div class="overflow-x-auto">
									<table class="w-full text-sm">
										<thead class="bg-gray-100 dark:bg-gray-700">
											<tr>
												<th class="px-4 py-2 text-left text-gray-700 dark:text-gray-300">Campo</th>
												<th class="px-4 py-2 text-left text-gray-700 dark:text-gray-300">Tipo</th>
												<th class="px-4 py-2 text-left text-gray-700 dark:text-gray-300">Null</th>
												<th class="px-4 py-2 text-left text-gray-700 dark:text-gray-300">Key</th>
												<th class="px-4 py-2 text-left text-gray-700 dark:text-gray-300">Default</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-gray-200 dark:divide-gray-600">
											${columnsRows}
										</tbody>
									</table>
								</div>
							</div>
							
							${buildDebugTableSampleSection(table)}
						</div>
					</div>
				`;
}

/**
 * Inicializar vista de debug
 */
function initDebugView() {
	async function cargarDebugTablas() {
		const container = document.getElementById('tables-container');
		const dbName = document.getElementById('db-name');
		const dbHost = document.getElementById('db-host');
		
		try {
			if (container) container.innerHTML = '<div class="text-center text-gray-600 dark:text-gray-400 py-8">Cargando...</div>';
			
			const response = await fetch('/api/debug/tables', {
				credentials: 'include'
			});
			
			if (!response.ok) {
				throw new Error(`HTTP ${response.status}`);
			}
			
			const data = await response.json();
			
			if (!data.success) {
				throw new Error(data.error || 'Error desconocido');
			}
			
			if (dbName) dbName.textContent = data.database || '-';
			if (dbHost) dbHost.textContent = data.host || '-';
			
			if (!data.tables || data.tables.length === 0) {
				if (container) container.innerHTML = '<div class="text-center text-gray-600 dark:text-gray-400 py-8">No se encontraron tablas.</div>';
				return;
			}
			
			const html = data.tables.map(table => buildDebugTableCardHtml(table)).join('');
			
			if (container) container.innerHTML = html;
			
		} catch (error) {
			if (container) {
				container.innerHTML = `
					<div class="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
						<p class="text-red-800 dark:text-red-200">❌ Error al cargar información: ${escapeHTML(error.message)}</p>
					</div>
				`;
			}
		}
	}

	cargarDebugTablas();
	
	const btnRefresh = document.getElementById('btn-refresh');
	if (btnRefresh) {
		btnRefresh.addEventListener('click', () => {
			cargarDebugTablas();
		});
	}
}

/**
 * Cargar vista de login
 */
async function loadLoginView() {
	if (!appContainer) return;

	appContainer.innerHTML = `
		<section class="mb-12 max-w-md mx-auto">
			<div class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 shadow-sm">
				<h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-4">Iniciar Sesión</h2>
				<form id="formulario-login" class="space-y-4">
					<div>
						<label for="username" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Usuario:
						</label>
						<input 
							type="text" 
							id="username" 
							name="username" 
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
							required 
						/>
					</div>
					<div>
						<label for="password" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Contraseña:
						</label>
						<input 
							type="password" 
							id="password" 
							name="password" 
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
							required 
						/>
					</div>
					<div id="login-error" class="text-red-600 dark:text-red-400 text-sm hidden"></div>
					<button 
						type="submit"
						class="w-full px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
					>
						Iniciar Sesión
					</button>

					<div class="text-center mt-4">
						<p class="text-sm text-gray-600 dark:text-gray-400">
							¿No tienes cuenta? 
							<a href="/registro" data-router class="text-blue-600 dark:text-blue-400 hover:underline">
								Regístrate aquí
							</a>
						</p>
					</div>
				</form>
			</div>
		</section>
	`;

	// Configurar formulario de login
	const formulario = document.getElementById('formulario-login');
	if (formulario) {
		formulario.addEventListener('submit', async (e) => {
			e.preventDefault();
			const username = document.getElementById('username').value.trim();
			const password = document.getElementById('password').value.trim();
			const errorDiv = document.getElementById('login-error');

			if (!username || !password) {
				errorDiv.textContent = 'Por favor, completa todos los campos.';
				errorDiv.classList.remove('hidden');
				return;
			}

			try {
				const response = await fetch('/api/login', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					credentials: 'include',
					body: JSON.stringify({ usuario: username, password })
				});

				const data = await response.json();

				if (response.ok && data.mensaje) {
					// Verificar autenticación y actualizar UI del usuario
					if (globalThis.verificarAutenticacion && globalThis.actualizarUI) {
						// Esperar un momento para que la cookie se establezca (más tiempo para Cloudflare)
						// Intentar múltiples veces si es necesario
						let intentos = 0;
						const maxIntentos = 5;
						const verificarYActualizar = async () => {
							intentos++;
							const userData = await globalThis.verificarAutenticacion();
							if (userData.authenticated) {
								globalThis.actualizarUI(userData);
							} else if (intentos < maxIntentos) {
								// Si no está autenticado, esperar un poco más e intentar de nuevo
								setTimeout(verificarYActualizar, 200);
							}
						};
						// Primer intento después de 300ms (más tiempo para Cloudflare Tunnel)
						setTimeout(verificarYActualizar, 300);
					}
					// Redirigir a noticias
					if (globalThis.router) {
						globalThis.router.navigate('/noticias');
					}
				} else {
					errorDiv.textContent = data.error || 'Credenciales incorrectas';
					errorDiv.classList.remove('hidden');
				}
			} catch (error) {
				console.debug('[login] Fallo de red o parseo:', error instanceof Error ? error.message : error);
				errorDiv.textContent = 'Error al conectar con el servidor';
				errorDiv.classList.remove('hidden');
			}
		});
	}
}

/**
 * Cargar vista de registro
 */
async function loadRegistroView() {
	if (!appContainer) return;

	appContainer.innerHTML = `
		<section class="mb-12 max-w-md mx-auto">
			<div class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 shadow-sm">
				<h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-4">Registrarse</h2>
				
				<form id="formulario-registro" class="space-y-4">
					<div>
						<label for="username-registro" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Usuario: <span class="text-red-500">*</span>
						</label>
						<input 
							type="text" 
							id="username-registro" 
							name="username" 
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
							required 
						/>
					</div>
					
					<div>
						<label for="password-registro" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Contraseña: <span class="text-red-500">*</span>
						</label>
						<input 
							type="password" 
							id="password-registro" 
							name="password" 
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
							required 
						/>
					</div>

					<div>
						<label for="nombre-registro" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Nombre completo:
						</label>
						<input 
							type="text" 
							id="nombre-registro" 
							name="nombre" 
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
						/>
					</div>

					<div>
						<label for="email-registro" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
							Email:
						</label>
						<input 
							type="email" 
							id="email-registro" 
							name="email" 
							class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
						/>
					</div>
					
					<div id="registro-error" class="text-red-600 dark:text-red-400 text-sm hidden"></div>
					<div id="registro-success" class="text-green-600 dark:text-green-400 text-sm hidden"></div>
					
					<button 
						type="submit"
						class="w-full px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
					>
						Registrarse
					</button>

					<div class="text-center mt-4">
						<p class="text-sm text-gray-600 dark:text-gray-400">
							¿Ya tienes cuenta? 
							<a href="/login" data-router class="text-blue-600 dark:text-blue-400 hover:underline">
								Inicia sesión aquí
							</a>
						</p>
					</div>
				</form>
			</div>
		</section>
	`;

	// Inicializar funcionalidad de registro
	initRegistroView();
}

/**
 * Inicializar vista de registro
 */
function initRegistroView() {
	const formulario = document.getElementById('formulario-registro');
	if (formulario) {
		formulario.addEventListener('submit', async (e) => {
			e.preventDefault();
			const errorDiv = document.getElementById('registro-error');
			const successDiv = document.getElementById('registro-success');
			const username = document.getElementById('username-registro').value.trim();
			const password = document.getElementById('password-registro').value.trim();
			const nombre = document.getElementById('nombre-registro').value.trim();
			const email = document.getElementById('email-registro').value.trim();

			errorDiv.classList.add('hidden');
			successDiv.classList.add('hidden');

			if (!username || !password) {
				errorDiv.textContent = 'Por favor, completa todos los campos requeridos.';
				errorDiv.classList.remove('hidden');
				return;
			}

			try {
				const response = await fetch('/api/register', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ usuario: username, password, nombre, email })
				});

				if (!response.ok) {
					const errorData = await response.json();
					errorDiv.textContent = errorData.error || 'Error al registrar usuario';
					errorDiv.classList.remove('hidden');
					return;
				}

				const data = await response.json();
				successDiv.textContent = data.mensaje || 'Usuario registrado exitosamente. Redirigiendo...';
				successDiv.classList.remove('hidden');
				formulario.reset();
				
				setTimeout(() => {
					if (globalThis.router) {
						globalThis.router.navigate('/login');
					}
				}, 2000);
			} catch (error) {
				console.debug('[registro] Fallo de red o parseo:', error instanceof Error ? error.message : error);
				errorDiv.textContent = 'Error al registrar usuario. Por favor, intenta nuevamente.';
				errorDiv.classList.remove('hidden');
			}
		});
	}
}

/**
 * Funciones auxiliares
 */
function escapeHTML(text) {
	if (!text) return '';
	const div = document.createElement('div');
	div.textContent = text;
	return div.innerHTML;
}

// Inicializar aplicación cuando el DOM esté listo
if (document.readyState === 'loading') {
	document.addEventListener('DOMContentLoaded', initApp);
} else {
	initApp();
}

// Exportar funciones para uso global
globalThis.app = {
	loadNoticiasView,
	loadNoticiaView,
	loadAdminView,
	loadAgregarView,
	loadDebugView,
	loadLoginView,
	loadRegistroView
};

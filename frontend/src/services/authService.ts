// Tipos para autenticación
export interface LoginCredentials {
	username: string;
	password: string;
}

export interface RegisterCredentials {
	username: string;
	password: string;
	nombre?: string;
	email?: string;
}

export interface AuthResponse {
	success: boolean;
	message?: string;
	user?: {
		username: string;
		nombre?: string;
		rol?: string;
	};
}

// Usar /api directamente - el proxy de Astro lo redirigirá a localhost:5000
// Esto asegura que las cookies funcionen correctamente porque están en el mismo dominio
const BACKEND_BASE_URL = '/api';

export async function register(credentials: RegisterCredentials): Promise<AuthResponse> {
	try {
		const res = await fetch(`${BACKEND_BASE_URL}/register`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				usuario: credentials.username,
				password: credentials.password,
				nombre: credentials.nombre || '',
				email: credentials.email || ''
			}),
		});

		if (!res.ok) {
			let errorData;
			try {
				errorData = await res.json();
			} catch {
				errorData = { error: `Error ${res.status}: ${res.statusText}` };
			}
			
			return {
				success: false,
				message: errorData.error || 'Error al registrar usuario',
			};
		}

		const data = await res.json();
		return {
			success: true,
			message: data.mensaje || 'Registro exitoso',
			user: { 
				username: data.usuario || credentials.username,
				nombre: data.nombre,
				rol: data.rol || 'usuario'
			},
		};
	} catch (error: any) {
		return {
			success: false,
			message: error.message || 'Error al conectarse con el servidor. Verifica que el backend Flask esté corriendo.',
		};
	}
}

export async function login(credentials: LoginCredentials): Promise<AuthResponse> {
	try {
		console.log('🔐 [AUTH SERVICE] Iniciando login:', credentials);
		const res = await fetch(`${BACKEND_BASE_URL}/login`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			credentials: 'include',
			body: JSON.stringify({
				usuario: credentials.username,
				password: credentials.password
			}),
		});

		console.log('🔐 [AUTH SERVICE] Respuesta del servidor:', res.status, res.statusText);

		if (!res.ok) {
			let errorData;
			try {
				errorData = await res.json();
			} catch {
				errorData = { error: `Error ${res.status}: ${res.statusText}` };
			}
			
			console.error('❌ [AUTH SERVICE] Error en login:', errorData);
			return {
				success: false,
				message: errorData.error || 'Credenciales incorrectas',
			};
		}

		const data = await res.json();
		console.log('✅ [AUTH SERVICE] Datos recibidos del login:', data);
		console.log('✅ [AUTH SERVICE] Rol recibido:', data.rol);
		
		return {
			success: true,
			message: data.mensaje || 'Login exitoso',
			user: { 
				username: data.usuario || credentials.username,
				nombre: data.nombre,
				rol: data.rol || 'usuario'
			}
		};
	} catch (error: any) {
		console.error('❌ [AUTH SERVICE] Excepción en login:', error);
		return {
			success: false,
			message: error.message || 'Error al conectarse con el servidor. Verifica que el backend Flask esté corriendo.',
		};
	}
}

export async function logout(): Promise<void> {
	try {
		await fetch(`${BACKEND_BASE_URL}/auth/logout`, {
			method: 'POST',
			credentials: 'include'
		});
	} catch (e) {
		// Silenciar errores de logout
	}
}

// NO hay caché local - TODO se obtiene del servidor en cada petición

export async function getCurrentUserInfo(): Promise<{ usuario: string; nombre: string; rol: string } | null> {
	try {
		console.log('👤 [AUTH SERVICE] Obteniendo información del usuario actual...');
		const res = await fetch(`${BACKEND_BASE_URL}/auth/me`, {
			credentials: 'include' // Incluir cookies
		});
		
		console.log('👤 [AUTH SERVICE] Respuesta de /auth/me:', res.status, res.statusText);
		console.log('👤 [AUTH SERVICE] Cookies disponibles:', document.cookie);
		
		if (res.ok) {
			const data = await res.json();
			console.log('👤 [AUTH SERVICE] Datos recibidos de /auth/me:', data);
			console.log('👤 [AUTH SERVICE] Rol recibido:', data.rol);
			console.log('👤 [AUTH SERVICE] Usuario recibido:', data.usuario);
			console.log('👤 [AUTH SERVICE] Nombre recibido:', data.nombre);
			
			if (data.authenticated) {
				const userInfo = {
					usuario: data.usuario,
					nombre: data.nombre || data.usuario,
					rol: data.rol || 'usuario'
				};
				console.log('✅ [AUTH SERVICE] Información del usuario:', userInfo);
				return userInfo;
			} else {
				console.warn('⚠️ [AUTH SERVICE] Usuario no autenticado');
			}
		} else {
			console.warn('⚠️ [AUTH SERVICE] Respuesta no OK:', res.status);
		}
		return null;
	} catch (e) {
		console.error('❌ [AUTH SERVICE] Error al obtener información del usuario:', e);
		return null;
	}
}

export async function isAuthenticated(): Promise<boolean> {
	const userInfo = await getCurrentUserInfo();
	return userInfo !== null;
}

export async function getCurrentUser(): Promise<string | null> {
	const userInfo = await getCurrentUserInfo();
	return userInfo?.usuario || null;
}

export async function getCurrentRole(): Promise<string> {
	const userInfo = await getCurrentUserInfo();
	return userInfo?.rol || 'usuario';
}

export async function getCurrentNombre(): Promise<string | null> {
	const userInfo = await getCurrentUserInfo();
	return userInfo?.nombre || null;
}

export async function hasPermission(permission: 'view' | 'create' | 'edit' | 'delete' | 'manage_users' | 'manage_admins'): Promise<boolean> {
	const role = await getCurrentRole();
	const permissions: Record<string, Record<string, boolean>> = {
		'superadmin': {
			'view': true,
			'create': true,
			'edit': true,
			'delete': true,
			'manage_users': true,
			'manage_admins': true
		},
		'admin': {
			'view': true,
			'create': true,
			'edit': true,
			'delete': true,
			'manage_users': false,
			'manage_admins': false
		},
		'maestro': {
			'view': true,
			'create': true,
			'edit': false,
			'delete': false,
			'manage_users': false,
			'manage_admins': false
		},
		'usuario': {
			'view': true,
			'create': false,
			'edit': false,
			'delete': false,
			'manage_users': false,
			'manage_admins': false
		}
	};
	
	return permissions[role]?.[permission] || false;
}

export async function getAuthHeaders(): Promise<Record<string, string>> {
	const headers: Record<string, string> = {
		'Content-Type': 'application/json',
	};
	
	// El token se envía automáticamente en la cookie HTTP-only
	// No necesitamos agregar headers manualmente
	// Todo se verifica en el servidor desde la cookie
	
	return headers;
}


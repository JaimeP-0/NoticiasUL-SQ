/**
 * Utilidades compartidas entre app.js y NewsViewModel (evita duplicación Sonar).
 * Debe cargarse antes que NewsViewModel.js y app.js.
 */

const ES_DATE_OPTS = { year: 'numeric', month: 'long', day: 'numeric' };
const ES_DATETIME_OPTS = {
	year: 'numeric',
	month: 'long',
	day: 'numeric',
	hour: '2-digit',
	minute: '2-digit',
};

function buildNewsSlug(text) {
	if (text == null || text === '') return '';
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

function formatNewsDateDisplay(dateString) {
	if (!dateString) {
		return 'Fecha no disponible';
	}
	try {
		const date = new Date(dateString);
		if (Number.isNaN(date.getTime())) {
			return 'Fecha no disponible';
		}
		return date.toLocaleDateString('es-ES', ES_DATE_OPTS);
	} catch (e) {
		console.error('Error al formatear fecha:', e, dateString);
		return 'Fecha no disponible';
	}
}

function formatNewsDateTimeDisplay(dateString) {
	if (!dateString) {
		return 'Fecha no disponible';
	}
	try {
		const date = new Date(dateString);
		if (Number.isNaN(date.getTime())) {
			return 'Fecha no disponible';
		}
		return date.toLocaleDateString('es-ES', ES_DATETIME_OPTS);
	} catch (e) {
		console.error('Error al formatear fecha:', e);
		return 'Fecha no disponible';
	}
}

if (globalThis.window !== undefined) {
	globalThis.buildNewsSlug = buildNewsSlug;
	globalThis.formatNewsDateDisplay = formatNewsDateDisplay;
	globalThis.formatNewsDateTimeDisplay = formatNewsDateTimeDisplay;
}

if (typeof module !== 'undefined' && module.exports) {
	module.exports = {
		buildNewsSlug,
		formatNewsDateDisplay,
		formatNewsDateTimeDisplay,
	};
}

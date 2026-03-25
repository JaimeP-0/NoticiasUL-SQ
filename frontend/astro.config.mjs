// @ts-check
import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

// https://astro.build/config
export default defineConfig({
	integrations: [tailwind()],
	vite: {
		server: {
			host: true,
			allowedHosts: [
				'.trycloudflare.com'
			],
			proxy: {
				'/api': {
					target: 'http://localhost:5000',
					changeOrigin: true,
					secure: false,
					// Preservar los headers de cookies
					configure: (proxy, _options) => {
						proxy.on('proxyReq', (proxyReq, req, _res) => {
							// Asegurar que las cookies se envíen
							if (req.headers.cookie) {
								proxyReq.setHeader('Cookie', req.headers.cookie);
							}
						});
						proxy.on('proxyRes', (proxyRes, req, res) => {
							// Asegurar que las cookies se reciban y se establezcan
							if (proxyRes.headers['set-cookie']) {
								// Modificar el dominio de las cookies para que funcionen en el mismo dominio
								const cookies = proxyRes.headers['set-cookie'].map(cookie => {
									// Remover el dominio específico para que funcione en localhost:4321
									return cookie
										.replace(/Domain=[^;]+;?/gi, '')
										.replace(/;?\s*Domain=[^;]+/gi, '');
								});
								res.setHeader('Set-Cookie', cookies);
							}
						});
					}
				}
			}
		}
	}
});

/*
 * Configuracion de runtime del frontend — Misión Atabey.
 *
 * Este archivo NO se compila: se sirve tal cual junto al bundle. Sirve para
 * cambiar la URL del backend (y del WebSocket) SIN tener que recompilar y
 * volver a desplegar el sitio.
 *
 *   - En Netlify/Vercel: se sobreescribe con las variables de entorno
 *     VITE_API_BASE_URL / VITE_WS_BASE_URL del panel del sitio.
 *   - En un servidor propio: se edita este archivo a mano.
 *   - Si no hay ningun valor definido, el frontend usa las variables de
 *     entorno del build (import.meta.env.VITE_API_BASE_URL).
 *
 * Claves disponibles:
 *   apiBaseUrl    URL base del backend FastAPI
 *   wsBaseUrl     URL base del WebSocket (si se omite, se deriva de apiBaseUrl)
 *   tileProvider  'esri' (default, sin clave ni watermark) | 'carto'
 *   cartoApiKey   key de CARTO, solo si tileProvider = 'carto'
 *
 * Ejemplo:
 *   window.__ATABEY_CONFIG__ = {
 *     apiBaseUrl: 'https://mi-backend.example.com',
 *     wsBaseUrl:  'wss://mi-backend.example.com',
 *     tileProvider: 'esri',
 *   }
 */
window.__ATABEY_CONFIG__ = window.__ATABEY_CONFIG__ || {
  apiBaseUrl: 'http://localhost:8000',
  wsBaseUrl: 'ws://localhost:8000',
  tileProvider: 'esri',
};

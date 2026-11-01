// Configuracion en runtime (public/runtime-config.js) tiene prioridad sobre
// las variables de entorno del build. Asi se puede cambiar la URL del backend
// en un sitio ya desplegado sin recompilar.
const RUNTIME_CONFIG = (typeof window !== 'undefined' && window.__ATABEY_CONFIG__) || {}

const RAW_API_BASE_URL =
  RUNTIME_CONFIG.apiBaseUrl || import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const RAW_WS_BASE_URL =
  RUNTIME_CONFIG.wsBaseUrl || import.meta.env.VITE_WS_BASE_URL

function trimTrailingSlash(value) {
  return value.replace(/\/+$/, '')
}

function toWebSocketBaseUrl(apiBaseUrl) {
  return apiBaseUrl.replace(/^http/i, protocol => protocol.toLowerCase() === 'https' ? 'wss' : 'ws')
}

export const API_BASE_URL = trimTrailingSlash(RAW_API_BASE_URL)
export const WS_BASE_URL = trimTrailingSlash(RAW_WS_BASE_URL ?? toWebSocketBaseUrl(API_BASE_URL))
export const CARTO_API_KEY = RUNTIME_CONFIG.cartoApiKey || import.meta.env.VITE_CARTO_API_KEY || ''
export const CARTO_ATTRIBUTION = '© OpenStreetMap contributors © CARTO'
export const ESRI_ATTRIBUTION = 'Tiles © Esri — Esri, DeLorme, NAVTEQ'
export const DEFAULT_MAP_CENTER = [-70.5609, 18.8776]

// Proveedor de tiles del mapa base.
//
//   'esri'   -> Esri Dark Gray Canvas (base + referencia). NO requiere API key
//               ni marca de agua. Es el valor por defecto.
//   'carto'  -> CARTO Dark Matter raster. La key del repo resulto expirada:
//               los tiles volvian identicos con y sin `?key=`, con el
//               watermark "API KEY REQUIRED". Se conserva como alternativa
//               para cuando haya una key valida.
//
// Se puede cambiar sin recompilar via `window.__ATABEY_CONFIG__.tileProvider`.
export const TILE_PROVIDER = (
  RUNTIME_CONFIG.tileProvider || import.meta.env.VITE_TILE_PROVIDER || 'esri'
).toLowerCase()

// Estilo CARTO Dark Matter en RASTER (tiles PNG).
//
// Se usa raster en vez del estilo vectorial (dark-matter-gl-style) por dos
// razones:
//   1. Los tiles raster no dependen del worker de MapLibre para parsear PBF,
//      que es donde fallaba la carga en algunos entornos.
//   2. Es la variante `dark_all` de CARTO, la misma del diccionario original
//      del proyecto, y funciona con o sin API key.
//
// La subdominacion a/b/c/d reparte las peticiones entre servidores.
const CARTO_RASTER_TILES = [
  'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
  'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
  'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
  'https://d.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
]

export function getCartoStyle(apiKey = CARTO_API_KEY) {
  // Estilo MapLibre con Dark Matter de CARTO en raster.
  const suffix = apiKey ? `?key=${encodeURIComponent(apiKey)}` : ''
  return {
    version: 8,
    sources: {
      carto: {
        type: 'raster',
        tiles: CARTO_RASTER_TILES.map(url => url + suffix),
        tileSize: 256,
        attribution: CARTO_ATTRIBUTION,
        maxzoom: 19,
      },
    },
    layers: [
      { id: 'carto-dark', type: 'raster', source: 'carto' },
    ],
  }
}

// Esri Dark Gray Canvas. El servicio usa el orden {z}/{y}/{x} (no {z}/{x}/{y}).
const ESRI_BASE_TILES = [
  'https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
]
const ESRI_REFERENCE_TILES = [
  'https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
]

export function getEsriStyle() {
  return {
    version: 8,
    sources: {
      esriBase: {
        type: 'raster',
        tiles: ESRI_BASE_TILES,
        tileSize: 256,
        attribution: ESRI_ATTRIBUTION,
        maxzoom: 16,
      },
      esriReference: {
        type: 'raster',
        tiles: ESRI_REFERENCE_TILES,
        tileSize: 256,
        attribution: ESRI_ATTRIBUTION,
        maxzoom: 16,
      },
    },
    layers: [
      { id: 'esri-base', type: 'raster', source: 'esriBase' },
      { id: 'esri-reference', type: 'raster', source: 'esriReference' },
    ],
  }
}

/**
 * Estilo del mapa base segun el proveedor configurado.
 * @param {string} [provider] 'esri' | 'carto'
 */
export function getBaseMapStyle(provider = TILE_PROVIDER) {
  return provider === 'carto' ? getCartoStyle() : getEsriStyle()
}

/** Texto de atribucion que corresponde al proveedor configurado. */
export function getBaseMapAttribution(provider = TILE_PROVIDER) {
  return provider === 'carto' ? CARTO_ATTRIBUTION : ESRI_ATTRIBUTION
}

export function apiUrl(path) {
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

export function wsUrl(path, params = {}) {
  const url = new URL(`${WS_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`)
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, value)
    }
  })
  return url.toString()
}

export function getCartoStyleUrl(apiKey = CARTO_API_KEY) {
  const baseStyleUrl = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
  return apiKey ? `${baseStyleUrl}?key=${encodeURIComponent(apiKey)}` : baseStyleUrl
}


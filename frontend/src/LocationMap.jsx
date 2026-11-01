import { useEffect, useRef } from 'react'
import * as maplibregl from 'maplibre-gl'
// MapLibre >= v6 trae un worker ESM separado que Vite no resuelve al
// pre-empaquetar; `?worker&url` fuerza a Vite a empaquetarlo con su
// dependencia `maplibre-gl-shared.mjs` incluida — sin esto da 404.
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import {
  CARTO_API_KEY,
  DEFAULT_MAP_CENTER,
  TILE_PROVIDER,
  getBaseMapAttribution,
  getBaseMapStyle,
} from './config'

// Llamar una sola vez antes de instanciar cualquier mapa.
maplibregl.setWorkerUrl(maplibreWorkerUrl)

/**
 * Mapa a pantalla completa. Mantiene el contrato de actualizacion en vivo:
 * cuando llega un mensaje WS con `type: "location"`, se actualiza `locations`
 * y el marcador se mueve via `marker.setLngLat(...)` sin recargar.
 *
 * Expone handlers de hover y click por marcador para que Dashboard.jsx muestre
 * la tarjeta flotante y abra el panel lateral derecho.
 *
 * Props:
 *  - locations          lista de posiciones [{device_id, lat, lon, ...}]
 *  - tripulanteMeta     mapa {device_id: 'M' | 'F'} para color del marker
 *  - tripulanteNombres  mapa {device_id: nombre} para el label visible
 *  - selectedDeviceId   tripulante seleccionado (resalta el marker)
 *  - onMarkerHover, onMarkerLeave, onMarkerSelect  handlers por marker
 *  - rightInset   ancho en px del panel lateral abierto, para centrar el grupo
 *                 de marcadores en el area visible del mapa
 */
export default function LocationMap({
  locations,
  tripulanteMeta = {},
  tripulanteNombres = {},
  selectedDeviceId = null,
  onMarkerHover,
  onMarkerLeave,
  onMarkerSelect,
  showApiKeyBanner = true,
  rightInset = 0,
}) {
  const mapNodeRef = useRef(null)
  const mapRef = useRef(null)
  const markersRef = useRef(new Map())
  const lastFitKeyRef = useRef(null)

  useEffect(() => {
    if (!mapNodeRef.current || mapRef.current) return undefined

    const map = new maplibregl.Map({
      container: mapNodeRef.current,
      style: getBaseMapStyle(),
      center: DEFAULT_MAP_CENTER,
      zoom: 13,
      attributionControl: false,
    })

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')
    map.addControl(
      new maplibregl.AttributionControl({
        compact: true,
        customAttribution: getBaseMapAttribution(),
      }),
      'bottom-right',
    )

    mapRef.current = map
    const markers = markersRef.current

    // Expone el ref del mapa y el ultimo estado de locations en window
    // para que el HoverCard pueda proyectar coordenadas en pixeles sin
    // prop drilling de refs.
    window.__atabeyMap = map
    window.__atabeyLastLocations = {}

    return () => {
      markers.forEach(marker => marker.remove())
      markers.clear()
      map.remove()
      mapRef.current = null
      if (window.__atabeyMap === map) window.__atabeyMap = null
      window.__atabeyLastLocations = {}
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    // Publica las posiciones actuales para la hover-card.
    const nextById = {}
    locations.forEach(l => { nextById[l.device_id] = l })
    window.__atabeyLastLocations = nextById

    const locationMap = new Map(locations.map(location => [location.device_id, location]))

    // Elimina marcadores que ya no estan presentes.
    markersRef.current.forEach((marker, deviceId) => {
      if (!locationMap.has(deviceId)) {
        marker.remove()
        markersRef.current.delete(deviceId)
      }
    })

    locations.forEach(location => {
      const lngLat = [location.lon, location.lat]
      const sexo = tripulanteMeta[location.device_id] ?? location.sexo ?? null
      const nombre = tripulanteNombres[location.device_id] ?? location.device_id
      const isSelected = selectedDeviceId === location.device_id

      let marker = markersRef.current.get(location.device_id)
      if (!marker) {
        const el = buildMarker(nombre, sexo)
        marker = new maplibregl.Marker({ element: el })
          .setLngLat(lngLat)
          .addTo(map)

        el.addEventListener('mouseenter', () => onMarkerHover?.(location.device_id))
        el.addEventListener('mouseleave', () => onMarkerLeave?.(location.device_id))
        el.addEventListener('click', e => {
          e.stopPropagation()
          onMarkerSelect?.(location.device_id)
        })

        markersRef.current.set(location.device_id, marker)
      } else {
        marker.setLngLat(lngLat)
        const el = marker.getElement()
        el.classList.toggle('is-male',   sexo === 'M')
        el.classList.toggle('is-female', sexo === 'F')
        el.classList.toggle('is-selected', isSelected)
        // Actualiza el nombre si cambia (caso edge).
        const labelEl = el.querySelector('.eva-map-marker__label')
        if (labelEl && labelEl.textContent !== nombre) labelEl.textContent = nombre
      }

      if (marker) {
        const el = marker.getElement()
        el.classList.toggle('is-selected', isSelected)
      }
    })

    if (!locations.length) return

    // Re-enquadra cuando cambia el conjunto de marcadores o cuando se abre /
    // cierra el panel lateral, para que el grupo quede siempre centrado en el
    // area visible (el mapa ocupa toda la pantalla, pero la barra de navegacion
    // de la izquierda y el panel de la derecha lo tapan).
    const fitKey = `${locations.length}:${rightInset}`
    if (lastFitKeyRef.current === fitKey) return
    lastFitKeyRef.current = fitKey

    const padding = {
      top: 96,
      bottom: 96,
      left: 140,            // barra de navegacion (92px) + margen
      right: rightInset + 48,
    }

    if (locations.length === 1) {
      map.easeTo({ center: [locations[0].lon, locations[0].lat], zoom: 15, duration: 800 })
    } else {
      const bounds = new maplibregl.LngLatBounds()
      locations.forEach(location => bounds.extend([location.lon, location.lat]))
      map.fitBounds(bounds, { padding, maxZoom: 15, duration: 800 })
    }
  }, [locations, tripulanteMeta, tripulanteNombres, selectedDeviceId, rightInset, onMarkerHover, onMarkerLeave, onMarkerSelect])

  return (
    <div className="eva-map-shell">
      <div ref={mapNodeRef} className="eva-map-canvas" />
      {TILE_PROVIDER === 'carto' && !CARTO_API_KEY && showApiKeyBanner && (
        <div className="eva-map-banner" role="status">
          Configura `VITE_CARTO_API_KEY` para usar Dark Matter sin watermark.
        </div>
      )}
    </div>
  )
}

function buildMarker(name, sexo) {
  const marker = document.createElement('div')
  marker.className = 'eva-map-marker'
  if (sexo === 'M') marker.classList.add('is-male')
  if (sexo === 'F') marker.classList.add('is-female')

  const dot = document.createElement('span')
  dot.className = 'eva-map-marker__dot'

  const label = document.createElement('span')
  label.className = 'eva-map-marker__label'
  label.textContent = name

  marker.append(dot, label)
  return marker
}

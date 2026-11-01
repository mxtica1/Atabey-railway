import { useState, useEffect, useCallback, useMemo } from 'react'
import LocationMap from './LocationMap'
import SettingsPanel from './SettingsPanel'
import TelemetryCountdown, { TELEMETRY_INTERVAL_MS } from './TelemetryCountdown'
import { apiUrl, wsUrl } from './config'
import {
  TRIPULANTES,
  getTripulante,
  getTripulanteByStreamDevice,
  getTripulanteBaseCoords,
  SEXO_LABEL,
} from './data/tripulantes'

// ─── Constantes ──────────────────────────────────────────────────────────────

const BIOMETRIC_SENSORS = new Set(['HR-01', 'SPO2-01', 'BTEMP-01'])
const SENSOR_ORDER = [
  'TEMP-01', 'HUM-01', 'CO2-01', 'LUX-01',
  'SOIL-HUM-01', 'SOIL-HUM-02', 'SOIL-HUM-03',
  'SOIL-TEMP-01', 'SOIL-TEMP-02', 'SOIL-TEMP-03',
  'NPK-N-01', 'NPK-P-01', 'NPK-K-01',
  'HR-01', 'SPO2-01', 'BTEMP-01',
  'EVA-TEMP-01', 'EVA-HUM-01', 'EVA-PRESS-01',
  'ACC-X-01', 'ACC-Y-01', 'ACC-Z-01', 'ACTIVITY-01',
]

const SENSOR_META = {
  'TEMP-01':      { label: 'Temperatura Domo', unit: '°C', group: 'domo_ambiental' },
  'HUM-01':       { label: 'Humedad Domo', unit: '%', group: 'domo_ambiental' },
  'CO2-01':       { label: 'CO₂', unit: 'ppm', group: 'domo_ambiental' },
  'LUX-01':       { label: 'Iluminación', unit: 'lux', group: 'domo_ambiental' },
  'SOIL-HUM-01':  { label: 'Humedad Suelo S1', unit: '%', group: 'domo_suelo' },
  'SOIL-HUM-02':  { label: 'Humedad Suelo S2', unit: '%', group: 'domo_suelo' },
  'SOIL-HUM-03':  { label: 'Humedad Suelo S3', unit: '%', group: 'domo_suelo' },
  'SOIL-TEMP-01': { label: 'Temp. Suelo S1', unit: '°C', group: 'domo_suelo' },
  'SOIL-TEMP-02': { label: 'Temp. Suelo S2', unit: '°C', group: 'domo_suelo' },
  'SOIL-TEMP-03': { label: 'Temp. Suelo S3', unit: '°C', group: 'domo_suelo' },
  'NPK-N-01':     { label: 'Nitrógeno', unit: 'mg/kg', group: 'domo_suelo' },
  'NPK-P-01':     { label: 'Fósforo', unit: 'mg/kg', group: 'domo_suelo' },
  'NPK-K-01':     { label: 'Potasio', unit: 'mg/kg', group: 'domo_suelo' },
  'EVA-TEMP-01':  { label: 'Temp. Traje', unit: '°C', group: 'eva' },
  'EVA-HUM-01':   { label: 'Humedad Traje', unit: '%', group: 'eva' },
  'EVA-PRESS-01': { label: 'Presión Traje', unit: 'hPa', group: 'eva' },
  'ACC-X-01':     { label: 'Aceleración X', unit: 'm/s²', group: 'imu' },
  'ACC-Y-01':     { label: 'Aceleración Y', unit: 'm/s²', group: 'imu' },
  'ACC-Z-01':     { label: 'Aceleración Z', unit: 'm/s²', group: 'imu' },
  'ACTIVITY-01':  { label: 'Actividad', unit: '', group: 'imu' },
  'HR-01':        { label: 'Pulso', unit: 'bpm', group: 'bio' },
  'SPO2-01':      { label: 'SpO₂', unit: '%', group: 'bio' },
  'BTEMP-01':     { label: 'Temp. Corporal', unit: '°C', group: 'bio' },
}

const ROL_DISPLAY = {
  administrador: 'Administrador',
  control_mision: 'Control de Misión',
  observador: 'Observador',
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function getSensorMeta(sensorId) {
  return SENSOR_META[sensorId] ?? { label: sensorId, unit: '', group: 'domo_ambiental' }
}

function sortSensorIds(sensorIds) {
  return [...sensorIds].sort((left, right) => {
    const leftIndex = SENSOR_ORDER.indexOf(left)
    const rightIndex = SENSOR_ORDER.indexOf(right)
    if (leftIndex === -1 && rightIndex === -1) return left.localeCompare(right)
    if (leftIndex === -1) return 1
    if (rightIndex === -1) return -1
    return leftIndex - rightIndex
  })
}

function sensorSubject(sensorId) {
  return getSensorMeta(sensorId).group.startsWith('domo_') ? 'domo' : 'tripulante'
}

function readingKey(reading) {
  return `${reading.device_id ?? 'unknown'}:${reading.sensor_id}`
}

function getReading(readings, sensorId, deviceId) {
  return Object.values(readings)
    .filter(reading => reading.sensor_id === sensorId && (!deviceId || reading.device_id === deviceId))
    .reduce((latest, reading) => {
      if (!latest) return reading
      return Date.parse(reading.timestamp) > Date.parse(latest.timestamp) ? reading : latest
    }, null)
}

function getTripulanteSourceLabel(tripulante) {
  return tripulante.streamSource === 'simulated'
    ? 'Simulación en navegador'
    : `Stream ${tripulante.streamSource} · simulador del gateway`
}

/**
 * Mismo criterio que el backend (`backend/mqtt_client.py`):
 *  - 'crit'  si margen/rango > 20%
 *  - 'alert' si excede el umbral pero dentro del 20%
 *  - 'ok'    si no hay umbral o el valor esta en rango
 */
function getReadingSeverity(sensorId, value, thresholds) {
  if (typeof value !== 'number') return 'ok'
  const threshold = thresholds?.[sensorId]
  if (!threshold) return 'ok'
  const { valor_min: min, valor_max: max } = threshold
  const rango = max - min
  let excedido = null
  let margen = 0
  if (value < min) { excedido = 'min'; margen = Math.abs(value - min) }
  else if (value > max) { excedido = 'max'; margen = Math.abs(value - max) }
  if (excedido === null) return 'ok'
  if (rango > 0 && margen / rango > 0.20) return 'crit'
  return 'alert'
}

function severityClass(severity, baseClass = 'value') {
  if (severity === 'crit') return `${baseClass} ${baseClass}--crit`
  if (severity === 'alert') return `${baseClass} ${baseClass}--alert`
  return baseClass
}

/**
 * Genera lecturas biometricas simuladas para un tripulante placeholder.
 * Estos datos se generan en el navegador; no vienen del hardware.
 */
function makeSimulatedReadings(tripulante, nowIso) {
  const sim = tripulante.simulated
  if (!sim) return {}
  const drift = () => (Math.random() - 0.5) * 0.6
  return {
    'HR-01':    { sensor_id: 'HR-01',    device_id: tripulante.id, value: +(sim.hr.value   + drift()).toFixed(1), unit: sim.hr.unit,    timestamp: nowIso },
    'SPO2-01':  { sensor_id: 'SPO2-01',  device_id: tripulante.id, value: Math.min(100, Math.max(90, +(sim.spo2.value + drift() * 0.3).toFixed(1))), unit: sim.spo2.unit, timestamp: nowIso },
    'BTEMP-01': { sensor_id: 'BTEMP-01', device_id: tripulante.id, value: +(sim.btemp.value + drift() * 0.05).toFixed(2), unit: sim.btemp.unit, timestamp: nowIso },
  }
}

// ─── Dashboard ──────────────────────────────────────────────────────────────

export default function Dashboard({ auth, setAuth, settingsOpen, setSettingsOpen, authMode }) {
  const { token, username, rol } = auth
  // En modo anonimo no hay sesion que cerrar: el backend no exige credenciales.
  const canLogout = !authMode || authMode.requires_login !== false

  // Estado global de la vista
  const [readings, setReadings] = useState({})
  const [alerts, setAlerts] = useState({})
  // Posiciones iniciales de los 4 tripulantes (offsets del dataset). Se
  // inicializa de forma lazy para que los marcadores existan desde el primer
  // render, sin necesidad de un efecto extra.
  const [locations, setLocations] = useState(() => {
    const baseCoords = getTripulanteBaseCoords()
    const nowIso = new Date().toISOString()
    const map = {}
    TRIPULANTES.forEach(t => {
      map[t.id] = {
        device_id: t.id,
        timestamp: nowIso,
        lat: baseCoords.lat + t.offset[0],
        lon: baseCoords.lon + t.offset[1],
        sequence: 0,
        sexo: t.sexo,
      }
    })
    return map
  })
  const [thresholds, setThresholds] = useState({})
  const [wsStatus, setWsStatus] = useState('connecting')
  const [wsError, setWsError] = useState('')
  const [lastTelemetryAt, setLastTelemetryAt] = useState(null)

  // Estado de interaccion con marcadores
  const [selectedDeviceId, setSelectedDeviceId] = useState(null)
  const [hoveredDeviceId, setHoveredDeviceId] = useState(null)

  const canResolve = rol === 'administrador' || rol === 'control_mision'

  // Los perfiles placeholder reciben datos locales; las claves incluyen
  // tripulante y sensor para evitar que sus sensores homonimos se sobrescriban.
  useEffect(() => {
    const updateSimulatedReadings = () => {
      setReadings(prev => {
        const next = { ...prev }
        const nowIso = new Date().toISOString()
        TRIPULANTES.forEach(t => {
          if (t.streamSource !== 'simulated') return
          const sim = makeSimulatedReadings(t, nowIso)
          Object.values(sim).forEach(reading => {
            next[readingKey(reading)] = reading
          })
        })
        return next
      })
      setLastTelemetryAt(performance.now())
    }

    updateSimulatedReadings()
    const interval = setInterval(updateSimulatedReadings, TELEMETRY_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [])

  // ── Carga inicial: alertas activas + umbrales (admin) ────────────────────
  useEffect(() => {
    let cancelled = false
    fetch(apiUrl('/alerts/active'), { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : [])
      .then(list => {
        if (cancelled) return
        const next = {}
        list.forEach(a => { next[a.id] = a })
        setAlerts(next)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [token])

  useEffect(() => {
    if (rol !== 'administrador') return
    let cancelled = false
    fetch(apiUrl('/admin/thresholds'), { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : [])
      .then(list => {
        if (cancelled) return
        const next = {}
        list.forEach(t => { next[t.sensor_id] = t })
        setThresholds(next)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [token, rol])

  // ── WebSocket: mismo mecanismo que ya existia (type: "location", "reading", "alert") ──
  useEffect(() => {
    const ws = new WebSocket(wsUrl('/ws/readings', { token }))

    ws.onopen = () => { setWsStatus('live'); setWsError('') }
    ws.onmessage = event => {
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'reading' || (!message.type && message.sensor_id)) {
          setLastTelemetryAt(performance.now())
          // Asociamos el device_id EVA-01 con el perfil humano T-03.
          const tripulanteReal = getTripulanteByStreamDevice(message.device_id)
          if (tripulanteReal && ['HR-01', 'SPO2-01', 'BTEMP-01', 'EVA-TEMP-01', 'EVA-HUM-01', 'EVA-PRESS-01'].includes(message.sensor_id)) {
            const reading = { ...message, device_id: tripulanteReal.id }
            setReadings(prev => ({
              ...prev,
              [readingKey(reading)]: reading,
            }))
          } else {
            setReadings(prev => ({ ...prev, [readingKey(message)]: message }))
          }
        } else if (message.type === 'alert') {
          setAlerts(prev => ({ ...prev, [message.id]: message }))
          setReadings(prev => {
            const existing = getReading(prev, message.sensor_id)
            const reading = {
              ...existing,
              ...message,
              sensor_id: message.sensor_id,
              value: message.value,
              timestamp: message.timestamp,
            }
            return { ...prev, [readingKey(reading)]: reading }
          })
        } else if (message.type === 'location' && message.device_id) {
          setLastTelemetryAt(performance.now())
          // MECANISMO YA EXISTENTE — extendido con `sexo`, no reemplazado.
          // Mapeamos EVA-01 → tripulante humano T-03.
          const tripulanteReal = getTripulanteByStreamDevice(message.device_id)
          const targetId = tripulanteReal ? tripulanteReal.id : message.device_id
          setLocations(prev => ({
            ...prev,
            [targetId]: { ...message, device_id: targetId, sexo: tripulanteReal?.sexo ?? message.sexo },
          }))
        }
      } catch {}
    }
    ws.onerror = () => { setWsStatus('error'); setWsError('Error de conexión WebSocket.') }
    ws.onclose = event => {
      // En modo anonimo no hay sesion que cerrar — no se.expulsa al usuario.
      if (event.code === 1008 && canLogout) setAuth(null)
      else setWsStatus('error')
    }
    return () => ws.close()
  }, [token, setAuth, canLogout])

  const handleResolve = useCallback(async alertId => {
    try {
      const response = await fetch(apiUrl(`/alerts/${alertId}/resolve`), {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (response.ok) {
        setAlerts(prev => {
          const next = { ...prev }
          delete next[alertId]
          return next
        })
      }
    } catch {}
  }, [token])

  // ── Handlers de hover y click sobre los marcadores ────────────────────────
  const handleMarkerHover = useCallback(deviceId => setHoveredDeviceId(deviceId), [])
  const handleMarkerLeave = useCallback(() => setHoveredDeviceId(null), [])
  const handleMarkerSelect = useCallback(deviceId => {
    setSelectedDeviceId(prev => (prev === deviceId ? null : deviceId))
  }, [])
  const closePanel = useCallback(() => setSelectedDeviceId(null), [])

  // ── Datos derivados ────────────────────────────────────────────────────────
  const allSensorIds = [...new Set(Object.values(readings).map(reading => reading.sensor_id))]
  const bioIds = sortSensorIds(allSensorIds.filter(sensorId => BIOMETRIC_SENSORS.has(sensorId)))
  const tripulanteTechIds = sortSensorIds(
    allSensorIds.filter(sensorId => ['eva', 'imu'].includes(getSensorMeta(sensorId).group)),
  )

  const activeAlerts = Object.values(alerts)
  const visibleAlerts = rol === 'observador'
    ? activeAlerts.filter(alert => !BIOMETRIC_SENSORS.has(alert.sensor_id))
    : activeAlerts
  const tripulanteAlerts = visibleAlerts.filter(alert => sensorSubject(alert.sensor_id) === 'tripulante')

  // Lista de marcadores: los 4 tripulantes del dataset, en orden.
  const tripulanteMarkers = useMemo(() => TRIPULANTES.map(t => locations[t.id]).filter(Boolean), [locations])

  const hoveredTripulante = hoveredDeviceId ? getTripulante(hoveredDeviceId) : null
  const selectedTripulante = selectedDeviceId ? getTripulante(selectedDeviceId) : null

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      {/* Mapa a pantalla completa (fondo) */}
      <LocationMap
        locations={tripulanteMarkers}
        tripulanteMeta={Object.fromEntries(TRIPULANTES.map(t => [t.id, t.sexo]))}
        tripulanteNombres={Object.fromEntries(TRIPULANTES.map(t => [t.id, t.nombre]))}
        selectedDeviceId={selectedDeviceId}
        onMarkerHover={handleMarkerHover}
        onMarkerLeave={handleMarkerLeave}
        onMarkerSelect={handleMarkerSelect}
        rightInset={selectedTripulante ? 380 : 0}
      />

      {/* Top bar flotante */}
      <div className="live-topbar">
        <div className="live-topbar__cluster">
          <span className={`live-topbar__dot is-${wsStatus === 'live' ? 'ok' : wsStatus === 'error' ? 'error' : 'waiting'}`} />
          <span className="live-topbar__title">
            {wsStatus === 'live' ? 'En vivo' : wsStatus === 'error' ? 'Sin conexión' : 'Conectando…'}
          </span>
          <span className="live-topbar__sub">MISIÓN ATABEY 1 · TRIPULANTES</span>
        </div>

        <TelemetryCountdown lastUpdateAt={lastTelemetryAt} status={wsStatus} />

        <div className="live-topbar__cluster" style={{ gap: '14px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-primary)' }}>{username}</span>
          <span style={{
            fontSize: '10px', letterSpacing: '0.08em',
            color: 'var(--text-secondary)',
            paddingLeft: '14px', borderLeft: '1px solid var(--border-strong)',
          }}>
            {ROL_DISPLAY[rol] ?? rol}
          </span>
          {canLogout && (
            <button onClick={() => setAuth(null)} className="live-logout">Salir</button>
          )}
        </div>
      </div>

      {wsError && (
        <div role="alert" className="eva-map-banner" style={{ top: 80, bottom: 'auto' }}>
          {wsError}
        </div>
      )}

      {/* Hover card con identidad del tripulante */}
      {hoveredTripulante && hoveredDeviceId !== selectedDeviceId && (
        <HoverCard
          tripulante={hoveredTripulante}
          readings={readings}
          thresholds={thresholds}
          tripulanteAlerts={tripulanteAlerts}
        />
      )}

      {/* Right side panel con detalle completo */}
      <aside className={`live-panel${selectedTripulante ? ' is-open' : ''}`} aria-hidden={!selectedTripulante}>
        {selectedTripulante && (
          <TripulanteDetailPanel
            tripulante={selectedTripulante}
            readings={readings}
            bioIds={bioIds}
            techIds={tripulanteTechIds}
            tripulanteAlerts={tripulanteAlerts}
            thresholds={thresholds}
            rol={rol}
            canResolve={canResolve}
            onClose={closePanel}
            onResolve={handleResolve}
          />
        )}
      </aside>

      {/* Settings panel (se abre desde el engranaje en App.jsx) */}
      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        auth={auth}
      />
    </>
  )
}

// ─── HoverCard con identidad del tripulante ─────────────────────────────────

function HoverCard({ tripulante, readings, thresholds, tripulanteAlerts }) {
  const [pos, setPos] = useState(null)
  const tripulanteId = tripulante?.id

  // Proyecta la posicion del tripulante en pixeles via map.project(lngLat).
  // Este es un sync con el mapa (sistema externo), por eso vive en un efecto.
  useEffect(() => {
    let raf = 0
    const tick = () => {
      const map = window.__atabeyMap
      const loc = tripulanteId ? window.__atabeyLastLocations?.[tripulanteId] : null
      if (map && loc) {
        const projected = map.project([loc.lon, loc.lat])
        setPos({ x: projected.x, y: projected.y })
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [tripulanteId])

  if (!pos || !tripulante) return null

  // Lecturas biometricas de ESTE tripulante
  const ownBioIds = ['HR-01', 'SPO2-01', 'BTEMP-01'].filter(sensorId => getReading(readings, sensorId, tripulante.id))

  // Estado del tripulante basado en alertas activas que le pertenecen
  const ownAlerts = tripulanteAlerts.filter(a => getReading(readings, a.sensor_id, tripulante.id))
  let statusLabel = 'Estable'
  let statusSeverity = 'ok'
  if (ownAlerts.some(a => a.severidad === 'critico')) { statusLabel = 'Crítico'; statusSeverity = 'crit' }
  else if (ownAlerts.length > 0) { statusLabel = 'Atención'; statusSeverity = 'alert' }

  const isSimulated = tripulante.streamSource === 'simulated'

  return (
    <div className="eva-hover-card" style={{ left: `${pos.x}px`, top: `${pos.y}px` }} role="tooltip">
      <div className="eva-hover-card__head">
        <span className="eva-hover-card__name">{tripulante.nombre}</span>
        <span className="eva-hover-card__sex">{SEXO_LABEL[tripulante.sexo] ?? '—'}</span>
      </div>

      {ownBioIds.length === 0 ? (
        <div style={{ fontSize: '11px', fontStyle: 'italic', color: 'var(--text-dim)' }}>
          {isSimulated ? 'Generando lecturas simuladas…' : 'Sin lecturas biométricas'}
        </div>
      ) : (
        ownBioIds.map(sensorId => {
          const meta = getSensorMeta(sensorId)
          const reading = getReading(readings, sensorId, tripulante.id)
          const sev = getReadingSeverity(sensorId, reading.value, thresholds)
          return (
            <div key={sensorId} className="eva-hover-card__row">
              <span className="eva-hover-card__label">{meta.label}</span>
              <span className={severityClass(sev, 'eva-hover-card__value')}>
                {Number.isFinite(reading.value) ? reading.value.toFixed(1) : reading.value}
                {meta.unit ? ` ${meta.unit}` : ''}
              </span>
            </div>
          )
        })
      )}

      <div className="eva-hover-card__status">
        <span className="eva-hover-card__statusLabel">Estado general</span>
        <span className={`eva-hover-card__statusValue ${statusSeverity === 'crit' ? 'eva-hover-card__statusValue--crit' : statusSeverity === 'alert' ? 'eva-hover-card__statusValue--alert' : ''}`}>
          {statusLabel}
        </span>
      </div>
    </div>
  )
}

// ─── Panel de detalle ──────────────────────────────────────────────────────

function TripulanteDetailPanel({
  tripulante,
  readings,
  bioIds,
  techIds,
  tripulanteAlerts,
  thresholds,
  rol,
  canResolve,
  onClose,
  onResolve,
}) {
  const isObservador = rol === 'observador'
  const isSimulated = tripulante.streamSource === 'simulated'

  const ownBioIds = bioIds.filter(sensorId => getReading(readings, sensorId, tripulante.id))
  const ownTechIds = techIds.filter(sensorId => getReading(readings, sensorId, tripulante.id))
  const ownAlerts = tripulanteAlerts.filter(a => getReading(readings, a.sensor_id, tripulante.id))

  return (
    <>
      <header className="live-panel__header">
        <div className="live-panel__title">
          <span className="live-panel__name">{tripulante.nombre}</span>
          <span className="live-panel__id">
            {tripulante.id} · {SEXO_LABEL[tripulante.sexo] ?? '—'}
          </span>
          <span className="live-panel__sub">
            {isSimulated
              ? 'Datos simulados en cliente (placeholder)'
                : getTripulanteSourceLabel(tripulante)}
          </span>
        </div>
        <button onClick={onClose} className="live-panel__close" aria-label="Cerrar panel" title="Cerrar">×</button>
      </header>

      <div className="live-panel__body">
        <div className="live-panel__group">
          <div className="live-panel__groupHead">
            <span className="live-panel__groupTitle">Posición</span>
            <span className="live-panel__groupSub">{getTripulanteSourceLabel(tripulante)}</span>
          </div>
          {isSimulated ? (
            <p className="live-panel__empty">
              Posición fija con offset respecto al sitio de la misión (placeholder).
            </p>
          ) : null}
        </div>

        <div className="live-panel__group">
          <div className="live-panel__groupHead">
            <span className="live-panel__groupTitle">Signos vitales</span>
            <span className="live-panel__groupSub">{ownBioIds.length} sensores</span>
          </div>
          {isObservador ? (
            <div className="live-panel__restricted">
              <span className="live-panel__restrictedIcon">⊘</span>
              <span className="live-panel__restrictedMsg">Sin acceso a datos biométricos — rol Observador</span>
              <span className="live-panel__restrictedSub">Requiere Administrador o Control de Misión.</span>
            </div>
          ) : ownBioIds.length === 0 ? (
            <p className="live-panel__empty">Esperando lecturas biométricas…</p>
          ) : (
            ownBioIds.map(sensorId => (
              <ReadingRow
                key={sensorId}
                sensorId={sensorId}
                reading={getReading(readings, sensorId, tripulante.id)}
                thresholds={thresholds}
                activeAlert={ownAlerts.find(a => a.sensor_id === sensorId)}
              />
            ))
          )}
        </div>

        <div className="live-panel__group">
          <div className="live-panel__groupHead">
            <span className="live-panel__groupTitle">Soporte EVA + IMU</span>
            <span className="live-panel__groupSub">{ownTechIds.length} sensores</span>
          </div>
          {ownTechIds.length === 0 ? (
            <p className="live-panel__empty">
              {isSimulated
                ? 'Sin telemetría EVA (placeholder).'
                : 'Esperando lecturas EVA/IMU…'}
            </p>
          ) : (
            ownTechIds.map(sensorId => (
              <ReadingRow
                key={sensorId}
                sensorId={sensorId}
                reading={getReading(readings, sensorId, tripulante.id)}
                thresholds={thresholds}
                activeAlert={ownAlerts.find(a => a.sensor_id === sensorId)}
              />
            ))
          )}
        </div>

        <div className="live-panel__group">
          <div className="live-panel__groupHead">
            <span className="live-panel__groupTitle">Alertas</span>
            <span className="live-panel__groupSub">{ownAlerts.length} activas</span>
          </div>
          {isObservador ? (
            <p className="live-panel__empty">Las alertas biométricas no son visibles para Observador.</p>
          ) : ownAlerts.length === 0 ? (
            <p className="live-panel__empty">Sin alertas activas para este tripulante.</p>
          ) : (
            <div className="live-panel__alerts">
              {ownAlerts.map(alert => (
                <AlertRow key={alert.id} alert={alert} canResolve={canResolve} onResolve={onResolve} />
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  )
}

function ReadingRow({ sensorId, reading, thresholds, activeAlert }) {
  const meta = getSensorMeta(sensorId)
  const isAlive = !!reading

  let sev = 'ok'
  if (activeAlert) sev = activeAlert.severidad === 'critico' ? 'crit' : 'alert'
  else if (thresholds[sensorId] && reading) sev = getReadingSeverity(sensorId, reading.value, thresholds)

  return (
    <div className="live-panel__row">
      <span className="live-panel__rowLabel">{meta.label}</span>
      {isAlive ? (
        <>
          <span className={severityClass(sev, 'live-panel__rowValue')}>
            {Number.isFinite(reading.value) ? reading.value.toFixed(1) : reading.value}
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            {meta.unit && <span className="live-panel__rowUnit">{meta.unit}</span>}
            <span className={`live-panel__rowStatus is-${sev === 'crit' ? 'crit' : sev === 'alert' ? 'alert' : 'ok'}`} />
          </span>
        </>
      ) : (
        <>
          <span className="live-panel__rowValue" style={{ color: 'var(--text-dim)' }}>—</span>
          <span className="live-panel__rowUnit" />
        </>
      )}
    </div>
  )
}

function AlertRow({ alert, canResolve, onResolve }) {
  const meta = getSensorMeta(alert.sensor_id)
  const isCrit = alert.severidad === 'critico'
  return (
    <div className={`live-panel__alert ${isCrit ? 'live-panel__alert--crit' : 'live-panel__alert--warn'}`}>
      <div>
        <div className="live-panel__alertName">{meta.label}</div>
        <div className="live-panel__alertDetail">
          <span style={{ color: isCrit ? 'var(--accent-crit)' : 'var(--accent-alert)' }}>
            {typeof alert.value === 'number' ? alert.value.toFixed(2) : alert.value}
          </span>
          {' '}fuera de{' '}
          <span>[{alert.valor_min}, {alert.valor_max}]</span>
          {meta.unit && <span> {meta.unit}</span>}
        </div>
        <div className="live-panel__alertTs">
          {new Date(alert.timestamp).toLocaleTimeString('es-DO', { hour12: false })}
        </div>
      </div>
      {canResolve && (
        <button onClick={() => onResolve(alert.id)} className="live-panel__resolve" title="Marcar como resuelta">
          Resolver
        </button>
      )}
    </div>
  )
}

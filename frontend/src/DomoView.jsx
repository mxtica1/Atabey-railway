import { useState, useEffect } from 'react'
import { wsUrl } from './config'
import TelemetryCountdown from './TelemetryCountdown'

/**
 * Vista del domo geodésico. Mantiene el mismo feed WebSocket que la vista de
 * tripulantes (para no duplicar conexiones), pero renderiza una sidebar con
 * los 7 campos del diccionario de datos original del proyecto.
 *
 * Los nombres, unidades y descripciones vienen exactos del prompt — algunos
 * son atipicos (Hz para humedad, N para humedad del suelo, mW/cm² para luz
 * UV) y se respetan tal cual.
 */

const DOMO_FIELDS = [
  {
    key:       'temperatura_aire',
    label:     'Temperatura del Aire',
    unit:      '°C',
    desc:      'Temperatura ambiental de la planta',
    sensorId:  'TEMP-01',
  },
  {
    key:       'humedad_aire',
    label:     'Humedad del Aire',
    unit:      'Hz',
    desc:      'Humedad ambiental de la planta',
    sensorId:  'HUM-01',
  },
  {
    key:       'humedad_suelo',
    label:     'Humedad del Suelo',
    unit:      'N',
    desc:      'Humedad local del suelo en las raíces',
    // Se promedian los 3 sensores de suelo para mostrar un valor unico.
    sensorIds: ['SOIL-HUM-01', 'SOIL-HUM-02', 'SOIL-HUM-03'],
  },
  {
    key:       'concentracion_gas',
    label:     'Concentración de Gas',
    unit:      'ppm',
    desc:      'Calidad de aire (CO₂/O₂)',
    sensorId:  'CO2-01',
  },
  {
    key:       'luz_ambiental',
    label:     'Luz Ambiental',
    unit:      'mW/cm²',
    desc:      'Intensidad UV (240–370 nm)',
    sensorId:  'LUX-01',
  },
  {
    key:       'nutrientes_suelo',
    label:     'Nutrientes del Suelo (N, P, K)',
    unit:      'mg/kg',
    desc:      'Macronutrientes del suelo',
    // Se muestran los 3 valores por separado bajo una sola entrada.
    sensorIds: ['NPK-N-01', 'NPK-P-01', 'NPK-K-01'],
  },
  {
    key:       'imagenes_planta',
    label:     'Imágenes de la planta',
    unit:      '—',
    desc:      'Frame de la cámara en vivo',
    camera:    true,
  },
]

export default function DomoView({ auth, setAuth }) {
  const { token } = auth

  const [readings, setReadings] = useState({})
  const [wsStatus, setWsStatus] = useState('connecting')
  const [lastTelemetryAt, setLastTelemetryAt] = useState(null)

  // ── WebSocket: reutiliza el mismo feed que la vista de tripulantes ──────
  useEffect(() => {
    const ws = new WebSocket(wsUrl('/ws/readings', { token }))

    ws.onopen = () => setWsStatus('live')
    ws.onmessage = event => {
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'reading' || (!message.type && message.sensor_id)) {
          setLastTelemetryAt(performance.now())
          setReadings(prev => ({ ...prev, [message.sensor_id]: message }))
        }
        // Los mensajes 'alert' y 'location' no aplican a la vista del domo.
      } catch {}
    }
    ws.onerror = () => setWsStatus('error')
    ws.onclose = event => {
      if (event.code === 1008) setAuth(null)
      else setWsStatus('error')
    }
    return () => ws.close()
  }, [token, setAuth])

  return (
    <div className="domo-shell">
      <div className="domo-stage">
        <div className="domo-stage__placeholder">
          Vista 3D del domo geodésico
          <br />
          <span style={{ fontSize: '11px', opacity: 0.7 }}>
            WS: {wsStatus === 'live' ? 'en vivo' : wsStatus === 'error' ? 'sin conexión' : 'conectando…'}
          </span>
        </div>
      </div>

      <DomoSidebar readings={readings} lastTelemetryAt={lastTelemetryAt} wsStatus={wsStatus} />
    </div>
  )
}

function DomoSidebar({ readings, lastTelemetryAt, wsStatus }) {
  return (
    <aside className="domo-sidebar" aria-label="Telemetría del domo">
      <header className="domo-sidebar__header">
        <div className="domo-sidebar__title">Telemetría del Domo</div>
        <div className="domo-sidebar__sub">7 campos · diccionario original</div>
        <TelemetryCountdown lastUpdateAt={lastTelemetryAt} status={wsStatus} />
      </header>
      <div className="domo-sidebar__body">
        {DOMO_FIELDS.map(field => (
          <DomoField key={field.key} field={field} readings={readings} />
        ))}
      </div>
    </aside>
  )
}

function DomoField({ field, readings }) {
  if (field.camera) return <CameraField field={field} />

  // Nutrients se renderiza especialmente (3 sub-valores).
  if (field.sensorIds && field.label.startsWith('Nutrientes')) {
    return (
      <div className="domo-field">
        <div className="domo-field__head">
          <span className="domo-field__label">{field.label}</span>
          <span className="domo-field__unit">{field.unit}</span>
        </div>
        <div className="domo-field__desc">{field.desc}</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 8 }}>
          {field.sensorIds.map(sensorId => {
            const reading = readings[sensorId]
            return (
              <div key={sensorId} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '10px',
                  letterSpacing: '0.06em',
                  color: 'var(--text-dim)',
                  textTransform: 'uppercase',
                }}>
                  {sensorId.replace('NPK-', '').replace('-01', '')}
                </span>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '14px',
                  fontWeight: 500,
                  color: reading ? 'var(--text-primary)' : 'var(--text-dim)',
                }}>
                  {reading ? `${Number(reading.value).toFixed(1)} ${field.unit}` : '—'}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  // Humedad del suelo se promedia de los 3 sensores.
  if (field.sensorIds) {
    const values = field.sensorIds.map(id => readings[id]?.value).filter(v => typeof v === 'number')
    const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null
    return (
      <div className="domo-field">
        <div className="domo-field__head">
          <span className="domo-field__label">{field.label}</span>
          <span className="domo-field__unit">{field.unit}</span>
        </div>
        <div className="domo-field__desc">{field.desc}</div>
        <div className="domo-field__value">
          {avg !== null ? `${avg.toFixed(1)} ${field.unit}` : <span className="domo-field__value--placeholder">Sin lecturas</span>}
        </div>
      </div>
    )
  }

  // Sensor unico
  const reading = readings[field.sensorId]
  return (
    <div className="domo-field">
      <div className="domo-field__head">
        <span className="domo-field__label">{field.label}</span>
        <span className="domo-field__unit">{field.unit}</span>
      </div>
      <div className="domo-field__desc">{field.desc}</div>
      <div className="domo-field__value">
        {reading ? `${Number(reading.value).toFixed(1)} ${field.unit}` : <span className="domo-field__value--placeholder">Sin lecturas</span>}
      </div>
    </div>
  )
}

function CameraField({ field }) {
  return (
    <div className="domo-field">
      <div className="domo-field__head">
        <span className="domo-field__label">{field.label}</span>
        <span className="domo-field__unit">{field.unit}</span>
      </div>
      <div className="domo-field__desc">{field.desc}</div>
      <div className="domo-camera">
        <span style={{ fontSize: '20px', color: 'var(--text-dim)' }}>⌖</span>
        <span className="domo-camera__label">Cámara no integrada</span>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '10px',
          color: 'var(--text-dim)',
          letterSpacing: '0.04em',
        }}>
          módulo aparte
        </span>
      </div>
    </div>
  )
}

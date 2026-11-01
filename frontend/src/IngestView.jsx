import { useState, useEffect, useCallback } from 'react'
import { apiUrl, wsUrl } from './config'

/**
 * Vista del REGISTRO DE INGESTA.
 *
 * Muestra, para cada lectura guardada por el servidor:
 *   - de que sensor vino (sensor_id + nombre del catalogo)
 *   - cuando lo midio el sensor (timestamp)
 *   - cuando se guardo en la computadora (received_at)
 *   - a que envio/buffer pertenecia (buffer_id)
 *
 * Se actualiza por polling y tambien en vivo por WebSocket (type="ingest").
 */
export default function IngestView({ auth, setAuth }) {
  const { token } = auth

  const [summary, setSummary] = useState(null)
  const [catalog, setCatalog] = useState({})
  const [wsStatus, setWsStatus] = useState('connecting')
  const [lastIngest, setLastIngest] = useState(null)

  // ── Carga del registro + catalogo ────────────────────────────────────────
  const load = useCallback(async () => {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : {}
      const [ingestRes, catalogRes] = await Promise.all([
        fetch(apiUrl('/ingest/recent?limit=200'), { headers }),
        fetch(apiUrl('/sensors/catalog'), { headers }),
      ])
      if (ingestRes.ok) setSummary(await ingestRes.json())
      if (catalogRes.ok) {
        const data = await catalogRes.json()
        const map = {}
        data.devices.forEach(d => d.sensors.forEach(s => { map[s.sensor_id] = s }))
        setCatalog(map)
      }
    } catch {}
  }, [token])

  useEffect(() => {
    load()
    const interval = setInterval(load, 5000)
    return () => clearInterval(interval)
  }, [load])

  // ── Actualizacion en vivo ────────────────────────────────────────────────
  useEffect(() => {
    const params = token ? { token } : {}
    const ws = new WebSocket(wsUrl('/ws/readings', params))
    ws.onopen = () => setWsStatus('live')
    ws.onmessage = event => {
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'ingest') {
          setLastIngest(message)
          load()
        }
      } catch {}
    }
    ws.onerror = () => setWsStatus('error')
    ws.onclose = event => {
      if (event.code === 1008) setAuth(null)
      else setWsStatus('error')
    }
    return () => ws.close()
  }, [token, setAuth, load])

  const records = summary?.records ?? []
  const buffers = summary?.buffers ?? []

  return (
    <div className="ingest-shell">
      <header className="ingest-header">
        <div>
          <h1 className="ingest-title">Registro de ingesta</h1>
          <p className="ingest-sub">
            Qué se guardó, de qué sensor vino y cuándo. Total: {summary?.total ?? 0} registros
          </p>
        </div>
        <div className="ingest-header__status">
          <span className={`live-topbar__dot is-${wsStatus === 'live' ? 'ok' : wsStatus === 'error' ? 'error' : 'waiting'}`} />
          <span>{wsStatus === 'live' ? 'En vivo' : wsStatus === 'error' ? 'Sin conexión' : 'Conectando…'}</span>
        </div>
      </header>

      {lastIngest && (
        <div className="ingest-banner">
          <strong>Último buffer recibido:</strong> {lastIngest.buffer_id} · {lastIngest.accepted} lecturas ·{' '}
          {new Date(lastIngest.received_at).toLocaleString('es-DO', { hour12: false })}
        </div>
      )}

      <div className="ingest-grid">
        <section className="ingest-card ingest-card--wide">
          <div className="ingest-card__head">
            <span className="live-panel__groupTitle">Lecturas guardadas</span>
            <span className="live-panel__groupSub">{records.length}</span>
          </div>
          <div className="ingest-table-wrap">
            <table className="ingest-table">
              <thead>
                <tr>
                  <th>Sensor</th>
                  <th>Variable</th>
                  <th>Valor</th>
                  <th>Medido</th>
                  <th>Guardado</th>
                  <th>Buffer</th>
                </tr>
              </thead>
              <tbody>
                {records.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="ingest-empty">
                      Todavía no hay lecturas guardadas. Envía un buffer para verlas aquí.
                    </td>
                  </tr>
                ) : records.map(record => {
                  const entry = catalog[record.sensor_id]
                  return (
                    <tr key={record.id}>
                      <td className="ingest-mono">{record.sensor_id}</td>
                      <td>{entry?.nombre ?? '—'}</td>
                      <td className="ingest-mono ingest-mono--value">
                        {record.value}
                        <span className="ingest-unit">{record.unit}</span>
                      </td>
                      <td className="ingest-mono ingest-mono--dim">
                        {new Date(record.timestamp).toLocaleString('es-DO', { hour12: false })}
                      </td>
                      <td className="ingest-mono">
                        {new Date(record.received_at).toLocaleString('es-DO', { hour12: false })}
                      </td>
                      <td className="ingest-mono ingest-mono--dim">{record.buffer_id ?? '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>

        <section className="ingest-card">
          <div className="ingest-card__head">
            <span className="live-panel__groupTitle">Envíos (buffers)</span>
            <span className="live-panel__groupSub">{buffers.length}</span>
          </div>
          <div className="ingest-buffers">
            {buffers.length === 0 ? (
              <p className="live-panel__empty">Sin buffers recibidos todavía.</p>
            ) : buffers.map(buffer => (
              <div key={buffer.buffer_id} className="ingest-buffer">
                <div className="ingest-buffer__id">{buffer.buffer_id}</div>
                <div className="ingest-buffer__meta">
                  {buffer.device_id} · {buffer.readings} lecturas
                </div>
                <div className="ingest-buffer__meta ingest-mono--dim">
                  {new Date(buffer.received_at).toLocaleString('es-DO', { hour12: false })}
                </div>
                <div className="ingest-buffer__sensors">
                  {buffer.sensors.map(sensorId => (
                    <span key={sensorId} className="ingest-chip">{sensorId}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}

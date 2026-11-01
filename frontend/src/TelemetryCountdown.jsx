import { useEffect, useState } from 'react'

export const TELEMETRY_INTERVAL_MS = 5000

function formatDuration(milliseconds) {
  return `${(Math.abs(milliseconds) / 1000).toFixed(1)} s`
}

export default function TelemetryCountdown({ lastUpdateAt, status }) {
  const [now, setNow] = useState(0)

  useEffect(() => {
    const updateClock = () => setNow(performance.now())
    updateClock()
    const interval = setInterval(updateClock, 100)
    return () => clearInterval(interval)
  }, [])

  let label = 'Esperando telemetría'
  let detail = 'Cadencia nominal · 5 s'
  let state = status === 'error' ? 'error' : 'waiting'

  if (lastUpdateAt !== null) {
    const remainingMs = TELEMETRY_INTERVAL_MS - Math.max(0, now - lastUpdateAt)
    state = status === 'error' ? 'error' : remainingMs > 0 ? 'countdown' : 'late'
    label = remainingMs > 0 ? 'Próximo dato' : 'Atraso'
    detail = formatDuration(remainingMs)
  }

  return (
    <div className={`telemetry-countdown is-${state}`} role="timer" aria-label={`${label}: ${detail}`}>
      <span className="telemetry-countdown__label">{label}</span>
      <span className="telemetry-countdown__value">{detail}</span>
      <span className="telemetry-countdown__cadence">Cadencia nominal · 5 s</span>
    </div>
  )
}

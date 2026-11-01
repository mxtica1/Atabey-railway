import { useState } from 'react'
import { apiUrl } from './config'

function decodeJwtPayload(token) {
  try {
    const base64Url = token.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const json = decodeURIComponent(
      atob(base64).split('').map(c => '%' + c.charCodeAt(0).toString(16).padStart(2, '0')).join('')
    )
    return JSON.parse(json)
  } catch { return {} }
}

export default function Login({ setAuth }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  const handleLogin = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await fetch(apiUrl('/auth/login'), {
        method:  'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body:    new URLSearchParams({ username, password }),
      })
      if (!res.ok) throw new Error('Credenciales incorrectas')
      const data    = await res.json()
      const payload = decodeJwtPayload(data.access_token)
      setAuth({ token: data.access_token, username: payload.sub ?? username, rol: payload.rol ?? 'observador' })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={s.page}>
      <div style={s.gridOverlay} aria-hidden="true" />

      <main style={s.card}>
        <header style={s.brandHeader}>
          <div style={s.brandRow}>
            <span style={s.brandMark}>A1</span>
            <span style={s.brandTag}>MISIÓN ATABEY 1</span>
          </div>
          <h1 style={s.title}>Control de Misión</h1>
          <p style={s.subtitle}>
            Sistema de telemetría análoga espacial dominicana.
            Monitoreo en tiempo real de domo y tripulante.
          </p>
        </header>

        <section style={s.formSection}>
          <p style={s.sectionLabel}>AUTENTICACIÓN</p>
          <h2 style={s.sectionTitle}>Acceso al sistema</h2>

          <form onSubmit={handleLogin} style={s.form}>
            <div style={s.field}>
              <label style={s.label} htmlFor="username">Usuario</label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
                autoComplete="username"
                className="auth-input"
                placeholder="nombre de usuario"
              />
            </div>

            <div style={s.field}>
              <label style={s.label} htmlFor="password">Contraseña</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="auth-input"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div role="alert" style={s.error}>
                <span style={s.errorIcon}>!</span>
                <span>{error}</span>
              </div>
            )}

            <button type="submit" disabled={loading} className="auth-btn">
              {loading ? 'Verificando…' : 'Ingresar'}
            </button>
          </form>
        </section>

        <footer style={s.statusFooter}>
          <span style={s.statusDot} />
          <span style={s.statusText}>Sistema operacional</span>
        </footer>
      </main>
    </div>
  )
}

const s = {
  page: {
    position: 'relative',
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '32px 24px',
    background: 'var(--bg-base)',
    fontFamily: 'var(--font-ui)',
    color: 'var(--text-primary)',
    overflow: 'hidden',
  },
  // Cuadrícula sutil para que el fondo no se vea plano (sin color decorativo).
  gridOverlay: {
    position: 'absolute',
    inset: 0,
    pointerEvents: 'none',
    backgroundImage:
      'linear-gradient(var(--hairline) 1px, transparent 1px), ' +
      'linear-gradient(90deg, var(--hairline) 1px, transparent 1px)',
    backgroundSize: '48px 48px',
    maskImage: 'radial-gradient(ellipse at center, rgba(0,0,0,0.6), transparent 75%)',
    WebkitMaskImage: 'radial-gradient(ellipse at center, rgba(0,0,0,0.6), transparent 75%)',
    opacity: 0.6,
  },
  card: {
    position: 'relative',
    width: '100%',
    maxWidth: '420px',
    background: 'var(--bg-surface)',
    border: '1px solid var(--border-strong)',
    borderRadius: '2px',
    padding: '40px 36px 28px',
    boxShadow: '0 32px 80px rgba(0, 0, 0, 0.55)',
  },

  // Branding
  brandHeader: { marginBottom: '36px' },
  brandRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginBottom: '24px',
  },
  brandMark: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '32px',
    height: '32px',
    border: '1px solid var(--text-primary)',
    color: 'var(--text-primary)',
    fontFamily: 'var(--font-mono)',
    fontSize: '12px',
    fontWeight: 600,
    letterSpacing: '0.04em',
  },
  brandTag: {
    fontSize: '10px',
    fontWeight: 600,
    letterSpacing: '0.18em',
    color: 'var(--text-secondary)',
  },
  title: {
    margin: '0 0 10px',
    fontSize: '30px',
    fontWeight: 600,
    lineHeight: 1.1,
    letterSpacing: '-0.025em',
    color: 'var(--text-primary)',
  },
  subtitle: {
    margin: 0,
    fontSize: '13px',
    color: 'var(--text-secondary)',
    lineHeight: 1.6,
  },

  // Form
  formSection: {
    paddingTop: '24px',
    borderTop: '1px solid var(--border)',
  },
  sectionLabel: {
    margin: '0 0 6px',
    fontSize: '10px',
    fontWeight: 600,
    letterSpacing: '0.18em',
    color: 'var(--text-dim)',
  },
  sectionTitle: {
    margin: '0 0 22px',
    fontSize: '16px',
    fontWeight: 600,
    letterSpacing: '-0.01em',
    color: 'var(--text-primary)',
  },
  form: { display: 'flex', flexDirection: 'column', gap: '18px' },
  field: { display: 'flex', flexDirection: 'column', gap: '6px' },
  label: { fontSize: '12px', fontWeight: 500, color: 'var(--text-secondary)', letterSpacing: '0.02em' },
  error: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '10px 12px',
    background: 'var(--bg-elevated)',
    border: '1px solid var(--text-primary)',
    borderRadius: '2px',
    color: 'var(--text-primary)',
    fontSize: '13px',
  },
  errorIcon: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '18px',
    height: '18px',
    border: '1px solid var(--text-primary)',
    borderRadius: '50%',
    fontFamily: 'var(--font-mono)',
    fontSize: '11px',
    flexShrink: 0,
  },

  // Footer
  statusFooter: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginTop: '28px',
    paddingTop: '20px',
    borderTop: '1px solid var(--border)',
  },
  statusDot: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    background: 'var(--text-primary)',
    flexShrink: 0,
  },
  statusText: {
    fontSize: '11px',
    color: 'var(--text-secondary)',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.04em',
  },
}

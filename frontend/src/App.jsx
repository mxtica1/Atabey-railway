import { useState, useEffect } from 'react'
import Login from './Login'
import Dashboard from './Dashboard'
import DomoView from './DomoView'
import IngestView from './IngestView'
import { apiUrl } from './config'

/**
 * Raíz de la aplicacion. Maneja:
 *  - modo de autenticacion (login requerido vs acceso directo)
 *  - navegacion entre la vista de tripulantes (mapa en vivo), el domo y la ingesta
 *  - apertura/cierre del panel de configuracion (incluye toggle de tema)
 */
function App() {
  const [auth, setAuth] = useState(null)
  const [authMode, setAuthMode] = useState(null)   // null = cargando
  const [view, setView] = useState('tripulantes')   // 'tripulantes' | 'domo' | 'ingesta'
  const [settingsOpen, setSettingsOpen] = useState(false)

  // El backend es la fuente de verdad del modo de acceso: si no exige login,
  // se entra directo con el rol por defecto (modo pruebas con sensores).
  useEffect(() => {
    let cancelled = false
    fetch(apiUrl('/auth/mode'))
      .then(r => r.ok ? r.json() : null)
      .then(mode => {
        if (cancelled) return
        if (mode && mode.requires_login === false) {
          setAuth({ token: '', username: mode.default_username, rol: mode.default_rol })
        }
        setAuthMode(mode ?? { requires_login: true, default_rol: 'observador', default_username: 'anonimo' })
      })
      .catch(() => {
        if (cancelled) return
        // Sin backend no se puede saber el modo: se pide login.
        setAuthMode({ requires_login: true, default_rol: 'observador', default_username: 'anonimo' })
      })
    return () => { cancelled = true }
  }, [])

  // Splash mientras se consulta el modo de acceso.
  if (authMode === null) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', background: 'var(--bg-base)', color: 'var(--text-dim)',
        fontFamily: 'var(--font-mono)', fontSize: 12, letterSpacing: '0.08em',
      }}>
        CARGANDO CONTROL DE MISIÓN…
      </div>
    )
  }

  if (!auth) {
    return <Login setAuth={setAuth} />
  }

  const goTo = next => { setView(next); setSettingsOpen(false) }

  return (
    <div className="live-shell">
      {/* Sidebar de navegacion (visible en todas las vistas autenticadas) */}
      <nav className="live-sidebar" aria-label="Navegación principal">
        <div className="live-sidebar__logo" title="Misión Atabey 1">A1</div>
        <div className="live-sidebar__nav">
          <SidebarIcon active={view === 'tripulantes'} onClick={() => goTo('tripulantes')} title="Tripulantes">
            <svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4" /><path d="M4 21v-1a8 8 0 0 1 16 0v1" /></svg>
          </SidebarIcon>
          <SidebarIcon active={view === 'domo'} onClick={() => goTo('domo')} title="Domo">
            <svg viewBox="0 0 24 24"><path d="M3 12 12 4l9 8" /><path d="M5 11v9h14v-9" /><path d="M5 14h14" /></svg>
          </SidebarIcon>
          <SidebarIcon active={view === 'ingesta'} onClick={() => goTo('ingesta')} title="Registro de ingesta">
            <svg viewBox="0 0 24 24">
              <ellipse cx="12" cy="5" rx="8" ry="3" />
              <path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5" />
              <path d="M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3" />
            </svg>
          </SidebarIcon>
        </div>
        <div className="live-sidebar__spacer" />
        <SidebarIcon active={settingsOpen} onClick={() => setSettingsOpen(prev => !prev)} title="Configuración">
          <svg viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06A2 2 0 1 1 4.27 16.9l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06A2 2 0 1 1 7.1 4.27l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06A2 2 0 1 1 19.73 7.1l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
          </svg>
        </SidebarIcon>
      </nav>

      {/* Vista activa */}
      {view === 'tripulantes' && (
        <Dashboard
          auth={auth}
          setAuth={setAuth}
          settingsOpen={settingsOpen}
          setSettingsOpen={setSettingsOpen}
          authMode={authMode}
        />
      )}
      {view === 'domo' && <DomoView auth={auth} setAuth={setAuth} />}
      {view === 'ingesta' && <IngestView auth={auth} setAuth={setAuth} />}
    </div>
  )
}

function SidebarIcon({ active, onClick, title, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={title}
      aria-pressed={active}
      className={`live-sidebar__item${active ? ' is-active' : ''}`}
    >
      {children}
    </button>
  )
}

export default App

import { useTheme } from './hooks/useTheme'

/**
 * Panel de configuracion. Se abre desde el icono de engranaje del sidebar.
 * Implementa el selector de tema claro/oscuro (persistido en localStorage
 * via useTheme) y un placeholder para futuras opciones.
 */
export default function SettingsPanel({ open, onClose, auth }) {
  const { theme, setTheme } = useTheme()

  return (
    <aside
      className={`live-settings${open ? ' is-open' : ''}`}
      aria-hidden={!open}
      aria-label="Configuración"
    >
      <header className="live-settings__header">
        <span className="live-settings__title">Configuración</span>
        <button onClick={onClose} className="live-panel__close" aria-label="Cerrar configuración" title="Cerrar">×</button>
      </header>

      <div className="live-settings__body">
        <div className="live-settings__row">
          <div>
            <div className="live-settings__rowLabel">Tema de la interfaz</div>
            <div className="live-settings__rowHint">Se aplica a toda la app y persiste tras recargar.</div>
          </div>
          <div className="theme-toggle" role="group" aria-label="Tema">
            <button
              type="button"
              className={`theme-toggle__btn${theme === 'dark' ? ' is-active' : ''}`}
              onClick={() => setTheme('dark')}
              aria-pressed={theme === 'dark'}
            >Oscuro</button>
            <button
              type="button"
              className={`theme-toggle__btn${theme === 'light' ? ' is-active' : ''}`}
              onClick={() => setTheme('light')}
              aria-pressed={theme === 'light'}
            >Claro</button>
          </div>
        </div>

        <div className="live-settings__row">
          <div>
            <div className="live-settings__rowLabel">Sesión activa</div>
            <div className="live-settings__rowHint">
              {auth?.username ?? '—'} · {auth?.rol ?? '—'}
            </div>
          </div>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            color: 'var(--text-secondary)',
            letterSpacing: '0.04em',
          }}>
            MISIÓN ATABEY 1
          </div>
        </div>
      </div>
    </aside>
  )
}

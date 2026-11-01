import { useState, useEffect, useCallback } from 'react'

const THEME_KEY = 'atabey.theme'

function readPersistedTheme() {
  try {
    const saved = localStorage.getItem(THEME_KEY)
    return saved === 'light' || saved === 'dark' ? saved : 'dark'
  } catch {
    return 'dark'
  }
}

/**
 * Hook que expone el tema activo y un setter. La preferencia se guarda en
 * localStorage y se refleja en el atributo `data-theme` del elemento raiz
 * (controlado por CSS en index.css).
 */
export function useTheme() {
  const [theme, setThemeState] = useState(readPersistedTheme)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    try { localStorage.setItem(THEME_KEY, theme) } catch {}
  }, [theme])

  const setTheme = useCallback(next => {
    if (next !== 'light' && next !== 'dark') return
    setThemeState(next)
  }, [])

  const toggleTheme = useCallback(() => {
    setThemeState(prev => (prev === 'dark' ? 'light' : 'dark'))
  }, [])

  return { theme, setTheme, toggleTheme }
}

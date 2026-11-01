import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'maplibre-gl/dist/maplibre-gl.css'
// Geist Sans — fuente principal de la app (instalada via @fontsource/geist-sans).
import '@fontsource/geist-sans/400.css'
import '@fontsource/geist-sans/500.css'
import '@fontsource/geist-sans/600.css'
import '@fontsource/geist-sans/700.css'
import './index.css'
import App from './App.jsx'

// Aplica el tema persistido antes del primer paint para evitar el flash.
// Default: 'dark'. La preferencia se guarda en localStorage bajo 'atabey.theme'.
const THEME_KEY = 'atabey.theme'
const initialTheme = (() => {
  try {
    return localStorage.getItem(THEME_KEY) || 'dark'
  } catch {
    return 'dark'
  }
})()
document.documentElement.setAttribute('data-theme', initialTheme)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

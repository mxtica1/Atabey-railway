import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    // MapLibre GL JS >= v6 trae un worker ESM separado que rompe al ser
    // pre-empaquetado por Vite (404 en `.vite/deps/maplibre-gl-worker.mjs`).
    // El fix principal es `setWorkerUrl` con `?worker&url` en LocationMap.jsx;
    // excluirlo del optimizer es un respaldo que ademas acelera el dev server.
    exclude: ['maplibre-gl'],
  },
  preview: {
    allowedHosts: ['atabey-frontend.onrender.com', 'localhost'],
  },
})

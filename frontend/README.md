# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and Oxlint's TypeScript related rules in your project.
# Atabey Frontend

Para iniciar el frontend localmente:

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Luego abre http://localhost:5173 en tu navegador.

Variables de entorno:

- `VITE_API_BASE_URL`: base HTTP del backend FastAPI.
- `VITE_WS_BASE_URL`: base WebSocket del backend.
- `VITE_CARTO_API_KEY`: API key de CARTO Basemaps para usar Dark Matter sin watermark.

## Fuentes de datos y actualización

En la vista de tripulantes, Geisy Camilo (T-01), Alba Vasquez (T-02) y Ángel Peña (T-04) muestran datos biométricos generados en el navegador. Eduardo Ortega (T-03) recibe el stream `EVA-01` por WebSocket; actualmente ese stream también es simulado, por `EvaReceiverSim` en el gateway, y no proviene de sensores físicos.

El indicador de actualización muestra una cuenta regresiva basada en la cadencia nominal de telemetría de 5 segundos. Los datos se actualizan por WebSocket al llegar cada mensaje; el contador no realiza consultas periódicas adicionales al backend. Si no llegan mensajes dentro de esa cadencia, indica cuánto tiempo lleva atrasado el siguiente dato esperado.

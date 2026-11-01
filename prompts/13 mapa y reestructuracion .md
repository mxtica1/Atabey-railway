# Prompt — Módulo 13: mapa de posición + reestructuración del dashboard (frontend)

Lee `AGENTS.md` en la raíz del repo antes de empezar. Respeta el contrato de datos, el stack técnico y la paleta/tipografía del módulo 11.

## Objetivo
Reestructurar el frontend en dos columnas — mapa a la izquierda con la posición en vivo del/los tripulante(s), paneles agrupados por sujeto (Tripulante / Domo) a la derecha — usando MapLibre GL JS. Al terminar, un punto debe moverse en el mapa sin recargar la página cuando llega una nueva coordenada, y toda la información de cada sujeto debe estar junta, no dispersa como hoy.

## Contexto
- Ya en pie —**no reconstruir la lógica de datos**—: `Dashboard.jsx` con los paneles del módulo 9 (Monitoreo del Domo, Signos Vitales, Telemetría EVA, Alertas Activas) sobre el token system visual del módulo 11; el WS ya distingue mensajes por `type` (`"reading"`, `"alert"`, y ahora `"location"` del módulo 12); `GET /locations/latest?device_id=` ya expone la posición más reciente.
- **Librería de mapa: MapLibre GL JS** (`maplibre-gl` en npm) — no Leaflet. Es un fork open source y gratuito de Mapbox GL JS, mismo motor de renderizado por vector tiles (rápido, minimalista, muy personalizable vía un archivo de estilo JSON).
- **Basemap: estilo "Dark Matter" de CARTO** — gratis, diseñado justo para visualización de datos sobre fondo oscuro, encaja con la paleta del módulo 11. Nota importante: CARTO ahora exige una API key gratuita (sin cola de aprobación, 5M tile requests/mes) en vez de ser completamente anónimo como antes — regístrate en carto.com/basemaps y guarda la key en una variable de entorno del frontend, nunca hardcodeada en el código.
- **Alternativa que puede ahorrar trabajo**: `mapcn` — componentes de mapa en React construidos sobre MapLibre, con el mismo patrón de shadcn/ui (se copian al proyecto en vez de instalarse como dependencia opaca), cambio automático claro/oscuro, marcadores y popups ya resueltos, tiles gratis de CARTO integrados. Vale la pena evaluarlo antes de escribir el wrapper de MapLibre a mano — decide y dilo explícitamente en el mensaje de vuelta.
- El mapa consume `GET /locations/latest` al cargar y se actualiza en vivo con los mensajes `type: "location"` del WS — un punto usando el acento cian ya definido (`#38BDF8`) por `device_id`, sin recargar la página.
- Reestructura `Dashboard.jsx` en dos columnas: mapa a la izquierda; a la derecha, agrupa por sujeto en vez de paneles sueltos — todo lo de **Tripulante** junto (signos vitales, telemetría EVA, posición actual, sus alertas) y todo lo del **Domo** junto (ambiental, suelo, sus alertas). Layout de referencia (ajusta proporciones, no la estructura):

```
┌───────────────────┬─────────────────────────────┐
│                    │  TRIPULANTE                  │
│                    │  ├─ Signos vitales            │
│                    │  ├─ Telemetría EVA            │
│       MAPA          │  ├─ Posición actual           │
│  (punto por         │  └─ Alertas del tripulante    │
│   tripulante)        │                              │
│                    │  DOMO                         │
│                    │  ├─ Ambiental                 │
│                    │  ├─ Suelo / nutrientes         │
│                    │  └─ Alertas del domo           │
└───────────────────┴─────────────────────────────┘
```

## Restricciones
- No cambies la lógica de datos ya construida (WS, roles, filtrado biométrico) — esto es reestructuración visual más el nuevo consumo de `location`.
- Coordenada base del simulador (módulo 12): por ahora un placeholder en RD. Si el equipo ya tiene las coordenadas reales del sitio de la misión, avísalo antes de dar esto por terminado.
- Nunca hardcodees la API key de CARTO — variable de entorno, `.env` fuera de git.
- Mantén la paleta y tipografía del módulo 11 — el mapa debe verse integrado (fondo oscuro, acentos cian/ámbar), no como un widget ajeno pegado encima.

## Cómo se sabe que está terminado
- El mapa carga con el estilo Dark Matter y muestra un punto por cada tripulante activo, en su posición más reciente.
- El punto se mueve sin recargar la página cuando llega un nuevo `type: "location"` por WS.
- Los paneles de la derecha quedan agrupados por Tripulante y Domo, no sueltos como hoy.
- Verificación real en navegador con los tres usuarios semilla — mismo estándar que los módulos anteriores, no un script.
# Prompt — Módulo 11: rediseño visual del dashboard (mission control)

Lee `AGENTS.md` en la raíz del repo antes de empezar. Respeta el contrato de datos y el stack técnico definidos ahí — este módulo es solo visual.

## Objetivo
Rediseñar visualmente `Dashboard.jsx`, `Login.jsx` y los estilos del frontend para que la app se vea como una consola de control de misión real, no como un panel de SaaS genérico, sin cambiar ninguna lógica de datos, roles o alertas ya construida y verificada en navegador.

## Contexto
Plan de diseño — síguelo tal cual, no lo sustituyas por un look genérico por defecto:

- **Color** (paleta base, 6 valores):
  - Fondo principal: `#0B1220` (azul-noche profundo, no negro puro)
  - Superficie/panel: `#121B2E`
  - Texto principal: `#E6EDF7`
  - Texto secundario: `#8B9BB4`
  - Acento "dato nominal": `#38BDF8` (cian de telemetría)
  - Acento "alerta": `#F5A524` (ámbar de advertencia — el mismo lenguaje que las luces de precaución en consolas reales; rojo se reserva para un futuro nivel "crítico" si hace falta)
  - Cada color tiene un significado funcional, nunca decorativo: cian = lectura normal, ámbar = alerta activa.
- **Tipografía**: dos familias con roles claros — una monoespaciada técnica (ej. `IBM Plex Mono` o `JetBrains Mono`) **solo** para los valores numéricos de sensores y timestamps (es funcional aquí, no decorativo: así se lee como telemetría real); una sans-serif técnica y legible (ej. `Inter` o `IBM Plex Sans`) para navegación, etiquetas y el resto del texto de UI.
- **Layout**: panel/grid de alta densidad separado por líneas finas (hairline rules) — no tarjetas idénticas con `border-radius` grande y sombra gris suave. Alineación mayormente a la izquierda; esto es una consola de operación, no un landing page.
- **Principios**: el panel de signos vitales restringido para Observador usa el mismo lenguaje visual que el resto de la app, no un estilo distinto "de error".

Base de componentes recomendada: **Cloudscape Design System** (`@cloudscape-design/components`, Apache 2.0, mantenido activamente por AWS, construido específicamente para consolas de monitoreo y flujos de alerta — el mismo tipo de aplicación que este dashboard) para tablas, indicadores de estado, formularios de umbral y el flujo de alertas — pero retemado con la paleta de arriba, no con su tema claro por defecto. Si Cloudscape no encaja bien con la estructura que ya tienes, la alternativa es construir directo con CSS/Tailwind usando los mismos tokens, sin adoptar una librería completa — decide y dilo explícitamente en el mensaje de vuelta.

## Restricciones
- Evita explícitamente estos clichés de diseño genérico que un agente de IA puede reproducir por defecto si no se le dice que no: fondo crema con serif y acento terracota; fondo casi negro con un único acento verde-ácido o vermellón; el "kit de tarjetas SaaS" (tarjetas idénticas, mismo border-radius, misma sombra gris suave); eyebrows en MAYÚSCULAS sobre cada título; flechas "→" al final de botones o links; metadatos separados por puntos medios (A · B · C).
- No cambies ninguna lógica de datos, WebSocket, roles o alertas — esto es solo visual (CSS, estructura de componentes, tipografía, color). Si adoptar Cloudscape obliga a cambiar cómo se renderiza algo, el comportamiento (qué ve cada rol, qué dispara una alerta) debe quedar idéntico.
- Mantén el mensaje "Sin acceso a datos biométricos — rol Observador" ya implementado; solo puedes rediseñarlo visualmente dentro de la nueva paleta.
- No agregues una librería de componentes nueva sin decirlo explícitamente si decides no usar Cloudscape.

## Cómo se sabe que está terminado
- El dashboard, visto en el navegador con los tres usuarios semilla, usa la paleta y tipografía definidas arriba de forma consistente — no colores ni tipos sueltos fuera del token system.
- Nada del comportamiento ya verificado se rompe: alertas en tiempo real, panel de signos vitales oculto para Observador, botón "Resolver" solo para administrador/control_mision.
- `npm run build` sigue limpio y los 73 tests de backend no se tocan.
- Verificación real en navegador (no solo build limpio): descripción o captura de cómo se ve con los tres roles.
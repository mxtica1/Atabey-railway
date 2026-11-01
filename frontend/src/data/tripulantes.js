/**
 * Perfiles de tripulantes de prueba (Módulo 13 - rediseño vista en vivo).
 *
 * Estos son DATOS DE PRUEBA — no representan tripulantes reales. La
 * asociacion con streams de telemetria reales es la siguiente:
 *
 *   - T-03 Eduardo Ortega  ← recibe el stream EVA-01 via WS. Actualmente el
 *                            gateway genera estos datos con EvaReceiverSim;
 *                            no provienen de sensores físicos.
 *   - T-01, T-02, T-04     ← placeholders. Sus posiciones y lecturas
 *                            son GENERADAS EN CLIENTE en este modulo,
 *                            claramente marcadas como datos simulados.
 *
 * Conectar los perfiles placeholder a streams de hardware es trabajo aparte
 * y queda fuera del alcance de este prompt.
 */

// Coordenada base del habitat (Reserva Cientifica Ebano Verde, Constanza, RD).
// Coincide con la del simulador de posicion y el default del mapa.
const BASE_LAT = 18.8776
const BASE_LON = -70.5609

// Desplazamientos pequeños (±0.0003°) para que los 4 marcadores se vean
// agrupados como un solo equipo en el mismo punto del habitat.
export const TRIPULANTES = [
  {
    id:           'T-01',
    nombre:       'Geisy Camilo',
    sexo:         'F',
    streamSource: 'websocket',                 // ✅ Esperar datos del WebSocket (Vantroi)
    offset:       [-0.00020, -0.00010],
    simulated: null,  // ✅ SIN simulación
  },
  {
    id:           'T-02',
    nombre:       'Alba Vasquez',
    sexo:         'F',
    streamSource: 'websocket',                 // ✅ Esperar datos del WebSocket (Vantroi)
    offset:       [ 0.00015,  0.00022],
    simulated: null,  // ✅ SIN simulación
  },
  {
    id:           'T-03',
    nombre:       'Eduardo Ortega',
    sexo:         'M',
    streamSource: 'EVA-01',                    // stream del simulador del gateway
    offset:       [-0.00010,  0.00018],
    simulated: null,
  },
  {
    id:           'T-04',
    nombre:       'Angel Peña',
    sexo:         'M',
    streamSource: 'websocket',                 // ✅ Esperar datos del WebSocket (Vantroi)
    offset:       [ 0.00025, -0.00018],
    simulated: null,  // ✅ SIN simulación
  },
]

export function getTripulante(id) {
  return TRIPULANTES.find(t => t.id === id)
}

export function getTripulanteByStreamDevice(deviceId) {
  // Asocia el device_id real (EVA-01) con su tripulante humano.
  return TRIPULANTES.find(t => t.streamSource === deviceId)
}

export function getTripulanteBaseCoords() {
  return { lat: BASE_LAT, lon: BASE_LON }
}

export const SEXO_LABEL = { F: 'Femenino', M: 'Masculino' }

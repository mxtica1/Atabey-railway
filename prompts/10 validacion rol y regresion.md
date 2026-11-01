# Prompt — Corrección: validar `rol` con tipo restringido + test de regresión de la migración

Lee `AGENTS.md` en la raíz del repo antes de empezar. Respeta el contrato de datos y el stack técnico definidos ahí.

## Objetivo
Cerrar el vacío que causó el bug de roles en mayúscula: validar `rol` con un tipo restringido en el backend —no un string libre— para que un valor inválido nunca pueda entrar por una vía nueva, y agregar un test de regresión que fije el comportamiento de la migración de normalización ya corregida. Al terminar, `POST /admin/users` con un `rol` fuera de los tres valores permitidos debe devolver 422, y la normalización de roles legacy en mayúscula debe estar cubierta por un test, no solo verificada a mano.

## Contexto
- Ya en pie —**no reconstruir**—: la migración en `db.py` que normaliza roles con mayúscula a minúscula al arrancar (la que agregaste tras el bug real encontrado probando en el navegador); `require_role(...)` en `auth.py`; el endpoint `POST /admin/users` en `main.py`.
- El campo `rol` hoy es un string libre en los esquemas Pydantic — nada impide que `POST /admin/users` reciba `"Administrador"`, `"ADMIN"`, o cualquier otro valor. La migración de arranque no ayuda ahí porque corre una sola vez al iniciar, no en cada inserción nueva.
- Restringe `rol` con un `Literal["administrador", "control_mision", "observador"]` (o un `Enum` de Python) en el/los esquema(s) Pydantic que usa `POST /admin/users` para crear un usuario. FastAPI debería devolver 422 automáticamente ante un valor fuera de esos tres.
- Como defensa adicional en la base de datos —complementa la validación de arriba, no la reemplaza—: agrega un `CHECK` constraint en la columna `rol` de la tabla `users` que solo permita esos tres valores exactos.

## Restricciones
- No cambies los tres valores de rol existentes (`administrador`, `control_mision`, `observador`) ni el claim del JWT — solo restringes qué puede llegar a la columna, no el vocabulario.
- No reconstruyas la migración de normalización ya corregida — solo agrégale un test.
- No agregues dependencias nuevas — `Literal` ya está disponible en `typing`.

## Cómo se sabe que está terminado
- Test que confirma que `POST /admin/users` con un `rol` inválido (ej. `"Administrador"`, `"admin"`, `"superusuario"`) devuelve 422, y que los tres valores válidos siguen funcionando sin cambios.
- Test de regresión para la migración: inserta (o mockea) un usuario con `rol="Administrador"`, corre la función de normalización, y confirma que queda en `administrador`.
- Si agregaste el `CHECK` en Postgres: una prueba o una nota clara en el README confirmando que un `INSERT`/`UPDATE` directo con un rol inválido falla a nivel de base de datos, no solo a nivel de API.
- La suite completa sigue en verde (61 + los nuevos).
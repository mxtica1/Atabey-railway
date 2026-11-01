"""
Pruebas de la cola SQLite offline.

Cubre:
  - Toda lectura se encola al llegar, sin excepcion.
  - Un reinicio del proceso no duplica lecturas ya encoladas.
  - count_pending y count_total reflejan el estado correcto.
  - pending() devuelve en orden por (sensor_id, sequence).
  - mark_synced reduce el contador de pendientes.
"""

from gateway.tests.conftest import make_reading


class TestEnqueue:
    def test_encola_lectura_valida(self, tmp_queue):
        reading = make_reading(1)
        tmp_queue.enqueue(reading)
        assert tmp_queue.count_pending() == 1
        assert tmp_queue.count_total() == 1

    def test_multiples_lecturas(self, tmp_queue):
        for i in range(1, 6):
            tmp_queue.enqueue(make_reading(i))
        assert tmp_queue.count_pending() == 5

    def test_no_duplicados_mismo_sequence(self, tmp_queue):
        """INSERT OR IGNORE: misma (sensor_id, sequence) no genera duplicado."""
        reading = make_reading(1)
        tmp_queue.enqueue(reading)
        tmp_queue.enqueue(reading)  # segundo intento con mismos datos
        assert tmp_queue.count_total() == 1

    def test_no_duplicados_tras_reinicio(self, tmp_queue):
        """
        Simula un reinicio: mismas lecturas intentan encolarse de nuevo.
        El conteo no debe aumentar.
        """
        readings = [make_reading(i) for i in range(1, 4)]
        for r in readings:
            tmp_queue.enqueue(r)
        # "reinicio": volvemos a encolar los mismos
        for r in readings:
            tmp_queue.enqueue(r)
        assert tmp_queue.count_total() == 3


class TestPending:
    def test_pending_devuelve_no_sincronizadas(self, tmp_queue):
        for i in range(1, 4):
            tmp_queue.enqueue(make_reading(i))
        pending = tmp_queue.pending()
        assert len(pending) == 3

    def test_pending_orden_por_sequence(self, tmp_queue):
        """Las lecturas deben drenarse en orden por sequence."""
        for i in [3, 1, 2]:
            tmp_queue.enqueue(make_reading(i))
        pending = tmp_queue.pending()
        sequences = [p["sequence"] for p in pending]
        assert sequences == sorted(sequences)

    def test_pending_respeta_limit(self, tmp_queue):
        for i in range(1, 11):
            tmp_queue.enqueue(make_reading(i))
        pending = tmp_queue.pending(limit=3)
        assert len(pending) == 3

    def test_pending_incluye_row_id(self, tmp_queue):
        tmp_queue.enqueue(make_reading(1))
        pending = tmp_queue.pending()
        assert "_row_id" in pending[0]

    def test_pending_tiene_todos_los_campos_del_contrato(self, tmp_queue):
        tmp_queue.enqueue(make_reading(1))
        item = tmp_queue.pending()[0]
        for campo in ("device_id", "sensor_id", "timestamp", "value", "unit", "sequence"):
            assert campo in item, f"Campo '{campo}' ausente en el item de la cola"


class TestMarkSynced:
    def test_mark_synced_reduce_pendientes(self, tmp_queue):
        tmp_queue.enqueue(make_reading(1))
        tmp_queue.enqueue(make_reading(2))
        pending = tmp_queue.pending()
        tmp_queue.mark_synced(pending[0]["_row_id"])
        assert tmp_queue.count_pending() == 1

    def test_mark_synced_no_borra_la_fila(self, tmp_queue):
        """Synced=1 pero el registro historico se conserva."""
        tmp_queue.enqueue(make_reading(1))
        row_id = tmp_queue.pending()[0]["_row_id"]
        tmp_queue.mark_synced(row_id)
        assert tmp_queue.count_total() == 1
        assert tmp_queue.count_pending() == 0

    def test_lecturas_sincronizadas_no_aparecen_en_pending(self, tmp_queue):
        for i in range(1, 4):
            tmp_queue.enqueue(make_reading(i))
        pending = tmp_queue.pending()
        # Sincronizamos la primera
        tmp_queue.mark_synced(pending[0]["_row_id"])
        remaining = tmp_queue.pending()
        synced_seq = pending[0]["sequence"]
        for item in remaining:
            assert item["sequence"] != synced_seq


class TestConcurrency:
    def test_hilos_concurrentes_no_corrompen_cola_ni_devuelven_none(self, tmp_queue):
        """
        Dispara multiples hilos escribiendo y consultando la cola al mismo tiempo
        (reproduciendo la condicion de orquestadores Domo + EVA + sync simultaneos).
        Verifica:
          - No hay excepciones de concurrencia (ej. NoneType is not subscriptable).
          - count_pending() y count_total() siempre devuelven int (nunca None).
          - No se corrompe la cola y el total coincide exactamente con las inserciones.
        """
        import concurrent.futures

        NUM_THREADS = 8
        OPS_PER_THREAD = 35
        errors = []

        def writer_and_reader(thread_idx: int):
            for i in range(1, OPS_PER_THREAD + 1):
                try:
                    reading = {
                        "device_id": f"DEV-{thread_idx % 2}",
                        "sensor_id": f"SENSOR-{thread_idx}",
                        "timestamp": "2026-09-24T20:15:00Z",
                        "value": float(i),
                        "unit": "C",
                        "sequence": i,
                    }
                    tmp_queue.enqueue(reading)

                    c = tmp_queue.count_pending()
                    if c is None or not isinstance(c, int):
                        errors.append(f"count_pending() no es int: {c!r}")

                    tot = tmp_queue.count_total()
                    if tot is None or not isinstance(tot, int):
                        errors.append(f"count_total() no es int: {tot!r}")

                    # Lectura concurrente de pending
                    if i % 5 == 0:
                        p = tmp_queue.pending(limit=5)
                        if p and "_row_id" in p[0]:
                            tmp_queue.mark_synced(p[0]["_row_id"])

                except Exception as exc:
                    errors.append(f"Excepcion en hilo {thread_idx}: {exc}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
            futures = [executor.submit(writer_and_reader, t) for t in range(NUM_THREADS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Errores de concurrencia detectados: {errors[:5]}"
        assert tmp_queue.count_total() == NUM_THREADS * OPS_PER_THREAD
        assert isinstance(tmp_queue.count_pending(), int)


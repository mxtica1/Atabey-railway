#!/usr/bin/env python3
"""
Verifica que los 23 sensor_id (13 domo + 10 EVA) respondan con una lectura
reciente en el backend, corriendo contra el stack completo (docker compose).

Uso:
    python verify_e2e.py
    python verify_e2e.py --base-url http://localhost:8000 --max-age 15
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

DOMO_SENSORS = [
    "TEMP-01", "HUM-01", "CO2-01", "LUX-01",
    "SOIL-HUM-01", "SOIL-HUM-02", "SOIL-HUM-03",
    "SOIL-TEMP-01", "SOIL-TEMP-02", "SOIL-TEMP-03",
    "NPK-N-01", "NPK-P-01", "NPK-K-01",
]

EVA_SENSORS = [
    "HR-01", "SPO2-01", "BTEMP-01",
    "EVA-TEMP-01", "EVA-HUM-01", "EVA-PRESS-01",
    "ACC-X-01", "ACC-Y-01", "ACC-Z-01", "ACTIVITY-01",
]

ALL_SENSORS = [("domo", s) for s in DOMO_SENSORS] + [("EVA", s) for s in EVA_SENSORS]


def check_sensor(base_url: str, sensor_id: str, max_age: float):
    url = f"{base_url}/readings/latest?sensor_id={sensor_id}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            if resp.status != 200:
                return False, f"HTTP {resp.status}"
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"error: {e}"

    ts_raw = data.get("timestamp")
    if not ts_raw:
        return False, "sin campo timestamp en la respuesta"

    try:
        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
    except ValueError:
        return False, f"timestamp no parseable: {ts_raw}"

    age = (datetime.now(timezone.utc) - ts).total_seconds()
    if age > max_age:
        return False, f"lectura obsoleta ({age:.1f}s > {max_age}s), value={data.get('value')}"

    return True, f"value={data.get('value')} {data.get('unit', '')} (hace {age:.1f}s)"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--max-age", type=float, default=15.0,
        help="segundos máximos de antigüedad aceptados (default 15; la cadencia real es 5s)",
    )
    args = parser.parse_args()

    print(f"Verificando {len(ALL_SENSORS)} sensor_id contra {args.base_url} ...\n")

    failures = []
    for group, sensor_id in ALL_SENSORS:
        ok, detail = check_sensor(args.base_url, sensor_id, args.max_age)
        status = "OK  " if ok else "FAIL"
        print(f"[{status}] {group:5s} {sensor_id:15s} {detail}")
        if not ok:
            failures.append(sensor_id)

    print()
    if failures:
        print(f"❌ {len(failures)}/{len(ALL_SENSORS)} sensores fallaron: {', '.join(failures)}")
        sys.exit(1)
    print(f"✅ {len(ALL_SENSORS)}/{len(ALL_SENSORS)} sensores respondieron con lecturas frescas.")
    sys.exit(0)


if __name__ == "__main__":
    main()
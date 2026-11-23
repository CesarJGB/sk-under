#!/usr/bin/env python3
"""Mediciones reproducibles del procesamiento local de Soul Knight.

Cada escenario se ejecuta en un proceso nuevo para separar el arranque del
trabajo y para que `ru_maxrss` no acumule el pico de otros escenarios. El
script no imprime contenido de partidas, identificadores ni huellas privadas.

Uso, desde `backend/`:

    uv run --locked python ../docs/research/phase5-4/benchmark.py

Para las nueve muestras privadas de 8.6.0, exporta las mismas variables que
usa `test_private_save_roundtrip.py`.
"""

import argparse
import gzip
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
FIXTURE = BACKEND / "tests" / "fixtures" / "cloud-save-sintetico.json"
FIXTURE_880 = BACKEND / "tests" / "fixtures" / "cloud-save-880-sintetico.json"
SAMPLES_ENV = "SK_PHASE4_SAMPLES_DIR"
CIPHER_ENV = "SK_PHASE4_CIPHER_ENV_FILE"


def usage():
    get = resource.getrusage(resource.RUSAGE_SELF)
    return get.ru_utime, get.ru_stime, get.ru_maxrss


def emit(scenario: str, **values) -> None:
    print(json.dumps({"scenario": scenario, **values}, sort_keys=True))


def run_startup(target: str) -> None:
    user0, system0, _ = usage()
    started = time.perf_counter()
    if target == "cloud":
        import app.cloud.importer  # noqa: F401
    elif target == "app":
        import app.main  # noqa: F401
    elif target != "empty":
        raise SystemExit(f"Objetivo de arranque desconocido: {target}")
    elapsed = time.perf_counter() - started
    user1, system1, rss = usage()
    emit(
        "startup_" + target,
        import_s=round(elapsed, 6),
        cpu_user_s=round(user1 - user0, 6),
        cpu_system_s=round(system1 - system0, 6),
        maxrss_kib=rss,
    )


def run_synthetic(source: str, iterations: int) -> None:
    if source == "current":
        from app.cloud_import import LocalFileSource, import_copy

        def work():
            return import_copy(LocalFileSource(FIXTURE))
    elif source in {"transport", "transport_gzip"}:
        from app.cloud.importer import import_from_transport
        from app.cloud.transport import SimulatedProviderTransport

        if source == "transport_gzip":
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "copia.gz"
                path.write_bytes(gzip.compress(FIXTURE.read_bytes(), mtime=0))
                transport = SimulatedProviderTransport(path)
                size = path.stat().st_size
                return _measure(
                    "synthetic_" + source,
                    lambda: import_from_transport(transport),
                    iterations,
                    processed_bytes=size * iterations,
                )
        transport = SimulatedProviderTransport(FIXTURE)

        def work():
            return import_from_transport(transport)
    else:
        raise SystemExit(f"Fuente sintética desconocida: {source}")

    return _measure(
        "synthetic_" + source,
        work,
        iterations,
        processed_bytes=FIXTURE.stat().st_size * iterations,
    )


def run_synthetic_large(compressed: bool) -> None:
    document = json.dumps(
        {
            "serialzedVersion": 1,
            "cloudSaveId": "sintetico-grande",
            "platformId": "sintetico-grande",
            "gameData": {"payload": "x" * 4_000_000},
            "itemData": {"materials": {}},
        },
        separators=(",", ":"),
    ).encode()
    payload = gzip.compress(document, mtime=0) if compressed else document
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "grande"
        path.write_bytes(payload)
        from app.cloud.importer import import_from_transport
        from app.cloud.transport import SimulatedProviderTransport

        transport = SimulatedProviderTransport(path)
        _measure(
            "synthetic_large_" + ("gzip" if compressed else "json"),
            lambda: import_from_transport(transport),
            1,
            processed_bytes=len(payload),
        )


def _measure(name: str, work, iterations: int, processed_bytes: int = 0) -> None:
    user0, system0, _ = usage()
    started = time.perf_counter()
    result = None
    for _ in range(iterations):
        result = work()
    elapsed = time.perf_counter() - started
    user1, system1, rss = usage()
    emit(
        name,
        iterations=iterations,
        work_s=round(elapsed, 6),
        mean_ms=round(elapsed * 1000 / iterations, 4),
        cpu_user_s=round(user1 - user0, 6),
        cpu_system_s=round(system1 - system0, 6),
        maxrss_kib=rss,
        processed_bytes=processed_bytes,
        result_type=type(result).__name__,
    )


def run_real(iterations: int) -> None:
    samples = os.environ.get(SAMPLES_ENV)
    cipher_env = os.environ.get(CIPHER_ENV)
    if not samples or not cipher_env:
        raise SystemExit(f"Faltan {SAMPLES_ENV} y {CIPHER_ENV}.")
    from app.formats.real_save import RealSaveAdapter
    from app.settings import Settings

    cipher = Settings(_env_file=cipher_env).save_cipher
    if cipher is None:
        raise SystemExit("La configuración privada no contiene el códec local.")
    adapter = RealSaveAdapter(*cipher)
    files = sorted(Path(samples).glob("*_111_.data"))
    if len(files) != 9:
        raise SystemExit(f"Se esperaban nueve muestras y hay {len(files)}.")

    def work():
        total = 0
        matched = 0
        for path in files:
            data = path.read_bytes()
            if adapter.read_if_matching(data) is None:
                raise SystemExit(f"La muestra {path.name} no fue reconocida.")
            matched += 1
            total += len(data)
        return matched, total

    user0, system0, _ = usage()
    started = time.perf_counter()
    total_bytes = 0
    for _ in range(iterations):
        matched, total_bytes = work()
    elapsed = time.perf_counter() - started
    user1, system1, rss = usage()
    emit(
        "real_86_decode",
        iterations=iterations,
        work_s=round(elapsed, 6),
        mean_ms=round(elapsed * 1000 / iterations, 4),
        cpu_user_s=round(user1 - user0, 6),
        cpu_system_s=round(system1 - system0, 6),
        maxrss_kib=rss,
        files=matched,
        processed_bytes=total_bytes,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario")
    parser.add_argument("--target", default="empty")
    parser.add_argument("--source", default="transport")
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--real-iterations", type=int, default=1)
    parser.add_argument("--compressed", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, str(BACKEND))
    if args.scenario:
        if args.scenario == "startup":
            run_startup(args.target)
        elif args.scenario == "synthetic":
            run_synthetic(args.source, args.iterations)
        elif args.scenario == "real":
            run_real(args.real_iterations)
        elif args.scenario == "large":
            run_synthetic_large(args.compressed)
        else:
            raise SystemExit(f"Escenario desconocido: {args.scenario}")
        return 0

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(BACKEND) + (
        os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else ""
    )

    def child(*arguments: str) -> dict[str, object]:
        command = [sys.executable, str(Path(__file__).resolve()), *arguments]
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=environment,
            timeout=300,
        )
        wall = time.perf_counter() - started
        if completed.returncode != 0:
            sys.stderr.write(completed.stderr)
            raise SystemExit(f"Falló {arguments[2] if len(arguments) > 2 else arguments}.")
        result = json.loads(completed.stdout.strip().splitlines()[-1])
        result["wall_s"] = round(wall, 6)
        return result

    results = [
        child("--scenario", "startup", "--target", "empty"),
        child("--scenario", "startup", "--target", "cloud"),
        child("--scenario", "startup", "--target", "app"),
        child("--scenario", "synthetic", "--source", "current", "--iterations", "200"),
        child("--scenario", "synthetic", "--source", "transport", "--iterations", "200"),
        child("--scenario", "synthetic", "--source", "transport_gzip", "--iterations", "200"),
        child("--scenario", "large"),
        child("--scenario", "large", "--compressed"),
    ]
    if os.environ.get(SAMPLES_ENV) and os.environ.get(CIPHER_ENV):
        results.append(child("--scenario", "real", "--real-iterations", "1"))

    print(json.dumps({"hardware": _hardware(), "results": results}, indent=2, sort_keys=True))
    return 0


def _hardware() -> dict[str, object]:
    meminfo = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines()[:3]:
            key, _, value = line.partition(":")
            meminfo[key] = value.strip()
    except OSError:
        pass
    return {
        "cpu": _cpu_model(),
        "cpu_count": os.cpu_count(),
        "kernel": os.uname().release,
        "python": sys.version.split()[0],
        "meminfo": meminfo,
    }


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.partition(":")[2].strip()
    except OSError:
        return "desconocido"
    return "desconocido"


if __name__ == "__main__":
    raise SystemExit(main())

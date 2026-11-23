#!/usr/bin/env python3
"""Informe de una referencia 8.8.0 suministrada por el titular.

No escribe el archivo, no publica identidad ni contenido y no llama a la red.
Ejecutar desde ``backend/`` con ``PYTHONPATH=.``.
"""

from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path

from app.cloud.decoder import RpcEnvelopeError, decode_rpc_gzip
from app.cloud.lab import SaveLab
from app.cloud_save import OPTIONAL_SECTIONS, CloudSaveError, _unpack
from app.cloud_envelope import inspect_rpc_frame
from app.parsers.json_document import parse_json


def describe(path: Path, *, allow_rpc_gzip: bool) -> dict[str, object]:
    payload = path.read_bytes()
    frame = inspect_rpc_frame(payload)
    rpc: dict[str, object] | None = None
    if frame.kind == "compressed":
        rpc = {"kind": frame.kind, "body_size": len(frame.body or b"")}
        if not allow_rpc_gzip:
            raise RpcEnvelopeError("El cuerpo RPC está comprimido; use --rpc-gzip para el intento experimental.")
        decoded = decode_rpc_gzip(payload)
        body = bytes(frame.body or b"")
        payload = body
        rpc["decoded"] = True
        rpc["body_sha256"] = sha256(body).hexdigest()
    elif frame.kind == "null_marker":
        raise RpcEnvelopeError("El sobre RPC contiene la marca nula.")

    lab = SaveLab.open(payload)
    encoding, document = _unpack(payload)
    tree = parse_json(document)
    if not isinstance(tree, dict):
        raise CloudSaveError("La raíz no es un objeto JSON.")
    sections = {"gameData": "present" if "gameData" in tree else "missing"}
    for name in OPTIONAL_SECTIONS:
        sections[name] = "missing" if name not in tree else ("null" if tree[name] is None else "present")
    return {
        "file": path.name,
        "size": len(payload),
        "sha256": sha256(payload).hexdigest(),
        "encoding": encoding,
        "rpc": rpc,
        "serialzedVersion": tree.get("serialzedVersion"),
        "sections": sections,
        "unknown_top_level": sorted(set(tree) - {
            "serialzedVersion", "cloudSaveId", "platformId", "gameData",
            *OPTIONAL_SECTIONS,
        }),
        "roundtrip": lab.report(encoding="same").roundtrip,
        "note": "Informe estructural; no declara aceptación por el cliente ni autenticidad de origen.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--rpc-gzip", action="store_true", help="Intento experimental del cuerpo RPC como gzip.")
    args = parser.parse_args()
    try:
        report = describe(args.file, allow_rpc_gzip=args.rpc_gzip)
    except (CloudSaveError, RpcEnvelopeError, OSError, ValueError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

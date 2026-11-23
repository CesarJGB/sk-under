#!/usr/bin/env python3
"""Laboratorio local: edita una copia, nunca el original.

Ejecutar desde ``backend/`` con ``PYTHONPATH=.``:

    uv run --locked python ../docs/research/phase5-5/tools/save_lab.py \
      --input /ruta/agregado.json --set gameData.gems=10 \
      --output /ruta/agregado.edit.json --report /ruta/informe.json

El original no se abre en modo escritura. Si el destino existe, se crea un
respaldo ``.bak`` antes de reemplazarlo y se exige ``--force``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from app.cloud.lab import LabError, SaveLab
from app.cloud_save import CloudSaveError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--set", action="append", default=[], metavar="RUTA=JSON")
    parser.add_argument("--encoding", choices=("same", "json", "gzip"), default="same")
    parser.add_argument("--force", action="store_true", help="Reemplaza el destino tras crear .bak.")
    parser.add_argument("--dry-run", action="store_true", help="Calcula el informe sin escribir la copia.")
    args = parser.parse_args()

    try:
        payload = args.input.read_bytes()
    except OSError:
        print(json.dumps({"error": "unreadable_input"}), file=sys.stderr)
        return 1

    output = args.output or args.input.with_name(args.input.stem + ".edit" + args.input.suffix)
    if output.resolve() == args.input.resolve():
        print(json.dumps({"error": "output_matches_input"}), file=sys.stderr)
        return 1

    try:
        lab = SaveLab.open(payload)
        for expression in args.set:
            if "=" not in expression:
                raise ValueError(f"Se esperaba RUTA=JSON: {expression}")
            path, raw = expression.split("=", 1)
            lab.set(path, json.loads(raw))
        report = lab.report(encoding=args.encoding)
    except (CloudSaveError, LabError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 1

    if not args.dry_run:
        if output.exists():
            if not args.force:
                print(json.dumps({"error": "output_exists"}), file=sys.stderr)
                return 1
            backup = output.with_name(output.name + ".bak")
            shutil.copy2(output, backup)
        output.write_bytes(report.output_data)

    document = report.as_dict()
    document["input"] = str(args.input)
    document["output"] = None if args.dry_run else str(output)
    document["dry_run"] = args.dry_run
    text = json.dumps(document, indent=2, ensure_ascii=False)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

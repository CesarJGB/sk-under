#!/usr/bin/env python3
"""Compara versiones, catálogos o snapshots de identificadores.

Ejemplos:
    python3 knowledge/tools/compare_versions.py --family weapons --from 8.6.0 --to 8.8.0
    python3 knowledge/tools/compare_versions.py --from-file a.json --to-file b.json
    python3 knowledge/tools/compare_versions.py --list
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sk_knowledge import common  # noqa: E402
from sk_knowledge.common import VERSION_DIFFS_DIR, read_json  # noqa: E402


def load_snapshots() -> dict[str, Any]:
    path = VERSION_DIFFS_DIR / "snapshots.json"
    if not path.is_file():
        raise SystemExit("No existe knowledge/version-diffs/snapshots.json")
    return read_json(path).get("versions", {})


def compare_id_sets(before: set[str], after: set[str]) -> dict[str, Any]:
    return {
        "count_before": len(before),
        "count_after": len(after),
        "added": sorted(after - before),
        "removed": sorted(before - after),
        "common": len(before & after),
    }


def compare_snapshots(from_version: str, to_version: str, family: str | None) -> dict[str, Any]:
    snapshots = load_snapshots()
    if from_version not in snapshots or to_version not in snapshots:
        raise SystemExit(
            f"Versiones disponibles: {', '.join(sorted(snapshots))}. "
            f"Solicitadas: {from_version}, {to_version}."
        )
    before = snapshots[from_version]
    after = snapshots[to_version]
    families = sorted(set(before.get("ids", {})) | set(after.get("ids", {})))
    if family:
        families = [family] if family in families else []
        if not families:
            raise SystemExit(f"Familia desconocida: {family}")
    result: dict[str, Any] = {
        "kind": "snapshot",
        "from_version": from_version,
        "to_version": to_version,
        "from_commit": before.get("commit"),
        "to_commit": after.get("commit"),
        "families": {},
    }
    for name in families:
        result["families"][name] = compare_id_sets(
            set(before.get("ids", {}).get(name, [])),
            set(after.get("ids", {}).get(name, [])),
        )
    return result


def compare_catalog_files(from_path: Path, to_path: Path) -> dict[str, Any]:
    before = read_json(from_path)
    after = read_json(to_path)
    before_items = {item["id"]: item for item in before.get("items", [])}
    after_items = {item["id"]: item for item in after.get("items", [])}
    changed = []
    for item_id in sorted(set(before_items) & set(after_items)):
        if before_items[item_id] != after_items[item_id]:
            changed.append(item_id)
    return {
        "kind": "catalog",
        "from": str(from_path),
        "to": str(to_path),
        "families": {
            before.get("family") or after.get("family") or "unknown": {
                **compare_id_sets(set(before_items), set(after_items)),
                "changed": changed,
            }
        },
    }


def print_markdown(result: dict[str, Any]) -> None:
    if result["kind"] == "snapshot":
        print(f"# Comparación {result['from_version']} → {result['to_version']}\n")
        print(f"- Commit origen: `{result['from_commit']}`")
        print(f"- Commit destino: `{result['to_commit']}`\n")
        for family, data in result["families"].items():
            print(f"## {family}\n")
            print(f"- Antes: {data['count_before']}")
            print(f"- Después: {data['count_after']}")
            print(f"- Comunes: {data['common']}")
            print(f"- Añadidos: {len(data['added'])}")
            print(f"- Eliminados: {len(data['removed'])}")
            if data["added"]:
                print(f"- Muestra añadidos: {', '.join(data['added'][:12])}")
            if data["removed"]:
                print(f"- Muestra eliminados: {', '.join(data['removed'][:12])}")
            print()
    else:
        family, data = next(iter(result["families"].items()))
        print(f"# Comparación de catálogo {family}\n")
        print(f"- Antes: {data['count_before']}")
        print(f"- Después: {data['count_after']}")
        print(f"- Añadidos: {len(data['added'])}")
        print(f"- Eliminados: {len(data['removed'])}")
        print(f"- Modificados: {len(data['changed'])}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", help="Familia de identificadores, por ejemplo weapons.")
    parser.add_argument("--from", dest="from_version", help="Versión de origen, por ejemplo 8.6.0.")
    parser.add_argument("--to", dest="to_version", help="Versión de destino, por ejemplo 8.8.0.")
    parser.add_argument("--from-file", type=Path)
    parser.add_argument("--to-file", type=Path)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.list:
        snapshots = load_snapshots()
        for version, data in sorted(snapshots.items()):
            print(f"{version}  commit={data.get('commit')}  familias={len(data.get('ids', {}))}")
        return 0

    if args.from_file or args.to_file:
        if not (args.from_file and args.to_file):
            parser.error("--from-file y --to-file deben usarse juntos.")
        result = compare_catalog_files(args.from_file, args.to_file)
    else:
        if not (args.from_version and args.to_version):
            parser.error("Indica --from/--to, --from-file/--to-file o --list.")
        result = compare_snapshots(args.from_version, args.to_version, args.family)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_markdown(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
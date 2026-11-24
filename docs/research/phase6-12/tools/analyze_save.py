#!/usr/bin/env python3
"""Herramientas locales de solo lectura para guardados de Soul Knight.

Uso previsto, desde ``backend/`` con el entorno del proyecto y las claves
locales del titular::

    uv run --locked python ../docs/research/phase6-12/tools/analyze_save.py \
        inventory ../captura.tar --keys-env ~/.config/sk-under/phase3/cipher.env

El script nunca escribe partidas ni imprime claves. Los valores solo aparecen
con ``--values``; las capturas y los informes con valores no se publican.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tarfile
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parents[4] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.cloud.resource_consistency import aggregate_tree  # noqa: E402
from app.local_save import LocalSaveError, LocalSaveLab, kind_from_filename
from app.parsers.real_save import decode_game_data
from app.save_analysis import (
    character_report,
    compare_documents,
    field_shapes,
    fish_chip_report,
    section_summary,
)

CAPTURE_LIMIT = 64 * 1024 * 1024
MAX_MEMBERS = 512
SECTION_BY_KIND = {
    "game": "gameData",
    "game_data": "gameData",
    "item_data": "itemData",
    "statistic": "statisticData",
    "season_data": "seasonData",
    "mall_reload_data": "mallReloadData",
    "bp_data": "battlePassSaveData",
    "misc_data": "miscData",
    "monsrise_data": "monsterRiseData",
    "pvp_data": "pvpData",
    "task": "taskData",
    "setting": "settingData",
    "weapon_evolution_data": "weaponEvolutionData",
    "escape_season_data": "escapeSeasonData",
    "sandbox_config": "sandboxConfig",
    "sandbox_maps": "maps",
}
PREFERENCES = "shared_prefs/com.ChillyRoom.DungeonShooter.v2.playerprefs.xml"


@dataclass
class Snapshot:
    kind: str
    documents: dict[str, dict[str, Any]] = field(default_factory=dict)
    files: dict[str, dict[str, Any]] = field(default_factory=dict)
    opaque: list[str] = field(default_factory=list)


def read_keys(path: Path | None) -> tuple[bytes, bytes, bytes]:
    values = {name: os.environ.get(name) for name in (
        "SK_SAVE_GENERAL_KEY_HEX", "SK_SAVE_STATISTICS_KEY_HEX", "SK_SAVE_IV_HEX",
    )}
    if path is not None:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name in values:
                values[name] = value.strip().strip('"').strip("'")
    if not all(values.values()):
        raise ValueError(
            "Faltan claves locales. Usa --keys-env o las variables "
            "SK_SAVE_GENERAL_KEY_HEX, SK_SAVE_STATISTICS_KEY_HEX y SK_SAVE_IV_HEX."
        )
    try:
        return tuple(bytes.fromhex(values[name]) for name in (
            "SK_SAVE_GENERAL_KEY_HEX", "SK_SAVE_STATISTICS_KEY_HEX", "SK_SAVE_IV_HEX",
        ))  # type: ignore[return-value]
    except ValueError:
        raise ValueError("Las claves locales no son hexadecimales válidas.") from None


def load_local(data: bytes, name: str, keys: tuple[bytes, bytes, bytes] | None) -> dict[str, Any]:
    if keys is None:
        raise ValueError(f"{name} necesita claves locales para decodificarse.")
    lab = LocalSaveLab.open(
        data, general_key=keys[0], statistics_key=keys[1], iv=keys[2], name=name,
    )
    return lab.document


def load_file(path: Path, keys: tuple[bytes, bytes, bytes] | None) -> Snapshot:
    payload = path.read_bytes()
    if len(payload) > CAPTURE_LIMIT:
        raise ValueError("El archivo supera el límite de análisis.")
    if path.name == "game.data" or decode_game_data(payload) is not None:
        document = decode_game_data(payload)
        if document is None:
            raise ValueError("game.data no coincide con el formato local conocido.")
        return Snapshot("game_data", {path.name: document}, {path.name: file_meta(payload, path.name)})
    if payload.lstrip()[:1] in (b"{", b"\x1f"):
        if payload.lstrip().startswith(b"{"):
            parsed = json.loads(payload)
            if not isinstance(parsed, dict):
                raise ValueError("El JSON debe contener un objeto.")
            if "serialzedVersion" not in parsed or "cloudSaveId" not in parsed:
                return Snapshot("decoded", {path.name: parsed}, {path.name: file_meta(payload, path.name)})
        return Snapshot("aggregate", {"cloud": aggregate_tree(payload)}, {"cloud": file_meta(payload, "cloud")})
    return Snapshot("local", {path.name: load_local(payload, path.name, keys)},
                    {path.name: file_meta(payload, path.name)})


def load_tar(path: Path, keys: tuple[bytes, bytes, bytes] | None) -> Snapshot:
    if path.stat().st_size > CAPTURE_LIMIT:
        raise ValueError("La captura supera el límite de análisis.")
    snapshot = Snapshot("tar")
    with tarfile.open(path, "r:") as archive:
        members = [member for member in archive if member.isfile()]
        if len(members) > MAX_MEMBERS:
            raise ValueError("La captura contiene demasiados archivos.")
        for member in members:
            name = member.name.removeprefix("./")
            payload = archive.extractfile(member).read()
            snapshot.files[name] = file_meta(payload, name)
            if not name.startswith("files/") or name.endswith(".new"):
                continue
            base = name.removeprefix("files/")
            try:
                if base == "game.data":
                    document = decode_game_data(payload)
                elif kind_from_filename(base) is not None:
                    if keys is None:
                        raise ValueError("La captura contiene secciones cifradas; indica --keys-env.")
                    document = load_local(payload, base, keys)
                else:
                    document = None
            except (LocalSaveError, ValueError):
                document = None
            if document is None:
                snapshot.opaque.append(name)
            else:
                snapshot.documents[name] = document
    return snapshot


def load_directory(path: Path, keys: tuple[bytes, bytes, bytes] | None) -> Snapshot:
    snapshot = Snapshot("directory")
    for child in sorted(path.iterdir()):
        if not child.is_file() or child.suffix not in (".data", ".json"):
            continue
        part = load_file(child, keys)
        snapshot.files[child.name] = file_meta(child.read_bytes(), child.name)
        snapshot.documents.update(part.documents)
    if not snapshot.documents:
        raise ValueError("El directorio no contiene archivos .data o .json analizables.")
    return snapshot


def load_source(path: Path, keys: tuple[bytes, bytes, bytes] | None) -> Snapshot:
    if path.is_dir():
        return load_directory(path, keys)
    if path.suffix == ".tar":
        return load_tar(path, keys)
    return load_file(path, keys)


def file_meta(payload: bytes, name: str) -> dict[str, Any]:
    return {"bytes": len(payload), "sha256": sha256(payload).hexdigest(), "name": name}


def source_view(snapshot: Snapshot, *, profile: str | None = None) -> dict[str, Any]:
    """Reconstruye una vista por secciones solo para análisis."""
    if snapshot.kind == "aggregate":
        return snapshot.documents["cloud"]
    if snapshot.kind in ("local", "decoded") and len(snapshot.documents) == 1:
        name, document = next(iter(snapshot.documents.items()))
        kind = kind_from_filename(name)
        return {SECTION_BY_KIND.get(kind, name): document}
    candidates: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for name, document in snapshot.documents.items():
        base = name.removeprefix("files/")
        kind = kind_from_filename(base)
        if kind is None:
            continue
        if profile is not None and "_" in base and f"_{profile}_" not in base:
            continue
        candidates.setdefault(kind, []).append((base, document))
    view: dict[str, Any] = {}
    for kind, entries in candidates.items():
        selected = entries[0]
        if len(entries) > 1:
            exact = [entry for entry in entries if f"_{profile}_" in entry[0]] if profile else []
            generic = [entry for entry in entries if entry[0].startswith(f"{kind}.")]
            if exact:
                selected = exact[0]
            elif generic:
                selected = generic[0]
            else:
                names = ", ".join(name for name, _ in entries)
                raise ValueError(f"Hay varias secciones {kind}; usa --profile. Candidatas: {names}")
        view[SECTION_BY_KIND.get(kind, kind)] = selected[1]
    return view


def compare_snapshots(
    before: Snapshot, after: Snapshot, *, profile: str | None = None,
) -> dict[str, Any]:
    if before.kind == after.kind and before.kind in ("aggregate", "local", "decoded"):
        old = next(iter(before.documents.values()))
        new = next(iter(after.documents.values()))
        return compare_documents(old, new, include_values=True)
    if before.kind in ("tar", "directory") and after.kind == before.kind:
        old_files, new_files = set(before.documents), set(after.documents)
        result: dict[str, Any] = {
            "files_added": sorted(new_files - old_files),
            "files_removed": sorted(old_files - new_files),
            "files_modified": [],
            "metadata_changed": [],
            "change_count": 0,
            "changes": [],
        }
        for name in sorted(old_files & new_files):
            changes = compare_documents(
                before.documents[name], after.documents[name], include_values=True,
            )["changes"]
            if changes:
                result["files_modified"].append(name)
                result["change_count"] += len(changes)
                result["changes"].extend({"file": name, **change} for change in changes)
        result["metadata_changed"] = sorted(
            name for name in before.files.keys() & after.files.keys()
            if before.files[name]["sha256"] != after.files[name]["sha256"]
        )
        return result
    old_view = source_view(before, profile=profile)
    new_view = source_view(after, profile=profile)
    return compare_documents(old_view, new_view, include_values=True)


def catalog_paths(directory: Path | None) -> tuple[list[str] | None, dict | None, dict | None]:
    if directory is None:
        local = Path(__file__).resolve().parents[4] / "backend/app/catalogs/characters-880.json"
        if not local.exists():
            return None, None, None
        catalog = json.loads(local.read_text(encoding="utf-8"))
        characters = catalog.get("characters", [])
        return (
            [row["code"] for row in characters],
            {f"c{row['index']}": {skin["key"]: skin["name"] for skin in row["skins"]} for row in characters},
            {skill["key"]: skill["name"] for row in characters for skill in row["skills"]},
        )
    codes_path = directory / "char_code_name.json"
    needed_path = directory / "needed_data.json"
    codes = json.loads(codes_path.read_text(encoding="utf-8")) if codes_path.exists() else None
    needed = json.loads(needed_path.read_text(encoding="utf-8")) if needed_path.exists() else None
    return (
        codes if isinstance(codes, list) else None,
        needed.get("skin") if isinstance(needed, dict) else None,
        needed.get("character_skill") if isinstance(needed, dict) else None,
    )


def emit(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("inventory", "fields", "compare", "fish", "characters"))
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--keys-env", type=Path, help="Archivo privado KEY=VALUE con las claves locales.")
    parser.add_argument("--profile", help="Perfil numérico de una captura con varias copias.")
    parser.add_argument("--file", help="Archivo concreto dentro de una captura tar.")
    parser.add_argument("--section", help="Sección superior que se quiere inspeccionar.")
    parser.add_argument("--depth", type=int, default=5, help="Profundidad para fields (por defecto 5).")
    parser.add_argument("--catalog-dir", type=Path, help="Directorio con char_code_name.json y needed_data.json.")
    parser.add_argument("--values", action="store_true", help="Incluye valores; no publicar la salida.")
    parser.add_argument("--json", action="store_true", help="Salida JSON; por defecto también es JSON.")
    args = parser.parse_args()

    try:
        try:
            keys = read_keys(args.keys_env)
        except ValueError:
            keys = None
        if args.command == "compare":
            if len(args.paths) != 2:
                parser.error("compare requiere exactamente dos rutas")
            result = compare_snapshots(
                load_source(args.paths[0], keys),
                load_source(args.paths[1], keys),
                profile=args.profile,
            )
        else:
            if len(args.paths) != 1:
                parser.error(f"{args.command} requiere una ruta")
            snapshot = load_source(args.paths[0], keys)
            if args.command == "inventory":
                result = inventory(snapshot, args)
            elif args.command == "fields":
                result = fields(snapshot, args)
            elif args.command == "fish":
                result = fish_chip_report(source_view(snapshot, profile=args.profile))
            elif args.command == "characters":
                codes, skins, skills = catalog_paths(args.catalog_dir)
                result = character_report(
                    source_view(snapshot, profile=args.profile).get("gameData", {}),
                    character_codes=codes, skin_catalog=skins, skill_catalog=skills,
                )
            else:  # pragma: no cover
                raise ValueError("Comando desconocido.")
        if not args.values:
            result = strip_values(result)
        emit(result)
    except (OSError, ValueError, tarfile.TarError, LocalSaveError) as exc:
        parser.exit(1, f"Análisis detenido: {exc}\n")


def inventory(snapshot: Snapshot, args: argparse.Namespace) -> dict[str, Any]:
    if snapshot.kind == "aggregate":
        document = snapshot.documents["cloud"]
        if args.section:
            if args.section not in document:
                raise ValueError(f"La sección no existe: {args.section}")
            document = {args.section: document[args.section]}
        return {"kind": snapshot.kind, "sections": section_summary(document)}
    rows = []
    for name, document in snapshot.documents.items():
        if args.section:
            if args.section not in document:
                continue
            document = {args.section: document[args.section]}
        kind = kind_from_filename(name.removeprefix("files/")) or snapshot.kind
        rows.append({"file": name, "kind": kind, "sections": section_summary(document)})
    return {
        "kind": snapshot.kind,
        "files": rows,
        "opaque": snapshot.opaque,
        "file_sizes": {name: meta["bytes"] for name, meta in sorted(snapshot.files.items())},
    }


def fields(snapshot: Snapshot, args: argparse.Namespace) -> dict[str, Any]:
    if args.file:
        if args.file not in snapshot.documents:
            raise ValueError(f"El archivo no está decodificado: {args.file}")
        document = snapshot.documents[args.file]
    elif snapshot.kind == "tar":
        raise ValueError("fields sobre tar requiere --file; usa inventory para ver los archivos.")
    elif snapshot.kind == "directory" and len(snapshot.documents) > 1:
        raise ValueError("fields sobre un directorio con varias copias requiere --file.")
    else:
        document = next(iter(snapshot.documents.values()))
    if args.section:
        if args.section not in document:
            raise ValueError(f"La sección no existe: {args.section}")
        document = document[args.section]
    return {
        "fields": [
            row.as_dict() for row in field_shapes(
                document, max_depth=args.depth, include_samples=args.values,
            )
        ]
    }


def strip_values(value: object) -> object:
    """Elimina valores de saldos y cambios antes de imprimir por defecto."""
    if isinstance(value, dict):
        return {
            key: strip_values(member)
            for key, member in value.items()
            if key not in ("balance", "before", "after", "sample", "value")
        }
    if isinstance(value, list):
        return [strip_values(member) for member in value]
    return value


if __name__ == "__main__":
    main()
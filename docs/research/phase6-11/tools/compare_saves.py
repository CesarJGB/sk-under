"""Compara capturas privadas sin extraer archivos ni escribir partidas."""
import argparse
import json
import tarfile
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree

from app.bridge import read_regular_file
from app.cloud.resource_consistency import (
    GEMS_PREFERENCES, RESOURCES, aggregate_tree, structural_diff,
)
from app.cloud_save import MAX_INPUT_BYTES
from app.parsers.real_save import decode_game_data

CAPTURE_LIMIT = 64 * 1024 * 1024
PREFERENCES = "shared_prefs/com.ChillyRoom.DungeonShooter.v2.playerprefs.xml"


def local_game(payload):
    tree = decode_game_data(payload)
    if tree is None:
        raise ValueError("game.data no coincide con el formato local conocido")
    return {"gameData": tree}


def preference_wallets(payload):
    result = {}
    for entry in ElementTree.fromstring(payload):
        prefix, _, suffix = entry.get("name", "").partition("_")
        if not prefix.isascii() or not prefix.isdecimal():
            prefix, suffix = "", entry.get("name", "")
        if suffix not in GEMS_PREFERENCES:
            continue
        wallet = result.setdefault(prefix, {})
        key = GEMS_PREFERENCES[suffix]
        if key in wallet:
            raise ValueError("Preferencia de saldo duplicada")
        wallet[key] = int(entry.get("value", "")) if entry.tag == "int" else entry.tag
    return result


def snapshot(path):
    if path.suffix == ".tar":
        files = {}
        game, backup, prefs = {}, {}, {}
        if path.stat().st_size > CAPTURE_LIMIT:
            raise ValueError("La captura supera el límite")
        with tarfile.open(path, "r:") as archive:
            for member in archive:
                if not member.isfile():
                    continue
                name = member.name.removeprefix("./")
                if name in files:
                    raise ValueError("La captura contiene rutas duplicadas")
                data = archive.extractfile(member).read()
                files[name] = sha256(data).digest()
                if name == "files/game.data":
                    game = local_game(data)
                elif name == "files/backup.data":
                    # Puede faltar o usar una variante aún desconocida.
                    backup = {"gameData": decode_game_data(data) or {}}
                elif name == PREFERENCES:
                    prefs = preference_wallets(data)
        return game, files, prefs, backup
    payload = read_regular_file(path, limit=MAX_INPUT_BYTES)
    if path.name == "game.data":
        return local_game(payload), None, {}, {}
    return aggregate_tree(payload), None, {}, {}


def wallet(tree):
    game = tree.get("gameData", {})
    return {
        key: game[key] if type(game[key]) is int else type(game[key]).__name__
        for _, key in RESOURCES["gems"].observed_paths
        if key in game
    }


def wallet_diff(before, after):
    return {
        "before": before,
        "after": after,
        "delta": {k: after[k] - value for k, value in before.items()
                  if type(value) is int and type(after.get(k)) is int},
    }


def compare(before, after, *, details=False):
    old_tree, old_files, old_prefs, old_backup = snapshot(before)
    new_tree, new_files, new_prefs, new_backup = snapshot(after)
    # Comparar solo gameData al cruzar un archivo local con un agregado remoto.
    if ("serialzedVersion" in old_tree) != ("serialzedVersion" in new_tree):
        old_tree = {k: old_tree[k] for k in ("gameData",) if k in old_tree}
        new_tree = {k: new_tree[k] for k in ("gameData",) if k in new_tree}
    changes = structural_diff(old_tree, new_tree)
    old_wallet, new_wallet = wallet(old_tree), wallet(new_tree)
    report = {
        **wallet_diff(old_wallet, new_wallet),
        "structural_changes": len(changes),
    }
    if old_backup or new_backup:
        report["backup_wallet"] = wallet_diff(wallet(old_backup), wallet(new_backup))
    if old_prefs or new_prefs:
        report["preferences_wallets"] = [
            wallet_diff(old_prefs.get(profile, {}), new_prefs.get(profile, {}))
            for profile in sorted(old_prefs.keys() | new_prefs.keys())
        ]
    if old_files is not None and new_files is not None:
        report["files_changed"] = {
            "added": sorted(new_files.keys() - old_files.keys()),
            "removed": sorted(old_files.keys() - new_files.keys()),
            "modified": sorted(k for k in old_files.keys() & new_files.keys()
                               if old_files[k] != new_files[k]),
        }
    if details:
        report["changes"] = changes
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--details", action="store_true", help="Incluye rutas y valores privados")
    args = parser.parse_args()
    try:
        print(json.dumps(compare(args.before, args.after, details=args.details), ensure_ascii=False, indent=2))
    except (OSError, ValueError, tarfile.TarError, ElementTree.ParseError) as exc:
        parser.exit(1, f"Comparación detenida: {exc}\n")


if __name__ == "__main__":
    main()

"""Mantenimiento administrativo del almacén y los respaldos nativos.

No inicia sesión, no contacta con ChillyRoom y no muestra identificadores. La
migración cifra los respaldos de la Fase 6.8 que aún estaban en claro. El
comando de limpieza elimina sesiones caducadas y perfiles automáticos no
vinculados, sin tocar perfiles activos ni respaldos.
"""

from __future__ import annotations

import argparse
import json
import sys
from ..cloud.backup_store import BackupStoreError, LabBackupStore
from ..settings import Settings
from .errors import NativeError
from .store import NativeStore


def _store(settings: Settings) -> NativeStore:
    if settings.native_store_key is None:
        raise NativeError("Falta SK_NATIVE_STORE_KEY.")
    return NativeStore(
        settings.native_store_path,
        bytes.fromhex(settings.native_store_key.get_secret_value()),
        idle_seconds=settings.native_idle_seconds,
        absolute_seconds=settings.native_absolute_seconds,
        login_attempts=settings.native_login_attempts,
        login_window_seconds=settings.native_login_window_seconds,
    )


def migrate_backups(settings: Settings) -> dict[str, object]:
    key = settings.native_backup_key_bytes()
    if key is None:
        raise NativeError("Falta una clave para cifrar los respaldos nativos.")
    root = settings.native_backup_path
    if not root.exists():
        return {"migrated": 0, "directories": 0}
    directories = [
        item for item in root.iterdir()
        if item.is_dir() and not item.is_symlink() and len(item.name) == 64
        and all(char in "0123456789abcdef" for char in item.name)
    ]
    migrated = 0
    for directory in directories:
        store = LabBackupStore(directory, cipher_key=key)
        migrated += store.migrate_legacy()
    return {"migrated": migrated, "directories": len(directories)}


def run(settings: Settings, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mantenimiento privado de SK-Under.")
    parser.add_argument(
        "command", choices=["migrate-backups", "cleanup", "profiles"],
        help="migrate-backups cifra respaldos antiguos; cleanup purga datos caducados; profiles lista metadatos.",
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "migrate-backups":
            print(json.dumps(migrate_backups(settings), ensure_ascii=False))
            return 0
        store = _store(settings)
        if args.command == "cleanup":
            store.cleanup()
            print(json.dumps({"cleanup": "ok"}, ensure_ascii=False))
            return 0
        print(json.dumps({"profiles": [item.public() for item in store.list_profiles()]}, ensure_ascii=False))
        return 0
    except (NativeError, BackupStoreError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError):
        print("No se pudo completar el mantenimiento privado.", file=sys.stderr)
        return 1


def main() -> None:
    raise SystemExit(run(Settings(), sys.argv[1:]))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""CLI Linux para autenticar una cuenta de ChillyRoom y descargar su partida.

Uso interactivo (recomendado):

    python3 experiments/phase6-7/native_auth_cli.py \
      --distro-id '<uuid de la instalación>' --download /ruta/privada/partida.json

La contraseña se solicita sin eco. Para automatización controlada existe
``--password-stdin``; no se acepta la contraseña como argumento de línea de
comandos porque quedaría en el historial y en la lista de procesos.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from native_auth import (
    AuthIdentityError,
    AuthProtocolError,
    AuthRejected,
    AuthTransportError,
    NativeAuthError,
    Session,
    authenticate,
)


def _prompt_email() -> str:
    return input("Correo de la cuenta: ").strip()


def _read_password(password_stdin: bool) -> str:
    if password_stdin:
        value = sys.stdin.readline()
        if not value:
            raise NativeAuthError("No se recibió la contraseña por stdin.")
        return value.rstrip("\n")
    if not sys.stdin.isatty():
        raise NativeAuthError("La contraseña requiere una terminal interactiva.")
    return getpass.getpass("Contraseña: ")


def _write_private(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        raise NativeAuthError("El archivo de salida ya existe; no se sobrescribe.") from None
    except OSError:
        raise NativeAuthError("No se pudo crear el archivo privado de salida.") from None
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


def _download(session: Session, unique_id: str, output: Path, timeout: float) -> dict[str, object]:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
    try:
        from app.cloud.modern import ModernCloudSaveProvider  # noqa: PLC0415
        from app.cloud_save import CloudSaveError, reconstruct_cloud_save  # noqa: PLC0415
    except ImportError:
        raise NativeAuthError("No se pudo cargar el proveedor de descarga del backend.") from None

    try:
        provider = ModernCloudSaveProvider(
            session.token, unique_id, session.distro_id, timeout=timeout
        )
        copy = provider.download()
        save = reconstruct_cloud_save(copy.payload)
    except CloudSaveError as exc:
        raise AuthProtocolError(f"La descarga o validación falló: {type(exc).__name__}.") from None
    _write_private(output, copy.payload)
    return {
        "bytes": copy.metadata.size,
        "sha256": copy.metadata.sha256,
        "gems": save.data.game_data.get("gems"),
        "output": str(output),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Login Linux experimental de ChillyRoom (Android Global 8.8.0)."
    )
    parser.add_argument(
        "--distro-id",
        default=os.environ.get("SK_NATIVE_DISTRO_ID", ""),
        help="UUID de distribución observado; también SK_NATIVE_DISTRO_ID.",
    )
    parser.add_argument(
        "--unique-id",
        default=os.environ.get("SK_NATIVE_UNIQUE_ID", ""),
        help="Identificador de instalación para BlobSave; también SK_NATIVE_UNIQUE_ID.",
    )
    parser.add_argument("--email", help="Correo; si falta se solicita.")
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Lee la contraseña de una línea de stdin (solo automatización controlada).",
    )
    parser.add_argument("--download", type=Path, help="Archivo privado de salida para la partida.")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--session-file",
        type=Path,
        help="Opcional: guarda token y vigencia en un archivo 0600 para integración.",
    )
    parser.add_argument("--json", action="store_true", help="Salida JSON sanitizada.")
    args = parser.parse_args(argv)

    if not args.distro_id:
        parser.error("Falta --distro-id o SK_NATIVE_DISTRO_ID.")
    if args.download and not args.unique_id:
        parser.error("--download requiere --unique-id o SK_NATIVE_UNIQUE_ID.")

    email = args.email or _prompt_email()
    try:
        password = _read_password(args.password_stdin)
        session = authenticate(
            email, password, distro_id=args.distro_id, timeout=args.timeout
        )
        del password
        result: dict[str, object] = {
            "ok": True,
            "session": session.summary(),
            "identity_verified": True,
            "download": None,
        }
        if args.session_file:
            args.session_file.parent.mkdir(parents=True, exist_ok=True)
            _write_private(
                args.session_file,
                json.dumps(
                    {
                        "token": session.token,
                        "uid": session.uid,
                        "expire": session.expire,
                        "distro_id": session.distro_id,
                    }
                ).encode("utf-8"),
            )
        if args.download:
            result["download"] = _download(
                session, args.unique_id, args.download, args.timeout
            )
    except AuthRejected as exc:
        print(
            json.dumps({"ok": False, "error": "rejected", "status": exc.status, "code": exc.code}),
            file=sys.stderr,
        )
        return 1
    except (AuthTransportError, AuthProtocolError, AuthIdentityError, NativeAuthError) as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__}), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        summary = result["session"]
        print(json.dumps(summary, indent=2, sort_keys=True))
        if result["download"]:
            print(json.dumps(result["download"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

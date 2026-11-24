"""Aprovisiona perfiles de instalación Android Global en el almacén cifrado.

Uso previsto: un proceso privado del propietario, con la misma
``SK_NATIVE_STORE_KEY`` y el mismo volumen que la API. Los identificadores se
leen sin eco (o de una entrada estándar controlada) y nunca se imprimen. El
perfil queda sin vincular y se vincula a la identidad en el primer inicio de
sesión; desde ese momento no se puede reutilizar para otra cuenta.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys

from ..settings import Settings
from .distributions import DISTRIBUTIONS
from .errors import NativeError
from .store import NativeStore


def _read_line(prompt: str, *, allow_empty: bool = False) -> str:
    try:
        value = getpass.getpass(prompt)
    except (EOFError, KeyboardInterrupt):
        raise NativeError("Entrada cancelada.") from None
    value = value.strip()
    if not value and not allow_empty:
        raise NativeError("El identificador no puede estar vacío.")
    return value


def _from_stdin() -> str:
    line = sys.stdin.readline()
    if not line:
        raise NativeError("Faltó la entrada esperada por la entrada estándar.")
    return line.strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aprovisiona un perfil de instalación nativa (sin red, sin contraseñas)."
    )
    parser.add_argument("--list", action="store_true", help="Lista los perfiles existentes sin mostrar secretos.")
    parser.add_argument("--label", help="Etiqueta local visible para el propietario (1-80 caracteres).")
    parser.add_argument("--distribution", default="android-global", choices=[item.id for item in DISTRIBUTIONS])
    parser.add_argument("--allow-write", action="store_true", help="Autoriza escritura para este perfil.")
    parser.add_argument("--no-unique", action="store_true", help="Crea el perfil con la instalación pendiente.")
    parser.add_argument("--distro-stdin", action="store_true", help="Lee la distribución de la entrada estándar.")
    parser.add_argument("--unique-stdin", action="store_true", help="Lee la instalación de la entrada estándar.")
    return parser


def run(settings: Settings, argv: list[str] | None = None, *, stdin_reader=_from_stdin) -> int:
    args = build_parser().parse_args(argv)
    if settings.native_store_key is None:
        print("Falta SK_NATIVE_STORE_KEY (64 dígitos hexadecimales).", file=sys.stderr)
        return 1
    try:
        store = NativeStore(
            settings.native_store_path,
            bytes.fromhex(settings.native_store_key.get_secret_value()),
            idle_seconds=settings.native_idle_seconds,
            absolute_seconds=settings.native_absolute_seconds,
            login_attempts=settings.native_login_attempts,
            login_window_seconds=settings.native_login_window_seconds,
        )
        if args.list:
            print(json.dumps({"profiles": [profile.public() for profile in store.list_profiles()]}, ensure_ascii=False))
            return 0
        if not args.label:
            print("Falta --label.", file=sys.stderr)
            return 1
        distro = stdin_reader() if args.distro_stdin else _read_line(
            "Identificador de distribución (sin eco): "
        )
        unique = None
        if not args.no_unique:
            unique = stdin_reader() if args.unique_stdin else _read_line(
                "Identificador de instalación (sin eco; vacío para dejarlo pendiente): ",
                allow_empty=True,
            ) or None
        profile = store.create_profile(
            label=args.label,
            distribution_id=args.distribution,
            distro_id=distro,
            unique_id=unique,
            allow_write=args.allow_write,
        )
        print(json.dumps({
            "profile": profile.public(),
            "message": "Perfil creado. Inicia sesión desde la web para vincularlo a su identidad.",
        }, ensure_ascii=False))
        return 0
    except NativeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError):
        print("No se pudo aprovisionar el perfil en el almacén privado.", file=sys.stderr)
        return 1


def main() -> None:
    raise SystemExit(run(Settings()))


if __name__ == "__main__":
    main()

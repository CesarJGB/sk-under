"""Generación de la identidad de instalación de una cuenta.

La Fase 6.9 comprobó que el gateway acepta un ``x-distro-id`` UUID v4 generado
por el cliente y que ``x-unique-id`` es un código de instalación con la forma
``<prefijo>_<16 hex>``. El prefijo observado en la instalación Android Global
del laboratorio es ``xiaomioutseas``; el sufijo lo genera el cliente y el
servicio lo vincula a la cuenta al abrir la partida.

Este módulo no copia identificadores de otras instalaciones ni reutiliza los de
una cuenta en otra. Cada perfil recibe un par nuevo y el almacén lo conserva
cifrado. El proveedor puede limitar la vinculación de dispositivos nuevos
(``error 100509``); esa restricción se respeta en el servicio y nunca se evita
regenerando identificadores en cada acceso.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from uuid import UUID, uuid4

# Prefijo de canal/región observado en la instalación Android Global 8.8.0.
# Solo se usa para construir un valor nuevo; no se toma de otra cuenta.
DEVICE_PREFIX = "xiaomioutseas"
_DEVICE_PREFIX_RE = re.compile(r"^[a-z0-9]{3,24}$")
_DISTRO_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_UNIQUE_RE = re.compile(r"^[a-z0-9]{3,24}_[0-9a-f]{16}$")


@dataclass(frozen=True)
class GeneratedIdentity:
    """Par de instalación generado localmente, sin relación con otra cuenta."""

    distro_id: str
    unique_id: str


def generate_distro_id() -> str:
    """UUID v4 con el formato que el gateway aceptó en la prueba real."""

    return str(uuid4())


def generate_unique_id(prefix: str = DEVICE_PREFIX) -> str:
    """Código de instalación nuevo: prefijo observado + 16 dígitos hex.

    El sufijo se genera con ``secrets`` y no se deriva del correo, del UID ni
    de otro perfil. El servidor lo vincula a la cuenta en el primer uso; por
    eso el llamador debe persistirlo y reutilizarlo.
    """

    if not isinstance(prefix, str) or not _DEVICE_PREFIX_RE.fullmatch(prefix):
        raise ValueError("El prefijo del identificador de instalación no es válido.")
    return f"{prefix}_{secrets.token_hex(8)}"


def generate_identity(prefix: str = DEVICE_PREFIX) -> GeneratedIdentity:
    return GeneratedIdentity(
        distro_id=generate_distro_id(),
        unique_id=generate_unique_id(prefix),
    )


def is_generated_distro(value: object) -> bool:
    return isinstance(value, str) and bool(_DISTRO_RE.fullmatch(value))


def is_generated_unique(value: object) -> bool:
    return isinstance(value, str) and bool(_UNIQUE_RE.fullmatch(value))


def distro_uuid(value: object) -> UUID | None:
    """Devuelve el UUID si el valor es un UUID v4 válido; si no, ``None``."""

    if not is_generated_distro(value):
        return None
    return UUID(value)

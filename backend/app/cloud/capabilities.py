"""Matriz única de capacidades por plataforma y función.

La disponibilidad de una operación no se deduce de que Android e iOS compartan
el mismo transporte. Cada función declara un estado explícito y la interfaz
solo habilita lo que la evidencia permite:

* ``read_only``: la función no escribe en la nube (descarga, respaldo,
  preparación local o verificación).
* ``write_pending_validation``: falta evidencia propia de que el proveedor
  acepte y persista la escritura para esa plataforma.
* ``write_experimental``: existe un mecanismo identificado, pero todavía no se
  ha validado de extremo a extremo.
* ``write_verified``: la escritura se ha probado con una cuenta autorizada,
  respaldo, confirmación y verificación de persistencia.

Los estados describen la capacidad de la plataforma, no los permisos de una
cuenta concreta. El servicio nativo sigue aplicando además el interruptor
global, la autorización del perfil y la preparación de la instalación.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Collection, Literal

type CapabilityState = Literal[
    "read_only",
    "write_pending_validation",
    "write_experimental",
    "write_verified",
]
type PlatformName = Literal["android", "ios", "unknown"]

STATES: frozenset[str] = frozenset(
    {"read_only", "write_pending_validation", "write_experimental", "write_verified"}
)

# Fase 10.2: la cuenta de pruebas expresamente autorizada por el propietario.
# Solo se guarda un digest con separación de dominio; nunca el correo ni la
# contraseña. La escritura iOS general sigue en ``write_pending_validation``.
_EXPERIMENTAL_DOMAIN = b"sk-under/phase10-2/ios-experimental\x00"
DEFAULT_IOS_EXPERIMENTAL_ACCOUNT_DIGESTS: frozenset[str] = frozenset(
    {"2167e7eb7bdaa3b08402534f6df4502d6663e1ca615c2f1f1c42a11057a7f09a"}
)


def account_digest(email: str) -> str:
    """Huella estable de una cuenta, sin conservar el correo en claro."""

    return sha256(_EXPERIMENTAL_DOMAIN + email.strip().casefold().encode("utf-8")).hexdigest()


def experimental_account(email: str | None, extra: Collection[str] = ()) -> bool:
    if not isinstance(email, str) or not email.strip():
        return False
    digest = account_digest(email)
    return digest in DEFAULT_IOS_EXPERIMENTAL_ACCOUNT_DIGESTS or digest in extra


@dataclass(frozen=True)
class CapabilityFunction:
    id: str
    label: str
    state: CapabilityState
    detail: str

    def summary(self) -> dict[str, str]:
        return {
            "id": self.id,
            "label": self.label,
            "state": self.state,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class PlatformCapabilities:
    platform: PlatformName
    state: CapabilityState
    read_ready: bool
    prepare_ready: bool
    write_supported: bool
    functions: tuple[CapabilityFunction, ...]
    reason: str
    evidence: str
    confirmation: str

    def summary(self) -> dict[str, object]:
        return {
            "platform": self.platform,
            "state": self.state,
            "read_ready": self.read_ready,
            "prepare_ready": self.prepare_ready,
            "write_supported": self.write_supported,
            "functions": {
                function.id: function.summary() for function in self.functions
            },
            "reason": self.reason,
            "evidence": self.evidence,
            "confirmation": self.confirmation,
        }


_COMMON_CONFIRMATION = (
    "Toda escritura exige respaldo completo previo, confirmación explícita, "
    "detección de cambios remotos y verificación de persistencia posterior."
)

_READ_FUNCTIONS = (
    ("authentication", "Autenticación", "Inicio de sesión y sesión aislada por cuenta."),
    ("download", "Descarga", "Descarga y validación de la partida remota."),
    ("backup", "Respaldos", "Copia cifrada local antes de preparar o escribir."),
    ("prepare", "Preparación de cambios", "Candidato local validado; no envía nada a la nube."),
    ("verify", "Verificación", "Comparación de la copia remota con un respaldo o candidato."),
)


def _functions(
    *,
    save: CapabilityState,
    restore: CapabilityState,
    save_detail: str,
    restore_detail: str,
) -> tuple[CapabilityFunction, ...]:
    read = tuple(
        CapabilityFunction(id=item[0], label=item[1], state="read_only", detail=item[2])
        for item in _READ_FUNCTIONS
    )
    return read + (
        CapabilityFunction(id="save", label="Subida", state=save, detail=save_detail),
        CapabilityFunction(
            id="restore", label="Restauración remota", state=restore, detail=restore_detail
        ),
    )


_DEFINITIONS: dict[PlatformName, PlatformCapabilities] = {
    "android": PlatformCapabilities(
        platform="android",
        state="write_verified",
        read_ready=True,
        prepare_ready=True,
        write_supported=True,
        functions=_functions(
            save="write_verified",
            restore="write_verified",
            save_detail=(
                "Flujo Android validado con respaldo, confirmación y verificación "
                "de persistencia en el laboratorio autorizado."
            ),
            restore_detail=(
                "Restauración Android validada con respaldo preventivo y "
                "verificación de la copia remota."
            ),
        ),
        reason="La escritura remota Android cuenta con validación propia.",
        evidence="Validación del flujo Android existente; no se extrapola a iOS.",
        confirmation=_COMMON_CONFIRMATION,
    ),
    "ios": PlatformCapabilities(
        platform="ios",
        state="write_pending_validation",
        read_ready=True,
        prepare_ready=True,
        write_supported=False,
        functions=_functions(
            save="write_pending_validation",
            restore="write_pending_validation",
            save_detail=(
                "La autenticación y la descarga están verificadas, pero no hay "
                "evidencia de que una sesión iOS acepte y persista una subida."
            ),
            restore_detail=(
                "La restauración usa la misma escritura remota pendiente de "
                "validación; no se envía ningún candidato."
            ),
        ),
        reason=(
            "No se ha validado con una cuenta iOS autorizada que BlobSave/Upload "
            "acepte el candidato y que Soul Knight lo conserve. La semejanza "
            "estructural con Android no es prueba de escritura."
        ),
        evidence=(
            "Login y descarga iOS verificados (8.8.0.14, respuesta IOS_). "
            "Publicaciones oficiales describen la subida solo desde el cliente. "
            "CRDE edita iOS, pero su mecanismo remoto no es público ni se ha "
            "reproducido. No se ha realizado ninguna subida iOS."
        ),
        confirmation=_COMMON_CONFIRMATION,
    ),
}


_IOS_EXPERIMENTAL = PlatformCapabilities(
    platform="ios",
    state="write_experimental",
    read_ready=True,
    prepare_ready=True,
    write_supported=True,
    functions=_functions(
        save="write_experimental",
        restore="write_experimental",
        save_detail=(
            "Subida iOS experimental limitada a la cuenta autorizada. La Fase "
            "10.2 confirmó aceptación y persistencia del servidor, pero el "
            "cliente oficial rechazó la copia por metadatos de versión; la "
            "Fase 10.1 corrige el protocolo y espera validación física."
        ),
        restore_detail=(
            "Restauración iOS experimental limitada a la cuenta autorizada. "
            "La escritura usa la versión de protocolo 8.8.0; no se declara "
            "compatible hasta que el cliente oficial recupere la copia."
        ),
    ),
    reason=(
        "Modo experimental limitado a la cuenta de pruebas autorizada. La "
        "escritura iOS general todavía no está validada ni habilitada."
    ),
    evidence=(
        "Fase 10.2, 2026-11-27: subida aceptada con HTTP 200 y persistencia "
        "exacta en el servidor, pero el cliente iOS mostró 'versión demasiado "
        "antigua'. Fase 10.1: causa identificada en x-app-version/x-game-version "
        "(se enviaba 8.8.0.13 en vez de 8.8.0); pendiente de prueba física."
        " No se generaliza a otras cuentas iOS."
    ),
    confirmation=_COMMON_CONFIRMATION,
)


def capability_matrix(
    platform: object, *, experimental_authorized: bool = False
) -> PlatformCapabilities:
    """Devuelve la matriz de una plataforma validada.

    Las plataformas desconocidas no heredan la capacidad Android: se degradan a
    solo lectura y sin preparación remota. ``experimental_authorized`` solo lo
    activa el servicio para la cuenta de pruebas autorizada.
    """

    if platform == "ios" and experimental_authorized:
        return _IOS_EXPERIMENTAL
    if platform in _DEFINITIONS:
        return _DEFINITIONS[platform]  # type: ignore[index]
    return PlatformCapabilities(
        platform="unknown",
        state="read_only",
        read_ready=False,
        prepare_ready=False,
        write_supported=False,
        functions=tuple(
            CapabilityFunction(
                id=item[0],
                label=item[1],
                state="read_only",
                detail="Plataforma no reconocida; no se habilita ninguna operación.",
            )
            for item in _READ_FUNCTIONS
        ),
        reason="La plataforma no está registrada o no está validada.",
        evidence="Sin evidencia para esta plataforma.",
        confirmation=_COMMON_CONFIRMATION,
    )


def write_state(platform: object, *, experimental_authorized: bool = False) -> CapabilityState:
    return capability_matrix(platform, experimental_authorized=experimental_authorized).state


def can_prepare(platform: object) -> bool:
    return capability_matrix(platform).prepare_ready


def can_write(platform: object, *, experimental_authorized: bool = False) -> bool:
    return capability_matrix(platform, experimental_authorized=experimental_authorized).write_supported
"""Registro extensible de distribuciones de Soul Knight.

``android-global`` es la distribución validada para lectura y escritura.
``ios-global`` está validada para autenticación y descarga con la cuenta iOS
autorizada; su escritura remota sigue limitada a la cuenta experimental hasta
que el cliente oficial confirme la recuperación. ``game_version`` es la versión
visible (iOS 8.8.0.14); ``protocol_*_version`` es la que entiende BlobSave
(8.8.0 en ambas plataformas). Las demás
distribuciones se enumeran para que el frontend las muestre, pero no se
presentan como funcionales. Añadir una distribución nueva exige cambiar este
registro y aportar evidencia propia; no hay lógica de distribución repartida
por el resto del código.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..cloud.compatibility import profile_for
from .errors import NativeDistributionDisabled, NativeDistributionUnknown

type Platform = Literal["android", "ios"]


@dataclass(frozen=True)
class Distribution:
    id: str
    label: str
    platform: Platform | None
    game_version: str
    enabled: bool
    validated: bool
    note: str
    # Versión que viaja en las cabeceras del protocolo (x-app-version y
    # x-game-version). No es la versión comercial/mostrada por la tienda:
    # iOS muestra 8.8.0.14, pero el cliente y el servidor comparan 8.8.0.
    protocol_app_version: str = "8.8.0"
    protocol_game_version: str = "8.8.0"

    def __post_init__(self) -> None:
        # El registro de compatibilidad es la fuente de verdad de las versiones
        # validadas. Si una distribución habilitada declara otra versión o
        # protocolo, el proceso falla al importar en lugar de escribir con un
        # perfil incoherente.
        if not (self.enabled and self.validated and self.platform):
            return
        profile = profile_for(self.id, self.game_version)
        if profile is None:
            raise ValueError(
                f"La distribución {self.id} {self.game_version} no tiene perfil de compatibilidad."
            )
        if (
            profile.protocol_app_version != self.protocol_app_version
            or profile.protocol_game_version != self.protocol_game_version
        ):
            raise ValueError(
                f"El protocolo de {self.id} no coincide con su perfil de compatibilidad."
            )

    def public(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "platform": self.platform,
            "game_version": self.game_version,
            "protocol_app_version": self.protocol_app_version,
            "protocol_game_version": self.protocol_game_version,
            "enabled": self.enabled,
            "validated": self.validated,
            "note": self.note,
        }


DISTRIBUTIONS: tuple[Distribution, ...] = (
    Distribution(
        id="android-global",
        label="Android Global (GP)",
        platform="android",
        game_version="8.8.0",
        enabled=True,
        validated=True,
        note="Distribución validada en el laboratorio con la cuenta autorizada.",
    ),
    Distribution(
        id="android-vietnam",
        label="Android Vietnam (GP_VNM)",
        platform="android",
        game_version="8.8.0",
        enabled=False,
        validated=False,
        note="Distribución no validada. No se usa para autenticar en esta fase.",
    ),
    Distribution(
        id="ios-global",
        label="iOS Global (IOS)",
        platform="ios",
        game_version="8.8.0.14",
        enabled=True,
        validated=True,
        note=(
            "Login y descarga verificados (compilación 8.8.0.14). El cuarto "
            "componente es compilación/hotfix; el protocolo usa 8.8.0. La "
            "escritura remota está habilitada en modo de prueba, pendiente de "
            "validación en el cliente oficial."
        ),
    ),
    Distribution(
        id="ios-vietnam",
        label="iOS Vietnam (IOS_VNM)",
        platform="ios",
        game_version="8.8.0",
        enabled=False,
        validated=False,
        note="Distribución regional no validada.",
    ),
    Distribution(
        id="ios-china",
        label="iOS China (IOS_CN)",
        platform="ios",
        game_version="8.8.0",
        enabled=False,
        validated=False,
        note="Distribución regional no validada.",
    ),
    Distribution(
        id="taptap",
        label="TapTap",
        platform="android",
        game_version="8.8.0",
        enabled=False,
        validated=False,
        note="Distribución TapTap no validada.",
    ),
)

_BY_ID = {distribution.id: distribution for distribution in DISTRIBUTIONS}


def get_distribution(distribution_id: object) -> Distribution:
    if not isinstance(distribution_id, str) or distribution_id not in _BY_ID:
        raise NativeDistributionUnknown("La distribución seleccionada no existe.")
    return _BY_ID[distribution_id]


def require_enabled(distribution_id: object) -> Distribution:
    distribution = get_distribution(distribution_id)
    if not distribution.enabled or not distribution.validated or distribution.platform is None:
        raise NativeDistributionDisabled(
            "Esta distribución todavía no está validada. Usa Android Global o iOS Global."
        )
    return distribution


def enabled_distributions() -> tuple[Distribution, ...]:
    return tuple(item for item in DISTRIBUTIONS if item.enabled and item.validated)

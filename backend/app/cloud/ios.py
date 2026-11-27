"""Importación y lectura de copias de iOS.

Se han verificado dos representaciones legítimas:

* la copia nativa descargada del servicio de guardado, con ``platformId``
  igual a ``IOS`` y ``cloudSaveId`` con prefijo ``IOS_``;
* la representación RAW de CRDE, que elimina esos metadatos y los sustituye
  por ``_crde_misc.platformId`` igual a ``IOS``.

La descarga nativa usa el mismo contrato de transporte que Android, pero la
plataforma se selecciona por el distro del jugador, no por la cabecera
``x-platform``. La escritura remota de iOS no está validada: este módulo y el
servicio nativo mantienen iOS en solo lectura.

El documento original se conserva byte a byte. El informe se construye con los
mismos analizadores de solo lectura que usa Android, pero nunca se habilita una
operación de escritura para iOS.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Literal

from ..cloud_save import (
    MAX_INPUT_BYTES,
    OBJECT_SECTIONS,
    AggregateFormatError,
    CloudSaveError,
    CopyLimitError,
    JsonObject,
    unpack_cloud_save,
)
from ..parsers.json_document import parse_json
from ..save_report import build_save_report

type IosSource = Literal["crde-raw", "native-json"]

CAPABILITIES: tuple[dict[str, str], ...] = (
    {
        "id": "resources",
        "label": "Monedas y recursos",
        "read": "read_compatible",
        "write": "not_exposed",
        "evidence": "E2",
        "note": "Valores observados en la muestra RAW de iOS; no se ha validado escritura.",
    },
    {
        "id": "characters",
        "label": "Personajes y niveles",
        "read": "read_compatible",
        "write": "not_exposed",
        "evidence": "E2",
        "note": "Mismos campos observados que Android; la persistencia iOS no está validada.",
    },
    {
        "id": "skills",
        "label": "Habilidades",
        "read": "read_compatible",
        "write": "not_exposed",
        "evidence": "E2",
        "note": "Estructura observada; sin prueba de escritura en iOS.",
    },
    {
        "id": "character_skins",
        "label": "Skins de personaje",
        "read": "read_compatible",
        "write": "not_exposed",
        "evidence": "E2",
        "note": "skinLock se interpreta solo como lectura; el valor 1 no se extrapola a iOS sin prueba.",
    },
    {
        "id": "weapon_skins",
        "label": "Skins de armas",
        "read": "read_compatible",
        "write": "not_exposed",
        "evidence": "E2",
        "note": "Catálogo compartido; falta confirmación en iOS físico.",
    },
    {
        "id": "kill_effects",
        "label": "Efectos de eliminación",
        "read": "read_compatible",
        "write": "not_exposed",
        "evidence": "E2",
        "note": "Catálogo compartido; falta confirmación en iOS físico.",
    },
    {
        "id": "pets",
        "label": "Mascotas y afinidad",
        "read": "read_compatible",
        "write": "not_exposed",
        "evidence": "E2",
        "note": "Campos observados; la afinidad y sus topes no se validan en iOS.",
    },
    {
        "id": "decorations",
        "label": "Decoraciones y vestíbulo",
        "read": "pending",
        "write": "not_exposed",
        "evidence": "E2",
        "note": "Se muestran solo datos presentes; la relación entre posesión y disponibilidad sigue siendo hipótesis.",
    },
    {
        "id": "blueprints",
        "label": "Planos",
        "read": "read_compatible",
        "write": "not_exposed",
        "evidence": "E2",
        "note": "En iOS se observaron valores enteros; no se escriben.",
    },
    {
        "id": "progression",
        "label": "Progreso y desbloqueos",
        "read": "read_compatible",
        "write": "not_exposed",
        "evidence": "E2",
        "note": "Solo lectura; los desbloqueos no se consideran validados en iOS.",
    },
    {
        "id": "remote_auth",
        "label": "Autenticación y descarga remota",
        "read": "read_compatible",
        "write": "not_exposed",
        "evidence": "E3",
        "note": "Login y descarga verificados con la cuenta iOS autorizada (8.8.0.14). La escritura remota no está validada.",
    },
)


class IosSaveError(CloudSaveError):
    code = "ios_save"


class NotIosSave(IosSaveError):
    code = "ios_not_detected"


class UnsupportedIosEncoding(IosSaveError):
    code = "ios_unsupported_encoding"


@dataclass(frozen=True)
class IosSave:
    original: bytes = field(repr=False)
    encoding: str
    source: IosSource
    serialzed_version: int | None
    cloud_save_id: str | None = field(repr=False)
    platform_id: str = field(repr=False)
    game_version: int | None
    app_version: int | None
    game_data: JsonObject = field(repr=False)
    optional_sections: JsonObject = field(repr=False)
    crde_misc: JsonObject | None = field(repr=False)
    extra_fields: JsonObject = field(repr=False)

    @property
    def size(self) -> int:
        return len(self.original)

    @property
    def sha256(self) -> str:
        return sha256(self.original).hexdigest()

    def summary(self) -> dict[str, object]:
        sections: dict[str, str] = {"gameData": "present"}
        for name in OBJECT_SECTIONS:
            if name not in self.optional_sections:
                sections[name] = "missing"
            elif self.optional_sections[name] is None:
                sections[name] = "null"
            else:
                sections[name] = "present"
        return {
            "experimental": True,
            "platform": "ios",
            "source": self.source,
            "encoding": self.encoding,
            "size": self.size,
            "sha256": self.sha256,
            "serialzed_version": self.serialzed_version,
            "game_version": self.game_version,
            "app_version": self.app_version,
            "has_cloud_save_id": self.cloud_save_id is not None,
            "has_platform_id": bool(self.platform_id),
            "has_crde_metadata": self.crde_misc is not None,
            "has_maps": "maps" in self.optional_sections,
            "sections": sections,
            "write_enabled": False,
            "capabilities": list(CAPABILITIES),
        }

    def report(self) -> dict[str, object]:
        document: dict[str, object] = dict(self.optional_sections)
        document["gameData"] = self.game_data
        report = build_save_report(document, platform="ios")
        report.update(
            {
                "platform": "ios",
                "source": self.source,
                "serialzed_version": self.serialzed_version,
                "encoding": self.encoding,
                "sha256": self.sha256,
                "read_only": True,
                "write_enabled": False,
            }
        )
        return report


def _platform_marker(root: dict[str, object]) -> tuple[IosSource, str, JsonObject | None]:
    misc = root.get("_crde_misc")
    if isinstance(misc, dict):
        value = misc.get("platformId")
        if isinstance(value, str) and value.strip().upper() == "IOS":
            return "crde-raw", value, misc
        if value is not None:
            raise NotIosSave("La copia contiene metadatos de CRDE que no identifican iOS.")
    value = root.get("platformId")
    if isinstance(value, str) and value.strip().upper() == "IOS":
        return "native-json", value, None
    if isinstance(value, str) and value.strip():
        raise NotIosSave("La copia identifica otra plataforma y no se importa como iOS.")
    raise NotIosSave(
        "No se reconoce una copia de iOS: falta platformId IOS o los metadatos de CRDE."
    )


def decode_ios_save(source: bytes) -> IosSave:
    """Decodifica una copia iOS ya extraída, sin modificarla ni interpretar más de lo observado."""
    if not source:
        raise CopyLimitError("La copia está vacía.")
    if len(source) > MAX_INPUT_BYTES:
        raise CopyLimitError("La copia supera el límite permitido.")
    try:
        encoding, document = unpack_cloud_save(source)
    except CloudSaveError:
        raise
    except (ValueError, RecursionError):
        raise UnsupportedIosEncoding("El documento no contiene JSON UTF-8 válido.") from None
    try:
        root = parse_json(document)
    except (ValueError, RecursionError):
        raise UnsupportedIosEncoding("El documento no contiene JSON UTF-8 válido.") from None
    if not isinstance(root, dict):
        raise AggregateFormatError("Se esperaba un objeto JSON en la raíz.")

    platform, platform_id, crde_misc = _platform_marker(root)
    game_data = root.get("gameData")
    if not isinstance(game_data, dict):
        raise AggregateFormatError("La copia de iOS no contiene gameData como objeto JSON.")

    for name in OBJECT_SECTIONS:
        section = root.get(name)
        if section is not None and not isinstance(section, dict):
            raise AggregateFormatError(f"La sección {name} debe ser un objeto JSON o nula.")

    version = root.get("serialzedVersion")
    if version is not None and (type(version) is not int or version < 0):
        raise AggregateFormatError("serialzedVersion debe ser un entero no negativo o estar ausente.")
    cloud_save_id = root.get("cloudSaveId")
    if cloud_save_id is not None and (not isinstance(cloud_save_id, str) or not cloud_save_id.strip()):
        raise AggregateFormatError("cloudSaveId debe ser texto no vacío o estar ausente.")

    game_version = game_data.get("gameVersion")
    item_data = root.get("itemData")
    app_version = item_data.get("AppVersion") if isinstance(item_data, dict) else None
    known = {
        "serialzedVersion",
        "cloudSaveId",
        "platformId",
        "gameData",
        "_crde_misc",
        *OBJECT_SECTIONS,
        "maps",
        "sandboxConfig",
    }
    return IosSave(
        original=source,
        encoding=encoding,
        source=platform,
        serialzed_version=version,
        cloud_save_id=cloud_save_id if isinstance(cloud_save_id, str) else None,
        platform_id=platform_id,
        game_version=game_version if type(game_version) is int else None,
        app_version=app_version if type(app_version) is int else None,
        game_data=game_data,
        optional_sections={name: root[name] for name in (*OBJECT_SECTIONS, "maps", "sandboxConfig") if name in root},
        crde_misc=crde_misc,
        extra_fields={name: value for name, value in root.items() if name not in known},
    )


def save_platform(source: bytes) -> str:
    """Identifica la plataforma de una copia ya decodificada.

    Solo se acepta una marca explícita. Las copias Android antiguas usan un
    UUID en ``platformId``; las iOS usan literalmente ``IOS``. Si no hay marca,
    se devuelve ``unknown`` para que el llamador rechace la copia en lugar de
    atribuirla a una plataforma por suposición.
    """

    try:
        root = json.loads(source)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return "unknown"
    if not isinstance(root, dict):
        return "unknown"
    misc = root.get("_crde_misc")
    if isinstance(misc, dict) and isinstance(misc.get("platformId"), str):
        value = misc["platformId"]
        if value.strip().upper() == "IOS":
            return "ios"
        return "unknown"
    value = root.get("platformId")
    if isinstance(value, str) and value.strip():
        return "ios" if value.strip().upper() == "IOS" else "android"
    return "unknown"
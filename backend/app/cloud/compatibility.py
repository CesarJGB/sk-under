"""Registro central de compatibilidad de versiones y preflight de escritura.

La versión comercial, la versión publicada en cada tienda, la versión de
protocolo, la versión interna del guardado y la versión de serialización son
capas distintas. Este módulo no las iguala ni las deduce entre sí:

* ``commercial_version``: la que muestra la distribución (Android 8.8.0,
  iOS 8.8.0.14).
* ``store_latest_version``: última publicación observada en una tienda; solo
  informativa hasta que se valide.
* ``protocol_app_version`` / ``protocol_game_version``: cabeceras del
  protocolo BlobSave (8.8.0 en ambas plataformas).
* ``game_version`` / ``app_version``: marcadores internos del documento.
* ``serialzed_version``: esquema del agregado (1 en las copias 8.8.0).

Una versión nueva o un marcador desconocido deja el registro en
``pending_verification`` o ``new_version_detected`` y bloquea la preparación y
la escritura. Nunca se actualizan automáticamente los valores usados para
escribir.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from hashlib import sha256
from threading import Lock, Thread
from typing import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..cloud_save import CloudSaveError
from ..catalogs.version import CATALOG_VERSION
from .aggregate_cache import validated_document as _validated_aggregate

type CompatibilityState = str

STATE_COMPATIBLE = "compatible"
STATE_EXPERIMENTAL = "experimental"
STATE_NEW_VERSION = "new_version_detected"
STATE_PENDING = "pending_verification"
STATE_READ_ONLY = "read_only"

_STATES = frozenset(
    {STATE_COMPATIBLE, STATE_EXPERIMENTAL, STATE_NEW_VERSION, STATE_PENDING, STATE_READ_ONLY}
)
_LABELS = {
    STATE_COMPATIBLE: "Compatible",
    STATE_EXPERIMENTAL: "Compatibilidad experimental",
    STATE_NEW_VERSION: "Nueva versión detectada",
    STATE_PENDING: "Verificación pendiente",
    STATE_READ_ONLY: "Solo lectura",
}

_PROFILE_FORMAT = 1
_CATALOG_KEYS = (
    "characters",
    "weapons",
    "weapon_skins",
    "kill_effects",
    "items",
    "pets",
    "blueprints",
)


class CompatibilityError(CloudSaveError):
    code = "cloud_compatibility"


class CompatibilityPending(CompatibilityError):
    code = "cloud_compatibility_pending"


class CompatibilityChanged(CompatibilityError):
    code = "cloud_compatibility_changed"


@dataclass(frozen=True)
class CompatibilityProfile:
    """Conocimiento validado para una distribución y versión comercial."""

    distribution_id: str
    platform: str
    commercial_version: str
    protocol_app_version: str
    protocol_game_version: str
    schema_versions: tuple[int, ...]
    catalog_versions: dict[str, str]
    state: str
    evidence: str
    source: str
    checked_at: str
    game_version: int | None = None
    app_version: int | None = None
    note: str = ""

    def public(self) -> dict[str, object]:
        return {
            "format": _PROFILE_FORMAT,
            "distribution_id": self.distribution_id,
            "platform": self.platform,
            "commercial_version": self.commercial_version,
            "protocol_app_version": self.protocol_app_version,
            "protocol_game_version": self.protocol_game_version,
            "schema_versions": list(self.schema_versions),
            "catalog_versions": dict(self.catalog_versions),
            "state": self.state,
            "evidence": self.evidence,
            "source": self.source,
            "checked_at": self.checked_at,
            "game_version": self.game_version,
            "app_version": self.app_version,
            "note": self.note,
        }


_CATALOGS_880 = {key: CATALOG_VERSION for key in _CATALOG_KEYS}

_PROFILES: tuple[CompatibilityProfile, ...] = (
    CompatibilityProfile(
        distribution_id="android-global",
        platform="android",
        commercial_version="8.8.0",
        protocol_app_version="8.8.0",
        protocol_game_version="8.8.0",
        schema_versions=(1,),
        catalog_versions=_CATALOGS_880,
        state=STATE_COMPATIBLE,
        evidence="E3: flujo Android validado con respaldo, confirmación y persistencia.",
        source="docs/save-research/version-compatibility.md; docs/research/phase5-7",
        checked_at="2026-11-27",
    ),
    CompatibilityProfile(
        distribution_id="ios-global",
        platform="ios",
        commercial_version="8.8.0.14",
        protocol_app_version="8.8.0",
        protocol_game_version="8.8.0",
        schema_versions=(1,),
        catalog_versions=_CATALOGS_880,
        state=STATE_EXPERIMENTAL,
        evidence=(
            "E1/E2: login y descarga verificados; subida iOS en modo de prueba. "
            "La persistencia del servidor no demuestra que el cliente oficial acepte el blob."
        ),
        source="docs/research/phase10-1/ios-version-metadata.md",
        checked_at="2026-11-27",
        game_version=2155,
        app_version=1531,
        note="El cuarto componente de 8.8.0.14 es compilación/hotfix; el protocolo usa 8.8.0.",
    ),
    CompatibilityProfile(
        distribution_id="ios-global",
        platform="ios",
        commercial_version="8.8.0.13",
        protocol_app_version="8.8.0",
        protocol_game_version="8.8.0",
        schema_versions=(1,),
        catalog_versions=_CATALOGS_880,
        state=STATE_PENDING,
        evidence="Compilación anterior; no se usa para escrituras en esta fase.",
        source="docs/research/phase10-1/ios-version-metadata.md",
        checked_at="2026-10-27",
        game_version=2155,
        app_version=1531,
        note="Solo referencia histórica.",
    ),
)

_BY_KEY = {(item.distribution_id, item.commercial_version): item for item in _PROFILES}


def profiles() -> tuple[CompatibilityProfile, ...]:
    return _PROFILES


def profile_for(distribution_id: str, commercial_version: str) -> CompatibilityProfile | None:
    return _BY_KEY.get((distribution_id, commercial_version))


def _catalog_versions() -> dict[str, str]:
    """Versiones de los catálogos empaquetados, sin cargarlos dos veces."""

    result: dict[str, str] = {}
    try:
        from ..catalogs import load_character_catalog

        value = load_character_catalog().get("version")
        if isinstance(value, str):
            result["characters"] = value
    except Exception:
        pass
    for key, loader in (
        ("weapons", "load_weapon_catalog"),
        ("weapon_skins", "load_weapon_skin_catalog"),
        ("kill_effects", "load_kill_effect_catalog"),
        ("items", "load_item_catalog"),
        ("pets", "load_pet_catalog"),
        ("blueprints", "load_blueprint_catalog"),
    ):
        try:
            module = __import__(f"app.catalogs.{key}", fromlist=[loader])
            catalog = getattr(module, loader)()
            value = catalog.get("version") if isinstance(catalog, Mapping) else None
            if isinstance(value, str):
                result[key] = value
        except Exception:
            pass
    return result


def _platform_from_root(root: Mapping[str, object]) -> str:
    marker = root.get("platformId")
    if marker == "IOS":
        return "ios"
    if isinstance(marker, str) and marker:
        return "android"
    return "unknown"


def _int_marker(value: object) -> int | None:
    return value if type(value) is int and not isinstance(value, bool) else None


@dataclass(frozen=True)
class DetectedVersions:
    platform: str
    serialzed_version: int
    game_version: int | None
    app_version: int | None
    cloud_save_id: str | None
    platform_marker: str | None

    def public(self) -> dict[str, object]:
        return {
            "platform": self.platform,
            "serialzed_version": self.serialzed_version,
            "game_version": self.game_version,
            "app_version": self.app_version,
            "cloud_save_id": self.cloud_save_id,
            "platform_marker": self.platform_marker,
        }


def inspect_versions(source: bytes) -> DetectedVersions:
    try:
        root, version = _validated_aggregate(
            source,
            unsupported_error=CompatibilityError,
            unsupported_message="La partida no usa el agregado JSON canónico esperado.",
        )
    except CompatibilityError:
        raise
    except Exception as exc:
        raise CompatibilityError("La partida no se pudo interpretar para comprobar su versión.") from exc
    game_data = root.get("gameData")
    item_data = root.get("itemData")
    game_version = _int_marker(game_data.get("gameVersion")) if isinstance(game_data, dict) else None
    app_version = _int_marker(item_data.get("AppVersion")) if isinstance(item_data, dict) else None
    cloud_save_id = root.get("cloudSaveId")
    return DetectedVersions(
        platform=_platform_from_root(root),
        serialzed_version=version,
        game_version=game_version,
        app_version=app_version,
        cloud_save_id=cloud_save_id if isinstance(cloud_save_id, str) else None,
        platform_marker=root.get("platformId") if isinstance(root.get("platformId"), str) else None,
    )


# ---------------------------------------------------------------------------
# Metadatos externos de las tiendas (solo lectura, con caducidad)


@dataclass(frozen=True)
class StoreMetadata:
    distribution_id: str
    version: str | None
    status: str
    source: str
    checked_at: float
    detail: str = ""

    def public(self, now: float | None = None) -> dict[str, object]:
        current = time.time() if now is None else now
        return {
            "distribution_id": self.distribution_id,
            "version": self.version,
            "status": self.status,
            "source": self.source,
            "checked_at": self.checked_at,
            "age_seconds": max(0.0, current - self.checked_at),
            "detail": self.detail,
        }


_APPLE_LOOKUP = "https://itunes.apple.com/lookup?bundleId=com.ChillyRoom.DungeonShooter&country=us"
_GOOGLE_DETAILS = "https://play.google.com/store/apps/details?id=com.ChillyRoom.DungeonShooter&hl=en&gl=US"
_VERSION_RE = re.compile(r'"(?:softwareVersion|versionName)"\s*:\s*"([0-9]+(?:\.[0-9]+){1,3})"')


def _fetch_apple() -> tuple[str | None, str]:
    request = Request(_APPLE_LOOKUP, headers={"User-Agent": "SK-Under/10.3 (+read-only metadata)"})
    with urlopen(request, timeout=5) as response:  # noqa: S310 - URL fija https
        payload = json.loads(response.read(512_000).decode("utf-8"))
    results = payload.get("results") if isinstance(payload, dict) else None
    if isinstance(results, list) and results and isinstance(results[0], Mapping):
        version = results[0].get("version")
        if isinstance(version, str) and re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}", version):
            return version, "Apple iTunes Lookup"
    return None, "Apple iTunes Lookup sin versión utilizable"


def _fetch_google() -> tuple[str | None, str]:
    request = Request(_GOOGLE_DETAILS, headers={"User-Agent": "Mozilla/5.0 (compatible; SK-Under/10.3)"})
    with urlopen(request, timeout=5) as response:  # noqa: S310 - URL fija https
        text = response.read(1_500_000).decode("utf-8", "replace")
    match = _VERSION_RE.search(text)
    if match:
        return match.group(1), "Google Play (metadatos públicos)"
    return None, "Google Play no expone la versión en el HTML recibido"


_FETCHERS: dict[str, Callable[[], tuple[str | None, str]]] = {
    "android-global": _fetch_google,
    "ios-global": _fetch_apple,
}


class StoreMetadataCache:
    """Caché TTL de consultas externas; un fallo no se convierte en versión."""

    def __init__(self, ttl: float = 6 * 60 * 60) -> None:
        if ttl <= 0:
            raise ValueError("El TTL debe ser positivo.")
        self.ttl = ttl
        self._entries: dict[str, StoreMetadata] = {}
        self._lock = Lock()

    def get(self, distribution_id: str, *, refresh: bool = False) -> StoreMetadata:
        now = time.time()
        with self._lock:
            existing = self._entries.get(distribution_id)
            if existing is not None and not refresh and now - existing.checked_at < self.ttl:
                return existing
        return self._fetch(distribution_id, now)

    def peek(self, distribution_id: str) -> StoreMetadata | None:
        """Devuelve la última consulta sin iniciar tráfico de red."""

        with self._lock:
            return self._entries.get(distribution_id)

    def _fetch(self, distribution_id: str, now: float) -> StoreMetadata:
        fetcher = _FETCHERS.get(distribution_id)
        if fetcher is None:
            entry = StoreMetadata(
                distribution_id=distribution_id,
                version=None,
                status="unsupported",
                source="manual",
                checked_at=now,
                detail="No hay una fuente automática registrada para esta distribución.",
            )
        else:
            try:
                version, detail = fetcher()
                entry = StoreMetadata(
                    distribution_id=distribution_id,
                    version=version,
                    status="ok" if version else "unavailable",
                    source=detail,
                    checked_at=now,
                    detail=detail,
                )
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                entry = StoreMetadata(
                    distribution_id=distribution_id,
                    version=None,
                    status="unavailable",
                    source=type(exc).__name__,
                    checked_at=now,
                    detail="La fuente externa no respondió; no se adopta ninguna versión.",
                )
        with self._lock:
            self._entries[distribution_id] = entry
        return entry

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def refresh_async(self, distribution_ids: tuple[str, ...] | list[str]) -> None:
        """Actualiza la caché en segundo plano; nunca bloquea una edición."""

        def work() -> None:
            for distribution_id in distribution_ids:
                try:
                    self._fetch(distribution_id, time.time())
                except Exception:
                    continue

        Thread(target=work, name="sk-under-store-metadata", daemon=True).start()


STORE_CACHE = StoreMetadataCache()


def _version_tuple(value: str) -> tuple[int, ...]:
    """Compara versiones numéricas sin fallar ante metadatos externos raros."""

    return tuple(int(part) for part in value.split(".") if part.isdigit())


@dataclass(frozen=True)
class CompatibilityDecision:
    state: str
    label: str
    profile: CompatibilityProfile | None
    detected: DetectedVersions
    store: StoreMetadata | None
    read_ready: bool
    prepare_ready: bool
    write_supported: bool
    reason: str
    warnings: tuple[str, ...]
    catalog_versions: dict[str, str] = field(default_factory=dict)

    def summary(self) -> dict[str, object]:
        profile = self.profile.public() if self.profile is not None else None
        return {
            "state": self.state,
            "label": self.label,
            "read_ready": self.read_ready,
            "prepare_ready": self.prepare_ready,
            "write_supported": self.write_supported,
            "reason": self.reason,
            "warnings": list(self.warnings),
            "detected": self.detected.public(),
            "profile": profile,
            "store": self.store.public() if self.store is not None else None,
            "catalog_versions": dict(self.catalog_versions),
            "sources": {
                "save": "metadatos del agregado descargado",
                "store": self.store.source if self.store is not None else "sin consulta",
                "official": "ChillyRoom/manual hasta disponer de un endpoint oficial estable",
            },
            "manual_validation": [
                "La versión publicada no se adopta automáticamente como versión de protocolo.",
                "Un cambio de gameVersion/AppVersion exige validar el cliente oficial.",
                "La aceptación del cliente no se deduce de un HTTP 200 ni de un SHA-256 igual.",
            ],
        }


def decision_for(
    *,
    distribution_id: str,
    commercial_version: str,
    platform: str,
    source: bytes,
    capability_state: str,
    store: StoreMetadata | None = None,
) -> CompatibilityDecision:
    detected = inspect_versions(source)
    profile = profile_for(distribution_id, commercial_version)
    warnings: list[str] = []
    catalog_versions = _catalog_versions()

    if detected.platform == "unknown":
        state = STATE_READ_ONLY
        reason = "El guardado no declara una plataforma reconocida; no se habilitan escrituras."
        return CompatibilityDecision(
            state=state,
            label=_LABELS[state],
            profile=profile,
            detected=detected,
            store=store,
            read_ready=False,
            prepare_ready=False,
            write_supported=False,
            reason=reason,
            warnings=("platformId ausente o desconocido",),
            catalog_versions=catalog_versions,
        )

    if profile is None:
        state = STATE_NEW_VERSION
        reason = (
            "La distribución o su versión comercial no tienen un perfil validado. "
            "Se permite lectura, pero no preparar ni escribir."
        )
        return CompatibilityDecision(
            state=state,
            label=_LABELS[state],
            profile=None,
            detected=detected,
            store=store,
            read_ready=True,
            prepare_ready=False,
            write_supported=False,
            reason=reason,
            warnings=("Sin perfil de compatibilidad para esta versión comercial",),
            catalog_versions=catalog_versions,
        )

    if detected.platform != profile.platform:
        warnings.append(
            f"La partida declara {detected.platform} y la distribución es {profile.platform}."
        )
    if detected.serialzed_version not in profile.schema_versions:
        warnings.append(
            f"serialzedVersion={detected.serialzed_version} no está validado para esta versión."
        )
    if profile.game_version is not None and detected.game_version not in (None, profile.game_version):
        warnings.append(
            f"gameVersion={detected.game_version} difiere del marcador validado {profile.game_version}."
        )
    if profile.app_version is not None and detected.app_version not in (None, profile.app_version):
        warnings.append(
            f"AppVersion={detected.app_version} difiere del marcador validado {profile.app_version}."
        )
    for key, expected in profile.catalog_versions.items():
        actual = catalog_versions.get(key)
        if actual is not None and actual != expected:
            warnings.append(f"Catálogo {key}: {actual} frente a {expected} validado.")

    latest = store.version if store is not None else None
    if latest and _version_tuple(latest) > _version_tuple(profile.commercial_version):
        state = STATE_NEW_VERSION
        warnings.append(
            f"La tienda publica {latest}; el perfil validado es {profile.commercial_version}."
        )
    elif warnings:
        state = STATE_PENDING
    elif capability_state == "write_experimental":
        state = STATE_EXPERIMENTAL
    elif capability_state == "write_pending_validation":
        state = STATE_PENDING
    elif capability_state == "read_only":
        state = STATE_READ_ONLY
    elif profile.state == STATE_PENDING:
        state = STATE_PENDING
    else:
        state = STATE_COMPATIBLE

    if state == STATE_COMPATIBLE:
        read_ready = prepare_ready = write_supported = True
        reason = "La versión y el esquema están validados para lectura, preparación y escritura."
    elif state == STATE_EXPERIMENTAL:
        read_ready = prepare_ready = write_supported = True
        reason = (
            "Lectura y preparación validadas; la escritura es experimental y exige "
            "respaldo, confirmación y verificación posterior."
        )
    elif state == STATE_NEW_VERSION:
        read_ready = True
        prepare_ready = write_supported = False
        reason = (
            "Hay una versión nueva o desconocida. Se permite leer, pero no preparar ni "
            "escribir hasta validar el protocolo, el esquema y los catálogos."
        )
        if latest is not None and profile is not None:
            reason = (
                f"La tienda publica {latest}; el perfil validado es "
                f"{profile.commercial_version}. Se permite leer, pero no preparar ni "
                "escribir hasta validar el nuevo protocolo, esquema y catálogos."
            )
    elif state == STATE_PENDING:
        read_ready = True
        prepare_ready = write_supported = False
        reason = (
            "La verificación de versión está pendiente. Solo se permiten operaciones de "
            "lectura comprobadas."
        )
    else:
        read_ready = prepare_ready = write_supported = False
        reason = "La partida no es compatible con ninguna operación habilitada."

    return CompatibilityDecision(
        state=state,
        label=_LABELS[state],
        profile=profile,
        detected=detected,
        store=store,
        read_ready=read_ready,
        prepare_ready=prepare_ready,
        write_supported=write_supported,
        reason=reason,
        warnings=tuple(warnings),
        catalog_versions=catalog_versions,
    )


def compatibility_report(
    *,
    distribution_id: str,
    commercial_version: str,
    platform: str,
    source: bytes | None = None,
    capability_state: str = "write_verified",
    refresh_store: bool = False,
    store: StoreMetadata | None = None,
) -> dict[str, object]:
    if source is not None and store is None:
        store = (
            STORE_CACHE.get(distribution_id, refresh=True)
            if refresh_store
            else STORE_CACHE.peek(distribution_id)
        )
    if source is None:
        profile = profile_for(distribution_id, commercial_version)
        return {
            "state": profile.state if profile else STATE_PENDING,
            "label": _LABELS[profile.state if profile else STATE_PENDING],
            "profile": profile.public() if profile else None,
            "store": store.public() if store is not None else None,
            "detected": None,
            "read_ready": bool(profile),
            "prepare_ready": False,
            "write_supported": False,
            "reason": "No se ha descargado una partida para comprobar sus metadatos.",
            "warnings": [],
            "catalog_versions": _catalog_versions(),
            "sources": {
                "save": "no disponible",
                "store": store.source if store is not None else "sin consulta",
                "official": "manual",
            },
            "manual_validation": [],
        }
    decision = decision_for(
        distribution_id=distribution_id,
        commercial_version=commercial_version,
        platform=platform,
        source=source,
        capability_state=capability_state,
        store=store,
    )
    return decision.summary()


# ---------------------------------------------------------------------------
# Preflight de escritura


def _binding(
    decision: CompatibilityDecision,
    source: bytes,
    *,
    distribution_id: str,
    platform: str,
    account_digest: str,
    plan_sha256: str | None,
) -> dict[str, object]:
    profile = decision.profile
    return {
        "format": _PROFILE_FORMAT,
        "distribution_id": distribution_id,
        "platform": platform,
        "commercial_version": profile.commercial_version if profile else None,
        "protocol_app_version": profile.protocol_app_version if profile else None,
        "protocol_game_version": profile.protocol_game_version if profile else None,
        "schema_version": decision.detected.serialzed_version,
        "game_version": decision.detected.game_version,
        "app_version": decision.detected.app_version,
        "source_sha256": sha256(source).hexdigest(),
        "source_size": len(source),
        "account_digest": account_digest,
        "catalog_versions": dict(decision.catalog_versions),
        "plan_sha256": plan_sha256,
        "policy": "phase10-3",
    }


@dataclass(frozen=True)
class WritePreflight:
    decision: CompatibilityDecision
    binding: dict[str, object]

    def summary(self) -> dict[str, object]:
        return {
            "state": self.decision.state,
            "label": self.decision.label,
            "reason": self.decision.reason,
            "warnings": list(self.decision.warnings),
            "binding": self.binding,
            "compatibility": self.decision.summary(),
        }


def preflight_write(
    source: bytes,
    *,
    distribution_id: str,
    commercial_version: str,
    platform: str,
    capability_state: str,
    account_digest: str = "",
    plan_sha256: str | None = None,
    store: StoreMetadata | None = None,
) -> WritePreflight:
    if not isinstance(account_digest, str):
        raise CompatibilityError("La identidad de la cuenta no es válida.")
    decision = decision_for(
        distribution_id=distribution_id,
        commercial_version=commercial_version,
        platform=platform,
        source=source,
        capability_state=capability_state,
        store=store,
    )
    binding = _binding(
        decision,
        source,
        distribution_id=distribution_id,
        platform=platform,
        account_digest=account_digest,
        plan_sha256=plan_sha256,
    )
    return WritePreflight(decision=decision, binding=binding)


def require_write_preflight(preflight: WritePreflight) -> None:
    if not preflight.decision.write_supported:
        raise CompatibilityPending(
            "La versión de la partida no permite una escritura segura: "
            + preflight.decision.reason
        )


def require_matching_binding(
    stored: Mapping[str, object] | None, current: Mapping[str, object]
) -> None:
    """Rechaza un candidato si cambió la versión, la cuenta o la partida."""

    if not stored:
        # Respaldos anteriores a la Fase 10.3: el hash remoto y la firma del
        # candidato siguen siendo la protección; se les añade el preflight actual.
        return
    fields = (
        "distribution_id",
        "platform",
        "commercial_version",
        "protocol_app_version",
        "protocol_game_version",
        "schema_version",
        "game_version",
        "app_version",
        "source_sha256",
        "source_size",
        "account_digest",
        "catalog_versions",
        "plan_sha256",
        "policy",
    )
    for key in fields:
        if stored.get(key) != current.get(key):
            raise CompatibilityChanged(
                "La versión, la cuenta, los catálogos o la partida original cambiaron "
                "desde que se preparó el candidato. Vuelve a preparar la edición."
            )
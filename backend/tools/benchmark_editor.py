"""Benchmark local del editor unificado de la Fase 10.3.

Uso (desde ``backend/``):

    uv run python tools/benchmark_editor.py --sample /ruta/privada/save.json

El archivo de muestra no se copia al repositorio. El script selecciona todas
las categorías editables que la muestra permita y mide, por separado, la
inspección de versiones, el preflight, la composición del candidato, el
respaldo, la carga del respaldo, la subida simulada y la descarga de
verificación. La subida es local: no se contacta con ChillyRoom.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.catalogs import load_character_catalog
from app.cloud.advanced_editor import read_advanced_source
from app.cloud.aggregate_cache import clear_aggregate_cache
from app.cloud.backup_store import LabBackupStore
from app.cloud.blueprint_editor import read_blueprints
from app.cloud.character_editor import read_characters
from app.cloud.compatibility import inspect_versions
from app.cloud.fish_chip_editor import read_fish_chip
from app.cloud.fish_progress_editor import read_fish_progress
from app.cloud.gems_editor import read_gems
from app.cloud.hero_level_editor import read_hero_levels
from app.cloud.kill_effect_editor import read_kill_effects
from app.cloud.lab_service import CloudLabService
from app.cloud.pet_affinity_editor import read_pet_affinity
from app.cloud.provider import AcquiredCloudSave, CloudSaveMetadata
from app.cloud.skin_editor import read_skins
from app.cloud.skill_editor import read_skills
from app.cloud.aggregate_cache import serialize_canonical
from app.cloud.unified_editor import normalize_unified_plan, prepare_unified_edit
from app.cloud.weapon_progression_editor import read_weapon_progression
from app.cloud.weapon_skin_editor import read_weapon_skins


class MutableProvider:
    """Proveedor local que permite simular una subida sin red."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    @property
    def metadata(self) -> CloudSaveMetadata:
        return CloudSaveMetadata(
            revision=f"local-{len(self.payload)}",
            size=len(self.payload),
            sha256=sha256(self.payload).hexdigest(),
        )

    def download(self, limit: int = 8 * 1024 * 1024) -> AcquiredCloudSave:
        return AcquiredCloudSave(self.metadata, self.payload)


@dataclass(frozen=True)
class LocalUploader:
    provider: MutableProvider

    def upload(self, aggregate: bytes):
        from app.cloud.blob_upload import UploadResult

        self.provider.payload = aggregate
        digest = sha256(aggregate).hexdigest()
        return UploadResult(
            status=200,
            accepted=True,
            aggregate_size=len(aggregate),
            aggregate_sha256=digest,
            body_size=len(aggregate),
            body_sha256=digest,
            response_size=0,
            response_sha256=sha256(b"").hexdigest(),
        )


def build_plan(source: bytes) -> tuple[dict[str, object], list[str]]:
    """Construye un plan con todas las categorías que la muestra admite."""

    plan: dict[str, object] = {
        "gems": read_gems(source).gems + 100,
        "fish_chip": read_fish_chip(source).fish_chip + 1,
        "fish_progress": read_fish_progress(source).cumulative_fish_count + 1,
    }

    characters = read_characters(source)
    catalog_codes = load_character_catalog()["codes"]
    locked_characters = [code for code in catalog_codes if code not in characters.unlocked]
    if locked_characters:
        plan["characters"] = locked_characters[:3]

    skills = read_skills(source)
    unlocked_skills = {(ref.code, ref.index) for ref in skills.unlocked}
    locked_skills = [
        ref for ref in skills.selected if (ref.code, ref.index) not in unlocked_skills
    ]
    if locked_skills:
        plan["skills"] = [
            {"code": ref.code, "index": ref.index} for ref in locked_skills[:3]
        ]

    skins = read_skins(source)
    unlocked_skins = {(ref.code, ref.index) for ref in skins.unlocked}
    locked_skins = [
        ref for ref in skins.selected if (ref.code, ref.index) not in unlocked_skins
    ]
    if locked_skins:
        plan["skins"] = [
            {"code": ref.code, "index": ref.index} for ref in locked_skins[:3]
        ]

    progression = read_weapon_progression(source)
    locked_weapons = [item["id"] for item in progression.items if not item["discovered"]]
    if locked_weapons:
        plan["weapon_progression"] = locked_weapons[:5]
    forgeable = [
        item["id"]
        for item in progression.items
        if item.get("forgeable") and not item.get("forge_unlock_ready")
    ]
    if forgeable:
        plan["weapon_forge_unlock"] = forgeable[:5]

    weapon_skins = read_weapon_skins(source)
    locked_weapon_skins = [
        item["id"] for item in weapon_skins.items if not item["unlocked"]
    ]
    if locked_weapon_skins:
        plan["weapon_skins"] = locked_weapon_skins[:5]

    kill_effects = read_kill_effects(source)
    locked_effects = [item["id"] for item in kill_effects.items if not item["unlocked"]]
    if locked_effects:
        plan["kill_effects"] = locked_effects[:2]

    advanced_source = read_advanced_source(source)
    advanced: dict[str, object] = {}
    for key in ("materials", "seeds"):
        editable = [
            item
            for item in advanced_source[key]
            if item.get("owned") and item.get("editable")
        ]
        if editable:
            item = editable[0]
            advanced[key] = [
                {"id": item["id"], "value": (item.get("count") or 0) + 1}
            ]
    if advanced_source["season_coin"].get("available"):
        advanced["season_coin"] = advanced_source["season_coin"]["value"] + 1
    if (
        advanced_source["reborn_card"].get("available")
        and not advanced_source["reborn_card"].get("value")
    ):
        advanced["reborn_card"] = True
    pets = [
        item
        for item in advanced_source["pets"]
        if item.get("unlocked") and item.get("editable")
    ]
    if pets:
        advanced["pets"] = [pets[0]["id"]]
    if advanced:
        plan["advanced"] = advanced

    hero_levels = read_hero_levels(source)
    editable_heroes = [
        item
        for item in hero_levels["entries"]
        if item.get("unlocked")
        and item.get("editable")
        and (item.get("level") or 0) < hero_levels["max"]
    ]
    if editable_heroes:
        item = editable_heroes[0]
        plan["hero_levels"] = {item["id"]: (item.get("level") or 0) + 1}

    affinity = read_pet_affinity(source)
    editable_pets = [
        item
        for item in affinity["entries"]
        if item.get("editable") and item.get("intimacy") is not None
    ]
    if editable_pets:
        item = editable_pets[0]
        plan["pet_affinity"] = {
            item["id"]: min(item["max"], item["intimacy"] + 1)
        }

    blueprints = read_blueprints(source)
    editable_blueprints = [
        item
        for item in blueprints["entries"]
        if item.get("creatable")
        or (item.get("editable") and item.get("status") == "Got")
    ]
    if editable_blueprints:
        plan["blueprints"] = {editable_blueprints[0]["id"]: "Researched"}

    normalized = normalize_unified_plan(plan)
    selected = [key for key, value in normalized.items() if value not in (None, [], {})]
    return normalized, selected


def pad_save(source: bytes, target_bytes: int) -> bytes:
    """Añade un campo desconocido para medir partidas grandes sin tocar datos."""

    if len(source) >= target_bytes:
        return source
    document = json.loads(source)
    document["phase10_3_padding"] = ""
    overhead = len(serialize_canonical(document))
    document["phase10_3_padding"] = "x" * max(0, target_bytes - overhead)
    return serialize_canonical(document)


def _timed(callable_):
    start = perf_counter()
    value = callable_()
    return (perf_counter() - start) * 1000, value


def run(sample: Path, rounds: int, target_bytes: int = 0) -> dict[str, object]:
    source = sample.read_bytes()
    if target_bytes:
        source = pad_save(source, target_bytes)
    plan, selected = build_plan(source)
    digest = sha256(source).hexdigest()

    cold_prepare: list[float] = []
    warm_prepare: list[float] = []
    for _ in range(rounds):
        clear_aggregate_cache()
        elapsed, edit = _timed(lambda: prepare_unified_edit(source, plan))
        cold_prepare.append(elapsed)
    for _ in range(rounds):
        elapsed, edit = _timed(lambda: prepare_unified_edit(source, plan))
        warm_prepare.append(elapsed)

    inspect_ms, detected = _timed(lambda: inspect_versions(source))
    cold_prepare_median = median(cold_prepare)
    warm_prepare_median = median(warm_prepare)

    service: dict[str, object] = {}
    distribution_id = "ios-global" if detected.platform == "ios" else "android-global"
    commercial_version = "8.8.0.14" if detected.platform == "ios" else "8.8.0"
    with TemporaryDirectory(prefix="sk-under-bench-") as directory:
        provider = MutableProvider(payload=source)
        store = LabBackupStore(Path(directory))
        lab = CloudLabService(
            provider,
            store,
            uploader=LocalUploader(provider),
            write_enabled=True,
            admin_configured=True,
            platform=detected.platform,
            distribution_id=distribution_id,
            commercial_version=commercial_version,
            account_digest="benchmark-local",
        )
        clear_aggregate_cache()

        load_ms, loaded = _timed(lambda: lab.load())
        preflight_ms, preflight = _timed(
            lambda: lab._preflight(source, plan_sha256=None)
        )
        prepare_ms, prepared = _timed(
            lambda: lab.prepare_unified(plan, expected_source=digest)
        )
        save_ms, bundle = _timed(lambda: store.load(prepared.backup.id))
        confirm_ms, confirmed = _timed(
            lambda: lab.confirm(
                prepared.backup.id,
                prepared.edit.candidate_sha256,
                single_attempt=True,
            )
        )
        # ``confirm`` valida y sube; la descarga de verificación está incluida.
        service = {
            "load_ms": round(load_ms, 1),
            "preflight_ms": round(preflight_ms, 1),
            "prepare_ms": round(prepare_ms, 1),
            "backup_load_ms": round(save_ms, 1),
            "confirm_ms": round(confirm_ms, 1),
            "persisted": confirmed.persisted,
            "backup_id": prepared.backup.id,
            "state": loaded.compatibility.get("state"),
            "preflight_state": preflight.decision.state,
        }

    return {
        "sample": str(sample),
        "sample_bytes": len(source),
        "sample_sha256": digest,
        "detected": detected.public(),
        "selected_categories": selected,
        "selected_count": len(selected),
        "steps": list(edit.steps),
        "changes": edit.change_count,
        "candidate_bytes": len(edit.candidate),
        "cold_prepare_ms": [round(value, 1) for value in cold_prepare],
        "warm_prepare_ms": [round(value, 1) for value in warm_prepare],
        "cold_prepare_median_ms": round(cold_prepare_median, 1),
        "warm_prepare_median_ms": round(warm_prepare_median, 1),
        "inspect_versions_ms": round(inspect_ms, 1),
        "service": service,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--pad-bytes", type=int, default=0)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = run(arguments.sample, max(1, arguments.rounds), arguments.pad_bytes)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if arguments.output:
        arguments.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
"""Regresiones del hotfix 9.1.1: respaldos unificados con decoraciones.

Las pruebas existentes componían el candidato en memoria, pero no lo
atravesaban por el almacén real de respaldos. Estas pruebas usan un directorio
temporal y un proveedor simulado: nunca tocan cuentas ni servicios reales.
"""

import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.api.cloud_lab import _backup_diagnostic, _http_error
from app.catalogs import load_character_catalog
from app.catalogs.blueprints import load_blueprint_catalog
from app.catalogs.pets import load_pet_catalog
from app.cloud.backup_store import (
    BackupCandidateMismatch,
    BackupCategoryUnsupported,
    BackupHashMismatch,
    BackupIncompatible,
    BackupIntegrityError,
    BackupPlanIncompatible,
    BackupStoreError,
    BackupUnreadable,
    LabBackupStore,
)
from app.cloud.lab_service import CloudLabService
from app.cloud.unified_editor import (
    UNIFIED_CATEGORY_KEYS,
    UNIFIED_OPTIONAL_CATEGORY_KEYS,
    normalize_unified_plan,
    prepare_unified_edit,
)
from test_cloud_lab_api import FakeProvider, FakeUploader

FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"


def canonical(document: dict) -> bytes:
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(", ", ": ")
    ).encode()


def base_document() -> dict:
    data = json.loads(FIXTURE.read_bytes())
    data["gameData"].update(
        gems=1000,
        fishChip=3,
        heroUnlock={},
        heroLevel={},
        petUnlock={},
        roomObjectLevel={"Book": 2, "CatFood": 0, "Chest": 1, "Planet": 3, "Safe": 4},
        currentRoomDecorate="Common",
        unlockRoomDecorate=[],
        roomLevel=1,
    )
    data["itemData"].update(
        materials={"material_ticket": 5, "material_fish": 3},
        cumulativeFishCount=0,
        seeds={},
        blueprints={},
        roomDecorateDic={"ItemEggMachine": [0]},
    )
    data["statisticData"]["event2Count"] = {}
    return data


def service_for(tmp_path: Path, payload: bytes) -> tuple[CloudLabService, FakeProvider, FakeUploader]:
    provider = FakeProvider(payload)
    uploader = FakeUploader(provider)
    service = CloudLabService(
        provider,
        LabBackupStore(tmp_path / "backups"),
        uploader=uploader,
        write_enabled=True,
        admin_configured=True,
    )
    return service, provider, uploader


def prepare_and_assert_no_write(
    service: CloudLabService, uploader: FakeUploader, plan: dict, payload: bytes
):
    prepared = service.prepare_unified(plan, expected_source=sha256(payload).hexdigest())
    assert uploader.calls == []
    return prepared


def rewrite_record(tmp_path: Path, backup_id: str, mutate) -> None:
    path = tmp_path / "backups" / backup_id / "record.json"
    record = json.loads(path.read_text())
    mutate(record)
    path.write_text(json.dumps(record, ensure_ascii=False, sort_keys=True))


def test_normalized_plan_keys_are_the_shared_category_source():
    plan = normalize_unified_plan({"gems": 10})
    assert set(plan) == UNIFIED_CATEGORY_KEYS
    assert UNIFIED_OPTIONAL_CATEGORY_KEYS <= UNIFIED_CATEGORY_KEYS


def test_decorations_only_backup_survives_store_confirm_and_restore(tmp_path):
    payload = canonical(base_document())
    service, provider, uploader = service_for(tmp_path, payload)
    plan = {
        "decorations": {
            "objects": ["ObjectSafe", "PetFood"],
            "levels": [{"id": "Book", "level": 5}],
        }
    }

    prepared = prepare_and_assert_no_write(service, uploader, plan, payload)
    assert prepared.backup.categories == ("decorations",)
    assert service.store.load(prepared.backup.id).record.categories == ("decorations",)

    confirmed = service.confirm(prepared.backup.id, prepared.edit.candidate_sha256)
    assert confirmed.persisted is True
    assert len(uploader.calls) == 1
    after = json.loads(provider.payload)
    assert after["itemData"]["roomDecorateDic"]["ObjectSafe"] == [0]
    assert after["gameData"]["roomObjectLevel"]["Book"] == 5

    restored = service.restore(prepared.backup.id)
    assert restored.persisted is True
    assert len(uploader.calls) == 2
    assert provider.payload == payload


def test_pet_affinity_only_backup_survives_store_and_confirmation(tmp_path):
    document = base_document()
    document["gameData"]["petUnlock"] = {"Cat": True}
    payload = canonical(document)
    service, _, uploader = service_for(tmp_path, payload)
    plan = {"pet_affinity": [{"code": "Cat", "value": 100}]}

    prepared = prepare_and_assert_no_write(service, uploader, plan, payload)
    assert prepared.backup.categories == ("pet_affinity",)
    confirmed = service.confirm(prepared.backup.id, prepared.edit.candidate_sha256)
    assert confirmed.persisted is True
    assert len(uploader.calls) == 1


def test_blueprints_only_backup_survives_store_and_confirmation(tmp_path):
    payload = canonical(base_document())
    service, _, uploader = service_for(tmp_path, payload)
    plan = {
        "blueprints": [
            {"id": "blueprint_multi_room_skin_2", "status": "Researched"},
        ]
    }

    prepared = prepare_and_assert_no_write(service, uploader, plan, payload)
    assert prepared.backup.categories == ("blueprints",)
    confirmed = service.confirm(prepared.backup.id, prepared.edit.candidate_sha256)
    assert confirmed.persisted is True
    assert len(uploader.calls) == 1


def test_combined_resources_characters_pets_blueprints_and_decorations(tmp_path):
    document = base_document()
    document["gameData"]["petUnlock"] = {"Cat": True}
    payload = canonical(document)
    service, provider, uploader = service_for(tmp_path, payload)
    plan = {
        "gems": 2000,
        "fish_chip": 10,
        "characters": ["Ranger"],
        "pet_affinity": [{"code": "Cat", "value": 120}],
        "blueprints": [
            {"id": "blueprint_multi_room_skin_2", "status": "Got"},
        ],
        "decorations": {
            "objects": ["ObjectSafe"],
            "levels": [{"id": "Book", "level": 5}],
        },
    }

    prepared = prepare_and_assert_no_write(service, uploader, plan, payload)
    assert set(prepared.backup.categories) == {
        "gems",
        "fish_chip",
        "characters",
        "pet_affinity",
        "blueprints",
        "decorations",
    }

    confirmed = service.confirm(prepared.backup.id, prepared.edit.candidate_sha256)
    assert confirmed.persisted is True
    assert len(uploader.calls) == 1
    after = json.loads(provider.payload)
    assert after["gameData"]["gems"] == 2000
    assert after["gameData"]["fishChip"] == 10
    assert after["gameData"]["heroUnlock"]["Ranger"] is True
    assert after["statisticData"]["event2Count"]["pet_0_intimacy"] == 120
    assert after["itemData"]["blueprints"]["multi_room_skin_2"] == "Got"
    assert after["itemData"]["roomDecorateDic"]["ObjectSafe"] == [0]

    restored = service.restore(prepared.backup.id)
    assert restored.persisted is True
    assert provider.payload == payload


def large_plan_document() -> tuple[bytes, dict, int]:
    document = base_document()
    characters = list(load_character_catalog()["codes"])
    blueprints = sorted(load_blueprint_catalog()["blueprint_ids"])
    pets = load_pet_catalog()["pets"]
    assert len(characters) == 42
    assert len(blueprints) == 296

    document["gameData"]["heroLevel"] = {code: 0 for code in characters[:7]}
    pet_codes: list[tuple[str, int]] = []
    for code, row in pets.items():
        if len(pet_codes) == 5:
            break
        numeric_id = row["numeric_id"]
        if numeric_id in (27, 56, 57):
            continue
        pet_codes.append((code, numeric_id))
    for code, numeric_id in pet_codes:
        document["gameData"]["petUnlock"][code] = True
        document["statisticData"]["event2Count"][f"pet_{numeric_id}_intimacy"] = 0

    plan = {
        "gems": 2000,
        "fish_progress": 12,
        "characters": characters,
        "hero_levels": [{"code": code, "level": 1} for code in characters[:7]],
        "pet_affinity": [{"code": code, "value": 10} for code, _ in pet_codes],
        "blueprints": [{"id": blueprint_id, "status": "Got"} for blueprint_id in blueprints],
        "decorations": {
            "objects": [
                "ItemTrashCan",
                "ObjectBooks",
                "ObjectDrinkSeller",
                "ObjectFishBowl",
                "ObjectMagicWell",
                "ObjectMysteriouStatue",
                "ObjectPlant",
                "ObjectSafe",
                "PetFood",
            ],
            "levels": [
                {"id": "Book", "level": 5},
                {"id": "CatFood", "level": 5},
                {"id": "Planet", "level": 5},
                {"id": "Safe", "level": 5},
            ],
        },
    }
    expected = 366
    return canonical(document), plan, expected


def test_large_batch_of_approximately_365_changes_roundtrips(tmp_path):
    payload, plan, expected_changes = large_plan_document()
    service, provider, uploader = service_for(tmp_path, payload)
    prepared = prepare_and_assert_no_write(service, uploader, plan, payload)
    assert prepared.edit.change_count == expected_changes
    assert prepared.backup.change_count == expected_changes
    assert set(prepared.backup.categories) == {
        "gems",
        "fish_progress",
        "characters",
        "hero_levels",
        "pet_affinity",
        "blueprints",
        "decorations",
    }
    loaded = service.store.load(prepared.backup.id)
    assert loaded.candidate == prepared.edit.candidate
    assert loaded.categories == prepared.backup.categories

    confirmed = service.confirm(prepared.backup.id, prepared.edit.candidate_sha256)
    assert confirmed.persisted is True
    assert len(uploader.calls) == 1
    assert provider.payload == prepared.edit.candidate

    restored = service.restore(prepared.backup.id)
    assert restored.persisted is True
    assert provider.payload == payload


def test_historical_plan_without_phase_9_categories_remains_readable(tmp_path):
    payload = canonical(base_document())
    service, _, uploader = service_for(tmp_path, payload)
    prepared = prepare_and_assert_no_write(service, uploader, {"gems": 2000}, payload)
    backup_id = prepared.backup.id

    def strip_new_categories(record: dict) -> None:
        for key in UNIFIED_OPTIONAL_CATEGORY_KEYS:
            record["unified_plan"].pop(key, None)

    rewrite_record(tmp_path, backup_id, strip_new_categories)
    path = tmp_path / "backups" / backup_id / "record.json"
    historical_bytes = path.read_bytes()
    assert "decorations" not in json.loads(historical_bytes)["unified_plan"]

    loaded = service.store.load(backup_id)
    assert loaded.record.unified_plan["decorations"] is None
    assert loaded.categories == ("gems",)
    assert path.read_bytes() == historical_bytes

    confirmed = service.confirm(backup_id, prepared.edit.candidate_sha256)
    assert confirmed.persisted is True
    assert len(uploader.calls) == 1
    assert service.verify(backup_id).matches_candidate is True


def test_historical_affinity_and_blueprint_candidate_is_reproducible(tmp_path):
    document = base_document()
    document["gameData"]["petUnlock"] = {"Cat": True}
    document["statisticData"]["event2Count"] = {"pet_0_intimacy": 20}
    document["itemData"]["blueprints"] = {"multi_room_skin_1": "Got"}
    payload = canonical(document)
    plan = {
        "pet_affinity": [{"code": "Cat", "value": 120}],
        "blueprints": [{"id": "blueprint_multi_room_skin_1", "status": "Researched"}],
    }
    service, _, uploader = service_for(tmp_path, payload)
    prepared = prepare_and_assert_no_write(service, uploader, plan, payload)

    def strip_decorations(record: dict) -> None:
        record["unified_plan"].pop("decorations", None)

    rewrite_record(tmp_path, prepared.backup.id, strip_decorations)
    loaded = service.store.load(prepared.backup.id)
    assert loaded.record.unified_plan["decorations"] is None
    assert loaded.candidate == prepared.edit.candidate
    assert set(loaded.categories) == {"pet_affinity", "blueprints"}

    confirmed = service.confirm(prepared.backup.id, prepared.edit.candidate_sha256)
    assert confirmed.persisted is True
    assert len(uploader.calls) == 1


def test_unknown_category_is_rejected_with_a_specific_internal_reason(tmp_path):
    payload = canonical(base_document())
    service, _, _ = service_for(tmp_path, payload)
    prepared = prepare_and_assert_no_write(
        service,
        service.uploader,
        {"decorations": {"objects": ["ObjectSafe"]}},
        payload,
    )

    def add_unknown_category(record: dict) -> None:
        record["categories"].append("invented_category")

    rewrite_record(tmp_path, prepared.backup.id, add_unknown_category)
    with pytest.raises(BackupCategoryUnsupported) as error:
        service.store.load(prepared.backup.id)
    assert _backup_diagnostic(error.value) == ("warning", "unsupported_category")
    assert _http_error(error.value).error.message == "El respaldo privado no superó la verificación."


def test_unknown_plan_key_is_rejected_as_incompatible_plan(tmp_path):
    payload = canonical(base_document())
    service, _, _ = service_for(tmp_path, payload)
    prepared = prepare_and_assert_no_write(service, service.uploader, {"gems": 1500}, payload)

    def add_unknown_plan_key(record: dict) -> None:
        record["unified_plan"]["invented"] = {"anything": True}

    rewrite_record(tmp_path, prepared.backup.id, add_unknown_plan_key)
    with pytest.raises(BackupPlanIncompatible) as error:
        service.store.load(prepared.backup.id)
    assert _backup_diagnostic(error.value) == ("warning", "incompatible_plan")


def test_altered_candidate_bytes_are_rejected_by_hash(tmp_path):
    payload = canonical(base_document())
    service, _, _ = service_for(tmp_path, payload)
    prepared = prepare_and_assert_no_write(service, service.uploader, {"gems": 1500}, payload)
    candidate_path = tmp_path / "backups" / prepared.backup.id / "candidate.json"
    altered = bytearray(candidate_path.read_bytes())
    altered[-2] = ord("9") if altered[-2] != ord("9") else ord("8")
    candidate_path.write_bytes(bytes(altered))

    with pytest.raises(BackupHashMismatch) as error:
        service.store.load(prepared.backup.id)
    assert _backup_diagnostic(error.value) == ("error", "hash_mismatch")
    assert error.value.code == "backup_integrity"


def test_candidate_that_cannot_be_reproduced_is_rejected(tmp_path):
    payload = canonical(base_document())
    service, _, _ = service_for(tmp_path, payload)
    prepared = prepare_and_assert_no_write(service, service.uploader, {"gems": 1500}, payload)

    def replace_candidate(record: dict) -> None:
        record["unified_plan"]["gems"] = 1600

    rewrite_record(tmp_path, prepared.backup.id, replace_candidate)
    with pytest.raises(BackupCandidateMismatch) as error:
        service.store.load(prepared.backup.id)
    assert _backup_diagnostic(error.value) == ("error", "candidate_not_reproducible")


def test_backup_failure_categories_are_distinguished_internally():
    assert _backup_diagnostic(BackupCategoryUnsupported("x")) == (
        "warning",
        "unsupported_category",
    )
    assert _backup_diagnostic(BackupPlanIncompatible("x")) == (
        "warning",
        "incompatible_plan",
    )
    assert _backup_diagnostic(BackupUnreadable("x")) == ("error", "decryption_failed")
    assert _backup_diagnostic(BackupHashMismatch("x")) == ("error", "hash_mismatch")
    assert _backup_diagnostic(BackupCandidateMismatch("x")) == (
        "error",
        "candidate_not_reproducible",
    )
    assert _backup_diagnostic(BackupStoreError("x")) == ("error", "storage_error")
    assert _backup_diagnostic(BackupIntegrityError("x")) == ("error", "integrity_error")
    # La clasificación interna no cambia el mensaje público seguro.
    for error in (
        BackupCategoryUnsupported("x"),
        BackupPlanIncompatible("x"),
        BackupHashMismatch("x"),
        BackupCandidateMismatch("x"),
    ):
        public = _http_error(error)
        assert public.status_code == 500
        assert public.error.code == "backup_integrity"
        assert public.error.message == "El respaldo privado no superó la verificación."


def test_store_rejects_a_plan_with_unknown_category_key_instead_of_crashing(tmp_path):
    payload = canonical(base_document())
    service, _, _ = service_for(tmp_path, payload)
    prepared = prepare_and_assert_no_write(service, service.uploader, {"gems": 1500}, payload)

    def add_unknown_category(record: dict) -> None:
        record["unified_plan"]["unknown_category"] = None

    rewrite_record(tmp_path, prepared.backup.id, add_unknown_category)
    with pytest.raises(BackupIncompatible):
        service.store.load(prepared.backup.id)
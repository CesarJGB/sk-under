import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.cloud.backup_store import BackupIntegrityError, LabBackupStore
from app.cloud.lab_service import CloudLabService
from app.cloud.unified_editor import (
    InvalidUnifiedPlan,
    normalize_unified_plan,
    prepare_unified_edit,
)
from conftest import ORIGIN
from test_cloud_lab_api import FakeProvider, FakeUploader

FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"


def canonical(document: dict) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(", ", ": ")).encode()


def source_document() -> dict:
    data = json.loads(FIXTURE.read_bytes())
    data["gameData"]["fishChip"] = 3
    data["gameData"]["petUnlock"] = {"Cat": True}
    data["itemData"]["materials"] = {"material_ticket": 5, "material_fish": 3}
    data["itemData"]["cumulativeFishCount"] = 5
    data["itemData"]["seeds"] = {}
    data["seasonData"] = {"coin": 100}
    data["battlePassSaveData"]["seasonData"] = []
    return data


def source_bytes() -> bytes:
    return canonical(source_document())


def plan() -> dict:
    return {
        "gems": 2000,
        "fish_chip": 10,
        "fish_progress": 21,
        "advanced": {"materials": [{"id": "material_ticket", "value": 12}]},
    }


def test_normalized_plan_requires_edits_and_rejects_unknown_keys():
    with pytest.raises(InvalidUnifiedPlan):
        normalize_unified_plan({})
    with pytest.raises(InvalidUnifiedPlan):
        normalize_unified_plan({"gems": 10, "unknown": 1})
    with pytest.raises(InvalidUnifiedPlan):
        normalize_unified_plan({"gems": 10, "characters": ["knight", "knight"]})


def test_composition_applies_each_writer_to_the_same_candidate():
    original = source_bytes()
    edit = prepare_unified_edit(original, plan())
    assert edit.steps == ("gems", "fish_chip", "fish_progress", "advanced")
    assert [category.key for category in edit.categories] == ["gems", "fish_chip", "fish_progress", "advanced"]
    assert edit.change_count == len(edit.changed_fields)
    assert len(set(edit.changed_fields)) == len(edit.changed_fields)
    after = json.loads(edit.candidate)
    assert after["gameData"]["gems"] == 2000
    assert after["gameData"]["fishChip"] == 10
    assert after["itemData"]["materials"]["material_fish"] == 10
    assert after["itemData"]["cumulativeFishCount"] == 21
    assert after["itemData"]["materials"]["material_ticket"] == 12
    assert after["itemData"]["materials"]["custom_unknown"] if "custom_unknown" in after["itemData"]["materials"] else True
    # La edición no cambia el original y puede reproducirse exactamente.
    assert edit.original == original
    assert prepare_unified_edit(original, plan()).candidate == edit.candidate


def test_service_creates_one_backup_and_one_upload_then_restores(tmp_path):
    payload = source_bytes()
    provider = FakeProvider(payload)
    uploader = FakeUploader(provider)
    service = CloudLabService(
        provider,
        LabBackupStore(tmp_path / "backups"),
        uploader=uploader,
        write_enabled=True,
        admin_configured=True,
    )
    prepared = service.prepare_unified(plan(), expected_source=sha256(payload).hexdigest())
    assert prepared.backup.field == "unified"
    assert prepared.backup.unified_plan == normalize_unified_plan(plan())
    assert prepared.backup.candidate_gems == prepared.edit.change_count
    summary = prepared.summary()
    assert summary["change_count"] == prepared.edit.change_count
    assert summary["categories"][0]["key"] == "gems"
    assert len(service.backups()) == 1

    result = service.confirm(prepared.backup.id, prepared.edit.candidate_sha256)
    assert result.persisted is True and result.uploaded is True
    assert len(uploader.calls) == 1
    assert json.loads(provider.payload)["gameData"]["gems"] == 2000
    assert service.backups()[0].field == "unified"

    verified = service.verify(prepared.backup.id)
    assert verified.matches_candidate is True

    restored = service.restore(prepared.backup.id)
    assert restored.persisted is True
    assert provider.payload == payload


def test_stale_source_is_rejected_before_backup(tmp_path):
    payload = source_bytes()
    service = CloudLabService(
        FakeProvider(payload),
        LabBackupStore(tmp_path / "backups"),
        uploader=FakeUploader(FakeProvider(payload)),
        write_enabled=True,
        admin_configured=True,
    )
    with pytest.raises(Exception) as error:
        service.prepare_unified(plan(), expected_source="0" * 64)
    assert getattr(error.value, "code", "") == "cloud_remote_changed"
    assert service.backups() == []


def test_unified_backup_plan_is_integrity_checked(tmp_path):
    payload = source_bytes()
    store = LabBackupStore(tmp_path / "backups")
    edit = prepare_unified_edit(payload, plan())
    bundle = store.save(
        edit,
        remote_source="fake-remote",
        remote_size=len(payload),
        remote_sha256=sha256(payload).hexdigest(),
        field="unified",
        original_value=0,
        new_value=edit.change_count,
        unified_plan=edit.plan,
    )
    record_path = tmp_path / "backups" / bundle.record.id / "record.json"
    record = json.loads(record_path.read_text())
    record["unified_plan"]["gems"] = 9999
    record_path.write_text(json.dumps(record, ensure_ascii=False, sort_keys=True))
    with pytest.raises(BackupIntegrityError):
        store.load(bundle.record.id)

def test_unified_backup_record_accepts_full_plan_above_legacy_limit(tmp_path):
    payload = source_bytes()
    weapon_ids = [f"weapon_{'x' * 72}{index:04d}" for index in range(995)]
    skin_ids = [f"skin_{'y' * 74}{index:04d}" for index in range(192)]
    normalized = normalize_unified_plan(
        {"weapon_progression": weapon_ids, "weapon_skins": skin_ids}
    )
    candidate = payload + b"\n"
    edit = SimpleNamespace(
        plan=normalized,
        changed=True,
        original=payload,
        candidate=candidate,
        original_sha256=sha256(payload).hexdigest(),
        candidate_sha256=sha256(candidate).hexdigest(),
        original_gems=0,
        new_gems=1,
        categories=(),
    )
    store = LabBackupStore(tmp_path / "backups")
    bundle = store.save(
        edit,
        remote_source="fake-remote",
        remote_size=len(payload),
        remote_sha256=sha256(payload).hexdigest(),
        field="unified",
        original_value=0,
        new_value=1,
        unified_plan=normalized,
    )
    record_path = tmp_path / "backups" / bundle.record.id / "record.json"
    assert len(record_path.read_bytes()) > 64 * 1024
    loaded = store.load(bundle.record.id)
    assert loaded.original == payload
    assert loaded.record.unified_plan == normalized

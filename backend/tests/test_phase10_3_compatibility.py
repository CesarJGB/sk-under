import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.cloud import compatibility
from app.cloud.backup_store import LabBackupStore
from app.cloud.compatibility import (
    CompatibilityChanged,
    CompatibilityPending,
    StoreMetadata,
    StoreMetadataCache,
    decision_for,
    inspect_versions,
    preflight_write,
    require_matching_binding,
    require_write_preflight,
)
from app.cloud.lab_service import CloudLabService
from test_cloud_lab_api import FakeProvider, FakeUploader

FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"
IOS_MARKERS = {"gameVersion": 2155, "AppVersion": 1531}


def canonical(document: dict) -> bytes:
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(", ", ": ")
    ).encode()


def android_source() -> bytes:
    return FIXTURE.read_bytes()


def ios_source() -> bytes:
    document = json.loads(FIXTURE.read_bytes())
    document["platformId"] = "IOS"
    document["cloudSaveId"] = "IOS_TEST_10_3"
    document["gameData"].update(IOS_MARKERS)
    document["itemData"]["AppVersion"] = IOS_MARKERS["AppVersion"]
    return canonical(document)


def test_registry_separates_commercial_protocol_and_save_versions():
    android = decision_for(
        distribution_id="android-global",
        commercial_version="8.8.0",
        platform="android",
        source=android_source(),
        capability_state="write_verified",
    )
    assert android.state == "compatible"
    assert android.profile is not None
    assert android.profile.protocol_game_version == "8.8.0"
    assert android.detected.serialzed_version == 1
    assert android.detected.game_version == 2155
    assert android.detected.app_version == 80800
    assert android.write_supported is True

    ios = decision_for(
        distribution_id="ios-global",
        commercial_version="8.8.0.14",
        platform="ios",
        source=ios_source(),
        capability_state="write_experimental",
    )
    assert ios.state == "experimental"
    assert ios.profile is not None
    assert ios.profile.protocol_game_version == "8.8.0"
    assert ios.detected.game_version == 2155
    assert ios.detected.app_version == 1531


def test_unknown_version_is_read_only_and_cannot_pass_preflight():
    document = json.loads(ios_source())
    document["gameData"]["gameVersion"] = 9999
    source = canonical(document)
    decision = decision_for(
        distribution_id="ios-global",
        commercial_version="8.8.0.14",
        platform="ios",
        source=source,
        capability_state="write_experimental",
    )
    assert decision.state == "pending_verification"
    assert decision.read_ready is True
    assert decision.prepare_ready is False
    assert decision.write_supported is False

    preflight = preflight_write(
        source,
        distribution_id="ios-global",
        commercial_version="8.8.0.14",
        platform="ios",
        capability_state="write_experimental",
    )
    with pytest.raises(CompatibilityPending):
        require_write_preflight(preflight)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("gameVersion", 80800),
        ("gameVersion", None),
        ("AppVersion", 1531),
        ("AppVersion", None),
    ],
)
def test_android_marker_mismatch_blocks_prepare_and_write(field, value):
    document = json.loads(android_source())
    if field == "gameVersion":
        document["gameData"][field] = value
    else:
        document["itemData"][field] = value
    decision = decision_for(
        distribution_id="android-global",
        commercial_version="8.8.0",
        platform="android",
        source=canonical(document),
        capability_state="write_verified",
    )
    assert decision.state == "pending_verification"
    assert decision.read_ready is True
    assert decision.prepare_ready is False
    assert decision.write_supported is False
    assert any("marcador validado" in warning for warning in decision.warnings)


def test_new_store_version_is_detected_but_not_adopted():
    store = StoreMetadata(
        distribution_id="android-global",
        version="8.9.0",
        status="ok",
        source="test",
        checked_at=1.0,
    )
    decision = decision_for(
        distribution_id="android-global",
        commercial_version="8.8.0",
        platform="android",
        source=android_source(),
        capability_state="write_verified",
        store=store,
    )
    assert decision.state == "new_version_detected"
    assert decision.write_supported is False
    assert decision.profile is not None
    assert decision.profile.commercial_version == "8.8.0"
    assert "8.9.0" in decision.reason


def test_store_cache_keeps_failures_without_fabricating_a_version(monkeypatch):
    cache = StoreMetadataCache(ttl=3600)
    calls = 0

    def failing():
        nonlocal calls
        calls += 1
        raise OSError("offline")

    monkeypatch.setitem(compatibility._FETCHERS, "android-global", failing)
    first = cache.get("android-global")
    second = cache.get("android-global")
    assert first is second
    assert first.status == "unavailable"
    assert first.version is None
    assert calls == 1
    assert cache.peek("android-global") is first
    assert cache.peek("ios-global") is None


def test_binding_rejects_changed_account_or_version():
    source = ios_source()
    first = preflight_write(
        source,
        distribution_id="ios-global",
        commercial_version="8.8.0.14",
        platform="ios",
        capability_state="write_experimental",
        account_digest="a" * 64,
        plan_sha256="b" * 64,
    ).binding
    same = preflight_write(
        source,
        distribution_id="ios-global",
        commercial_version="8.8.0.14",
        platform="ios",
        capability_state="write_experimental",
        account_digest="a" * 64,
        plan_sha256="b" * 64,
    ).binding
    require_matching_binding(first, same)
    other_account = dict(same, account_digest="c" * 64)
    with pytest.raises(CompatibilityChanged):
        require_matching_binding(first, other_account)
    other_source = canonical({**json.loads(source), "serialzedVersion": 2})
    other = preflight_write(
        other_source,
        distribution_id="ios-global",
        commercial_version="8.8.0.14",
        platform="ios",
        capability_state="write_experimental",
        account_digest="a" * 64,
        plan_sha256="b" * 64,
    ).binding
    with pytest.raises(CompatibilityChanged):
        require_matching_binding(first, other)


def test_lab_service_blocks_platform_mismatch_before_preparing(tmp_path):
    payload = ios_source()
    service = CloudLabService(
        FakeProvider(payload),
        LabBackupStore(tmp_path / "backups"),
        uploader=FakeUploader(FakeProvider(payload)),
        write_enabled=True,
        admin_configured=True,
        platform="android",
        distribution_id="android-global",
        commercial_version="8.8.0",
    )
    with pytest.raises(CompatibilityPending):
        service.prepare_unified({"gems": 1234})
    assert service.backups() == []


def test_prepared_backup_keeps_the_compatibility_binding(tmp_path):
    payload = android_source()
    service = CloudLabService(
        FakeProvider(payload),
        LabBackupStore(tmp_path / "backups"),
        uploader=FakeUploader(FakeProvider(payload)),
        write_enabled=True,
        admin_configured=True,
        platform="android",
        distribution_id="android-global",
        commercial_version="8.8.0",
        account_digest="d" * 64,
    )
    prepared = service.prepare_unified({"gems": 1234})
    binding = prepared.backup.compatibility_binding
    assert binding["distribution_id"] == "android-global"
    assert binding["account_digest"] == "d" * 64
    assert binding["source_sha256"] == sha256(payload).hexdigest()
    assert binding["schema_version"] == 1
    assert binding["plan_sha256"]
    assert binding["policy"] == "phase10-3"
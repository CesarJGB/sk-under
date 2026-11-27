"""Pruebas de la matriz de capacidades y de la preparación iOS aislada.

No se envía ninguna escritura iOS: la plataforma debe conservar el candidato y
el respaldo, pero rechazar la subida con un código específico.
"""

from __future__ import annotations

import json
import time
from hashlib import sha256
from pathlib import Path

import pytest

from app.cloud.backup_store import LabBackupStore
from app.cloud.capabilities import STATES, can_prepare, can_write, capability_matrix
from app.cloud.lab_service import CloudLabService, LabWritePendingValidation
from test_gems_editor import FakeUploader, FixedProvider
from test_native_api import API, HEADERS, PAYLOAD_A, login, make_native

IOS_PAYLOAD = json.dumps(
    json.loads(PAYLOAD_A) | {"platformId": "IOS", "cloudSaveId": "IOS_synthetic"},
    ensure_ascii=False,
    sort_keys=True,
    separators=(", ", ": "),
).encode()


def test_capability_matrix_states_are_explicit_and_do_not_extrapolate_android():
    android = capability_matrix("android")
    ios = capability_matrix("ios")
    assert android.state == "write_verified"
    assert android.write_supported is True and android.prepare_ready is True
    android_functions = {function.id: function for function in android.functions}
    ios_functions = {function.id: function for function in ios.functions}
    assert android_functions["save"].state == "write_verified"
    assert android_functions["restore"].state == "write_verified"
    assert ios.state == "write_pending_validation"
    assert ios.write_supported is False and ios.prepare_ready is True
    assert ios_functions["save"].state == "write_pending_validation"
    assert ios_functions["restore"].state == "write_pending_validation"
    assert ios_functions["download"].state == "read_only"
    assert can_prepare("ios") is True and can_write("ios") is False
    assert {function.state for function in ios.functions} <= STATES
    unknown = capability_matrix("unknown")
    assert unknown.state == "read_only" and unknown.prepare_ready is False


def test_ios_lab_prepares_a_candidate_and_blocks_upload_and_restore(tmp_path: Path):
    provider = FixedProvider(IOS_PAYLOAD)
    uploader = FakeUploader(provider)
    lab = CloudLabService(
        provider,
        LabBackupStore(tmp_path / "backups"),
        uploader=uploader,
        write_enabled=True,
        admin_configured=True,
        platform="ios",
    )
    status = lab.status()
    assert status.mode == "read_only"
    assert status.write_state == "write_pending_validation"
    assert status.prepare_ready is True and status.write_ready is False
    assert status.capabilities["functions"]["save"]["state"] == "write_pending_validation"

    prepared = lab.prepare(1002)
    assert prepared.changed is True
    assert prepared.backup.changed is True
    assert prepared.backup.original_sha256 == sha256(IOS_PAYLOAD).hexdigest()
    assert prepared.edit.candidate != IOS_PAYLOAD
    assert json.loads(prepared.edit.candidate)["gameData"]["gems"] == 1002

    with pytest.raises(LabWritePendingValidation):
        lab.confirm(prepared.backup.id, prepared.edit.candidate_sha256)
    assert uploader.calls == []
    with pytest.raises(LabWritePendingValidation):
        lab.restore(prepared.backup.id)
    assert uploader.calls == []
    assert provider.payload == IOS_PAYLOAD


def test_native_ios_session_can_prepare_but_cannot_confirm(tmp_path: Path):
    env = make_native(tmp_path, payload_a=IOS_PAYLOAD, write=True)
    profile = env["store"].create_profile(
        label="Instalación iOS sintética",
        distribution_id="ios-global",
        distro_id="distro-a",
        unique_id="unique-a",
        allow_write=True,
    )
    response = env["client"].post(
        API + "/login",
        headers=HEADERS,
        json={
            "distribution": "ios-global",
            "email": "a@example.test",
            "password": "pass-a",
            "profile_id": profile.id,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["account"]["platform"] == "ios"
    assert body["read_only"] is True
    assert body["prepare_ready"] is True
    assert body["write_state"] == "write_pending_validation"
    assert body["write_ready"] is False
    assert body["save"]["sha256"] == sha256(IOS_PAYLOAD).hexdigest()

    source = env["client"].get(API + "/save", headers=HEADERS)
    assert source.status_code == 200, source.text
    prepared = env["client"].post(
        API + "/prepare",
        headers=HEADERS,
        json={"new_gems": 1002, "source_sha256": source.json()["sha256"]},
    )
    assert prepared.status_code == 200, prepared.text
    draft = prepared.json()
    assert draft["backup"]["changed"] is True

    blocked = env["client"].post(
        API + "/confirm",
        headers=HEADERS,
        json={
            "backup_id": draft["backup"]["id"],
            "expected_sha256": draft["candidate_sha256"],
            "confirmation": "SUBIR",
        },
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["code"] == "native_write_pending_validation"
    assert env["uploaders"]["unique-a"].calls == []
    assert env["providers"]["unique-a"].payload == IOS_PAYLOAD


def test_native_view_exposes_platform_capabilities(tmp_path: Path):
    env = make_native(tmp_path)
    profile = env["store"].create_profile(
        label="Instalación iOS sintética",
        distribution_id="ios-global",
        distro_id="distro-a",
        unique_id="unique-a",
        allow_write=True,
    )
    view = env["service"]._view_values(
        profile,
        int(time.time()) + 3600,
        int(time.time()) + 3600,
        email="a@example.test",
    )
    assert view["prepare_ready"] is True
    assert view["write_ready"] is False
    assert view["write_state"] == "write_pending_validation"
    assert view["capabilities"]["platform"] == "ios"
    assert view["capabilities"]["functions"]["save"]["state"] == "write_pending_validation"
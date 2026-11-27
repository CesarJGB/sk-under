"""Pruebas del modo de prueba iOS y del aislamiento por cuenta.

La cuenta real no aparece en las pruebas: se usa un correo sintético y el mismo
digest con separación de dominio que aplica el servicio. El modo global es
temporal y reversible; no equivale a compatibilidad nativa validada.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from app.cloud.backup_store import LabBackupStore
from app.cloud.blob_wire import build_blob_headers
from app.cloud.capabilities import account_digest, capability_matrix, experimental_account
from app.cloud.lab_service import CloudLabService
from test_gems_editor import FakeUploader, FixedProvider
from test_native_api import API, HEADERS, PAYLOAD_A, make_native

_EMAIL = "a@example.test"
_IOS_DOCUMENT = json.loads(PAYLOAD_A) | {
    "platformId": "IOS",
    "cloudSaveId": "IOS_synthetic",
}
# Marcador observado en la partida iOS real 8.8.0.14; no es la versión comercial.
_IOS_DOCUMENT["gameData"]["gameVersion"] = 2155
_IOS_DOCUMENT["itemData"]["AppVersion"] = 1531
IOS_PAYLOAD = json.dumps(
    _IOS_DOCUMENT,
    ensure_ascii=False,
    sort_keys=True,
    separators=(", ", ": "),
).encode()


def test_ios_write_test_mode_is_enabled_and_explicit():
    default = capability_matrix("ios")
    assert default.state == "write_experimental"
    assert default.write_supported is True

    experimental = capability_matrix("ios", experimental_authorized=True)
    assert experimental.state == "write_experimental"
    assert experimental.write_supported is True
    functions = {function.id: function for function in experimental.functions}
    assert functions["save"].state == "write_experimental"
    assert functions["restore"].state == "write_experimental"
    assert functions["download"].state == "read_only"

    assert experimental_account(_EMAIL, {account_digest(_EMAIL)}) is True
    assert experimental_account("otra@example.test", {account_digest(_EMAIL)}) is False


def test_blob_headers_use_the_protocol_version_on_both_platforms():
    android = build_blob_headers("token", "unique", "distro")
    assert android["x-platform"] == "android"
    assert android["x-app-version"] == "8.8.0"
    ios = build_blob_headers(
        "token",
        "unique",
        "distro",
        platform="ios",
        app_version="8.8.0",
        game_version="8.8.0",
    )
    assert ios["x-platform"] == "ios"
    assert ios["x-app-version"] == "8.8.0"
    assert ios["x-game-version"] == "8.8.0"


def test_experimental_lab_requires_backup_and_verifies_persistence(tmp_path: Path):
    provider = FixedProvider(IOS_PAYLOAD)
    uploader = FakeUploader(provider)
    lab = CloudLabService(
        provider,
        LabBackupStore(tmp_path / "backups"),
        uploader=uploader,
        write_enabled=True,
        admin_configured=True,
        platform="ios",
        experimental=True,
    )
    status = lab.status()
    assert status.mode == "live"
    assert status.write_state == "write_experimental"
    assert status.write_ready is True

    prepared = lab.prepare(1200)
    assert prepared.backup.original_sha256 == sha256(IOS_PAYLOAD).hexdigest()
    result = lab.confirm(prepared.backup.id, prepared.edit.candidate_sha256)
    assert result.uploaded is True and result.accepted is True
    assert result.persisted is True
    assert result.remote_gems == 1200
    assert uploader.calls[-1] == prepared.edit.candidate
    assert json.loads(provider.payload)["platformId"] == "IOS"

    restored = lab.restore(prepared.backup.id)
    assert restored.persisted is True
    assert restored.remote_gems == prepared.edit.original_gems
    assert provider.payload == IOS_PAYLOAD


def test_native_ios_test_mode_keeps_accounts_isolated(tmp_path: Path):
    env = make_native(tmp_path, payload_a=IOS_PAYLOAD, write=True)
    env["service"].ios_experimental_accounts = frozenset({account_digest(_EMAIL)})
    profile = env["store"].create_profile(
        label="Instalación iOS sintética",
        distribution_id="ios-global",
        distro_id="distro-a",
        unique_id="unique-a",
        allow_write=False,
    )
    response = env["client"].post(
        API + "/login",
        headers=HEADERS,
        json={
            "distribution": "ios-global",
            "email": _EMAIL,
            "password": "pass-a",
            "profile_id": profile.id,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["write_state"] == "write_experimental"
    assert body["write_ready"] is True
    assert body["read_only"] is False

    source = env["client"].get(API + "/save", headers=HEADERS)
    assert source.status_code == 200, source.text
    prepared = env["client"].post(
        API + "/prepare",
        headers=HEADERS,
        json={"new_gems": 1300, "source_sha256": source.json()["sha256"]},
    )
    assert prepared.status_code == 200, prepared.text
    draft = prepared.json()
    confirmed = env["client"].post(
        API + "/confirm",
        headers=HEADERS,
        json={
            "backup_id": draft["backup"]["id"],
            "expected_sha256": draft["candidate_sha256"],
            "confirmation": "SUBIR",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()
    assert result["persisted"] is True
    assert result["remote_gems"] == 1300
    assert sha256(env["uploaders"]["unique-a"].calls[-1]).hexdigest() == draft["candidate_sha256"]
    assert json.loads(env["providers"]["unique-a"].payload)["platformId"] == "IOS"

    other = env["store"].create_profile(
        label="Otra instalación iOS sintética",
        distribution_id="ios-global",
        distro_id="distro-b",
        unique_id="unique-b",
        allow_write=False,
    )
    other_login = env["client"].post(
        API + "/login",
        headers=HEADERS,
        json={
            "distribution": "ios-global",
            "email": "b@example.test",
            "password": "pass-b",
            "profile_id": other.id,
        },
    )
    assert other_login.status_code == 200, other_login.text
    other_body = other_login.json()
    assert other_body["write_state"] == "write_experimental"
    assert other_body["write_ready"] is True
    assert env["uploaders"]["unique-b"].calls == []
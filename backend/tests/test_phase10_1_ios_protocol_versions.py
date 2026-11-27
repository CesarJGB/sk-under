"""Regresión de la Fase 10.1: versiones de protocolo distintas de la visible.

El cliente iOS muestra 8.8.0.14, pero BlobSave compara la versión de protocolo
8.8.0. Enviar la versión visible en ``x-app-version``/``x-game-version`` marca
la copia remota como más nueva y el cliente oficial la rechaza como "versión
demasiado antigua". Estas pruebas fijan la separación entre ambos valores.
"""

from __future__ import annotations

import gzip
import json
from hashlib import sha256

import pytest

from app.cloud.blob_upload import BlobSaveUploader
from app.cloud.modern import ModernCloudSaveProvider, _raise_remote_error
from app.cloud.provider import CloudProviderSaveVersionAhead
from app.cloud.upload_dry_run import prepare_upload_candidate
from app.native.client import build_login_headers
from app.native.distributions import get_distribution
from app.native.service import _default_provider, _default_uploader
from app.parsers.json_document import parse_json


def test_ios_display_version_is_not_the_protocol_version():
    ios = get_distribution("ios-global")
    assert ios.game_version == "8.8.0.14"
    assert ios.protocol_app_version == "8.8.0"
    assert ios.protocol_game_version == "8.8.0"

    android = get_distribution("android-global")
    assert android.game_version == "8.8.0"
    assert android.protocol_app_version == "8.8.0"
    assert android.protocol_game_version == "8.8.0"


def test_download_and_upload_clients_use_protocol_versions():
    ios = get_distribution("ios-global")
    provider = _default_provider("token", "unique", "distro", ios)
    uploader = _default_uploader("token", "unique", "distro", ios)
    assert isinstance(provider, ModernCloudSaveProvider)
    assert isinstance(uploader, BlobSaveUploader)
    assert (provider.app_version, provider.game_version) == ("8.8.0", "8.8.0")
    assert (uploader.app_version, uploader.game_version) == ("8.8.0", "8.8.0")


def test_login_headers_use_protocol_versions_on_ios():
    headers = build_login_headers(get_distribution("ios-global"))
    assert headers["x-platform"] == "ios"
    assert headers["x-app-version"] == "8.8.0"
    assert headers["x-game-version"] == "8.8.0"


def test_server_version_marker_is_a_distinct_diagnostic():
    body = gzip.compress(
        json.dumps(
            {
                "error": 100599,
                "errordetails": {"reason": "VersionLowerThanBlobSave"},
            }
        ).encode(),
        mtime=0,
    )
    with pytest.raises(CloudProviderSaveVersionAhead):
        _raise_remote_error(400, body, "gzip")


def test_unmodified_ios_roundtrip_preserves_bytes_and_unknown_fields():
    document = {
        "battlePassSaveData": {"seasonData": []},
        "cloudSaveId": "IOS_synthetic",
        "gameData": {"gems": 1000, "gameVersion": 2155, "unknownNested": {"a": 1}},
        "itemData": {"AppVersion": 1531, "unknownList": [1, 2, 3]},
        "platformId": "IOS",
        "serialzedVersion": 1,
        "unknownTopLevel": {"keep": True},
    }
    original = json.dumps(document, ensure_ascii=False, sort_keys=True).encode()
    parsed = parse_json(original)
    rebuilt = json.dumps(parsed, ensure_ascii=False, sort_keys=True).encode()
    assert rebuilt == original
    assert sha256(rebuilt).hexdigest() == sha256(original).hexdigest()
    assert parse_json(rebuilt)["unknownTopLevel"] == {"keep": True}
    assert parse_json(rebuilt)["gameData"]["unknownNested"] == {"a": 1}

    candidate = prepare_upload_candidate(original)
    envelope = parse_json(gzip.decompress(candidate.body))
    assert envelope["data"].encode("utf-8") == original
    assert candidate.aggregate_sha256 == sha256(original).hexdigest()
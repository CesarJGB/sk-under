"""Pruebas de importación y lectura de copias de iOS.

Las muestras reales son privadas y no viven en el repositorio. Estos documentos
sintéticos conservan únicamente la forma observada: ``platformId`` IOS,
``cloudSaveId`` con prefijo IOS_, las secciones compartidas y la representación
RAW de CRDE con ``_crde_misc``.
"""

import gzip
import json
from hashlib import sha256

import pytest

from app.cloud.ios import CAPABILITIES, IosSave, decode_ios_save, save_platform
from app.cloud.provider import AcquiredCloudSave, CloudSaveMetadata
from app.native.distributions import require_enabled
from app.native.errors import NativeSavePlatformMismatch
from app.native.service import NativeSaveProvider
from app.native.store import NativeStore

ORIGIN = "http://127.0.0.1:5173"
KEY = bytes.fromhex("ab" * 32)


def document(**overrides):
    value = {
        "serialzedVersion": 1,
        "cloudSaveId": "IOS_1234",
        "platformId": "IOS",
        "gameData": {
            "gameVersion": 2155,
            "ChillyUid": 1234,
            "gems": 7409045,
            "fishChip": 88600,
            "heroLevel": {"0": 8},
        },
        "itemData": {"AppVersion": 1531, "blueprints": {"room_decorate_safe": 2}},
        "statisticData": {"room_unlock_safe": 1},
        "settingData": {"language": "es"},
        "maps": {"maps": []},
    }
    value.update(overrides)
    return value


def encode(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def test_decode_native_ios_save_preserves_bytes_and_reports_read_only():
    source = encode(document())
    save = decode_ios_save(source)
    assert isinstance(save, IosSave)
    assert save.source == "native-json"
    assert save.encoding == "json"
    assert save.serialzed_version == 1
    assert save.cloud_save_id == "IOS_1234"
    assert save.platform_id == "IOS"
    assert save.game_version == 2155
    assert save.app_version == 1531
    assert save.original == source
    assert save.sha256 == sha256(source).hexdigest()
    assert save.size == len(source)
    summary = save.summary()
    assert summary["platform"] == "ios"
    assert summary["experimental"] is True
    assert summary["write_enabled"] is False
    assert summary["sections"]["gameData"] == "present"
    assert summary["sections"]["itemData"] == "present"
    assert summary["sections"]["pvpData"] == "missing"
    assert summary["has_cloud_save_id"] is True
    report = save.report()
    assert report["platform"] == "ios"
    assert report["read_only"] is True
    assert report["write_enabled"] is False
    assert report["sha256"] == save.sha256


def test_decode_crde_raw_without_native_metadata():
    value = document()
    for name in ("cloudSaveId", "platformId", "serialzedVersion", "maps"):
        value.pop(name)
    value["_crde_misc"] = {"maps": {"maps": []}, "platformId": "IOS"}
    save = decode_ios_save(encode(value))
    assert save.source == "crde-raw"
    assert save.serialzed_version is None
    assert save.cloud_save_id is None
    assert save.crde_misc == {"maps": {"maps": []}, "platformId": "IOS"}
    assert save.summary()["has_crde_metadata"] is True
    assert save.summary()["has_maps"] is False


def test_decode_accepts_gzip_without_rewriting_the_document():
    source = gzip.compress(encode(document()))
    save = decode_ios_save(source)
    assert save.encoding == "gzip"
    assert save.original == source
    assert save.report()["fish_chips"]["balance"] == 88600


def test_unknown_and_android_platforms_are_rejected():
    with pytest.raises(Exception) as missing:
        decode_ios_save(encode(document(platformId=None)))
    assert getattr(missing.value, "code", "") == "ios_not_detected"
    with pytest.raises(Exception) as android:
        decode_ios_save(encode(document(platformId="00000000-0000-4000-8000-000000000001")))
    assert getattr(android.value, "code", "") == "ios_not_detected"
    with pytest.raises(Exception) as gp:
        decode_ios_save(encode(document(platformId="GP")))
    assert getattr(gp.value, "code", "") == "ios_not_detected"


def test_invalid_sections_and_versions_are_rejected():
    with pytest.raises(Exception) as section:
        decode_ios_save(encode(document(itemData=[])))
    assert getattr(section.value, "code", "") == "invalid_aggregate"
    with pytest.raises(Exception):
        decode_ios_save(encode(document(serialzedVersion=True)))
    with pytest.raises(Exception):
        decode_ios_save(encode(document(serialzedVersion=-1)))


def test_save_platform_requires_an_explicit_marker():
    assert save_platform(encode(document())) == "ios"
    assert save_platform(encode(document(platformId="IOS_1234"))) == "android"
    assert save_platform(encode(document(platformId=None))) == "unknown"
    crde = document(platformId=None, _crde_misc={"platformId": "IOS"})
    assert save_platform(encode(crde)) == "ios"
    crde["_crde_misc"] = {"platformId": "ANDROID"}
    assert save_platform(encode(crde)) == "unknown"


def test_capabilities_publish_verified_download_and_disabled_write():
    by_id = {entry["id"]: entry for entry in CAPABILITIES}
    assert by_id["remote_auth"]["read"] == "read_compatible"
    assert by_id["remote_auth"]["write"] == "not_exposed"
    assert by_id["remote_auth"]["evidence"] == "E3"
    assert all(entry["write"] == "not_exposed" for entry in CAPABILITIES)


def test_ios_distribution_is_enabled_and_read_only_metadata_is_explicit():
    distribution = require_enabled("ios-global")
    assert distribution.platform == "ios"
    assert distribution.game_version == "8.8.0.13"
    assert "solo lectura" in distribution.note.lower()


def test_identity_subjects_are_scoped_per_platform(tmp_path):
    store = NativeStore(tmp_path / "native", KEY)
    legacy = store.identity_subject(email="a@example.test", uid=1, player_id=2)
    explicit = store.identity_subject(email="a@example.test", uid=1, player_id=2, scope="")
    ios = store.identity_subject(email="a@example.test", uid=1, player_id=2, scope="ios")
    assert legacy == explicit
    assert ios != legacy
    assert ios == store.identity_subject(
        email="a@example.test", uid=1, player_id=2, scope="ios"
    )


def test_native_provider_rejects_a_save_from_another_platform(tmp_path):
    store = NativeStore(tmp_path / "native", KEY)
    android = encode(document(platformId="00000000-0000-4000-8000-000000000001"))
    metadata = CloudSaveMetadata(
        revision="synthetic", size=len(android), sha256=sha256(android).hexdigest()
    )

    class Remote:
        def download(self, limit=0):
            return AcquiredCloudSave(metadata=metadata, payload=android)

        def metadata(self):
            return metadata

    provider = NativeSaveProvider(
        remote=Remote(),
        store=store,
        subject=store.identity_subject(email="a@example.test", uid=1, player_id=2, scope="ios"),
        distribution="ios-global",
        expected_platform="ios",
    )
    with pytest.raises(NativeSavePlatformMismatch):
        provider.download()


def test_api_capabilities_and_inspection_are_read_only(client):
    response = client.get("/api/v1/cloud/ios/capabilities", headers={"origin": ORIGIN})
    assert response.status_code == 200
    body = response.json()
    assert body["platform"] == "ios"
    assert body["authentication"] == "available_read_only"
    assert body["download"] == "available_read_only"
    assert body["write_enabled"] is False

    source = encode(document())
    response = client.post(
        "/api/v1/cloud/ios/inspect",
        content=source,
        headers={"origin": ORIGIN, "content-type": "application/json"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sha256"] == sha256(source).hexdigest()
    assert body["size"] == len(source)
    assert body["write_enabled"] is False
    assert body["report"]["read_only"] is True


def test_api_rejects_android_documents_and_wrong_content_type(client):
    response = client.post(
        "/api/v1/cloud/ios/inspect",
        content=encode(document(platformId="00000000-0000-4000-8000-000000000001")),
        headers={"origin": ORIGIN, "content-type": "application/json"},
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "ios_not_detected"

    response = client.post(
        "/api/v1/cloud/ios/inspect",
        content=encode(document()),
        headers={"origin": ORIGIN, "content-type": "text/plain"},
    )
    assert response.status_code == 415

    response = client.post(
        "/api/v1/cloud/ios/inspect",
        content=b"{not json",
        headers={"origin": ORIGIN, "content-type": "application/json"},
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "ios_unsupported_encoding"
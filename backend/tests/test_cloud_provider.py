from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

import pytest

from app.bridge import CloudBridge
from app.cloud.provider import (
    AcquiredCloudSave,
    CloudProviderDisabled,
    CloudProviderProtocolError,
    CloudProviderUnauthenticated,
    CloudSaveMetadata,
    DisabledCloudSaveProvider,
    GatewayCloudSaveProvider,
    LocalFixtureCloudSaveProvider,
)
from app.cloud_save import CopyLimitError

CLOUD = {
    "serialzedVersion": 1,
    "cloudSaveId": "fixture-cloud-id",
    "platformId": "android",
    "gameData": {"gems": 7, "nested": {"keep": True}},
    "itemData": {"cumulativeFishCount": 2},
    "unknownSection": {"opaque": [1, 2, 3]},
}


def write_cloud(path: Path, *, gzipped: bool = False) -> Path:
    payload = json.dumps(CLOUD, ensure_ascii=False).encode("utf-8")
    if gzipped:
        payload = gzip.compress(payload, mtime=0)
    path.write_bytes(payload)
    return path


def test_disabled_provider_is_typed_and_has_no_transport() -> None:
    provider = DisabledCloudSaveProvider()
    with pytest.raises(CloudProviderDisabled):
        provider.metadata()
    with pytest.raises(CloudProviderDisabled):
        provider.download()


def test_fixture_provider_metadata_and_download_are_labeled(tmp_path: Path) -> None:
    path = write_cloud(tmp_path / "cloud.json")
    provider = LocalFixtureCloudSaveProvider(path)
    metadata = provider.metadata()
    assert metadata.source == "fixture"
    assert metadata.size == path.stat().st_size
    acquired = provider.download()
    assert acquired.metadata.source == "fixture"
    assert acquired.payload == path.read_bytes()
    assert "fixture-cloud-id" not in json.dumps(acquired.summary())


def test_fixture_provider_rejects_symlink(tmp_path: Path) -> None:
    path = write_cloud(tmp_path / "cloud.json")
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(Exception):
        LocalFixtureCloudSaveProvider(link).download()


def test_fixture_provider_honors_limit(tmp_path: Path) -> None:
    path = write_cloud(tmp_path / "cloud.json")
    with pytest.raises(CopyLimitError):
        LocalFixtureCloudSaveProvider(path).download(10)


def test_gateway_provider_extracts_data_string() -> None:
    source = json.dumps(CLOUD).encode("utf-8")

    def fetch(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
        assert url.endswith("/Backup/GetBlobSave")
        assert headers["Authorization"] == "Bearer test-token"
        return 200, json.dumps({"data": source.decode("utf-8")}).encode("utf-8")

    provider = GatewayCloudSaveProvider(token="test-token", fetch=fetch)
    acquired = provider.download()
    assert acquired.payload == source
    assert acquired.metadata.source == "gateway"
    assert "test-token" not in repr(provider)
    assert "test-token" not in json.dumps(acquired.summary())


def test_gateway_provider_accepts_direct_aggregate() -> None:
    source = json.dumps(CLOUD).encode("utf-8")

    def fetch(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
        return 200, source

    acquired = GatewayCloudSaveProvider(token="t", fetch=fetch).download()
    assert acquired.payload == source


def test_gateway_provider_maps_error_envelope() -> None:
    def fetch(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
        return 400, json.dumps({"ok": False, "errorCode": 10001}).encode("utf-8")

    with pytest.raises(CloudProviderUnauthenticated):
        GatewayCloudSaveProvider(token="t", fetch=fetch).download()


def test_gateway_provider_maps_http_401() -> None:
    def fetch(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
        return 401, b""

    with pytest.raises(CloudProviderUnauthenticated):
        GatewayCloudSaveProvider(token="t", fetch=fetch).download()


def test_gateway_provider_requires_https_and_token() -> None:
    with pytest.raises(CloudProviderUnauthenticated):
        GatewayCloudSaveProvider(token="   ")
    with pytest.raises(CloudProviderProtocolError):
        GatewayCloudSaveProvider(token="t", base_url="http://example.invalid")
    with pytest.raises(CloudProviderProtocolError):
        GatewayCloudSaveProvider(token="t", timeout=0)


def test_gateway_provider_rejects_non_json() -> None:
    def fetch(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
        return 200, b"not json"

    with pytest.raises(CloudProviderProtocolError):
        GatewayCloudSaveProvider(token="t", fetch=fetch).download()


def test_gateway_provider_rejects_oversized_response() -> None:
    def fetch(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
        return 200, b"{" + b" " * 64 + b"}"

    with pytest.raises(CopyLimitError):
        GatewayCloudSaveProvider(token="t", fetch=fetch).download(16)


def test_acquired_save_rejects_metadata_mismatch() -> None:
    metadata = CloudSaveMetadata("r", 2, "00" * 32)
    with pytest.raises(CloudProviderProtocolError):
        AcquiredCloudSave(metadata, b"{}")


def test_cloud_bridge_roundtrip_preserves_unknown_fields_and_source(tmp_path: Path) -> None:
    path = write_cloud(tmp_path / "cloud.json")
    original = path.read_bytes()
    bridge = CloudBridge()
    acquisition = bridge.acquire(LocalFixtureCloudSaveProvider(path))
    assert acquisition.copy.aggregate.data.extra_fields == {"unknownSection": {"opaque": [1, 2, 3]}}
    assert acquisition.summary()["serialzed_version"] == 1
    target = bridge.export(LocalFixtureCloudSaveProvider(path), tmp_path / "export.json")
    assert Path(target.target).read_bytes() == original
    assert path.read_bytes() == original
    assert os.stat(target.target).st_mode & 0o777 == 0o600


def test_cloud_bridge_accepts_gzip_fixture(tmp_path: Path) -> None:
    path = write_cloud(tmp_path / "cloud.json.gz", gzipped=True)
    acquisition = CloudBridge().acquire(LocalFixtureCloudSaveProvider(path))
    assert acquisition.acquired.metadata.source == "fixture"
    assert acquisition.copy.aggregate.encoding == "gzip"
    assert acquisition.copy.aggregate.data.game_data["gems"] == 7


def test_gateway_provider_does_not_treat_arbitrary_data_as_cloud_save() -> None:
    def fetch(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
        return 200, b'{"data":{"message":"not a save"}}'

    with pytest.raises(CloudProviderProtocolError):
        GatewayCloudSaveProvider(token="t", fetch=fetch).download()

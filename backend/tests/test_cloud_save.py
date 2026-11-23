import gzip
import json
from hashlib import sha256
from pathlib import Path

import pytest

from app import cloud_save
from app.cloud_save import CloudSaveError, reconstruct_cloud_save

FIXTURE = Path(__file__).with_name("fixtures") / "cloud-save-sintetico.json"


@pytest.mark.parametrize("encoding", ["json", "gzip"])
def test_reconstructs_typed_data_and_summarizes_sections(encoding):
    fixture = FIXTURE.read_bytes()
    source = gzip.compress(fixture, mtime=0) if encoding == "gzip" else fixture
    result = reconstruct_cloud_save(source)

    assert result.encoding == encoding
    assert result.source_size == len(source)
    assert result.source_sha256 == sha256(source).hexdigest()
    assert result.data.serialzed_version == 0
    assert result.data.cloud_save_id == "sintetico-cuenta"
    assert result.data.platform_id == "sintetico-plataforma"
    assert result.data.game_data == {}
    assert result.data.optional_sections["itemData"]["materials"] == {}
    assert result.data.extra_fields == {"campoSintetico": {"entero": 9007199254740993}}

    summary = result.summary()
    assert summary["experimental"] is True
    assert summary["sections"]["gameData"] == "present"
    assert summary["sections"]["maps"] == "present"
    assert summary["sections"]["taskData"] == "null"
    assert summary["sections"]["battlePassSaveData"] == "missing"
    for visible in (repr(result), repr(result.data), json.dumps(summary)):
        assert "sintetico-cuenta" not in visible
        assert "sintetico-plataforma" not in visible
        assert "9007199254740993" not in visible
        assert result.source_sha256 not in visible


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("serialzedVersion", False),
        ("serialzedVersion", -1),
        ("cloudSaveId", " "),
        ("platformId", 1),
        ("gameData", []),
        ("itemData", "dato"),
        ("taskData", []),
    ],
)
def test_rejects_incompatible_field_types(name, value):
    root = json.loads(FIXTURE.read_bytes())
    root[name] = value
    with pytest.raises(CloudSaveError, match=name):
        reconstruct_cloud_save(json.dumps(root).encode())


@pytest.mark.parametrize("name", ["serialzedVersion", "cloudSaveId", "platformId", "gameData"])
def test_rejects_missing_required_fields(name):
    root = json.loads(FIXTURE.read_bytes())
    del root[name]
    with pytest.raises(CloudSaveError, match=name):
        reconstruct_cloud_save(json.dumps(root).encode())


@pytest.mark.parametrize(
    "source",
    [
        b"",
        b"PK\x03\x04archive",
        b'{"Data":"{}"}',
        b'{"gameData":{',
        b'{"campo":"\xff"}',
        b'{"gameData":{"campo":1,"campo":2}}',
        b'{"campo":NaN}',
        b'{"campo":[1e400]}',
        b'{"campo":' + b"[" * 65 + b"0" + b"]" * 65 + b"}",
        gzip.compress(b"[]"),
    ],
)
def test_rejects_invalid_documents(source):
    with pytest.raises(CloudSaveError):
        reconstruct_cloud_save(source)


def test_rejects_invalid_gzip_frames():
    compressed = gzip.compress(FIXTURE.read_bytes(), mtime=0)
    corrupted = compressed[:-8] + bytes([compressed[-8] ^ 1]) + compressed[-7:]
    for source in (compressed[:-1], corrupted, compressed + b"\x00", compressed * 2):
        with pytest.raises(CloudSaveError, match="gzip"):
            reconstruct_cloud_save(source)


def test_caps_source_and_inflated_sizes(monkeypatch):
    fixture = FIXTURE.read_bytes()
    compressed = gzip.compress(fixture, mtime=0)
    monkeypatch.setattr(cloud_save, "MAX_INPUT_BYTES", len(compressed))
    with pytest.raises(CloudSaveError, match="entrada"):
        reconstruct_cloud_save(compressed + b" ")

    monkeypatch.setattr(cloud_save, "MAX_INPUT_BYTES", len(fixture))
    monkeypatch.setattr(cloud_save, "MAX_JSON_BYTES", len(fixture))
    assert reconstruct_cloud_save(fixture).source_size == len(fixture)
    assert reconstruct_cloud_save(compressed).source_size == len(compressed)
    monkeypatch.setattr(cloud_save, "MAX_JSON_BYTES", len(fixture) - 1)
    for source in (fixture, compressed):
        with pytest.raises(CloudSaveError, match="JSON supera"):
            reconstruct_cloud_save(source)

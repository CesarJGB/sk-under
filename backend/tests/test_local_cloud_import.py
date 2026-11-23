import gzip
import json
import os
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from app.cloud_envelope import inspect_rpc_frame, parse_blobsave_data
from app.cloud_import import (
    CopyIntegrityError, CopyMetadata, CopySourceError, LocalFileSource, MissingSection, import_copy,
)
from app.cloud_save import MAX_INPUT_BYTES, AggregateFormatError, CopyLimitError, UnsupportedEncoding

FIXTURES = Path(__file__).with_name("fixtures")
FILE = FIXTURES / "cloud-save-sintetico.json"
DOCUMENT = FILE.read_bytes()
VECTORS = json.loads((FIXTURES / "rpc-frames-sinteticos.json").read_bytes())


@pytest.mark.parametrize("vector", VECTORS)
def test_rpc_boundary(vector):
    original = None if vector["wire"] is None else bytes.fromhex(vector["wire"])
    frame = inspect_rpc_frame(original)
    assert frame.kind == vector["kind"]
    assert frame.original is original
    assert (None if frame.body is None else frame.body.hex()) == vector["body"]


def test_rpc_size_limit():
    with pytest.raises(CopyLimitError):
        inspect_rpc_frame(b"\0" * (MAX_INPUT_BYTES + 1))


def test_managed_data_text():
    reconstructed = parse_blobsave_data(DOCUMENT.decode())
    assert reconstructed.data.optional_sections["itemData"]["materials"] == {}
    assert reconstructed.source_sha256 == sha256(DOCUMENT).hexdigest()


@pytest.mark.parametrize("text", [None, "\ud800", '{"Data": "otro DTO"}'])
def test_invalid_managed_data(text):
    with pytest.raises(AggregateFormatError):
        parse_blobsave_data(text)


@pytest.mark.parametrize("compressed", [True, False])
def test_file_to_sections_keeps_original(tmp_path, compressed):
    payload = gzip.compress(DOCUMENT, mtime=0) if compressed else DOCUMENT
    path = tmp_path / "sin-extension"
    path.write_bytes(payload)
    copy = import_copy(LocalFileSource(path))
    assert copy.original == path.read_bytes() == payload
    assert copy.section("itemData") == json.loads(DOCUMENT)["itemData"]
    assert copy.section("gameData") == {}
    assert copy.section("taskData") is None
    assert copy.aggregate.data.extra_fields == {"campoSintetico": {"entero": 9007199254740993}}
    with pytest.raises(MissingSection):
        copy.section("battlePassSaveData")


@pytest.mark.parametrize("size,digest", [
    (len(DOCUMENT) - 1, sha256(DOCUMENT).hexdigest()),
    (len(DOCUMENT) + 1, sha256(DOCUMENT).hexdigest()),
    (len(DOCUMENT), "0" * 64),
])
def test_expected_revision(size, digest):
    with pytest.raises(CopyIntegrityError):
        import_copy(LocalFileSource(FILE, CopyMetadata(size, digest)))


@pytest.mark.parametrize("payload,error", [
    (DOCUMENT[:-6], AggregateFormatError),
    (DOCUMENT.replace(b'"gameData":', b'"gameData": {}, "gameData":'), AggregateFormatError),
    (gzip.compress(DOCUMENT, mtime=0)[:-4], AggregateFormatError),
    (bytes.fromhex("1f8b"), AggregateFormatError),
    (bytes.fromhex("00000080") + DOCUMENT, UnsupportedEncoding),
    (b"x" * 12, UnsupportedEncoding),
    (b"", CopyLimitError),
])
def test_file_errors_preserve_original(tmp_path, payload, error):
    path = tmp_path / "muestra"
    path.write_bytes(payload)
    with pytest.raises(error):
        import_copy(LocalFileSource(path))
    assert path.read_bytes() == payload


def test_nonregular_and_missing(tmp_path):
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    for path in (tmp_path, tmp_path / "missing", fifo):
        with pytest.raises(CopySourceError):
            import_copy(LocalFileSource(path))


def test_oversize_local_file(tmp_path):
    path = tmp_path / "sparse"
    with path.open("wb") as stream:
        stream.truncate(MAX_INPUT_BYTES + 1)
    with pytest.raises(CopyLimitError):
        import_copy(LocalFileSource(path))


def test_cli_from_file(tmp_path):
    path = tmp_path / "agregado"
    path.write_bytes(DOCUMENT)
    cmd = [sys.executable, "-m", "app.cloud_import", str(path)]
    cwd = Path(__file__).resolve().parents[1]
    summary = subprocess.run(cmd, cwd=cwd, capture_output=True, check=True)
    assert json.loads(summary.stdout)["sections"]["itemData"] == "present"
    assert b"sintetico-cuenta" not in summary.stdout
    args = ["--size", str(len(DOCUMENT)), "--sha256", sha256(DOCUMENT).hexdigest()]
    section = subprocess.run(cmd + args + ["--section", "itemData"], cwd=cwd, capture_output=True, check=True)
    assert json.loads(section.stdout) == json.loads(DOCUMENT)["itemData"]
    args[-1] = "0" * 64
    failure = subprocess.run(cmd + args, cwd=cwd, capture_output=True)
    assert failure.returncode == 1 and not failure.stdout
    assert json.loads(failure.stderr)["error"] == "integrity_mismatch"
    assert path.read_bytes() == DOCUMENT

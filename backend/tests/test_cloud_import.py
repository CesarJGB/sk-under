import gzip
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pytest

from app.cloud_import import CopyMetadata, summarize_copy
from app.cloud_save import MAX_INPUT_BYTES, CloudSaveError

DOCUMENT = (Path(__file__).parent / "fixtures" / "cloud-save-sintetico.json").read_bytes()


@dataclass
class SyntheticSource:
    description: CopyMetadata
    payload: bytes

    def metadata(self):
        return self.description

    def read(self, limit):
        assert limit == self.description.size
        return self.payload


@pytest.mark.parametrize("encoding", ["json", "gzip"])
def test_independent_summary(encoding):
    payload = gzip.compress(DOCUMENT) if encoding == "gzip" else DOCUMENT
    metadata = CopyMetadata(len(payload), sha256(payload).hexdigest())
    summary = summarize_copy(SyntheticSource(metadata, payload))
    assert summary["encoding"] == encoding
    assert summary["experimental"]
    assert summary["sections"]["itemData"] == "present"


@pytest.mark.parametrize("changed", [DOCUMENT[:-1], DOCUMENT.replace(b"cuenta", b"CUENTA")])
def test_changed_revision(changed):
    metadata = CopyMetadata(len(DOCUMENT), sha256(DOCUMENT).hexdigest())
    with pytest.raises(CloudSaveError, match="metadatos"):
        summarize_copy(SyntheticSource(metadata, changed))


def test_size_checked_before_read():
    class Oversize:
        def metadata(self):
            return CopyMetadata(MAX_INPUT_BYTES + 1, "")

        def read(self, limit):
            pytest.fail("La lectura debe rechazarse antes de pedir bytes.")

    with pytest.raises(CloudSaveError, match="límites"):
        summarize_copy(Oversize())


@pytest.mark.parametrize("prefix", [bytes.fromhex("00000080"), bytes.fromhex("ffffffff")])
def test_rpc_framing_is_outside_aggregate_contract(prefix):
    payload = prefix + DOCUMENT
    metadata = CopyMetadata(len(payload), sha256(payload).hexdigest())
    with pytest.raises(CloudSaveError, match="JSON"):
        summarize_copy(SyntheticSource(metadata, payload))


def test_blobsave_managed_text_boundary():
    # La clave representa la propiedad administrada en un DTO sintético.
    synthetic_dto = {"Data": DOCUMENT.decode("utf-8")}
    outer = json.dumps(synthetic_dto).encode()
    metadata = CopyMetadata(len(outer), sha256(outer).hexdigest())
    with pytest.raises(CloudSaveError, match="serialzedVersion"):
        summarize_copy(SyntheticSource(metadata, outer))

    aggregate = synthetic_dto["Data"].encode("utf-8")
    metadata = CopyMetadata(len(aggregate), sha256(aggregate).hexdigest())
    assert summarize_copy(SyntheticSource(metadata, aggregate))["sections"]["taskData"] == "null"

import gzip
import json
import os
import socket
from hashlib import sha256
from pathlib import Path

import pytest

from app.cloud.decoder import (
    RpcBodyNotGzip,
    RpcBodyUnknown,
    RpcNullMarker,
    decode_copy,
    decode_rpc_gzip,
    detect_format,
)
from app.cloud.importer import CloudImporter, import_from_transport
from app.cloud.preview import preview_issues
from app.cloud.transport import (
    DisabledRemoteTransport,
    RemoteTransportDisabled,
    RevisionMetadata,
    SimulatedProviderTransport,
    TransportUnavailable,
)
from app.cloud.validator import CopyIntegrityError, validate_payload
from app.cloud_import import MissingSection
from app.cloud_save import (
    AggregateFormatError,
    CopyLimitError,
    MAX_INPUT_BYTES,
    MAX_JSON_BYTES,
    UnsupportedEncoding,
)

FIXTURES = Path(__file__).with_name("fixtures")
DOCUMENT = FIXTURES / "cloud-save-sintetico.json"
DOCUMENT_880 = FIXTURES / "cloud-save-880-sintetico.json"
SIZE_880 = 875
SHA256_880 = "77bd5fb754b9ebc990f8033c314a338d67760045f51dc46d398a8852148c565c"


def simulated(path: Path, **options) -> SimulatedProviderTransport:
    return SimulatedProviderTransport(path, **options)


def test_disabled_remote_transport_is_explicit() -> None:
    with pytest.raises(RemoteTransportDisabled) as caught:
        DisabledRemoteTransport().fetch_latest(MAX_INPUT_BYTES)
    assert caught.value.code == "transport_disabled"


def test_simulated_provider_declares_the_exact_revision() -> None:
    envelope = simulated(DOCUMENT, revision="rev-sintetica").fetch_latest(MAX_INPUT_BYTES)
    assert envelope.metadata.revision == "rev-sintetica"
    assert envelope.metadata.size == DOCUMENT.stat().st_size
    assert envelope.metadata.sha256 == sha256(DOCUMENT.read_bytes()).hexdigest()
    assert envelope.payload == DOCUMENT.read_bytes()


@pytest.mark.parametrize("compressed", [False, True])
def test_importer_accepts_a_local_revision(tmp_path: Path, compressed: bool) -> None:
    raw = DOCUMENT.read_bytes()
    payload = gzip.compress(raw, mtime=0) if compressed else raw
    path = tmp_path / "copia"
    path.write_bytes(payload)

    imported = import_from_transport(simulated(path))
    assert imported.format == ("gzip" if compressed else "json")
    assert imported.metadata.size == len(payload)
    assert imported.copy.original == payload
    assert imported.section("itemData") == json.loads(raw)["itemData"]
    assert imported.section("taskData") is None
    assert imported.summary()["sections"]["battlePassSaveData"] == "missing"
    assert "sintetico-cuenta" not in json.dumps(imported.summary())
    with pytest.raises(MissingSection):
        imported.section("battlePassSaveData")


@pytest.mark.parametrize(
    ("size", "digest"),
    [
        (DOCUMENT.stat().st_size - 1, sha256(DOCUMENT.read_bytes()).hexdigest()),
        (DOCUMENT.stat().st_size + 1, sha256(DOCUMENT.read_bytes()).hexdigest()),
        (DOCUMENT.stat().st_size, "0" * 64),
    ],
)
def test_importer_rejects_a_changed_declaration(size: int, digest: str) -> None:
    declared = RevisionMetadata("rev", size, digest)
    transport = simulated(DOCUMENT, declared=declared)
    with pytest.raises(CopyIntegrityError):
        CloudImporter(transport).fetch()


def test_importer_rejects_a_limit_lower_than_the_copy() -> None:
    transport = simulated(DOCUMENT)
    with pytest.raises(CopyLimitError):
        transport.fetch_latest(10)
    with pytest.raises(CopyLimitError):
        CloudImporter(transport, limit=10).fetch()


def test_simulated_provider_rejects_non_regular_paths(tmp_path: Path) -> None:
    fifo = tmp_path / "tuberia"
    os.mkfifo(fifo)
    for path in (tmp_path, tmp_path / "ausente", fifo):
        with pytest.raises(TransportUnavailable):
            simulated(path).fetch_latest(MAX_INPUT_BYTES)


def test_empty_copy_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "vacia"
    path.write_bytes(b"")
    with pytest.raises(CopyLimitError):
        import_from_transport(simulated(path))


def test_rpc_markers_are_classified_and_not_guessed() -> None:
    compressed = b"\x00\x00\x00\x80" + b"cuerpo"
    with pytest.raises(RpcBodyUnknown) as caught:
        decode_copy(compressed)
    assert caught.value.code == "rpc_codec_unknown"
    assert bytes(caught.value.frame.body) == b"cuerpo"

    marked = b"\xff\xff\xff\xff" + b"datos"
    with pytest.raises(RpcNullMarker) as caught:
        decode_copy(marked)
    assert caught.value.code == "rpc_null_marker"
    assert caught.value.frame.kind == "null_marker"


def test_rpc_gzip_candidate_is_opt_in_and_preserves_the_frame() -> None:
    body = gzip.compress(DOCUMENT.read_bytes(), mtime=0)
    framed = b"\x00\x00\x00\x80" + body

    with pytest.raises(RpcBodyUnknown):
        decode_copy(framed)

    decoded = decode_copy(framed, rpc_body="gzip_candidate")
    assert decoded.format == "gzip"
    assert decoded.original == framed
    assert decoded.aggregate.data.serialzed_version == 0
    assert decoded.aggregate.data.game_data == {}

    direct = decode_rpc_gzip(framed)
    assert direct.aggregate.source_sha256 == sha256(body).hexdigest()

    validated = validate_payload(framed, rpc_body="gzip_candidate")
    assert validated.format == "gzip"
    assert validated.original == framed


def test_rpc_gzip_candidate_does_not_guess_other_codecs() -> None:
    with pytest.raises(RpcBodyNotGzip) as caught:
        decode_rpc_gzip(b"\x00\x00\x00\x80" + b"cuerpo")
    assert caught.value.code == "rpc_body_not_gzip"

    with pytest.raises(RpcBodyUnknown):
        decode_rpc_gzip(b"\x00\x00\x00\x80")


def test_rpc_gzip_candidate_rejects_a_truncated_or_trailing_member() -> None:
    body = gzip.compress(DOCUMENT.read_bytes(), mtime=0)
    with pytest.raises(AggregateFormatError):
        decode_rpc_gzip(b"\x00\x00\x00\x80" + body[:-4])
    with pytest.raises(AggregateFormatError):
        decode_rpc_gzip(b"\x00\x00\x00\x80" + body + b"x")


def test_rpc_gzip_candidate_stops_a_decompression_bomb() -> None:
    bomb = gzip.compress(b"{" + b" " * (MAX_JSON_BYTES + 1), mtime=0)
    with pytest.raises(CopyLimitError):
        decode_rpc_gzip(b"\x00\x00\x00\x80" + bomb)


def test_unknown_and_truncated_inputs_are_typed() -> None:
    with pytest.raises(UnsupportedEncoding):
        detect_format(b"")
    with pytest.raises(UnsupportedEncoding):
        decode_copy(b"x" * 16)
    with pytest.raises(AggregateFormatError):
        validate_payload(DOCUMENT.read_bytes()[:-8])


def test_simulated_import_does_not_open_sockets(monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("El proveedor simulado no debe abrir sockets.")

    monkeypatch.setattr(socket, "socket", forbidden)
    imported = import_from_transport(simulated(DOCUMENT))
    assert imported.format == "json"


def test_synthetic_880_fixture_is_stable_and_forward_compatible() -> None:
    payload = DOCUMENT_880.read_bytes()
    assert len(payload) == SIZE_880
    assert sha256(payload).hexdigest() == SHA256_880

    imported = import_from_transport(simulated(DOCUMENT_880))
    assert imported.format == "json"
    assert imported.copy.aggregate.data.serialzed_version == 1
    assert imported.copy.aggregate.data.game_data["gameVersion"] == 80800
    assert imported.copy.aggregate.data.extra_fields["campoSintetico880"] == {
        "entero": 9007199254740993
    }
    assert imported.copy.aggregate.data.extra_fields["seccionNuevaSintetica"] == {
        "presente": True
    }
    assert imported.copy.aggregate.data.optional_sections["settingData"] is None
    assert "mallReloadData" not in imported.copy.aggregate.data.optional_sections


def test_preview_issues_distinguish_null_from_missing() -> None:
    imported = import_from_transport(simulated(DOCUMENT_880))
    grouped: dict[str, set[str]] = {}
    for issue in preview_issues(imported.copy.aggregate):
        grouped.setdefault(issue.code, set()).add(issue.section)
    assert grouped["null_section"] == {"settingData", "maps"}
    assert grouped["missing_section"] == {"mallReloadData"}


def test_gzip_diagnostics_report_header_crc_and_size() -> None:
    from app.cloud.decoder import diagnose_gzip, diagnose_payload

    raw = DOCUMENT.read_bytes()
    body = gzip.compress(raw, mtime=0)
    report = diagnose_gzip(body)
    assert report.header is True
    assert report.crc_ok is True
    assert report.decompressed_bytes == len(raw)
    assert report.trailing_bytes == 0
    assert report.error is None

    framed = b"\x00\x00\x00\x80" + body
    payload = diagnose_payload(framed)
    assert payload["rpc"] == "compressed"
    assert payload["format"] == "gzip"
    assert payload["decoded"] is True
    assert payload["error"] is None


def test_gzip_diagnostics_reject_truncated_trailing_and_oversized_members() -> None:
    from app.cloud.decoder import diagnose_gzip

    body = gzip.compress(DOCUMENT.read_bytes(), mtime=0)
    assert diagnose_gzip(body[:-4]).error == "truncated"
    assert diagnose_gzip(body + b"x").error == "trailing_bytes"
    assert diagnose_gzip(b"not-gzip").error == "missing_header"
    bomb = gzip.compress(b"{" + b" " * (MAX_JSON_BYTES + 1), mtime=0)
    assert diagnose_gzip(bomb).error == "size_limit"


def test_diagnostics_do_not_hide_an_unknown_rpc_body() -> None:
    from app.cloud.decoder import diagnose_payload

    payload = diagnose_payload(b"\x00\x00\x00\x80cuerpo")
    assert payload["rpc"] == "compressed"
    assert payload["format"] == "unknown"
    assert payload["decoded"] is False
    assert payload["error"] == "rpc_body_not_gzip"

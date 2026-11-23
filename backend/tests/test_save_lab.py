import gzip
from pathlib import Path

import pytest

from app.cloud.lab import (
    LabPathError,
    LabTypeError,
    LabVerificationError,
    SaveLab,
    binary_diff,
    parse_path,
)
from app.cloud_save import AggregateFormatError, CopyLimitError

FIXTURE = Path(__file__).with_name("fixtures") / "cloud-save-880-sintetico.json"


def test_edit_changes_only_the_requested_path_and_preserves_unknown_fields() -> None:
    original = FIXTURE.read_bytes()
    lab = SaveLab.open(original)
    lab.set("gameData.gems", 7)
    report = lab.report()

    assert report.roundtrip is True
    assert report.unknown_fields_preserved is True
    assert report.changes[0].path == "gameData.gems"
    assert report.changes[0].before == 0
    assert report.changes[0].after == 7
    assert report.output_data != original

    import json

    edited = json.loads(report.output_data)
    baseline = json.loads(original)
    assert edited["gameData"]["gems"] == 7
    assert edited["gameData"]["heroes"] == baseline["gameData"]["heroes"]
    assert edited["campoSintetico880"] == baseline["campoSintetico880"]
    assert edited["seccionNuevaSintetica"] == baseline["seccionNuevaSintetica"]
    assert edited["campoSintetico880"]["entero"] == 9007199254740993


def test_type_mismatch_and_boolean_are_rejected() -> None:
    lab = SaveLab.open(FIXTURE.read_bytes())
    with pytest.raises(LabTypeError):
        lab.set("gameData.gems", "7")
    with pytest.raises(LabTypeError):
        lab.set("gameData.gems", True)
    with pytest.raises(LabTypeError):
        lab.set("serialzedVersion", 1.0)


def test_unknown_paths_and_sections_are_rejected() -> None:
    lab = SaveLab.open(FIXTURE.read_bytes())
    with pytest.raises(LabPathError):
        lab.set("gameData.ausente", 1)
    with pytest.raises(LabPathError):
        lab.set("campoSintetico880.entero", 1)
    with pytest.raises(LabPathError):
        lab.set("gameData.heroes[9]", 1)


def test_gzip_input_can_be_kept_as_gzip() -> None:
    payload = gzip.compress(FIXTURE.read_bytes(), mtime=0)
    lab = SaveLab.open(payload)
    lab.set("gameData.gems", 3)
    report = lab.report(encoding="same")
    assert report.encoding == "gzip"
    assert report.output_data.startswith(b"\x1f\x8b")

    reopened = SaveLab.open(report.output_data)
    assert reopened.document["gameData"]["gems"] == 3
    assert reopened.document["campoSintetico880"]["entero"] == 9007199254740993


def test_no_effective_change_returns_the_original_bytes() -> None:
    payload = gzip.compress(FIXTURE.read_bytes(), mtime=0)
    lab = SaveLab.open(payload)
    change = lab.set("gameData.gems", 0)
    report = lab.report()
    assert report.output_data == payload
    assert change.before == change.after


def test_malformed_input_is_typed() -> None:
    with pytest.raises(CopyLimitError):
        SaveLab.open(b"")
    with pytest.raises(AggregateFormatError):
        SaveLab.open(b'{"serialzedVersion": 1}')
    with pytest.raises(AggregateFormatError):
        SaveLab.open(b"{not json}")


def test_write_never_overwrites_without_explicit_permission(tmp_path: Path) -> None:
    original = FIXTURE.read_bytes()
    lab = SaveLab.open(original)
    lab.set("gameData.gems", 1)
    target = tmp_path / "copia.json"
    target.write_bytes(b"existente")
    with pytest.raises(FileExistsError):
        lab.write(target)
    assert target.read_bytes() == b"existente"

    report = lab.write(target, overwrite=True)
    assert target.read_bytes() == report.output_data
    assert FIXTURE.read_bytes() == original


def test_binary_diff_reports_the_first_difference() -> None:
    diff = binary_diff(b"abcdef", b"abXdef")
    assert diff.first_difference == 2
    assert diff.common_prefix == 2
    assert diff.common_suffix == 3
    assert diff.changed_original_bytes == 1
    assert diff.changed_modified_bytes == 1
    assert binary_diff(b"abc", b"abc").first_difference is None


def test_parse_path_supports_objects_and_arrays() -> None:
    assert parse_path("gameData.heroes[0].name") == ("gameData", "heroes", 0, "name")
    with pytest.raises(LabPathError):
        parse_path("gameData..gems")

import os
from hashlib import sha256
from pathlib import Path

import pytest

from app.local_save import (
    LocalFormatError,
    LocalSaveLab,
    decode_local_section,
    inspect_local_directory,
)
from app.settings import Settings


@pytest.fixture(scope="module")
def private_880():
    directory = os.environ.get("SK_PHASE56_880_DIR")
    config = os.environ.get("SK_PHASE4_CIPHER_ENV_FILE")
    if not directory or not config:
        pytest.skip("Configura SK_PHASE56_880_DIR y SK_PHASE4_CIPHER_ENV_FILE para probar la muestra 8.8.0.")
    path = Path(directory)
    if not path.is_dir():
        pytest.fail("El directorio privado 8.8.0 configurado no existe.")
    settings = Settings(_env_file=config)
    if settings.save_cipher is None:
        pytest.fail("Falta la configuración del códec local.")
    return path, settings.save_cipher


def test_private_880_inventory_is_valid_and_opaque_game_data_is_not_guessed(private_880):
    directory, (general, statistics, iv) = private_880
    summary = inspect_local_directory(directory, general_key=general, statistics_key=statistics, iv=iv)
    by_name = {item.name: item for item in summary.files}
    decoded = [item for item in summary.files if item.status == "decoded"]
    assert len(decoded) >= 18
    assert by_name["game.data"].status == "decoded"
    assert by_name["game.data"].kind == "game_data"
    sandbox = [item for item in summary.files if item.name.startswith("sandbox_maps")]
    assert sandbox and sandbox[0].status == "plain_json"
    assert all(item.kind is None or item.version is None or item.version >= 0 for item in decoded)


def test_private_880_noop_roundtrip_is_binary_exact(private_880):
    directory, (general, statistics, iv) = private_880
    checked = 0
    for path in sorted(directory.glob("*.data")):
        data = path.read_bytes()
        section = decode_local_section(data, general_key=general, statistics_key=statistics, iv=iv, name=path.name)
        if section is None:
            continue
        lab = LocalSaveLab.open(data, general_key=general, statistics_key=statistics, iv=iv, name=path.name)
        report = lab.report()
        assert report.output == data
        assert report.unknown_fields_preserved is True
        assert sha256(report.output).hexdigest() == sha256(data).hexdigest()
        checked += 1
    assert checked >= 18


def test_private_880_edit_preserves_unknown_fields_and_original(private_880):
    directory, (general, statistics, iv) = private_880
    candidates = sorted(directory.glob("item_data*.data"))
    if not candidates:
        pytest.skip("No hay una sección item_data en el directorio privado.")
    path = candidates[0]
    original = path.read_bytes()
    lab = LocalSaveLab.open(original, general_key=general, statistics_key=statistics, iv=iv, name=path.name)
    assert lab.section.kind == "item_data"
    before = lab.document.get("unknownSynthetic") if "unknownSynthetic" in lab.document else None
    if "cumulativeFishCount" not in lab.document:
        pytest.skip("La muestra no contiene cumulativeFishCount.")
    value = 1 << 60
    lab.set("cumulativeFishCount", value)
    report = lab.report()
    assert report.roundtrip is True
    assert report.unknown_fields_preserved is True
    reopened = LocalSaveLab.open(report.output, general_key=general, statistics_key=statistics, iv=iv, name=path.name)
    assert reopened.document["cumulativeFishCount"] == value
    assert path.read_bytes() == original
    if before is not None:
        assert reopened.document["unknownSynthetic"] == before


def test_private_880_game_data_xor_roundtrip_and_edit(private_880):
    directory, (general, statistics, iv) = private_880
    path = directory / "game.data"
    if not path.is_file():
        pytest.skip("No hay game.data en el directorio privado.")
    original = path.read_bytes()
    lab = LocalSaveLab.open(original, general_key=general, statistics_key=statistics, iv=iv, name=path.name)
    assert lab.section.kind == "game_data"
    assert lab.section.codec == "xor-json"
    report = lab.report()
    assert report.output == original
    before = lab.document["gems"]
    lab.set("gems", before + 1)
    edited = lab.report()
    assert edited.output != original
    assert edited.unknown_fields_preserved is True
    reopened = LocalSaveLab.open(edited.output, general_key=general, statistics_key=statistics, iv=iv, name=path.name)
    assert reopened.document["gems"] == before + 1
    assert path.read_bytes() == original


def test_private_880_unknown_version_is_not_accepted(private_880):
    directory, (general, statistics, iv) = private_880
    candidates = sorted(directory.glob("item_data*.data"))
    if not candidates:
        pytest.skip("No hay una sección item_data en el directorio privado.")
    data = candidates[0].read_bytes()
    with pytest.raises(LocalFormatError):
        LocalSaveLab.open(data[: len(data) // 2], general_key=general, statistics_key=statistics, iv=iv, name=candidates[0].name)

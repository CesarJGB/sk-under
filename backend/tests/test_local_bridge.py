import base64
import json
import os
from hashlib import sha256
from pathlib import Path

import pytest
from Crypto.Cipher import DES
from Crypto.Util.Padding import pad

from app.bridge import (
    LocalBridge,
    LocalFileProvider,
    LocalSectionDecoder,
    LocalSectionEditor,
    LocalSectionValidator,
    LocalFileExporter,
    LocalSectionValidator,
    build_bridge,
    read_regular_file,
)
from app.local_save import (
    MAX_LOCAL_FILE_BYTES,
    LocalEditError,
    LocalFormatError,
    LocalLimitError,
    LocalSaveLab,
    decode_local_section,
    inspect_local_directory,
    kind_from_filename,
)
from app.parsers.real_save import encode_game_data
from app.settings import Settings

GENERAL = b"general!"
STATISTICS = b"stats!!!"
IV = b"test-iv!"


def wrap(document: object, key: bytes = GENERAL) -> bytes:
    plain = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode()
    return base64.b64encode(DES.new(key, DES.MODE_CBC, IV).encrypt(pad(plain, DES.block_size)))


def item_880(**extra):
    return {
        "AppVersion": 80800,
        "materials": {},
        "seeds": {},
        "blueprints": {},
        "itemUnlock": [],
        "cumulativeFishCount": 0,
        "trainingJourney": {"revision": 0, "steps": []},
        "unknown_field": {"big": 9007199254740993},
        **extra,
    }


def bridge() -> LocalBridge:
    return LocalBridge(
        decoder=LocalSectionDecoder(GENERAL, STATISTICS, IV),
        validator=LocalSectionValidator(),
        editor=LocalSectionEditor(GENERAL, STATISTICS, IV),
        exporter=LocalFileExporter(),
    )


def test_880_section_is_decoded_and_noop_export_is_byte_identical(tmp_path: Path) -> None:
    original = wrap(item_880())
    path = tmp_path / "item_data_880_.data"
    path.write_bytes(original)

    result = bridge().inspect(LocalFileProvider(path))
    assert result.valid is True
    assert result.decoded.status == "decoded"
    assert result.decoded.section is not None
    assert result.decoded.section.kind == "item_data"
    assert result.decoded.section.version == 80800
    assert result.decoded.section.document["unknown_field"]["big"] == 9007199254740993
    assert "sections" in result.summary()
    assert "unknown_field" in result.summary()["sections"]

    target = tmp_path / "copia.data"
    exported = bridge().export(LocalFileProvider(path), target)
    assert exported.sha256 == sha256(original).hexdigest()
    assert target.read_bytes() == original
    assert path.read_bytes() == original
    assert oct(target.stat().st_mode & 0o777) == "0o600"


def test_860_and_880_versions_are_both_accepted_but_unknown_versions_are_not() -> None:
    old = wrap(item_880(AppVersion=80300))
    new = wrap(item_880())
    for payload in (old, new):
        section = decode_local_section(payload, general_key=GENERAL, statistics_key=STATISTICS, iv=IV, name="item_data_.data")
        assert section is not None and section.kind == "item_data"

    with pytest.raises(Exception) as caught:
        decode_local_section(wrap(item_880(AppVersion=80700)), general_key=GENERAL, statistics_key=STATISTICS, iv=IV, name="item_data_.data")
    assert getattr(caught.value, "code", "") == "unsupported_version"


def test_new_880_sections_are_recognized() -> None:
    cases = {
        "setting_1_.data": ({"shakeLevel": 1, "sandboxFlyable": False, "promotionIndex": -1, "bgmName": "bgm_room", "customKeyboardLayoutVersion": 1}, "setting"),
        "mall_reload_data_1_.data": ({"mallPurchaseCountHistoryIndexed": {}, "buyGemCount800": 0, "hasGetWeeklyBundle": False}, "mall_reload"),
        "escape_season_data_1_.data": ({"version": 1, "maxRaidSessionId": 0, "money": 0, "playerBag": {}, "safeSlots": {}, "totalIronMoneyEarned": 0}, "escape_season"),
        "bp_data_1_.data": ({"seasonData": {}, "bpShopOthersPurchaseCounts": {}, "bpShopOthersRefreshMonthKey": 0}, "bp_data"),
        "statistic_1_.data": ({"StatisticsData": {"A": {}}, "handbookWeaponCollectionTrackedLevels": {}, "achieve_record": {}, "passInfo": {}}, "statistic"),
    }
    for name, (document, kind) in cases.items():
        key = STATISTICS if kind == "statistic" else GENERAL
        section = decode_local_section(wrap(document, key), general_key=GENERAL, statistics_key=STATISTICS, iv=IV, name=name)
        assert section is not None, name
        assert section.kind == kind
        assert section.document == document


def test_edit_preserves_unknown_fields_and_reopens(tmp_path: Path) -> None:
    original = wrap(item_880(cumulativeFishCount=4))
    path = tmp_path / "item_data_880_.data"
    path.write_bytes(original)
    lab = LocalSaveLab.open(original, general_key=GENERAL, statistics_key=STATISTICS, iv=IV, name=path.name)
    lab.set("cumulativeFishCount", 1 << 60)
    lab.set("trainingJourney.revision", 5)
    report = lab.report()
    assert report.roundtrip is True
    assert report.unknown_fields_preserved is True
    assert report.output != original

    reopened = LocalSaveLab.open(report.output, general_key=GENERAL, statistics_key=STATISTICS, iv=IV, name=path.name)
    assert reopened.document["cumulativeFishCount"] == 1 << 60
    assert reopened.document["trainingJourney"]["revision"] == 5
    assert reopened.document["unknown_field"] == {"big": 9007199254740993}
    assert path.read_bytes() == original


@pytest.mark.parametrize("path,value", [
    ("AppVersion", 80801),
    ("version", 2),
    ("ChillyUid", "other"),
    ("cumulativeFishCount", "1"),
    ("cumulativeFishCount", True),
    ("trainingJourney", {"revision": 1}),
    ("missing.path", 1),
])
def test_invalid_or_protected_edits_are_rejected(path: str, value: object) -> None:
    document = item_880()
    document["ChillyUid"] = "private-account"
    lab = LocalSaveLab.open(wrap(document), general_key=GENERAL, statistics_key=STATISTICS, iv=IV, name="item_data_.data")
    with pytest.raises(LocalEditError):
        lab.set(path, value)


def test_empty_corrupt_and_unknown_inputs_are_typed() -> None:
    with pytest.raises(LocalLimitError):
        LocalSaveLab.open(b"", general_key=GENERAL, statistics_key=STATISTICS, iv=IV)
    with pytest.raises(LocalLimitError):
        decode_local_section(b"", general_key=GENERAL, statistics_key=STATISTICS, iv=IV)
    with pytest.raises(LocalLimitError):
        decode_local_section(b"x" * (MAX_LOCAL_FILE_BYTES + 1), general_key=GENERAL, statistics_key=STATISTICS, iv=IV)
    assert decode_local_section(b"x", general_key=GENERAL, statistics_key=STATISTICS, iv=IV) is None
    with pytest.raises(LocalFormatError):
        LocalSaveLab.open(b"not-base64", general_key=GENERAL, statistics_key=STATISTICS, iv=IV)
    with pytest.raises(LocalFormatError):
        LocalSaveLab.open(wrap({"unexpected": []}), general_key=GENERAL, statistics_key=STATISTICS, iv=IV)
    with pytest.raises(LocalFormatError):
        LocalSaveLab.open(wrap(item_880())[:-8], general_key=GENERAL, statistics_key=STATISTICS, iv=IV)


def test_directory_summary_keeps_values_out_and_marks_opaque_files(tmp_path: Path) -> None:
    (tmp_path / "item_data_1_.data").write_bytes(wrap(item_880()))
    (tmp_path / "game.data").write_bytes(encode_game_data({
        "skinLock": {}, "heroUnlock": {}, "heroLevel": {}, "gems": 0, "roomLevel": 0,
        "gameVersion": 0, "lastPlayTime": 0, "rebornCard": False,
    }))
    (tmp_path / "sandbox_maps_1_.data").write_bytes(b'{"maps":[]}')
    (tmp_path / "unknown.bin").write_bytes(b"ignored")
    summary = inspect_local_directory(tmp_path, general_key=GENERAL, statistics_key=STATISTICS, iv=IV).as_dict()
    by_name = {item["name"]: item for item in summary["files"]}
    assert by_name["item_data_1_.data"]["status"] == "decoded"
    assert by_name["game.data"]["status"] == "decoded"
    assert by_name["game.data"]["kind"] == "game_data"
    assert by_name["sandbox_maps_1_.data"]["status"] == "plain_json"
    assert "unknown.bin" not in by_name
    assert summary["recognized"] == 2
    assert "9007199254740993" not in json.dumps(summary)


def test_provider_rejects_directories_fifos_and_oversized_files(tmp_path: Path) -> None:
    with pytest.raises(LocalFormatError):
        read_regular_file(tmp_path)
    fifo = tmp_path / "tuberia"
    os.mkfifo(fifo)
    with pytest.raises(LocalFormatError):
        read_regular_file(fifo)
    large = tmp_path / "grande.data"
    large.write_bytes(b"x" * (8 * 1024 * 1024 + 1))
    with pytest.raises(LocalFormatError):
        read_regular_file(large)


def test_exporter_never_overwrites_without_permission(tmp_path: Path) -> None:
    source = tmp_path / "item_data_.data"
    source.write_bytes(wrap(item_880()))
    target = tmp_path / "copia.data"
    target.write_bytes(b"existente")
    with pytest.raises(FileExistsError):
        bridge().export(LocalFileProvider(source), target)
    assert target.read_bytes() == b"existente"


def test_build_bridge_requires_complete_cipher() -> None:
    with pytest.raises(Exception):
        build_bridge(Settings(_env_file=None))
    settings = Settings(_env_file=None, save_general_key_hex=GENERAL.hex(),
                        save_statistics_key_hex=STATISTICS.hex(), save_iv_hex=IV.hex())
    assert isinstance(build_bridge(settings), LocalBridge)


def test_kind_from_filename_is_bounded() -> None:
    assert kind_from_filename("item_data_236_.data") == "item_data"
    assert kind_from_filename("statistic.data") == "statistic"
    assert kind_from_filename("game.data") == "game"
    assert kind_from_filename("random.data") is None


def test_game_data_xor_roundtrip_and_edit() -> None:
    document = {
        "skinLock": {"Knight": []}, "heroUnlock": {"Knight": True},
        "heroLevel": {"Knight": 0}, "gems": 0, "lastGems": 0, "varGems": 0,
        "cumulativeGems": 0, "rebornCard": False, "roomLevel": 0,
        "gameVersion": 0, "lastPlayTime": 0, "totalGameTime": 0,
        "unknownSyntheticGame": {"entero": 9007199254740993},
    }
    original = encode_game_data(document)
    lab = LocalSaveLab.open(original, general_key=b"", statistics_key=b"", iv=b"", name="game.data")
    assert lab.section.kind == "game_data"
    assert lab.section.codec == "xor-json"
    assert lab.report().output == original
    lab.set("gems", 7)
    report = lab.report()
    assert report.output != original
    assert report.unknown_fields_preserved is True
    reopened = LocalSaveLab.open(report.output, general_key=b"", statistics_key=b"", iv=b"", name="game.data")
    assert reopened.document["gems"] == 7
    assert reopened.document["unknownSyntheticGame"] == {"entero": 9007199254740993}


def test_exporter_does_not_follow_a_symlink(tmp_path: Path) -> None:
    source = tmp_path / "item_data_.data"
    source.write_bytes(wrap(item_880()))
    outside = tmp_path / "outside"
    outside.write_bytes(b"no tocar")
    link = tmp_path / "link"
    link.symlink_to(outside)
    with pytest.raises(OSError):
        bridge().export(LocalFileProvider(source), link)
    assert outside.read_bytes() == b"no tocar"


def test_game_data_is_detected_after_rename() -> None:
    document = {
        "skinLock": {}, "heroUnlock": {}, "heroLevel": {}, "gems": 0, "roomLevel": 0,
        "gameVersion": 0, "lastPlayTime": 0, "rebornCard": False,
    }
    lab = LocalSaveLab.open(encode_game_data(document), general_key=b"", statistics_key=b"", iv=b"", name="renombrado.data")
    assert lab.section.kind == "game_data"
    assert lab.section.codec == "xor-json"

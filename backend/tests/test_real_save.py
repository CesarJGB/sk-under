import base64
import json
from dataclasses import replace
from hashlib import sha256

import pytest
from Crypto.Cipher import DES
from Crypto.Util.Padding import pad
from pydantic import ValidationError

from app.engine import Editor
from app.errors import EditorError
from app.formats.real_save import RealSaveAdapter
from app.parsers.real_save import encode_game_data
from app.settings import Settings
from conftest import make_client
from test_api import FILES, TEST_TOKEN, V1, assert_error, envelope

GENERAL = b"general!"
STATISTICS = b"stats!!!"
IV = b"test-iv!"
CONFIG = {
    "save_general_key_hex": GENERAL.hex(),
    "save_statistics_key_hex": STATISTICS.hex(),
    "save_iv_hex": IV.hex(),
}

SCHEMAS = {
    "bp_data": {"seasonData": [{"Key": 91, "Value": {}}], "bpShopOthersPurchaseCounts": [],
                "bpShopOthersRefreshMonthKey": 21},
    "item_data": {"AppVersion": 80300, "materials": {"example": 110}, "seeds": {}, "blueprints": {},
                  "itemUnlock": [], "cumulativeFishCount": 4},
    "misc_data": {"returningEventCurrentDay": 2, "isReturnPlayerInit": False,
                  "unlockedKillEffectIds": [3], "equippedKillEffectIdByScene": []},
    "monsrise_data": {"version": 1, "maxClearLevel": 7, "pveGameTimes": 9,
                      "monsterTeams": [], "CollectedMonsters": {}},
    "pvp_data": {"isPvpFirstMatch": False, "pvpLobbyOpenCount": 18,
                 "pvpTaskData": {}, "pvpSkinSelectionByHero": {}},
    "season_data": {"coin": 71, "gainedCoinToday": 6, "cumulativeCoinCount": 120,
                    "gainedCoinInSeason": {}, "chips": []},
    "statistic": {"StatisticsData": {"Test": {}}, "handbookWeaponCollectionTrackedLevels": {},
                  "achieve_record": [{"Key": 2, "Value": {"other": False}}], "passInfo": {}},
    "task": {"NewTaskData": [{"ID": 11, "Status": "sample", "CurrentProgress": 3, "TargetProgress": 6}],
             "tasks": [], "ActivityTaskData": {}, "changeCount": 2},
    "weapon_evolution_data": {
        "weapons": {"demo": {"Name": "example", "Level": 2, "CurrentSkinIndex": 0, "UnlockedSkins": []}},
        "blindBoxOpenCount0": 0, "favorWeapons": [],
    },
}


def wrap(plaintext: bytes, key: bytes = GENERAL) -> bytes:
    return base64.b64encode(DES.new(key, DES.MODE_CBC, IV).encrypt(pad(plaintext, 8)))


def encoded_payload(payload: object, key: bytes = GENERAL) -> bytes:
    return wrap(json.dumps(payload).encode(), key)


@pytest.fixture
def real_client():
    return make_client(env="production", access_token=TEST_TOKEN, **CONFIG)


AUTH = {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.mark.parametrize("kind", SCHEMAS)
def test_real_noop_roundtrip(real_client, kind):
    # Conserva espacios, Unicode, números y datos desconocidos tal como se recibieron.
    doc = SCHEMAS[kind] | {"unknownSynthetic": ["á", {"n": 1.5e20}, None]}
    key = STATISTICS if kind == "statistic" else GENERAL
    original = wrap((json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode(), key)
    response = real_client.post(FILES + "/inspect", headers=AUTH, json=envelope(original))
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    inspection = response.json()
    assert inspection["format"]["compatibility"] == "read_only"
    assert inspection["sha256"] == sha256(original).hexdigest()
    assert all(not field["editable"] for field in inspection["fields"])
    assert inspection["fields"][0]["id"] == "save_type"
    assert "unknownSynthetic" not in response.text

    request = envelope(original, changes={})
    validation = real_client.post(FILES + "/validate", headers=AUTH, json=request)
    assert validation.status_code == 200
    assert validation.json()["output_sha256"] == inspection["sha256"]
    assert not validation.json()["changes"]
    result = real_client.post(FILES + "/export", headers=AUTH, json=request)
    assert result.status_code == 200
    assert result.headers["Cache-Control"] == "no-store"
    assert result.headers["Content-Disposition"] == f'attachment; filename="copia-{kind}.data"'
    assert result.content == original
    reopened = real_client.post(FILES + "/inspect", headers=AUTH, json=envelope(result.content))
    assert reopened.json() == inspection


def test_projected_values(real_client):
    original = encoded_payload(SCHEMAS["item_data"] | {"cumulativeFishCount": 1 << 53})
    result = real_client.post(FILES + "/inspect", headers=AUTH, json=envelope(original))
    assert result.status_code == 200
    fields = {row["id"]: row["value"] for row in result.json()["fields"]}
    assert fields == {"save_type": "Inventario", "AppVersion": 80300, "materials": 1, "seeds": 0,
                      "blueprints": 0, "itemUnlock": 0, "cumulativeFishCount": str(1 << 53)}


@pytest.mark.parametrize(("kind", "optional"), [
    ("bp_data", "bpShopOthersPurchaseCounts"),
    ("misc_data", "equippedKillEffectIdByScene"),
    ("pvp_data", "pvpSkinSelectionByHero"),
    ("statistic", "passInfo"),
    ("task", "ActivityTaskData"),
    ("weapon_evolution_data", "favorWeapons"),
])
def test_optional_field_may_be_absent_but_must_be_typed_if_present(real_client, kind, optional):
    payload = SCHEMAS[kind].copy()
    del payload[optional]
    key = STATISTICS if kind == "statistic" else GENERAL
    original = encoded_payload(payload, key)
    result = real_client.post(FILES + "/inspect", headers=AUTH, json=envelope(original))
    assert result.status_code == 200
    assert optional not in {field["id"] for field in result.json()["fields"]}
    exported = real_client.post(FILES + "/export", headers=AUTH, json=envelope(original, changes={}))
    assert exported.status_code == 200
    assert exported.headers["Content-Disposition"] == f'attachment; filename="copia-{kind}.data"'
    assert exported.content == original

    malformed = encoded_payload(payload | {optional: None}, key)
    assert_error(real_client.post(FILES + "/inspect", headers=AUTH, json=envelope(malformed)),
                 415, "unsupported_format")


@pytest.mark.parametrize("broken", [
    b"not-a-format", b"YWJjZA==", b"YWFhYWFhYWE=\n", b"YWFhYWFhYWF=",
    wrap(b"{"), wrap(b'{"private_example":1,"private_example":2}'), wrap(b"\xff"),
    wrap(b'{"private_example":NaN}'), wrap(b'{"private_example":' + b"[" * 1100),
    encoded_payload(SCHEMAS["item_data"] | {"materials": {"example": True}}),
    encoded_payload(SCHEMAS["task"] | {"NewTaskData": [{"Status": 0}]}),
    encoded_payload(SCHEMAS["pvp_data"] | SCHEMAS["misc_data"]),
    encoded_payload(SCHEMAS["statistic"], GENERAL),
    encoded_payload(SCHEMAS["item_data"], STATISTICS),
    wrap(json.dumps(SCHEMAS["season_data"])[:-1].encode() + b',"unknown":{"x":1,"x":2}}'),
    encoded_payload({"weapons": {}, "favorWeapons": []}),
    encoded_payload([SCHEMAS["pvp_data"]]),
])
def test_invalid_envelopes_and_schemas(real_client, broken):
    response = real_client.post(FILES + "/inspect", headers=AUTH, json=envelope(broken))
    assert_error(response, 415, "unsupported_format")
    assert "private_example" not in response.text


def test_ciphertext_corruption(real_client):
    original = bytearray(base64.b64decode(encoded_payload(SCHEMAS["season_data"])))
    original[-1] ^= 1
    corrupted = base64.b64encode(original)
    for operation in ("/inspect", "/validate", "/export"):
        changes = {} if operation == "/inspect" else {"changes": {}}
        assert_error(real_client.post(FILES + operation, headers=AUTH, json=envelope(corrupted, **changes)),
                     415, "unsupported_format")


@pytest.mark.parametrize(("kind", "version", "invalid"), [
    ("item_data", "AppVersion", 80600),
    ("item_data", "AppVersion", "80300"),
    ("monsrise_data", "version", 2),
    ("monsrise_data", "version", True),
])
def test_incompatible_version(real_client, kind, version, invalid):
    data = encoded_payload(SCHEMAS[kind] | {version: invalid})
    assert_error(real_client.post(FILES + "/inspect", headers=AUTH, json=envelope(data)),
                 415, "unsupported_version")


@pytest.mark.parametrize(("kind", "version"), [("item_data", "AppVersion"), ("monsrise_data", "version")])
def test_missing_version_marker_is_rejected(real_client, kind, version):
    payload = SCHEMAS[kind].copy()
    del payload[version]
    original = encoded_payload(payload)
    for operation in ("/inspect", "/validate", "/export"):
        changes = {} if operation == "/inspect" else {"changes": {}}
        assert_error(real_client.post(FILES + operation, headers=AUTH, json=envelope(original, **changes)),
                     415, "unsupported_version")


@pytest.mark.parametrize("changes", [{"coin": 4}, {"coin": 71}, {"unknown": "value"}])
def test_real_edits_rejected(real_client, changes):
    data = encoded_payload(SCHEMAS["season_data"])
    for operation in ("/validate", "/export"):
        response = real_client.post(FILES + operation, headers=AUTH, json=envelope(data, changes=changes))
        error = assert_error(response, 422, "invalid_changes")
        assert error["issues"][0]["code"] == "field_not_editable"


def test_real_export_rejects_a_structurally_valid_but_modified_copy():
    class FaultyAdapter(RealSaveAdapter):
        def serialize(self, document, original):
            output = super().serialize(document, original)
            modified = encoded_payload(SCHEMAS["season_data"] | {"unknownSynthetic": "changed"})
            return replace(output, data=modified)

    editor = Editor([FaultyAdapter(GENERAL, STATISTICS, IV)])
    with pytest.raises(EditorError) as caught:
        editor.prepare_export(encoded_payload(SCHEMAS["season_data"]), {}, 1024)
    assert caught.value.error.code == "export_verification_failed"


def test_real_adapter_opt_in_and_auth(client, real_client):
    formats = real_client.get(V1 + "/formats").json()["formats"]
    assert [entry["compatibility"] for entry in formats] == ["synthetic", "read_only", "read_only"]
    data = encoded_payload(SCHEMAS["season_data"])
    assert_error(client.post(FILES + "/inspect", json=envelope(data)), 415, "unsupported_format")
    for operation in ("/inspect", "/validate", "/export"):
        assert_error(real_client.post(FILES + operation, content=b"not parsed"), 401, "access_denied")


def test_cipher_configuration_is_complete_and_redacted():
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, **(CONFIG | {"save_iv_hex": "private-example"}))
    assert "private-example" not in str(caught.value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, save_general_key_hex=GENERAL.hex())


@pytest.mark.parametrize("invalid", [False, 0, 1234567890123456])
def test_cipher_rejects_non_text_configuration(invalid):
    with pytest.raises(ValidationError, match="16 dígitos hexadecimales"):
        Settings(_env_file=None, **(CONFIG | {"save_iv_hex": invalid}))


SCHEMAS_880 = {
    "item_data": {
        "AppVersion": 80800,
        "materials": {},
        "seeds": {},
        "blueprints": {},
        "itemUnlock": [],
        "cumulativeFishCount": 0,
        "trainingJourney": {"steps": []},
        "unknownSynthetic880": {"entero": 9007199254740993},
    },
    "setting": {
        "shakeLevel": 1,
        "sandboxFlyable": False,
        "promotionIndex": -1,
        "bgmName": "bgm_room",
        "customKeyboardLayoutVersion": 1,
        "ChillyUid": "synthetic-account",
    },
    "mall_reload": {
        "mallPurchaseCountHistoryIndexed": {},
        "buyGemCount800": 0,
        "buyGemCount5000": 0,
        "buyGemCount12000": 0,
        "hasGetWeeklyBundle": False,
    },
    "escape_season": {
        "version": 1,
        "maxRaidSessionId": 0,
        "money": 0,
        "playerBag": {},
        "safeSlots": {},
        "totalIronMoneyEarned": 0,
    },
    "bp_data": {
        "seasonData": {},
        "bpShopOthersPurchaseCounts": {},
        "bpShopOthersRefreshMonthKey": 0,
    },
    "statistic": {
        "StatisticsData": {"A": {}},
        "handbookWeaponCollectionTrackedLevels": {},
        "achieve_record": {},
        "passInfo": {},
    },
}


@pytest.mark.parametrize("kind", SCHEMAS_880)
def test_880_local_sections_are_read_only_and_roundtrip(real_client, kind):
    key = STATISTICS if kind == "statistic" else GENERAL
    original = encoded_payload(SCHEMAS_880[kind], key)
    inspection = real_client.post(FILES + "/inspect", headers=AUTH, json=envelope(original))
    assert inspection.status_code == 200
    body = inspection.json()
    assert body["format"]["id"] == "sk-local-des-cbc"
    assert body["format"]["compatibility"] == "read_only"
    assert all(not field["editable"] for field in body["fields"])
    assert body["sha256"] == sha256(original).hexdigest()

    request = envelope(original, changes={})
    validated = real_client.post(FILES + "/validate", headers=AUTH, json=request)
    assert validated.status_code == 200
    assert validated.json()["output_sha256"] == sha256(original).hexdigest()
    exported = real_client.post(FILES + "/export", headers=AUTH, json=request)
    assert exported.status_code == 200
    assert exported.content == original
    assert exported.headers["Content-Disposition"] == f'attachment; filename="copia-{kind}.data"'


def test_880_item_version_zero_is_the_prelogin_default(real_client):
    payload = encoded_payload(SCHEMAS_880["item_data"] | {"AppVersion": 0})
    result = real_client.post(FILES + "/inspect", headers=AUTH, json=envelope(payload))
    assert result.status_code == 200
    assert {row["id"]: row["value"] for row in result.json()["fields"]}["AppVersion"] == 0


def test_880_unknown_item_version_is_rejected(real_client):
    payload = encoded_payload(SCHEMAS_880["item_data"] | {"AppVersion": 80700})
    assert_error(real_client.post(FILES + "/inspect", headers=AUTH, json=envelope(payload)),
                 415, "unsupported_version")


def test_880_game_data_xor_is_read_only_and_binary_exact(real_client):
    document = {
        "skinLock": {"Knight": []}, "heroUnlock": {"Knight": True},
        "heroLevel": {"Knight": 0}, "gems": 0, "lastGems": 0, "varGems": 0,
        "cumulativeGems": 0, "rebornCard": False, "roomLevel": 0,
        "gameVersion": 0, "lastPlayTime": 0, "totalGameTime": 0,
        "unknownSyntheticGame": {"entero": 9007199254740993},
    }
    original = encode_game_data(document)
    inspection = real_client.post(FILES + "/inspect", headers=AUTH, json=envelope(original))
    assert inspection.status_code == 200
    body = inspection.json()
    assert body["format"]["id"] == "sk-local-game-xor"
    assert body["format"]["compatibility"] == "read_only"
    assert all(not field["editable"] for field in body["fields"])
    fields = {row["id"]: row["value"] for row in body["fields"]}
    assert fields["gems"] == 0 and fields["gameVersion"] == 0

    request = envelope(original, changes={})
    exported = real_client.post(FILES + "/export", headers=AUTH, json=request)
    assert exported.status_code == 200
    assert exported.content == original
    assert exported.headers["Content-Disposition"] == 'attachment; filename="copia-game.data"'

    changed = real_client.post(FILES + "/export", headers=AUTH, json=envelope(original, changes={"gems": 1}))
    assert_error(changed, 422, "invalid_changes")


def test_game_data_adapter_does_not_guess_arbitrary_data(real_client):
    assert_error(real_client.post(FILES + "/inspect", headers=AUTH, json=envelope(b"not-a-game")),
                 415, "unsupported_format")

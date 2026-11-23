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


def encoded_payload(payload: dict, key: bytes = GENERAL) -> bytes:
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


@pytest.mark.parametrize("broken", [
    b"not-a-format", b"YWJjZA==", b"YWFhYWFhYWE=\n", b"YWFhYWFhYWF=",
    wrap(b"{"), wrap(b'{"private_example":1,"private_example":2}'), wrap(b"\xff"),
    wrap(b'{"private_example":NaN}'), wrap(b'{"private_example":' + b"[" * 1100),
    encoded_payload(SCHEMAS["item_data"] | {"materials": {"example": True}}),
    encoded_payload(SCHEMAS["task"] | {"NewTaskData": [{"Status": 0}]}),
    encoded_payload(SCHEMAS["pvp_data"] | SCHEMAS["misc_data"]),
    encoded_payload(SCHEMAS["statistic"], GENERAL),
    encoded_payload(SCHEMAS["item_data"], STATISTICS),
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


@pytest.mark.parametrize("changes", [{"coin": 4}, {"coin": 71}, {"unknown": "value"}])
def test_real_edits_rejected(real_client, changes):
    data = encoded_payload(SCHEMAS["season_data"])
    for operation in ("/validate", "/export"):
        response = real_client.post(FILES + operation, headers=AUTH, json=envelope(data, changes=changes))
        error = assert_error(response, 422, "invalid_changes")
        assert error["issues"][0]["code"] == "field_not_editable"


def test_real_export_rejects_a_structurally_valid_but_modified_copy():
    class FaultyAdapter(RealSaveAdapter):
        def serialize(self, document):
            output = super().serialize(document)
            modified = encoded_payload(SCHEMAS["season_data"] | {"unknownSynthetic": "changed"})
            return replace(output, data=modified)

    editor = Editor([FaultyAdapter(GENERAL, STATISTICS, IV)])
    with pytest.raises(EditorError) as caught:
        editor.prepare_export(encoded_payload(SCHEMAS["season_data"]), {}, 1024)
    assert caught.value.error.code == "export_verification_failed"


def test_real_adapter_opt_in_and_auth(client, real_client):
    formats = real_client.get(V1 + "/formats").json()["formats"]
    assert [entry["compatibility"] for entry in formats] == ["synthetic", "read_only"]
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

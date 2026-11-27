import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.cloud.provider import CloudProviderUnauthenticated
from app.main import create_app
from app.native.client import GatewaySession, NativeAuthRejected, NativeDistributionRejected
from app.settings import Settings
from test_cloud_lab_api import FakeProvider, FakeUploader, canonical

API = "/api/v1/cloud/native"
ORIGIN = "http://127.0.0.1:5173"
FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"
PAYLOAD_A = FIXTURE.read_bytes()
PAYLOAD_B = canonical(json.loads(PAYLOAD_A) | {"cloudSaveId": "sintetico-cuenta-beta"})


def customization_payload() -> bytes:
    data = json.loads(PAYLOAD_A)
    data["weaponEvolutionData"] = {"weapons": {}}
    data["miscData"] = {"unlockedKillEffectIds": []}
    return canonical(data)


PHASE93_PAYLOAD = customization_payload()
HEADERS = {"Origin": ORIGIN}
COOKIE = "sk_native_dev"


class FakeAuth:
    def __init__(self):
        self.accounts = {
            "a@example.test": {
                "password": "pass-a", "uid": 1, "player_id": 11,
                "distro": "distro-a", "email": "a@example.test",
            },
            "b@example.test": {
                "password": "pass-b", "uid": 2, "player_id": 22,
                "distro": "distro-b", "email": "b@example.test",
            },
        }
        self.calls: list[tuple[str, str]] = []
        self.override: dict[str, GatewaySession] = {}

    def authenticate(self, email, password, *, distribution, distro_id, unique_id=None):
        self.calls.append((email, distro_id))
        account = self.accounts.get(email)
        if account is None or password != account["password"]:
            raise NativeAuthRejected(401)
        if distro_id != account["distro"]:
            raise NativeDistributionRejected("distro fixture")
        if email in self.override:
            return self.override[email]
        return GatewaySession(
            token=f"token-{account['uid']}-{len(self.calls)}",
            uid=account["uid"],
            email=account["email"],
            player_id=account["player_id"],
            expire=int(time.time()) + 3600,
            distro_id=distro_id,
        )


def make_native(
    tmp_path, *, write=False, allow_write=True, unique_a="unique-a", attempts=20,
    payload_a=PAYLOAD_A,
):
    settings = Settings(
        _env_file=None,
        env="development",
        allowed_origins=[ORIGIN],
        native_auth_enabled=True,
        native_write_enabled=write,
        native_store_key="ab" * 32,
        native_store_dir=tmp_path / "native",
        native_backup_dir=tmp_path / "native-backups",
        native_origin=ORIGIN,
        native_distro_id="distro-a",
        native_unique_id=unique_a,
        native_profile_allow_write=allow_write,
        native_auto_identity=False,
        native_login_attempts=attempts,
        native_login_window_seconds=300,
    )
    app = create_app(settings)
    service = app.state.native_service
    assert service is not None
    auth = FakeAuth()
    providers = {"unique-a": FakeProvider(payload_a), "unique-b": FakeProvider(PAYLOAD_B)}
    uploaders = {key: FakeUploader(provider) for key, provider in providers.items()}
    service.client = auth
    service.provider_factory = lambda token, unique, distro, distribution: providers[unique]
    service.uploader_factory = lambda token, unique, distro, distribution: uploaders[unique]
    client = TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000))
    return {
        "settings": settings, "app": app, "service": service, "store": service.store,
        "client": client, "auth": auth, "providers": providers, "uploaders": uploaders,
    }


def add_account_b(env):
    profile = env["store"].create_profile(
        label="Cuenta B", distribution_id="android-global",
        distro_id="distro-b", unique_id="unique-b", allow_write=True,
    )
    return profile


def login(client, email="a@example.test", password="pass-a", profile=None, headers=HEADERS):
    payload = {"distribution": "android-global", "email": email, "password": password}
    if profile is not None:
        payload["profile_id"] = profile
    return client.post(API + "/login", json=payload, headers=headers)


def session_of(client):
    return client.get(API + "/session", headers=HEADERS).json()


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    assert response.headers["Cache-Control"] == "no-store"
    error = response.json()["error"]
    assert error["code"] == code
    return error


def prepare(client, gems=1002):
    source = client.get(API + "/save", headers=HEADERS)
    assert source.status_code == 200, source.text
    response = client.post(
        API + "/prepare",
        headers=HEADERS,
        json={"new_gems": gems, "source_sha256": source.json()["sha256"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def confirmation(draft):
    return {
        "backup_id": draft["backup"]["id"],
        "expected_sha256": draft["candidate_sha256"],
        "confirmation": "SUBIR",
    }


def test_config_lists_all_distributions_with_android_and_ios_enabled(tmp_path):
    env = make_native(tmp_path)
    response = env["client"].get(API + "/config", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True and body["login_available"] is True
    assert body["native_auth_ready"] is True
    assert len(body["distributions"]) == 6
    enabled = [item for item in body["distributions"] if item["enabled"]]
    assert [item["id"] for item in enabled] == ["android-global", "ios-global"]
    ios = next(item for item in enabled if item["id"] == "ios-global")
    assert ios["platform"] == "ios" and ios["game_version"] == "8.8.0.14"
    assert ios["protocol_app_version"] == "8.8.0"
    assert ios["protocol_game_version"] == "8.8.0"
    assert "escritura remota" in ios["note"].lower()
    assert {item["id"] for item in body["distributions"]} == {
        "android-global", "android-vietnam", "ios-global",
        "ios-vietnam", "ios-china", "taptap",
    }
    assert body["profiles"][0]["label"] == "Instalación Android Global"
    assert body["profiles"][0]["installation_ready"] is True
    assert body["session"]["active"] is False
    text = response.text
    assert "a@example.test" not in text
    assert "distro-a" not in text and "unique-a" not in text
    assert "ab" * 32 not in text


def test_login_sets_an_isolated_cookie_and_never_echoes_secrets(tmp_path):
    env = make_native(tmp_path)
    response = login(env["client"])
    assert response.status_code == 200, response.text
    cookie = response.headers["set-cookie"]
    assert f"{COOKIE}=" in cookie
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    body = response.json()
    assert body["active"] is True and body["identity_verified"] is True
    assert body["installation_ready"] is True and body["write_ready"] is False
    assert body["save"]["gems"] == 1000
    assert body["save"]["report"]["characters"]["counts"]["characters"] == 42
    assert body["save"]["report"]["resources"]["groups"]
    assert body["account"]["email"] == "a@example.test"
    text = response.text
    for secret in ("distro-a", "unique-a", "token-", "cloudSaveId"):
        assert secret not in text
    active = session_of(env["client"])
    assert active["active"] is True and active["account"]["label"] == "Instalación Android Global"
    assert active["account"]["email"] == "a@example.test"
    raw = env["store"].database.read_bytes()
    for secret in (b"a@example.test", b"distro-a", b"unique-a", b"token-"):
        assert secret not in raw
    assert env["store"].database.stat().st_mode & 0o777 == 0o600


def test_login_save_includes_customization_catalogs_with_empty_inventory(tmp_path):
    env = make_native(tmp_path, payload_a=PHASE93_PAYLOAD)
    response = login(env["client"])
    assert response.status_code == 200, response.text
    save = response.json()["save"]
    assert save["weapon_progression"]["total_weapons"] == 995
    assert len(save["weapon_progression"]["items"]) == 995
    assert save["weapon_progression"]["discovered"] == []
    assert save["weapon_progression"]["forge_ready_count"] == 0
    assert save["weapon_progression"]["field"] == "statisticData.object2ObtainTime"
    assert save["weapon_skins"]["total_skins"] == 192
    assert len(save["weapon_skins"]["items"]) == 192
    assert save["weapon_skins"]["unlocked"] == []
    assert save["weapon_skins"]["weapons_with_data"] == 0
    assert save["weapon_skins"]["field"] == "weaponEvolutionData.weapons"
    assert save["kill_effects"]["total_effects"] == 9
    assert len(save["kill_effects"]["items"]) == 9
    assert save["kill_effects"]["unlocked"] == []
    assert save["kill_effects"]["field"] == "miscData.unlockedKillEffectIds"
    assert save["weapon_progression_write_policy"] == "experimental"
    assert save["weapon_skin_write_policy"] == "confirmed_by_owner"
    assert save["kill_effect_write_policy"] == "confirmed_by_owner"
    assert save["report"]["characters"]["counts"]["characters"] == 42


def test_completed_installation_returns_customization_catalogs(tmp_path):
    env = make_native(tmp_path, unique_a=None, payload_a=PHASE93_PAYLOAD)
    assert login(env["client"]).status_code == 200
    completed = env["client"].post(
        API + "/installation", headers=HEADERS, json={"unique_id": "unique-a"}
    )
    assert completed.status_code == 200, completed.text
    save = completed.json()["save"]
    assert len(save["weapon_progression"]["items"]) == 995
    assert save["weapon_progression"]["discovered"] == []
    assert len(save["weapon_skins"]["items"]) == 192
    assert len(save["kill_effects"]["items"]) == 9
    assert save["kill_effects"]["unlocked"] == []


def test_cors_allows_the_account_selector_for_reads_and_writes(tmp_path):
    env = make_native(tmp_path)
    client = env["client"]
    account_id = login(client).json()["account_id"]
    checks = (
        (API + "/session", "GET"),
        (API + "/save", "GET"),
        (API + "/backups", "GET"),
        (API + "/prepare", "POST"),
    )
    for path, method in checks:
        preflight = client.options(path, headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type,x-sk-account",
        })
        assert preflight.status_code == 200, (path, preflight.text)
        assert preflight.headers["Access-Control-Allow-Origin"] == ORIGIN
        assert preflight.headers["Access-Control-Allow-Credentials"] == "true"
        assert "x-sk-account" in preflight.headers["Access-Control-Allow-Headers"].lower()
    selected = client.get(API + "/session", headers={**HEADERS, "X-SK-Account": account_id})
    assert selected.status_code == 200, selected.text
    assert selected.json()["account_id"] == account_id
    assert selected.headers["Access-Control-Allow-Origin"] == ORIGIN
    denied = client.options(API + "/session", headers={
        "Origin": "https://foreign.example",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "x-sk-account",
    })
    assert denied.status_code == 400
    assert "Access-Control-Allow-Origin" not in denied.headers


def test_wrong_credentials_are_rejected_and_attempts_are_limited(tmp_path):
    env = make_native(tmp_path, attempts=2)
    first = login(env["client"], password="wrong-1")
    assert_error(first, 401, "native_credentials_rejected")
    second = login(env["client"], password="wrong-2")
    assert_error(second, 401, "native_credentials_rejected")
    blocked = login(env["client"])
    assert_error(blocked, 429, "native_login_throttled")
    assert "Retry-After" in blocked.headers
    assert len(env["auth"].calls) == 2
    assert "a@example.test" not in blocked.text and "wrong-2" not in blocked.text


def test_identity_mismatch_does_not_create_a_session(tmp_path):
    env = make_native(tmp_path)
    env["auth"].override["a@example.test"] = GatewaySession(
        token="t" * 32, uid=1, email="other@example.test", player_id=11,
        expire=int(time.time()) + 3600, distro_id="distro-a",
    )
    response = login(env["client"])
    assert_error(response, 409, "native_identity_mismatch")
    assert COOKIE not in response.cookies
    assert session_of(env["client"])["active"] is False
    assert "other@example.test" not in response.text


def test_profile_cannot_be_reused_for_another_account(tmp_path):
    env = make_native(tmp_path)
    profile_a = next(
        item for item in env["service"].store.list_profiles()
        if item.label == "Instalación Android Global"
    )
    assert login(env["client"]).status_code == 200
    env["auth"].accounts["b@example.test"]["distro"] = "distro-a"
    env["auth"].accounts["b@example.test"]["email"] = "b@example.test"
    other = TestClient(env["app"], base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50001))
    response = login(other, email="b@example.test", password="pass-b", profile=profile_a.id)
    assert_error(response, 409, "native_profile_identity_mismatch")
    assert session_of(other)["active"] is False
    assert session_of(env["client"])["active"] is True


def test_a_second_profile_for_the_same_identity_is_rejected_cleanly(tmp_path):
    env = make_native(tmp_path)
    add_account_b(env)
    profile_a = next(
        item for item in env["service"].store.list_profiles()
        if item.label == "Instalación Android Global"
    )
    second_same_account = env["store"].create_profile(
        label="Duplicado", distribution_id="android-global",
        distro_id="distro-a", unique_id="unique-a", allow_write=False,
    )
    assert login(env["client"], profile=profile_a.id).status_code == 200
    response = login(env["client"], profile=second_same_account.id)
    assert_error(response, 409, "native_profile_identity_mismatch")
    assert "Traceback" not in response.text


def test_installation_pending_can_be_completed_from_the_owner_session(tmp_path):
    env = make_native(tmp_path, unique_a=None)
    response = login(env["client"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["installation_ready"] is False
    assert body["save"] is None and body["save_error"] == "native_installation_required"
    assert_error(env["client"].get(API + "/save", headers=HEADERS), 409, "native_installation_required")
    assert_error(
        env["client"].post(API + "/installation", headers=HEADERS, json={"unique_id": "bad value"}),
        422,
        "invalid_request",
    )
    completed = env["client"].post(API + "/installation", headers=HEADERS, json={"unique_id": "unique-a"})
    assert completed.status_code == 200, completed.text
    assert completed.json()["installation_ready"] is True
    assert completed.json()["save"]["gems"] == 1000
    assert env["client"].get(API + "/save", headers=HEADERS).json()["gems"] == 1000


def test_two_accounts_have_isolated_sessions_backups_and_saves(tmp_path):
    env = make_native(tmp_path)
    profile_b = add_account_b(env)
    profile_a = next(
        item for item in env["service"].store.list_profiles()
        if item.label == "Instalación Android Global"
    )
    client_a = env["client"]
    client_b = TestClient(env["app"], base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50001))
    assert login(client_a, profile=profile_a.id).status_code == 200
    assert login(client_b, email="b@example.test", password="pass-b", profile=profile_b.id).status_code == 200
    assert client_a.get(API + "/save", headers=HEADERS).json()["gems"] == 1000
    assert client_b.get(API + "/save", headers=HEADERS).json()["gems"] == 1000

    draft = prepare(client_a)
    assert client_b.get(API + "/backups", headers=HEADERS).json() == {
        "backups": [], "total": 0, "listed": 0, "limit": 25, "unreadable": 0, "next_cursor": None,
    }
    foreign = client_b.post(API + "/verify", headers=HEADERS, json={"backup_id": draft["backup"]["id"]})
    assert_error(foreign, 404, "backup_not_found")

    assert client_a.post(API + "/logout", headers=HEADERS, json={}).status_code == 204
    assert_error(client_a.get(API + "/save", headers=HEADERS), 401, "native_session_required")
    assert client_b.get(API + "/save", headers=HEADERS).status_code == 200

    replay = TestClient(env["app"], base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50002))
    replay.cookies.set(COOKIE, "z" * 43, domain="127.0.0.1", path="/")
    assert_error(replay.get(API + "/save", headers=HEADERS), 401, "native_session_required")

    subject_a = env["store"].identity_subject(email="a@example.test", uid=1, player_id=11)
    subject_b = env["store"].identity_subject(email="b@example.test", uid=2, player_id=22)
    assert subject_a != subject_b
    assert (env["service"].backup_root / subject_a).is_dir()
    assert not (env["service"].backup_root / subject_b).exists()


def test_login_fails_closed_when_blob_save_rejects_the_token(tmp_path):
    env = make_native(tmp_path)

    def reject(*_args, **_kwargs):
        raise CloudProviderUnauthenticated("provider fixture")

    env["providers"]["unique-a"].download = reject
    response = login(env["client"])
    assert_error(response, 502, "native_session_rejected")
    assert session_of(env["client"])["active"] is False


def test_installation_fails_closed_when_blob_save_rejects_the_token(tmp_path):
    env = make_native(tmp_path, unique_a=None)
    assert login(env["client"]).status_code == 200
    assert session_of(env["client"])["active"] is True

    def reject(*_args, **_kwargs):
        raise CloudProviderUnauthenticated("provider fixture")

    env["providers"]["unique-a"].download = reject
    response = env["client"].post(API + "/installation", headers=HEADERS, json={"unique_id": "unique-a"})
    assert_error(response, 401, "native_session_expired")
    assert session_of(env["client"])["active"] is False


def test_a_save_from_another_account_is_rejected_after_binding(tmp_path):
    env = make_native(tmp_path)
    assert login(env["client"]).status_code == 200
    saved = env["client"].get(API + "/save", headers=HEADERS)
    assert saved.status_code == 200
    env["providers"]["unique-a"].payload = PAYLOAD_B
    response = login(env["client"])
    assert_error(response, 422, "native_save_identity_mismatch")
    assert "sintetico-cuenta-beta" not in response.text


def test_session_expiry_idle_and_restart_persistence(tmp_path):
    env = make_native(tmp_path)
    assert login(env["client"]).status_code == 200
    draft = prepare(env["client"])
    cookie = env["client"].cookies.get(COOKIE)
    assert cookie

    with sqlite3.connect(env["store"].database) as db:
        db.execute("UPDATE sessions SET session_expires = ?", (int(time.time()) - 1,))
    assert_error(env["client"].get(API + "/save", headers=HEADERS), 401, "native_session_expired")
    assert session_of(env["client"]) == {
        "active": False, "reason": "expired",
        "message": "La sesión caducó. Inicia sesión de nuevo.",
    }

    restarted_app = create_app(env["settings"])
    restarted_service = restarted_app.state.native_service
    restarted_service.client = env["auth"]
    restarted_service.provider_factory = env["service"].provider_factory
    restarted_service.uploader_factory = env["service"].uploader_factory
    restarted = TestClient(restarted_app, base_url="http://127.0.0.1:8000",
                           client=("127.0.0.1", 50000), cookies={COOKIE: cookie})
    assert_error(restarted.get(API + "/save", headers=HEADERS), 401, "native_session_expired")

    assert login(restarted).status_code == 200
    with sqlite3.connect(env["store"].database) as db:
        db.execute("UPDATE sessions SET last_seen = ?", (int(time.time()) - 4000,))
    assert_error(restarted.get(API + "/save", headers=HEADERS), 401, "native_session_expired")

    assert login(restarted).status_code == 200
    assert restarted.get(API + "/backups", headers=HEADERS).json()["backups"][0]["id"] == draft["backup"]["id"]


def test_write_requires_global_flag_profile_permission_and_confirmation(tmp_path):
    read_only = make_native(tmp_path / "off", write=False)
    assert login(read_only["client"]).status_code == 200
    draft = prepare(read_only["client"])
    assert_error(
        read_only["client"].post(API + "/confirm", headers=HEADERS, json=confirmation(draft)),
        503, "native_write_disabled",
    )
    assert read_only["uploaders"]["unique-a"].calls == []

    denied = make_native(tmp_path / "denied", write=True, allow_write=False)
    assert login(denied["client"]).status_code == 200
    draft = prepare(denied["client"])
    assert_error(
        denied["client"].post(API + "/confirm", headers=HEADERS, json=confirmation(draft)),
        403, "native_write_denied",
    )
    assert denied["uploaders"]["unique-a"].calls == []

    writable = make_native(tmp_path / "write", write=True, allow_write=True)
    assert login(writable["client"]).status_code == 200
    draft = prepare(writable["client"])
    assert_error(
        writable["client"].post(API + "/confirm", headers=HEADERS,
                                json=confirmation(draft) | {"confirmation": "subir"}),
        422, "invalid_request",
    )
    assert_error(
        writable["client"].post(API + "/confirm", headers=HEADERS,
                                json=confirmation(draft) | {"expected_sha256": "0" * 64}),
        422, "cloud_hash_mismatch",
    )
    confirmed = writable["client"].post(API + "/confirm", headers=HEADERS, json=confirmation(draft))
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["persisted"] is True
    assert len(writable["uploaders"]["unique-a"].calls) == 1
    assert_error(
        writable["client"].post(API + "/confirm", headers=HEADERS, json=confirmation(draft)),
        409, "cloud_already_confirmed",
    )
    restored = writable["client"].post(
        API + "/restore", headers=HEADERS,
        json={"backup_id": draft["backup"]["id"], "confirmation": "RESTAURAR"},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["persisted"] is True
    assert writable["providers"]["unique-a"].payload == PAYLOAD_A


@pytest.mark.parametrize("unsupported", ["new_version", "malformed_preference_snapshot"])
def test_incompatible_aggregate_is_readable_but_cannot_prepare_a_write(tmp_path, unsupported):
    env = make_native(tmp_path, write=True)
    client = env["client"]
    assert login(client).status_code == 200
    payload = json.loads(PAYLOAD_A)
    if unsupported == "new_version":
        payload["serialzedVersion"] = 2
    else:
        payload["gameData"]["lastGems"] = True
    env["providers"]["unique-a"].payload = canonical(payload)
    source = client.get(API + "/save", headers=HEADERS)
    assert source.status_code == 200
    expected = (
        "cloud_compatibility_pending"
        if unsupported == "new_version"
        else "unsupported_gems_structure"
    )
    assert_error(
        client.post(API + "/prepare", headers=HEADERS,
                    json={"new_gems": 1002, "source_sha256": source.json()["sha256"]}),
        422, expected,
    )
    assert client.get(API + "/backups", headers=HEADERS).json()["backups"] == []
    assert env["uploaders"]["unique-a"].calls == []


@pytest.mark.parametrize(("gems", "expected_error"), [
    (1001, "inconsistent_gems_balance"),
    (1000, "unknown_gems_dependencies"),
])
def test_native_rejects_partial_gems_edits_before_backup_or_upload(tmp_path, gems, expected_error):
    env = make_native(tmp_path, write=True)
    client = env["client"]
    assert login(client).status_code == 200
    original = json.loads(PAYLOAD_A)
    original["gameData"].update(gems=gems, lastGems=0, cumulativeGems=1000, cumulativeConsumeGems=0)
    if expected_error == "unknown_gems_dependencies":
        del original["gameData"]["varGems"]
    else:
        original["gameData"]["varGems"] = 1000
    before = canonical(original)
    env["providers"]["unique-a"].payload = before
    source = client.get(API + "/save", headers=HEADERS)
    assert source.status_code == 200
    assert source.json()["gems"] == gems
    assert_error(
        client.post(API + "/prepare", headers=HEADERS,
                    json={"new_gems": 1002, "source_sha256": source.json()["sha256"]}),
        422, expected_error,
    )
    assert client.get(API + "/backups", headers=HEADERS).json()["backups"] == []
    assert env["uploaders"]["unique-a"].calls == []
    assert env["providers"]["unique-a"].payload == before


def test_origin_content_type_and_body_limits_are_enforced(tmp_path):
    env = make_native(tmp_path)
    assert_error(login(env["client"], headers={}), 403, "native_origin_denied")
    assert_error(login(env["client"], headers={"Origin": "https://foreign.example"}), 403, "native_origin_denied")
    assert_error(
        login(env["client"], headers=HEADERS | {"Sec-Fetch-Site": "cross-site"}),
        403, "native_origin_denied",
    )
    assert_error(
        env["client"].post(API + "/login", headers=HEADERS | {"Content-Type": "text/plain"}, content=b"x"),
        415, "invalid_content_type",
    )
    assert_error(
        env["client"].post(API + "/login", headers=HEADERS | {"Content-Type": "application/json"},
                           content=b"x" * 70_000),
        413, "request_too_large",
    )
    assert_error(env["client"].get(API + "/config", headers={"Origin": "https://foreign.example"}),
                 403, "native_origin_denied")


def test_multiple_profiles_require_an_explicit_choice(tmp_path):
    env = make_native(tmp_path)
    add_account_b(env)
    assert_error(login(env["client"]), 409, "native_profile_required")
    profile_b = next(item for item in env["service"].store.list_profiles() if item.label == "Cuenta B")
    assert login(env["client"], email="b@example.test", password="pass-b", profile=profile_b.id).status_code == 200


def test_concurrent_confirmation_uploads_exactly_once(tmp_path):
    env = make_native(tmp_path, write=True, allow_write=True)
    second = TestClient(env["app"], base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50001))
    assert login(env["client"]).status_code == 200
    assert login(second).status_code == 200
    draft = prepare(env["client"])
    payload = confirmation(draft)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda client: client.post(API + "/confirm", headers=HEADERS, json=payload),
            (env["client"], second),
        ))
    assert sorted(result.status_code for result in results) == [200, 409]
    assert len(env["uploaders"]["unique-a"].calls) == 1


def test_diagnostics_are_sanitized_and_private(tmp_path):
    env = make_native(tmp_path)
    assert_error(env["client"].get(API + "/diagnostics", headers=HEADERS), 401, "native_session_required")
    assert login(env["client"]).status_code == 200
    response = env["client"].get(API + "/diagnostics", headers=HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["enabled"] is True and body["profiles_total"] == 1
    assert any(event["event"] == "login" for event in body["events"])
    text = response.text
    for secret in ("a@example.test", "distro-a", "unique-a", "token-"):
        assert secret not in text


def test_native_auth_is_disabled_by_default_and_does_not_parse_credentials():
    app = create_app(Settings(_env_file=None, env="development", allowed_origins=[ORIGIN]))
    client = TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000))
    config = client.get(API + "/config").json()
    assert config["available"] is False and config["login_available"] is False
    assert config["native_auth_ready"] is False
    response = client.post(API + "/login", headers=HEADERS | {"Content-Type": "application/json"},
                           json={"distribution": "android-global", "email": "holder@example.test",
                                 "password": "private-fixture-password"})
    assert_error(response, 503, "native_auth_disabled")
    assert "private-fixture-password" not in response.text


def test_secure_cookie_and_https_origin(tmp_path):
    origin = "https://editor.example.test"
    settings = Settings(
        _env_file=None,
        env="production",
        allowed_origins=[origin],
        native_auth_enabled=True,
        native_store_key="cd" * 32,
        native_store_dir=tmp_path / "native",
        native_backup_dir=tmp_path / "native-backups",
        native_origin=origin,
        native_auto_identity=False,
        native_distro_id="distro-a",
        native_unique_id="unique-a",
    )
    app = create_app(settings)
    service = app.state.native_service
    auth = FakeAuth()
    provider = FakeProvider(PAYLOAD_A)
    service.client = auth
    service.provider_factory = lambda token, unique, distro, distribution: provider
    service.uploader_factory = lambda token, unique, distro, distribution: FakeUploader(provider)
    client = TestClient(app, base_url="https://api.example.test", client=("127.0.0.1", 50000))
    response = client.post(API + "/login", headers={"Origin": origin},
                           json={"distribution": "android-global", "email": "a@example.test",
                                 "password": "pass-a"})
    assert response.status_code == 200, response.text
    cookie = response.headers["set-cookie"]
    assert "__Host-sk_native=" in cookie and "Secure" in cookie and "HttpOnly" in cookie
    assert client.get(API + "/session", headers={"Origin": origin}).json()["active"] is True


def fish_payload(fish_chip: int = 4) -> bytes:
    data = json.loads(PAYLOAD_A)
    data["gameData"]["fishChip"] = fish_chip
    data["itemData"]["materials"] = {"material_fish": fish_chip, "material_ticket": 5}
    data["itemData"]["cumulativeFishCount"] = 42
    return canonical(data)


def prepare_fish_chip(client, value=9):
    source = client.get(API + "/save", headers=HEADERS)
    assert source.status_code == 200, source.text
    response = client.post(
        API + "/prepare-fish-chip",
        headers=HEADERS,
        json={"new_fish_chip": value, "source_sha256": source.json()["sha256"]},
    )
    assert response.status_code == 200, response.text
    return source.json(), response.json()


def test_native_fish_chip_experimental_flow_preserves_gems_and_backups(tmp_path):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = fish_payload()
    client = env["client"]
    assert login(client).status_code == 200

    source, draft = prepare_fish_chip(client)
    assert source["fish_chip"] == 4
    assert source["material_fish"] == 4
    assert draft["field"] == "gameData.fishChip"
    assert draft["experimental"] is True
    assert draft["original_fish_chip"] == 4 and draft["new_fish_chip"] == 9
    assert draft["original_material_fish"] == 4 and draft["new_material_fish"] == 9
    assert draft["changed_fields"] == [
        "gameData.fishChip", "itemData.materials.material_fish",
    ]
    assert draft["backup"]["field"] == "fish_chip"
    assert draft["backup"]["original_value"] == 4
    assert draft["backup"]["candidate_value"] == 9

    confirmed = client.post(API + "/confirm", headers=HEADERS, json=confirmation(draft))
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()
    assert result["persisted"] is True
    assert result["field"] == "gameData.fishChip"
    assert result["remote_value"] == 9
    assert result["remote_material_fish"] == 9
    assert result["remote_gems"] == 1000

    uploaded = json.loads(env["providers"]["unique-a"].payload)
    assert uploaded["gameData"]["fishChip"] == 9
    assert uploaded["gameData"]["gems"] == 1000
    assert uploaded["itemData"]["materials"] == {"material_fish": 9, "material_ticket": 5}
    assert uploaded["itemData"]["cumulativeFishCount"] == 42

    refreshed = client.get(API + "/save", headers=HEADERS).json()
    assert refreshed["fish_chip"] == 9 and refreshed["material_fish"] == 9
    assert refreshed["gems"] == 1000
    backups = client.get(API + "/backups", headers=HEADERS).json()["backups"]
    assert backups[0]["field"] == "fish_chip"

    verified = client.post(API + "/verify", headers=HEADERS,
                           json={"backup_id": draft["backup"]["id"]})
    assert verified.status_code == 200, verified.text
    assert verified.json()["matches_candidate"] is True
    assert verified.json()["remote_value"] == 9
    assert verified.json()["remote_material_fish"] == 9

    restored = client.post(API + "/restore", headers=HEADERS,
                           json={"backup_id": draft["backup"]["id"], "confirmation": "RESTAURAR"})
    assert restored.status_code == 200, restored.text
    assert restored.json()["persisted"] is True
    assert restored.json()["remote_value"] == 4
    assert restored.json()["remote_material_fish"] == 4
    assert restored.json()["remote_gems"] == 1000

    # La edición de gemas sigue funcionando y no toca las fichas restauradas.
    gems = prepare(client, 1001)
    assert gems["original_gems"] == 1000
    gems_confirmed = client.post(API + "/confirm", headers=HEADERS, json=confirmation(gems))
    assert gems_confirmed.status_code == 200, gems_confirmed.text
    assert gems_confirmed.json()["persisted"] is True
    after = client.get(API + "/save", headers=HEADERS).json()
    assert after["gems"] == 1001 and after["fish_chip"] == 4


@pytest.mark.parametrize("value", [-1, 2_147_483_648, "9", 9.5, True])
def test_native_rejects_invalid_fish_chip_values_before_backup(tmp_path, value):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = fish_payload()
    client = env["client"]
    assert login(client).status_code == 200
    source = client.get(API + "/save", headers=HEADERS)
    assert source.status_code == 200
    response = client.post(
        API + "/prepare-fish-chip",
        headers=HEADERS,
        json={"new_fish_chip": value, "source_sha256": source.json()["sha256"]},
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] in {"invalid_fish_chip_value", "invalid_request"}
    assert client.get(API + "/backups", headers=HEADERS).json()["backups"] == []


def test_native_reports_missing_fish_chip_without_creating_a_backup(tmp_path):
    env = make_native(tmp_path, write=True)
    client = env["client"]
    assert login(client).status_code == 200
    source = client.get(API + "/save", headers=HEADERS).json()
    assert source["fish_chip"] is None
    response = client.post(
        API + "/prepare-fish-chip",
        headers=HEADERS,
        json={"new_fish_chip": 9, "source_sha256": source["sha256"]},
    )
    assert_error(response, 422, "fish_chip_field_missing")
    assert client.get(API + "/backups", headers=HEADERS).json()["backups"] == []


def test_native_fish_progress_flow_preserves_balance_and_history(tmp_path):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = fish_payload()
    client = env["client"]
    assert login(client).status_code == 200

    source = client.get(API + "/save", headers=HEADERS).json()
    assert source["cumulative_fish_count"] == 42
    assert source["cumulative_fish_count_path"] == "itemData.cumulativeFishCount"
    response = client.post(
        API + "/prepare-fish-progress",
        headers=HEADERS,
        json={"new_cumulative_fish_count": 120, "source_sha256": source["sha256"]},
    )
    assert response.status_code == 200, response.text
    draft = response.json()
    assert draft["field"] == "itemData.cumulativeFishCount"
    assert draft["experimental"] is True
    assert draft["original_cumulative_fish_count"] == 42
    assert draft["new_cumulative_fish_count"] == 120
    assert draft["changed_fields"] == ["itemData.cumulativeFishCount"]
    assert draft["backup"]["field"] == "fish_progress"
    assert draft["backup"]["original_value"] == 42
    assert draft["backup"]["candidate_value"] == 120

    confirmed = client.post(API + "/confirm", headers=HEADERS, json=confirmation(draft))
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()
    assert result["persisted"] is True
    assert result["field"] == "itemData.cumulativeFishCount"
    assert result["remote_value"] == 120
    assert result["remote_gems"] == 1000

    uploaded = json.loads(env["providers"]["unique-a"].payload)
    assert uploaded["itemData"]["cumulativeFishCount"] == 120
    assert uploaded["gameData"]["fishChip"] == 4
    assert uploaded["itemData"]["materials"] == {"material_fish": 4, "material_ticket": 5}

    refreshed = client.get(API + "/save", headers=HEADERS).json()
    assert refreshed["cumulative_fish_count"] == 120
    assert refreshed["fish_chip"] == 4
    assert refreshed["material_fish"] == 4

    restored = client.post(API + "/restore", headers=HEADERS,
                           json={"backup_id": draft["backup"]["id"], "confirmation": "RESTAURAR"})
    assert restored.status_code == 200, restored.text
    assert restored.json()["persisted"] is True
    assert restored.json()["remote_value"] == 42
    after = client.get(API + "/save", headers=HEADERS).json()
    assert after["cumulative_fish_count"] == 42
    assert after["fish_chip"] == 4


@pytest.mark.parametrize("value", [-1, 2_147_483_648, "9", 9.5, True])
def test_native_rejects_invalid_fish_progress_values_before_backup(tmp_path, value):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = fish_payload()
    client = env["client"]
    assert login(client).status_code == 200
    source = client.get(API + "/save", headers=HEADERS).json()
    response = client.post(
        API + "/prepare-fish-progress",
        headers=HEADERS,
        json={"new_cumulative_fish_count": value, "source_sha256": source["sha256"]},
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] in {"invalid_fish_progress_value", "invalid_request"}
    assert client.get(API + "/backups", headers=HEADERS).json()["backups"] == []


def test_native_reports_missing_fish_progress_without_creating_it(tmp_path):
    env = make_native(tmp_path, write=True)
    data = json.loads(PAYLOAD_A)
    data["itemData"]["cumulativeFishCount"] = 42
    del data["itemData"]["cumulativeFishCount"]
    env["providers"]["unique-a"].payload = canonical(data)
    client = env["client"]
    assert login(client).status_code == 200
    source = client.get(API + "/save", headers=HEADERS).json()
    assert source["cumulative_fish_count"] is None
    response = client.post(
        API + "/prepare-fish-progress",
        headers=HEADERS,
        json={"new_cumulative_fish_count": 120, "source_sha256": source["sha256"]},
    )
    assert_error(response, 422, "fish_progress_field_missing")
    assert client.get(API + "/backups", headers=HEADERS).json()["backups"] == []


def character_payload(unlocked=("Knight", "CostumePrince")) -> bytes:
    from app.save_report import _load_character_catalog

    codes = _load_character_catalog()["codes"]
    data = json.loads(PAYLOAD_A)
    data["gameData"]["heroUnlock"] = {code: code in unlocked for code in codes}
    data["gameData"]["heroLevel"] = {code: 0 for code in codes}
    data["gameData"]["heroLevel"]["Knight"] = 2
    data["gameData"]["heroSkill"] = {code: 0 for code in codes}
    catalog = _load_character_catalog()
    data["gameData"]["heroSkillUnlock"] = {
        code: [
            {"Key": skill["index"], "Value": skill["index"] == 0}
            for skill in catalog["characters"][code]["skills"]
        ]
        for code in codes
    }
    data["gameData"]["skinLock"] = {
        code: [
            {"Key": skin["index"], "Value": 1 if skin["index"] == 0 else 0}
            for skin in catalog["characters"][code]["skins"]
        ]
        for code in codes
    }
    data["gameData"]["currentSkinDatas"] = {"Knight": 1}
    data["gameData"]["fishChip"] = 3
    data["itemData"]["materials"] = {"material_fish": 3, "material_ticket": 5}
    return canonical(data)


def prepare_characters(client, codes):
    source = client.get(API + "/save", headers=HEADERS)
    assert source.status_code == 200, source.text
    response = client.post(
        API + "/prepare-characters",
        headers=HEADERS,
        json={"codes": codes, "source_sha256": source.json()["sha256"]},
    )
    assert response.status_code == 200, response.text
    return source.json(), response.json()


def test_native_character_unlock_single_flow_preserves_progress_and_restores(tmp_path):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = character_payload()
    client = env["client"]
    assert login(client).status_code == 200

    source, draft = prepare_characters(client, ["Ranger"])
    assert source["character_write_policy"] == "confirmed_by_owner"
    assert source["skill_write_policy"] == "confirmed_by_owner"
    assert source["skin_write_policy"] == "confirmed_by_owner"
    assert draft["field"] == "gameData.heroUnlock"
    assert draft["experimental"] is False
    assert draft["validation"]["evidence_level"] == "confirmed_by_owner"
    assert draft["original_unlocked_count"] == 2
    assert draft["new_unlocked_count"] == 3
    assert draft["total_characters"] == 42
    assert draft["selected_codes"] == ["Ranger"]
    assert draft["newly_unlocked_codes"] == ["Ranger"]
    assert draft["changed_fields"] == ["gameData.heroUnlock.Ranger"]
    assert draft["backup"]["field"] == "characters"
    assert draft["backup"]["character_codes"] == ["Ranger"]
    assert draft["backup"]["original_value"] == 2
    assert draft["backup"]["candidate_value"] == 3
    assert draft["validation"]["only_characters_changed"] is True

    confirmed = client.post(API + "/confirm", headers=HEADERS, json=confirmation(draft))
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()
    assert result["persisted"] is True
    assert result["field"] == "gameData.heroUnlock"
    assert result["remote_characters"] == 3
    assert result["remote_gems"] == 1000

    uploaded = json.loads(env["providers"]["unique-a"].payload)
    assert uploaded["gameData"]["heroUnlock"]["Knight"] is True
    assert uploaded["gameData"]["heroUnlock"]["CostumePrince"] is True
    assert uploaded["gameData"]["heroUnlock"]["Ranger"] is True
    assert uploaded["gameData"]["heroUnlock"]["Mage"] is False
    assert uploaded["gameData"]["heroLevel"]["Knight"] == 2
    assert uploaded["gameData"]["heroSkill"] == {
        code: 0 for code in uploaded["gameData"]["heroSkill"]
    }
    assert sum(len(items) for items in uploaded["gameData"]["skinLock"].values()) == 802
    assert uploaded["gameData"]["skinLock"]["Knight"][0] == {"Key": 0, "Value": 1}
    assert uploaded["gameData"]["skinLock"]["Knight"][1] == {"Key": 1, "Value": 0}
    assert uploaded["gameData"]["currentSkinDatas"] == {"Knight": 1}
    assert uploaded["gameData"]["gems"] == 1000
    assert uploaded["gameData"]["fishChip"] == 3
    assert uploaded["itemData"]["materials"] == {"material_fish": 3, "material_ticket": 5}

    verified = client.post(API + "/verify", headers=HEADERS,
                           json={"backup_id": draft["backup"]["id"]})
    assert verified.status_code == 200, verified.text
    assert verified.json()["matches_candidate"] is True
    assert verified.json()["remote_characters"] == 3

    restored = client.post(API + "/restore", headers=HEADERS,
                           json={"backup_id": draft["backup"]["id"], "confirmation": "RESTAURAR"})
    assert restored.status_code == 200, restored.text
    assert restored.json()["persisted"] is True
    assert restored.json()["remote_characters"] == 2
    after = json.loads(env["providers"]["unique-a"].payload)
    assert after["gameData"]["heroUnlock"]["Ranger"] is False
    assert after["gameData"]["heroUnlock"]["Knight"] is True
    assert after["gameData"]["heroLevel"]["Knight"] == 2


def prepare_skills(client, skills):
    source = client.get(API + "/save", headers=HEADERS)
    assert source.status_code == 200, source.text
    response = client.post(
        API + "/prepare-skills",
        headers=HEADERS,
        json={"skills": skills, "source_sha256": source.json()["sha256"]},
    )
    assert response.status_code == 200, response.text
    return source.json(), response.json()


def test_native_skill_unlock_single_flow_preserves_progress_and_restores(tmp_path):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = character_payload()
    client = env["client"]
    assert login(client).status_code == 200

    source, draft = prepare_skills(client, [{"code": "Knight", "index": 1}])
    assert source["skill_write_policy"] == "confirmed_by_owner"
    assert source["skin_write_policy"] == "confirmed_by_owner"
    assert source["character_write_policy"] == "confirmed_by_owner"
    assert draft["field"] == "gameData.heroSkillUnlock"
    assert draft["experimental"] is False
    assert draft["validation"]["evidence_level"] == "E3"
    assert draft["validation"]["only_skills_changed"] is True
    assert draft["original_unlocked_count"] == 42
    assert draft["new_unlocked_count"] == 43
    assert draft["total_skills"] == 105
    assert draft["selected_skills"] == [{"code": "Knight", "index": 1}]
    assert draft["newly_unlocked_skills"] == [{"code": "Knight", "index": 1}]
    assert draft["affected_codes"] == ["Knight"]
    assert draft["changed_fields"] == ["gameData.heroSkillUnlock.Knight[1]"]
    assert draft["backup"]["field"] == "skills"
    assert draft["backup"]["skill_selections"] == [{"code": "Knight", "index": 1}]
    assert draft["backup"]["original_value"] == 42
    assert draft["backup"]["candidate_value"] == 43

    confirmed = client.post(API + "/confirm", headers=HEADERS, json=confirmation(draft))
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()
    assert result["persisted"] is True
    assert result["field"] == "gameData.heroSkillUnlock"
    assert result["remote_skills"] == 43
    assert result["remote_characters"] is None
    assert result["remote_gems"] == 1000

    uploaded = json.loads(env["providers"]["unique-a"].payload)
    assert uploaded["gameData"]["heroSkillUnlock"]["Knight"][1]["Value"] is True
    assert uploaded["gameData"]["heroSkill"] == {
        code: 0 for code in uploaded["gameData"]["heroSkill"]
    }
    assert uploaded["gameData"]["heroUnlock"] == {
        code: code in {"Knight", "CostumePrince"}
        for code in uploaded["gameData"]["heroUnlock"]
    }
    assert uploaded["gameData"]["heroLevel"]["Knight"] == 2
    assert uploaded["gameData"]["gems"] == 1000
    assert uploaded["gameData"]["fishChip"] == 3
    assert uploaded["itemData"]["materials"] == {"material_fish": 3, "material_ticket": 5}

    verified = client.post(API + "/verify", headers=HEADERS,
                           json={"backup_id": draft["backup"]["id"]})
    assert verified.status_code == 200, verified.text
    assert verified.json()["matches_candidate"] is True
    assert verified.json()["remote_skills"] == 43

    restored = client.post(API + "/restore", headers=HEADERS,
                           json={"backup_id": draft["backup"]["id"], "confirmation": "RESTAURAR"})
    assert restored.status_code == 200, restored.text
    assert restored.json()["persisted"] is True
    assert restored.json()["remote_skills"] == 42
    after = json.loads(env["providers"]["unique-a"].payload)
    assert after["gameData"]["heroSkillUnlock"]["Knight"][1]["Value"] is False
    assert after["gameData"]["heroSkillUnlock"]["Knight"][0]["Value"] is True


def prepare_skins(client, skins):
    source = client.get(API + "/save", headers=HEADERS)
    assert source.status_code == 200, source.text
    response = client.post(
        API + "/prepare-skins",
        headers=HEADERS,
        json={"skins": skins, "source_sha256": source.json()["sha256"]},
    )
    assert response.status_code == 200, response.text
    return source.json(), response.json()


def test_native_skin_unlock_single_flow_preserves_progress_and_restores(tmp_path):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = character_payload()
    client = env["client"]
    assert login(client).status_code == 200

    source, draft = prepare_skins(client, [{"code": "Knight", "index": 1}])
    assert source["skin_write_policy"] == "confirmed_by_owner"
    assert source["skill_write_policy"] == "confirmed_by_owner"
    assert source["character_write_policy"] == "confirmed_by_owner"
    assert draft["field"] == "gameData.skinLock"
    assert draft["experimental"] is False
    assert draft["validation"]["evidence_level"] == "E3"
    assert draft["validation"]["only_skins_changed"] is True
    assert draft["original_unlocked_count"] == 42
    assert draft["new_unlocked_count"] == 43
    assert draft["total_skins"] == 802
    assert draft["selected_skins"] == [{"code": "Knight", "index": 1}]
    assert draft["newly_unlocked_skins"] == [{"code": "Knight", "index": 1}]
    assert draft["affected_codes"] == ["Knight"]
    assert draft["locked_character_codes"] == []
    assert draft["changed_fields"] == ["gameData.skinLock.Knight[1]"]
    assert draft["backup"]["field"] == "skins"
    assert draft["backup"]["skin_selections"] == [{"code": "Knight", "index": 1}]
    assert draft["backup"]["original_value"] == 42
    assert draft["backup"]["candidate_value"] == 43

    confirmed = client.post(API + "/confirm", headers=HEADERS, json=confirmation(draft))
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()
    assert result["persisted"] is True
    assert result["field"] == "gameData.skinLock"
    assert result["remote_skins"] == 43
    assert result["remote_skills"] is None
    assert result["remote_characters"] is None
    assert result["remote_gems"] == 1000

    uploaded = json.loads(env["providers"]["unique-a"].payload)
    assert uploaded["gameData"]["skinLock"]["Knight"][1] == {"Key": 1, "Value": 1}
    assert uploaded["gameData"]["skinLock"]["Knight"][2] == {"Key": 2, "Value": 0}
    assert uploaded["gameData"]["currentSkinDatas"] == {"Knight": 1}
    assert uploaded["gameData"]["heroUnlock"]["Ranger"] is False
    assert uploaded["gameData"]["heroSkillUnlock"]["Knight"][1]["Value"] is False
    assert uploaded["gameData"]["heroLevel"]["Knight"] == 2
    assert uploaded["gameData"]["gems"] == 1000
    assert uploaded["gameData"]["fishChip"] == 3
    assert uploaded["itemData"]["materials"] == {"material_fish": 3, "material_ticket": 5}

    verified = client.post(API + "/verify", headers=HEADERS,
                           json={"backup_id": draft["backup"]["id"]})
    assert verified.status_code == 200, verified.text
    assert verified.json()["matches_candidate"] is True
    assert verified.json()["remote_skins"] == 43

    restored = client.post(API + "/restore", headers=HEADERS,
                           json={"backup_id": draft["backup"]["id"], "confirmation": "RESTAURAR"})
    assert restored.status_code == 200, restored.text
    assert restored.json()["persisted"] is True
    assert restored.json()["remote_skins"] == 42
    after = json.loads(env["providers"]["unique-a"].payload)
    assert after["gameData"]["skinLock"]["Knight"][1] == {"Key": 1, "Value": 0}
    assert after["gameData"]["currentSkinDatas"] == {"Knight": 1}


def test_native_skin_unlock_mass_keeps_previous_and_equipped_selection(tmp_path):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = character_payload()
    client = env["client"]
    assert login(client).status_code == 200

    from app.save_report import _load_character_catalog

    catalog = _load_character_catalog()
    pending = [
        {"code": code, "index": skin["index"]}
        for code in catalog["codes"]
        for skin in catalog["characters"][code]["skins"]
        if skin["index"] != 0
    ]
    _, draft = prepare_skins(client, pending)
    assert draft["original_unlocked_count"] == 42
    assert draft["new_unlocked_count"] == 802
    assert len(draft["newly_unlocked_skins"]) == 760
    confirmed = client.post(API + "/confirm", headers=HEADERS, json=confirmation(draft))
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["remote_skins"] == 802
    uploaded = json.loads(env["providers"]["unique-a"].payload)
    assert sum(
        entry["Value"] == 1
        for items in uploaded["gameData"]["skinLock"].values()
        for entry in items
    ) == 802
    assert uploaded["gameData"]["currentSkinDatas"] == {"Knight": 1}
    assert uploaded["gameData"]["heroUnlock"] == {
        code: code in {"Knight", "CostumePrince"}
        for code in uploaded["gameData"]["heroUnlock"]
    }


def test_native_skin_unlock_rejects_unknown_and_duplicate_positions(tmp_path):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = character_payload()
    client = env["client"]
    assert login(client).status_code == 200
    source = client.get(API + "/save", headers=HEADERS).json()
    for skins, code in (
        ([{"code": "Knight", "index": 500}], "unknown_skin_index"),
        ([{"code": "NoExiste", "index": 0}], "unknown_skin_character"),
        ([{"code": "Knight", "index": 1}] * 2, "invalid_skin_selection"),
    ):
        response = client.post(
            API + "/prepare-skins",
            headers=HEADERS,
            json={"skins": skins, "source_sha256": source["sha256"]},
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == code
    assert client.get(API + "/backups", headers=HEADERS).json()["backups"] == []



def test_native_skill_unlock_rejects_unknown_and_duplicate_positions(tmp_path):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = character_payload()
    client = env["client"]
    assert login(client).status_code == 200
    source = client.get(API + "/save", headers=HEADERS).json()
    for skills, code in (
        ([{"code": "Envoy", "index": 1}], "unknown_skill_index"),
        ([{"code": "NoExiste", "index": 0}], "unknown_skill_character"),
        ([{"code": "Knight", "index": 1}] * 2, "invalid_skill_selection"),
    ):
        response = client.post(
            API + "/prepare-skills",
            headers=HEADERS,
            json={"skills": skills, "source_sha256": source["sha256"]},
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == code
    assert client.get(API + "/backups", headers=HEADERS).json()["backups"] == []


def test_native_character_unlock_multiple_and_mass_keeps_previous_unlocks(tmp_path):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = character_payload()
    client = env["client"]
    assert login(client).status_code == 200

    _, multiple = prepare_characters(client, ["Ranger", "Mage"])
    assert multiple["newly_unlocked_codes"] == ["Ranger", "Mage"]
    confirm_multiple = client.post(API + "/confirm", headers=HEADERS, json=confirmation(multiple))
    assert confirm_multiple.status_code == 200, confirm_multiple.text
    assert confirm_multiple.json()["remote_characters"] == 4

    from app.save_report import _load_character_catalog

    remaining = [
        code for code in _load_character_catalog()["codes"]
        if code not in {"Knight", "CostumePrince", "Ranger", "Mage"}
    ]
    _, mass = prepare_characters(client, remaining)
    assert mass["original_unlocked_count"] == 4
    assert mass["new_unlocked_count"] == 42
    assert mass["newly_unlocked_codes"] == remaining
    confirm_mass = client.post(API + "/confirm", headers=HEADERS, json=confirmation(mass))
    assert confirm_mass.status_code == 200, confirm_mass.text
    assert confirm_mass.json()["remote_characters"] == 42
    uploaded = json.loads(env["providers"]["unique-a"].payload)
    assert all(uploaded["gameData"]["heroUnlock"].values())
    assert uploaded["gameData"]["heroLevel"]["Knight"] == 2
    assert uploaded["gameData"]["gems"] == 1000


@pytest.mark.parametrize(
    "codes, code",
    [
        ([], "invalid_request"),
        (["Knight", "Knight"], "invalid_character_selection"),
        (["NoExiste"], "unknown_character"),
    ],
)
def test_native_rejects_invalid_character_selections_before_backup(tmp_path, codes, code):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = character_payload()
    client = env["client"]
    assert login(client).status_code == 200
    source = client.get(API + "/save", headers=HEADERS).json()
    response = client.post(
        API + "/prepare-characters",
        headers=HEADERS,
        json={"codes": codes, "source_sha256": source["sha256"]},
    )
    assert_error(response, 422, code)
    assert client.get(API + "/backups", headers=HEADERS).json()["backups"] == []


def test_native_unified_prepare_confirm_uses_one_backup_and_one_upload(tmp_path):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = character_payload()
    client = env["client"]
    assert login(client).status_code == 200
    source = client.get(API + "/save", headers=HEADERS).json()
    response = client.post(
        API + "/prepare-unified",
        headers=HEADERS,
        json={
            "gems": 1200,
            "characters": ["Ranger"],
            "weapon_progression": ["weapon_002"],
            "source_sha256": source["sha256"],
        },
    )
    assert response.status_code == 200, response.text
    draft = response.json()
    assert draft["field"] == "unified"
    assert draft["change_count"] > 0
    assert [category["key"] for category in draft["categories"]] == [
        "gems", "characters", "weapon_progression",
    ]
    assert draft["backup"]["field"] == "unified"
    assert draft["backup"]["unified_plan"]["gems"] == 1200
    assert draft["backup"]["unified_plan"]["characters"] == ["Ranger"]
    assert draft["backup"]["unified_plan"]["weapon_progression"] == ["weapon_002"]
    assert len(client.get(API + "/backups", headers=HEADERS).json()["backups"]) == 1

    confirmed = client.post(API + "/confirm", headers=HEADERS, json=confirmation(draft))
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()
    assert result["persisted"] is True
    assert result["remote_gems"] == 1200
    assert result["remote_characters"] == 3
    assert len(env["uploaders"]["unique-a"].calls) == 1
    uploaded = json.loads(env["providers"]["unique-a"].payload)
    assert uploaded["gameData"]["gems"] == 1200
    assert uploaded["gameData"]["heroUnlock"]["Ranger"] is True
    assert uploaded["gameData"]["heroUnlock"]["Mage"] is False
    assert uploaded["gameData"]["heroLevel"]["Knight"] == 2
    assert uploaded["statisticData"]["object2ObtainTime"]["weapon_002"] == 1

    duplicate = client.post(API + "/confirm", headers=HEADERS, json=confirmation(draft))
    assert_error(duplicate, 409, "cloud_already_confirmed")
    assert len(env["uploaders"]["unique-a"].calls) == 1


def test_native_unified_prepares_weapon_forge_unlock_without_touching_queue(tmp_path):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = character_payload()
    client = env["client"]
    assert login(client).status_code == 200
    source = client.get(API + "/save", headers=HEADERS).json()
    response = client.post(
        API + "/prepare-unified",
        headers=HEADERS,
        json={
            "weapon_forge_unlock": ["weapon_002"],
            "source_sha256": source["sha256"],
        },
    )
    assert response.status_code == 200, response.text
    draft = response.json()
    assert [category["key"] for category in draft["categories"]] == ["weapon_forge_unlock"]
    assert draft["backup"]["unified_plan"]["weapon_forge_unlock"] == ["weapon_002"]
    assert draft["backup"]["unified_plan"]["weapon_progression"] == []


def test_native_unified_rejects_stale_source_and_empty_plan(tmp_path):
    env = make_native(tmp_path, write=True)
    env["providers"]["unique-a"].payload = character_payload()
    client = env["client"]
    assert login(client).status_code == 200
    source = client.get(API + "/save", headers=HEADERS).json()
    stale = client.post(
        API + "/prepare-unified",
        headers=HEADERS,
        json={"gems": 1200, "source_sha256": "0" * 64},
    )
    assert_error(stale, 409, "cloud_remote_changed")
    empty = client.post(
        API + "/prepare-unified",
        headers=HEADERS,
        json={"source_sha256": source["sha256"]},
    )
    assert_error(empty, 422, "invalid_unified_plan")
    assert client.get(API + "/backups", headers=HEADERS).json()["backups"] == []

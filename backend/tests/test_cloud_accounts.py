import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from time import time

import pytest
from fastapi.testclient import TestClient

import app.cloud.accounts as accounts_module
from app.cloud.provider import CloudProviderUnauthenticated, CloudProviderUnavailable
from app.main import create_app
from app.settings import Settings
from test_cloud_lab_api import FIXTURE, FakeProvider, FakeUploader, assert_error, canonical

API = "/api/v1/cloud/accounts"
ORIGIN = "https://editor.example.test"
BASE = "https://api.example.test"
HEADERS = {"Origin": ORIGIN}
FIRST = ("first-fixture", "device", "channel")
SECOND = ("second-fixture", "device", "channel")


@pytest.fixture
def setup(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        allowed_origins=[ORIGIN, "https://preview.example.test"],
        cloud_accounts_origin=ORIGIN,
        cloud_accounts_key="a1" * 32,
        cloud_accounts_dir=tmp_path / "accounts",
        cloud_backup_dir=tmp_path / "admin",
        cloud_write_enabled=True,
    )
    first = FakeProvider(FIXTURE.read_bytes())
    second = FakeProvider(canonical(json.loads(FIXTURE.read_bytes()) | {"cloudSaveId": "second-subject"}))
    providers = {FIRST: first, SECOND: second}
    uploads = {values: FakeUploader(provider) for values, provider in providers.items()}
    monkeypatch.setattr(accounts_module, "ModernCloudSaveProvider", lambda *values: providers[values])
    monkeypatch.setattr(accounts_module, "BlobSaveUploader", lambda *values, enabled: uploads[values])
    app = create_app(settings)
    store = app.state.cloud_accounts
    client = TestClient(app, base_url=BASE)
    return settings, store, app, client, providers, uploads


def issue(store, values=FIRST, *, write=True, expires=None):
    return store.issue(values[0], values, expires=expires or int(time()) + 600, can_write=write)


def claim(client, ticket):
    response = client.post(API + "/claim", json={"ticket": ticket}, headers=HEADERS)
    assert response.status_code == 200, response.text
    return response


def endpoint(account, name):
    return f"{API}/{account}/{name}"


def prepare(client, account):
    source = client.get(endpoint(account, "save")).json()
    assert "downloaded_at" in source
    response = client.post(endpoint(account, "prepare"), headers=HEADERS,
                           json={"new_gems": 1001, "source_sha256": source["sha256"]})
    assert response.status_code == 200, response.text
    return response.json()


def confirmation(draft):
    return {"backup_id": draft["backup"]["id"], "expected_sha256": draft["candidate_sha256"],
            "confirmation": "SUBIR"}


def test_unavailable_login_never_collects_credentials_and_reports_missing_config():
    client = TestClient(create_app(Settings(_env_file=None)), base_url=BASE)
    status = client.get(API)
    assert status.json()["configured"] is False
    assert status.json()["storage_status"] == "misconfigured"
    assert status.json()["problem_code"] == "cloud_accounts_origin"
    assert status.json()["password_login_available"] is False
    rejected = client.post(API + "/login", json={"password": "ignored-fixture-password"})
    assert_error(rejected, 503, "cloud_login_unavailable")
    assert "ignored-fixture-password" not in rejected.text


def test_origin_trailing_slash_is_canonicalized_so_browser_origin_stays_exact(setup):
    settings, _, _, _, *_ = setup
    app = create_app(settings.model_copy(update={"cloud_accounts_origin": ORIGIN + "/"}))
    assert app.state.cloud_accounts.origin == ORIGIN
    client = TestClient(app, base_url=BASE)
    assert client.get(API, headers=HEADERS).json()["storage_status"] == "ready"
    assert_error(client.get(API, headers={"Origin": ORIGIN + "/"}), 403, "cloud_origin_denied")


def test_disabled_login_checks_origin_without_parsing_the_body(setup):
    _, _, _, client, *_ = setup
    payload = {"content": b"{" + b"private-fixture" * 1000}
    assert_error(client.post(API + "/login", headers=HEADERS | {"Content-Type": "application/json"}, **payload),
                 503, "cloud_login_unavailable")
    assert_error(client.post(API + "/login", headers={"Content-Type": "application/json"}, **payload),
                 403, "cloud_origin_denied")


def test_accounts_storage_failure_does_not_mark_api_unavailable(setup, monkeypatch, caplog):
    _, store, _, client, *_ = setup

    def unavailable():
        raise sqlite3.OperationalError("private-fixture")

    with monkeypatch.context() as temporary:
        temporary.setattr(store, "connect", unavailable)
        response = client.get(API, headers=HEADERS)
        assert_error(response, 503, "cloud_accounts_storage")
        assert response.headers["access-control-allow-origin"] == ORIGIN
        assert "private-fixture" not in response.text + caplog.text
        assert client.get("/api/v1/health").status_code == 200
    assert client.get(API, headers=HEADERS).json()["storage_status"] == "ready"


@pytest.mark.usefixtures("legacy_gems_policy")
def test_logout_revokes_browser_cookie_and_cloud_session_without_affecting_second_owner(setup):
    _, store, app, client, *_ = setup
    account = claim(client, issue(store)).json()["accounts"][0]["id"]
    other = TestClient(app, base_url=BASE)
    other_id = claim(other, issue(store, SECOND)).json()["accounts"][0]["id"]
    assert_error(other.get(endpoint(account, "save")), 404, "cloud_account_missing")
    draft = prepare(client, account)
    pending_reconnect = issue(store)
    old_session = client.cookies.get("__Host-sk_under")
    assert client.get(API).json()["session_active"] is True
    assert_error(client.post(API + "/logout", json={}), 403, "cloud_origin_denied")

    response = client.post(API + "/logout", headers=HEADERS, json={})
    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"] and "Secure" in response.headers["set-cookie"]
    assert client.get(API).json()["session_active"] is False
    replay = TestClient(app, base_url=BASE, cookies={"__Host-sk_under": old_session})
    assert_error(replay.get(endpoint(account, "save")), 401, "cloud_browser_required")
    assert_error(replay.post(API + "/claim", headers=HEADERS, json={"ticket": pending_reconnect}),
                 404, "cloud_grant_invalid")
    assert other.get(endpoint(other_id, "save")).status_code == 200

    assert claim(client, issue(store)).json()["accounts"][0]["id"] == account
    assert client.get(endpoint(account, "backups")).json()["backups"][0]["id"] == draft["backup"]["id"]
    assert_error(replay.get(endpoint(account, "save")), 401, "cloud_browser_required")


def test_claim_checks_origin_replays_and_cookie_privacy(setup):
    settings, store, app, client, *_ = setup
    ticket = issue(store)
    for headers in ({}, {"Origin": "https://preview.example.test"}):
        assert_error(client.post(API + "/claim", headers=headers, json={"ticket": ticket}),
                     403, "cloud_origin_denied")
    preflight = client.options(API + "/claim", headers={
        "Origin": ORIGIN, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    })
    assert preflight.headers["access-control-allow-credentials"] == "true"
    response = claim(client, ticket)
    cookie = response.headers["set-cookie"]
    assert "__Host-sk_under=" in cookie and "HttpOnly" in cookie and "Secure" in cookie
    assert "SameSite=strict" in cookie and "Path=/" in cookie and "Domain=" not in cookie
    assert ticket not in response.text
    assert_error(client.post(API + "/claim", headers=HEADERS, json={"ticket": ticket}),
                 404, "cloud_grant_invalid")
    alternate = TestClient(app, base_url=BASE)
    reconnect = issue(store)
    assert_error(alternate.post(API + "/claim", headers=HEADERS, json={"ticket": reconnect}),
                 409, "cloud_account_linked")
    claim(client, reconnect)
    raw = store.database.read_bytes()
    assert FIRST[0].encode() in raw  # local label is public to the owner
    assert b'"device"' not in raw and ticket.encode() not in raw
    assert client.cookies.get("__Host-sk_under").encode() not in raw
    assert store.database.stat().st_mode & 0o777 == 0o600
    wrong_key = create_app(settings.model_copy(update={"cloud_accounts_key": type(settings.cloud_accounts_key)("b2" * 32)}))
    assert not TestClient(wrong_key, base_url=BASE).get(API).json()["configured"]


@pytest.mark.usefixtures("legacy_gems_policy")
def test_switch_accounts_reject_cross_account_access_and_preserve_browser_after_restart(setup):
    settings, store, app, client, *_ = setup
    first = claim(client, issue(store)).json()["accounts"][0]["id"]
    second = next(item["id"] for item in claim(client, issue(store, SECOND)).json()["accounts"]
                  if item["id"] != first)
    draft = prepare(client, first)
    backup_id = draft["backup"]["id"]
    assert client.get(endpoint(second, "backups")).json() == {"backups": []}
    foreign = client.post(endpoint(second, "verify"), json={"backup_id": backup_id}, headers=HEADERS)
    assert_error(foreign, 404, "backup_not_found")
    stranger = TestClient(app, base_url=BASE)
    assert_error(stranger.get(endpoint(first, "backups")), 401, "cloud_browser_required")
    with stranger:
        stranger.cookies.set("__Host-sk_under", "f" * 43, domain="api.example.test", path="/")
        assert_error(stranger.get(endpoint(first, "save")), 401, "cloud_browser_required")
    restarted = TestClient(create_app(settings), base_url=BASE, cookies=client.cookies)
    assert len(restarted.get(API).json()["accounts"]) == 2
    response = restarted.post(endpoint(first, "rename"), headers=HEADERS, json={"label": "Local"})
    assert any(item["label"] == "Local" for item in response.json()["accounts"])
    unlinked = restarted.post(endpoint(first, "unlink"), headers=HEADERS, json={"confirmation": "DESVINCULAR"})
    assert [item["id"] for item in unlinked.json()["accounts"]] == [second]
    assert_error(restarted.get(endpoint(first, "backups")), 404, "cloud_account_missing")


@pytest.mark.usefixtures("legacy_gems_policy")
def test_confirm_checks_concurrency_and_integrity_and_restores(setup):
    _, store, _, client, providers, uploads = setup
    account = claim(client, issue(store)).json()["accounts"][0]["id"]
    provider = providers[FIRST]
    original = provider.payload
    draft = prepare(client, account)
    payload = confirmation(draft)
    provider.payload = canonical(json.loads(original) | {"gameData": {"gems": 1003}})
    assert_error(client.post(endpoint(account, "prepare"), headers=HEADERS,
                             json={"new_gems": 1001, "source_sha256": draft["backup"]["original_sha256"]}),
                 409, "cloud_remote_changed")
    assert_error(client.post(endpoint(account, "confirm"), headers=HEADERS, json=payload),
                 409, "cloud_remote_changed")
    provider.payload = original
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda _: client.post(endpoint(account, "confirm"), headers=HEADERS, json=payload), range(2)
        ))
    assert sorted(result.status_code for result in results) == [200, 409]
    assert next(result for result in results if result.status_code == 200).json()["persisted"]
    assert len(uploads[FIRST].calls) == 1
    assert client.get(endpoint(account, "backups")).json()["backups"][0]["confirmed"]
    backup = store.root / "backups" / account / payload["backup_id"]
    restore = {"backup_id": payload["backup_id"], "confirmation": "RESTAURAR"}
    (backup / "original.json").write_bytes(b"corrupt")
    assert_error(client.post(endpoint(account, "restore"), headers=HEADERS, json=restore), 500, "backup_integrity")
    (backup / "original.json").write_bytes(original)
    result = client.post(endpoint(account, "restore"), headers=HEADERS, json=restore)
    assert result.json()["persisted"] and provider.payload == original


def test_expiry_network_and_remote_identity(setup, monkeypatch):
    _, store, _, client, providers, _ = setup
    account = claim(client, issue(store)).json()["accounts"][0]["id"]
    provider = providers[FIRST]

    def fail(error):
        def download(*_):
            raise error("provider fixture")
        return download

    with monkeypatch.context() as temporary:
        temporary.setattr(provider, "download", fail(CloudProviderUnavailable))
        assert_error(client.get(endpoint(account, "save")), 502, "cloud_provider_unavailable")
        assert client.get(API).json()["accounts"][0]["connected"]
        temporary.setattr(provider, "download", fail(CloudProviderUnauthenticated))
        assert_error(client.get(endpoint(account, "save")), 409, "cloud_session_expired")
    assert not client.get(API).json()["accounts"][0]["connected"]
    assert_error(client.get(endpoint(account, "save")), 409, "cloud_session_expired")
    claim(client, issue(store))
    assert client.get(API).json()["accounts"][0]["connected"]
    provider.payload = providers[SECOND].payload
    assert_error(client.get(endpoint(account, "save")), 422, "cloud_account_mismatch")


@pytest.mark.usefixtures("legacy_gems_policy")
def test_uncertain_upload_requires_a_fresh_edit_and_global_guard_survives_restart(setup, monkeypatch):
    settings, store, _, client, _, uploads = setup
    account = claim(client, issue(store)).json()["accounts"][0]["id"]
    draft = prepare(client, account)
    payload = confirmation(draft)
    writable = endpoint(account, "confirm")
    no_write = TestClient(create_app(settings.model_copy(update={"cloud_write_enabled": False})),
                          base_url=BASE, cookies=client.cookies)
    assert_error(no_write.post(writable, headers=HEADERS, json=payload), 503, "cloud_write_disabled")
    uploader = uploads[FIRST]

    def timeout(aggregate):
        uploader.calls.append(aggregate)
        raise CloudProviderUnavailable("timeout")

    monkeypatch.setattr(uploader, "upload", timeout)
    assert_error(client.post(writable, headers=HEADERS, json=payload), 502, "cloud_provider_unavailable")
    restarted = TestClient(create_app(settings), base_url=BASE, cookies=client.cookies)
    assert_error(restarted.post(writable, headers=HEADERS, json=payload), 409, "backup_already_confirmed")
    assert len(uploader.calls) == 1

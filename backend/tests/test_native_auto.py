"""Autenticación autónoma: identidad generada, reutilización y límites.

Estas pruebas no tocan la red. El cliente de autenticación y el proveedor de
BlobSave se inyectan; lo que se comprueba es que el servidor no exige un
``unique_id`` aprovisionado, conserva el par generado y respeta la espera que
impone el proveedor cuando vincula un dispositivo nuevo.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.cloud.provider import CloudProviderDeviceBindingThrottled, CloudProviderUnavailable
from app.main import create_app
from app.native.client import GatewaySession
from app.native.identity import is_generated_distro, is_generated_unique
from app.native.portal import PortalPlayer, PortalProfile
from app.settings import Settings
from test_cloud_lab_api import FakeProvider, canonical

API = "/api/v1/cloud/native"
ORIGIN = "http://127.0.0.1:5173"
FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"
PAYLOAD_A = FIXTURE.read_bytes()
PAYLOAD_B = canonical(json.loads(PAYLOAD_A) | {"cloudSaveId": "sintetico-cuenta-beta"})
HEADERS = {"Origin": ORIGIN}


PORTAL_DISTRO_A = "11111111-1111-4111-8111-111111111111"
PORTAL_DISTRO_B = "22222222-2222-4222-8222-222222222222"
PORTAL_DISTRO_EMPTY = "33333333-3333-4333-8333-333333333333"


class FakePortal:
    def __init__(self, players=None, *, error=None):
        self.players = players or {
            "a@example.test": [(11, PORTAL_DISTRO_A)],
            "b@example.test": [(22, PORTAL_DISTRO_B)],
        }
        self.error = error
        self.calls = 0

    def profile(self, email, password):
        self.calls += 1
        if self.error is not None:
            raise self.error
        entries = self.players.get(email)
        if entries is None:
            from app.native.errors import NativePortalRejected

            raise NativePortalRejected("cuenta no válida")
        return PortalProfile(
            email=email,
            players=tuple(
                PortalPlayer(
                    pid=pid, game_id="1", game_name="Soulknight",
                    register_distro_id=distro, last_login_distro_id=distro,
                )
                for pid, distro in entries
            ),
        )


class AutoAuth:
    """Acepta el par generado por el servidor y devuelve una identidad fija."""

    def __init__(self, accounts=None, *, player_by_distro=None):
        self.accounts = accounts or {
            "a@example.test": {"password": "pass-a", "uid": 1, "player_id": 11},
            "b@example.test": {"password": "pass-b", "uid": 2, "player_id": 22},
        }
        self.player_by_distro = dict(player_by_distro or {})
        self.calls: list[dict[str, object]] = []

    def authenticate(self, email, password, *, distribution, distro_id, unique_id=None):
        self.calls.append(
            {
                "email": email,
                "distro_id": distro_id,
                "unique_id": unique_id,
                "distribution": distribution.id,
            }
        )
        account = self.accounts.get(email)
        if account is None or password != account["password"]:
            from app.native.client import NativeAuthRejected

            raise NativeAuthRejected(401)
        if not is_generated_distro(distro_id):
            from app.native.client import NativeDistributionRejected

            raise NativeDistributionRejected("distro no generada")
        return GatewaySession(
            token=f"token-{account['uid']}-{len(self.calls)}",
            uid=account["uid"],
            email=email,
            player_id=self.player_by_distro.get(distro_id, account["player_id"]),
            expire=int(time.time()) + 3600,
            distro_id=distro_id,
        )


class BindingProvider:
    def __init__(self, retry_after=120, payload=PAYLOAD_A):
        self.retry_after = retry_after
        self.payload = payload
        self.calls = 0

    def download(self, limit=8 * 1024 * 1024):
        self.calls += 1
        raise CloudProviderDeviceBindingThrottled(self.retry_after)


def make_auto(tmp_path, *, now=None, provider=None, portal=None, auth=None):
    settings = Settings(
        _env_file=None,
        env="development",
        allowed_origins=[ORIGIN],
        native_auth_enabled=True,
        native_write_enabled=False,
        native_store_key="ab" * 32,
        native_store_dir=tmp_path / "native",
        native_backup_dir=tmp_path / "native-backups",
        native_origin=ORIGIN,
        native_auto_identity=True,
        native_login_attempts=20,
        native_login_window_seconds=300,
    )
    app = create_app(settings)
    service = app.state.native_service
    assert service is not None
    auth = auth or AutoAuth()
    portal = portal or FakePortal()
    service.client = auth
    service.portal_client = portal
    providers = {"1": provider or FakeProvider(PAYLOAD_A), "2": FakeProvider(PAYLOAD_B)}
    service.provider_factory = lambda token, unique, distro, distribution: providers.get(
        token.split("-")[1], FakeProvider(PAYLOAD_A)
    )
    service.uploader_factory = lambda token, unique, distro, distribution: None
    if now is not None:
        service.now = now
        service.store.now = now
    client = TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000))
    return {
        "settings": settings,
        "app": app,
        "service": service,
        "store": service.store,
        "client": client,
        "auth": auth,
        "portal": portal,
        "providers": providers,
    }


def login(client, email="a@example.test", password="pass-a"):
    return client.post(
        API + "/login",
        headers=HEADERS,
        json={"distribution": "android-global", "email": email, "password": password},
    )


def test_auto_login_creates_and_reuses_a_generated_identity(tmp_path):
    env = make_auto(tmp_path)
    first = login(env["client"])
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["active"] is True
    assert body["auto_identity"] is True
    assert body["installation_ready"] is True
    assert body["save"]["gems"] == 1000
    profile = env["store"].list_profiles()[0]
    assert profile.auto_generated is True
    assert profile.bound is True
    assert is_generated_distro(profile.distro_id)
    assert is_generated_unique(profile.unique_id)
    assert body["account"]["label"] == profile.label
    assert "distro" not in json.dumps(body)
    assert "unique" not in json.dumps(body)

    second = login(env["client"])
    assert second.status_code == 200, second.text
    profiles = env["store"].list_profiles()
    assert len(profiles) == 1
    assert profiles[0].id == profile.id
    assert env["auth"].calls[0]["distro_id"] == env["auth"].calls[1]["distro_id"]
    assert env["auth"].calls[0]["unique_id"] == env["auth"].calls[1]["unique_id"]
    assert env["auth"].calls[0]["unique_id"] == profile.unique_id


def test_failed_credentials_do_not_leave_an_unbound_auto_profile(tmp_path):
    env = make_auto(tmp_path)
    response = login(env["client"], password="wrong")
    assert response.status_code == 401
    assert env["store"].list_profiles() == []


def test_binding_throttle_is_reported_and_not_retried_automatically(tmp_path):
    env = make_auto(tmp_path, provider=BindingProvider(retry_after=81970))
    first = login(env["client"])
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["save_error"] == "native_device_binding_throttled"
    assert body["binding_wait_until"] is not None
    profile = env["store"].list_profiles()[0]
    assert profile.binding_wait_until is not None
    # Un segundo login reutiliza el perfil y no vuelve a llamar al proveedor.
    second = login(env["client"])
    assert second.status_code == 200, second.text
    assert second.json()["save_error"] == "native_device_binding_throttled"
    assert len(env["store"].list_profiles()) == 1


def test_save_while_binding_wait_returns_429_without_network(tmp_path):
    env = make_auto(tmp_path, provider=BindingProvider(retry_after=600))
    assert login(env["client"]).status_code == 200
    calls_before = env["providers"]["1"].calls
    response = env["client"].get(API + "/save", headers=HEADERS)
    assert response.status_code == 429, response.text
    assert response.headers["Retry-After"]
    assert response.json()["error"]["code"] == "native_device_binding_throttled"
    assert env["providers"]["1"].calls == calls_before


def test_after_wait_the_same_identity_can_download(tmp_path):
    clock = [int(time.time())]
    provider = BindingProvider(retry_after=120)
    env = make_auto(tmp_path, now=lambda: clock[0], provider=provider)
    assert login(env["client"]).status_code == 200
    assert env["store"].list_profiles()[0].binding_wait_until is not None
    # El proveedor deja de limitar; el mismo perfil reintenta tras la espera.
    provider.download = lambda limit=8 * 1024 * 1024: FakeProvider(PAYLOAD_A).download(limit)
    clock[0] += 121
    response = env["client"].get(API + "/save", headers=HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()["gems"] == 1000
    assert env["store"].list_profiles()[0].binding_wait_until is None


def test_two_auto_accounts_are_isolated(tmp_path):
    env = make_auto(tmp_path)
    first = login(env["client"], email="a@example.test", password="pass-a")
    assert first.status_code == 200
    cookie_a = env["client"].cookies.get("sk_native_dev")
    assert cookie_a
    env["client"].cookies.clear()
    second = login(env["client"], email="b@example.test", password="pass-b")
    assert second.status_code == 200
    cookie_b = env["client"].cookies.get("sk_native_dev")
    assert cookie_b and cookie_b != cookie_a
    profiles = env["store"].list_profiles()
    assert len(profiles) == 2
    assert profiles[0].subject != profiles[1].subject
    assert profiles[0].unique_id != profiles[1].unique_id
    assert {profile.email_hash for profile in profiles} == {
        env["store"].hash_email("a@example.test"),
        env["store"].hash_email("b@example.test"),
    }
    # La cookie de A no puede operar como B.
    env["client"].cookies.clear()
    env["client"].cookies.set("sk_native_dev", cookie_a)
    save_a = env["client"].get(API + "/save", headers=HEADERS)
    assert save_a.status_code == 200
    assert save_a.json()["gems"] == 1000
    env["client"].cookies.clear()
    env["client"].cookies.set("sk_native_dev", cookie_b)
    save_b = env["client"].get(API + "/save", headers=HEADERS)
    assert save_b.status_code == 200
    # El fixture B conserva el mismo número de gemas, pero el sujeto de
    # guardado es distinto y el respaldo se guarda bajo otro sujeto.
    assert env["store"].list_profiles()[0].subject != env["store"].list_profiles()[1].subject


class NoSaveProvider:
    def __init__(self):
        self.calls = 0

    def download(self, limit=8 * 1024 * 1024):
        self.calls += 1
        raise CloudProviderUnavailable("sin partida", provider_code=100504)


class PortalChallenge:
    def __init__(self, error):
        self.error = error
        self.calls = 0

    def profile(self, email, password):
        self.calls += 1
        raise self.error


def test_selects_the_portal_player_that_has_the_save(tmp_path):
    portal = FakePortal({"a@example.test": [(99, PORTAL_DISTRO_EMPTY), (11, PORTAL_DISTRO_A)]})
    auth = AutoAuth(player_by_distro={PORTAL_DISTRO_EMPTY: 99, PORTAL_DISTRO_A: 11})
    env = make_auto(tmp_path, portal=portal, auth=auth)
    empty = NoSaveProvider()
    env["service"].provider_factory = lambda token, unique, distro, distribution: (
        empty if distro == PORTAL_DISTRO_EMPTY else FakeProvider(PAYLOAD_A)
    )
    response = login(env["client"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["save"]["gems"] == 1000
    profiles = env["store"].list_profiles()
    assert len(profiles) == 1
    assert profiles[0].distro_id == PORTAL_DISTRO_A
    assert profiles[0].bound is True
    # El primer jugador no tenía partida y no se creó un perfil para él.
    assert profiles[0].last_save_error is None
    assert portal.calls == 1


def test_no_cloud_save_is_reported_without_creating_a_false_download(tmp_path):
    portal = FakePortal({"a@example.test": [(11, PORTAL_DISTRO_A)]})
    env = make_auto(tmp_path, portal=portal)
    env["service"].provider_factory = lambda token, unique, distro, distribution: NoSaveProvider()
    response = login(env["client"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["active"] is True
    assert body["save"] is None
    assert body["save_error"] == "native_no_cloud_save"
    profile = env["store"].list_profiles()[0]
    assert profile.last_save_error == "native_no_cloud_save"
    assert profile.binding_wait_until is None


def test_portal_challenge_is_reported_and_does_not_create_a_profile(tmp_path):
    from app.native.errors import NativePortalChallengeRequired

    portal = PortalChallenge(NativePortalChallengeRequired("captcha"))
    env = make_auto(tmp_path, portal=portal)
    response = login(env["client"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "native_portal_challenge_required"
    assert env["store"].list_profiles() == []
    assert portal.calls == 1


def test_new_account_without_portal_players_gets_a_generated_identity(tmp_path):
    portal = FakePortal({"a@example.test": []})
    env = make_auto(tmp_path, portal=portal)
    env["service"].provider_factory = lambda token, unique, distro, distribution: NoSaveProvider()
    response = login(env["client"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["auto_identity"] is True
    assert body["save_error"] == "native_no_cloud_save"
    profile = env["store"].list_profiles()[0]
    assert is_generated_distro(profile.distro_id)
    assert is_generated_unique(profile.unique_id)


def test_portal_is_consulted_only_on_the_first_auto_login(tmp_path):
    portal = FakePortal()
    env = make_auto(tmp_path, portal=portal)
    assert login(env["client"]).status_code == 200
    assert portal.calls == 1
    assert login(env["client"]).status_code == 200
    assert portal.calls == 1


def test_reuses_a_bound_phase_6_8_profile_without_binding_a_second_device(tmp_path):
    env = make_auto(tmp_path)
    store = env["store"]
    subject = store.identity_subject(email="a@example.test", uid=1, player_id=11)
    existing = store.create_profile(
        label="Perfil anterior", distribution_id="android-global",
        distro_id=PORTAL_DISTRO_A, unique_id="xiaomioutseas_" + "a" * 16,
        allow_write=False,
    )
    store.bind(existing.id, subject)
    provider = FakeProvider(PAYLOAD_A)
    env["service"].provider_factory = lambda token, unique, distro, distribution: provider
    response = login(env["client"])
    assert response.status_code == 200, response.text
    profiles = store.list_profiles()
    assert len(profiles) == 1
    assert profiles[0].id == existing.id
    assert profiles[0].email_hash == store.hash_email("a@example.test")
    assert profiles[0].distro_id == PORTAL_DISTRO_A
    assert provider.calls == 1
    assert env["portal"].calls == 1


class RejectOldDistroAuth(AutoAuth):
    def authenticate(self, email, password, *, distribution, distro_id, unique_id=None):
        if distro_id == PORTAL_DISTRO_EMPTY:
            from app.native.client import NativeAuthRejected

            raise NativeAuthRejected(401)
        return super().authenticate(
            email, password, distribution=distribution, distro_id=distro_id, unique_id=unique_id
        )


def test_updates_a_stale_existing_profile_after_identity_verification(tmp_path):
    env = make_auto(tmp_path, auth=RejectOldDistroAuth())
    store = env["store"]
    subject = store.identity_subject(email="a@example.test", uid=1, player_id=11)
    existing = store.create_profile(
        label="Perfil antiguo", distribution_id="android-global",
        distro_id=PORTAL_DISTRO_EMPTY, unique_id="xiaomioutseas_" + "b" * 16,
        allow_write=False,
    )
    store.bind(existing.id, subject)
    env["service"].provider_factory = lambda token, unique, distro, distribution: FakeProvider(PAYLOAD_A)
    response = login(env["client"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["save"]["gems"] == 1000
    profiles = store.list_profiles()
    assert len(profiles) == 1 and profiles[0].id == existing.id
    assert profiles[0].distro_id == PORTAL_DISTRO_A
    assert profiles[0].unique_id != existing.unique_id

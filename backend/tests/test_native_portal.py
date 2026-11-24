"""Validación de la respuesta del portal oficial de cuentas."""

from __future__ import annotations

import pytest

from app.native.errors import NativePortalIdentityMismatch, NativePortalUnavailable
from app.native.portal import PROFILE_QUERY, parse_portal_profile


def document(players, email="holder@example.test"):
    return {
        "data": {
            "getUserProfileByToken": {
                "accountInfo": {"userId": "1", "email": email},
                "gamesInfo": [{"gameId": "1", "players": players}],
            }
        }
    }


def player(pid, distro, *, last=None, game="1", name="Soulknight"):
    return {
        "pid": pid,
        "gameId": game,
        "gameName": name,
        "registerDistroId": distro,
        "lastLoginDistroId": last or distro,
    }


def test_profile_query_requests_the_observed_distro_fields():
    assert "registerDistroId" in PROFILE_QUERY
    assert "lastLoginDistroId" in PROFILE_QUERY
    assert "getUserProfileByToken" in PROFILE_QUERY


def test_parses_players_and_prefers_last_login_distro():
    first = "11111111-1111-4111-8111-111111111111"
    second = "22222222-2222-4222-8222-222222222222"
    parsed = parse_portal_profile(
        document([player(11, first), player(22, second)]), "holder@example.test"
    )
    assert [item.pid for item in parsed.players] == [11, 22]
    assert parsed.players[0].distro_id == first
    assert parsed.players[0].public()["distro_id_sha256"]


def test_uses_register_distro_when_last_is_missing():
    distro = "33333333-3333-4333-8333-333333333333"
    entry = player(11, distro)
    entry["lastLoginDistroId"] = None
    parsed = parse_portal_profile(document([entry]), "holder@example.test")
    assert parsed.players[0].distro_id == distro


def test_ignores_other_games_and_duplicate_distros():
    distro = "44444444-4444-4444-8444-444444444444"
    parsed = parse_portal_profile(
        document([
            player(11, distro),
            player(12, distro),
            player(13, "55555555-5555-4555-8555-555555555555", game="2", name="Other Game"),
        ]),
        "holder@example.test",
    )
    assert len(parsed.players) == 2
    assert [item.pid for item in parsed.soulknight_players()] == [11]


def test_rejects_a_different_account():
    with pytest.raises(NativePortalIdentityMismatch):
        parse_portal_profile(document([], email="other@example.test"), "holder@example.test")


@pytest.mark.parametrize("payload", [{}, {"data": {}}, {"data": {"getUserProfileByToken": {}}}])
def test_rejects_incomplete_profiles(payload):
    with pytest.raises(NativePortalUnavailable):
        parse_portal_profile(payload, "holder@example.test")


def test_malformed_players_are_ignored():
    parsed = parse_portal_profile(
        document([
            {"pid": "bad", "registerDistroId": "x"},
            {"pid": 11, "registerDistroId": "not-a-uuid"},
            {"pid": 12, "registerDistroId": None},
        ]),
        "holder@example.test",
    )
    assert parsed.players == ()


def test_portal_client_uses_the_observed_redwood_flow():
    from app.native.portal import PortalClient

    calls = []

    def fetch(method, url, headers, body):
        calls.append((method, url, dict(headers), body))
        if url.endswith("/login"):
            return 200, {"Content-Type": "text/html"}, b"<html></html>"
        if url.endswith("/.redwood/functions/auth"):
            return 200, {"Set-Cookie": "session=session-token; Path=/"}, b'{"id":1}'
        if url.endswith("/api/csrf-refresh"):
            return 200, {"Set-Cookie": "csrf-token=csrf-token; Path=/"}, b"{}"
        if url.endswith("/graphql"):
            return 200, {"Content-Type": "application/json"}, __import__("json").dumps(
                document([player(11, "66666666-6666-4666-8666-666666666666")])
            ).encode()
        raise AssertionError(url)

    client = PortalClient(base_url="https://portal.test", fetch=fetch)
    profile = client.profile("holder@example.test", "fixture-password")
    assert len(profile.players) == 1
    graphql = calls[-1]
    assert graphql[2]["auth-provider"] == "chillyRoomAuth"
    assert graphql[2]["Authorization"] == "Bearer session-token"
    assert graphql[2]["x-csrf-token"] == "csrf-token"
    assert graphql[2]["Apollo-Require-Preflight"] == "1"
    assert b"fixture-password" not in graphql[3]
    auth_calls = [call for call in calls if call[1].endswith("/.redwood/functions/auth")]
    assert len(auth_calls) == 1 and b"fixture-password" in auth_calls[0][3]
    assert all(b"fixture-password" not in (call[3] or b"") for call in calls if call not in auth_calls)


def test_portal_client_rejects_bad_credentials_without_echoing_them():
    from app.native.errors import NativePortalRejected
    from app.native.portal import PortalClient

    def fetch(method, url, headers, body):
        if url.endswith("/login"):
            return 200, {}, b"<html></html>"
        return 400, {}, b'{"error":"bad","detail":"secret-password"}'

    with pytest.raises(NativePortalRejected) as error:
        PortalClient(base_url="https://portal.test", fetch=fetch).profile(
            "holder@example.test", "secret-password"
        )
    assert "secret-password" not in str(error.value)


def test_portal_client_reports_a_challenge_without_retrying():
    from app.native.errors import NativePortalChallengeRequired
    from app.native.portal import PortalClient

    count = {"n": 0}

    def fetch(method, url, headers, body):
        count["n"] += 1
        if url.endswith("/login"):
            return 200, {}, b"<html></html>"
        return 403, {}, b"captcha"

    with pytest.raises(NativePortalChallengeRequired):
        PortalClient(base_url="https://portal.test", fetch=fetch).profile("a@b.test", "pw")
    assert count["n"] == 2

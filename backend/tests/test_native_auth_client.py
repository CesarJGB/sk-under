import gzip
import json
from time import time

import pytest

from app.native.client import (
    NativeAuthClient,
    NativeAuthProtocol,
    NativeAuthRejected,
    NativeAuthUnavailable,
    NativeDistributionRejected,
    NativeProviderThrottled,
    build_login_body,
)
from app.native.distributions import require_enabled
from app.native.errors import NativeIdentityMismatch

DISTRIBUTION = require_enabled("android-global")
DISTRO = "11111111-2222-4333-8444-555555555555"
NOW = 1_800_000_000.0


def success_document(**changes):
    document = {
        "session": {"uid": "42", "token": "s" * 32, "expire": str(int(NOW + 3600))},
        "user": {"id": 42, "email": "holder@example.test"},
        "player": {"id": 77, "status": 0},
        "legacyGateway": {"token": "l" * 20, "host": "legacy.example.test"},
        "isNewUser": False,
        "isNewPlayer": False,
    }
    for key, value in changes.items():
        section, _, field = key.partition(".")
        if field:
            document[section][field] = value
        else:
            document[section] = value
    return document


def responder(status=200, document=None, *, encoding="", raw=None, error=None):
    calls = []

    def transport(url, body, headers, timeout):
        calls.append({"url": url, "body": json.loads(body), "headers": headers, "timeout": timeout})
        if error is not None:
            raise error
        payload = raw if raw is not None else json.dumps(document if document is not None else success_document()).encode()
        return status, encoding, payload

    return transport, calls


def client(transport):
    return NativeAuthClient(transport=transport, now=lambda: NOW)


def login(auth, email="holder@example.test", password="fixture-password"):
    return auth.authenticate(email, password, distribution=DISTRIBUTION, distro_id=DISTRO)


def test_headers_and_body_follow_the_observed_contract():
    transport, calls = responder()
    session = login(client(transport))
    call = calls[0]
    assert call["url"] == "https://api-gateway.soulknight.chillyroom.com/UserAuth/Login"
    assert call["headers"]["x-distro-id"] == DISTRO
    assert call["headers"]["x-platform"] == "android"
    assert call["headers"]["x-app-version"] == "8.8.0"
    assert "x-unique-id" not in call["headers"]
    assert call["body"] == {
        "loginType": 3,
        "account": "holder@example.test",
        "password": "fixture-password",
        "credential": None,
    }
    assert session.uid == 42 and session.player_id == 77 and session.email == "holder@example.test"
    assert session.legacy_host == "legacy.example.test"


def test_gzip_response_is_decompressed_with_limits():
    transport, _ = responder(
        raw=gzip.compress(json.dumps(success_document()).encode()),
        encoding="gzip",
    )
    assert login(client(transport)).uid == 42
    body = build_login_body("holder@example.test", "fixture-password")
    assert b"loginType" in body and b"credential" in body


def test_distribution_rejection_and_throttling_are_typed():
    for status, code in ((502, 10003), (400, 10003)):
        transport, _ = responder(status, {"errorCode": code, "message": "private-body"})
        with pytest.raises(NativeDistributionRejected) as error:
            login(client(transport))
        assert "private-body" not in str(error.value)

    transport, _ = responder(429, {})
    with pytest.raises(NativeProviderThrottled):
        login(client(transport))


def test_credentials_are_rejected_without_echoing_the_upstream_body():
    transport, _ = responder(401, {"errorCode": 10001, "message": "private-account-detail"})
    with pytest.raises(NativeAuthRejected) as error:
        login(client(transport))
    assert "private-account-detail" not in str(error.value)
    assert "fixture-password" not in str(error.value)
    assert error.value.status == 401


def test_network_and_protocol_errors_are_typed():
    transport, _ = responder(error=OSError("private-network"))
    with pytest.raises(NativeAuthUnavailable):
        login(client(transport))

    transport, _ = responder(raw=b"x" * (1_048_576 + 1))
    with pytest.raises(NativeAuthProtocol):
        login(client(transport))

    transport, _ = responder(raw=b"not-json")
    with pytest.raises(NativeAuthProtocol):
        login(client(transport))

    transport, _ = responder(raw=gzip.compress(b"{}"), encoding="br")
    with pytest.raises(NativeAuthProtocol):
        login(client(transport))


@pytest.mark.parametrize(
    "change,message",
    [
        ({"session.uid": 99}, "usuario"),
        ({"user.email": "other@example.test"}, "correo"),
        ({"session.expire": int(NOW) - 10}, "caducada"),
        ({"player.id": 0}, "jugador"),
    ],
)
def test_identity_checks_reject_inconsistent_responses(change, message):
    transport, _ = responder(document=success_document(**change))
    with pytest.raises(NativeIdentityMismatch) as error:
        login(client(transport))
    assert message in str(error.value)


def test_invalid_arguments_do_not_reach_the_transport():
    transport, calls = responder()
    auth = client(transport)
    with pytest.raises(NativeDistributionRejected):
        auth.authenticate("holder@example.test", "fixture-password", distribution=DISTRIBUTION, distro_id="../bad")
    with pytest.raises(NativeAuthRejected):
        auth.authenticate("not-an-email", "fixture-password", distribution=DISTRIBUTION, distro_id=DISTRO)
    assert calls == []


def test_session_repr_hides_secrets():
    transport, _ = responder()
    session = login(client(transport))
    text = repr(session)
    assert "s" * 32 not in text
    assert "holder@example.test" not in text
    assert DISTRO not in text
    summary = session.summary()
    assert len(summary["token_sha256"]) == 64
    assert "s" * 32 not in json.dumps(summary)

"""Cuentas múltiples agrupadas por navegador y migración de sesión única."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from test_native_api import (
    API,
    COOKIE,
    HEADERS,
    add_account_b,
    assert_error,
    login,
    make_native,
    session_of,
)


def accounts_of(client):
    response = client.get(API + "/accounts", headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()["accounts"]


def account_header(account_id):
    return {**HEADERS, "X-SK-Account": account_id}


def test_second_account_does_not_revoke_the_first(tmp_path):
    env = make_native(tmp_path)
    profile_b = add_account_b(env)
    profile_a = next(
        item for item in env["store"].list_profiles() if item.label == "Instalación Android Global"
    )
    client = env["client"]

    first = login(client, profile=profile_a.id)
    assert first.status_code == 200, first.text
    account_a = first.json()["account_id"]
    browser_cookie = client.cookies.get(COOKIE)
    assert browser_cookie

    second = login(client, email="b@example.test", password="pass-b", profile=profile_b.id)
    assert second.status_code == 200, second.text
    account_b = second.json()["account_id"]
    assert account_a != account_b
    assert client.cookies.get(COOKIE) == browser_cookie

    listed = accounts_of(client)
    assert {item["id"] for item in listed} == {account_a, account_b}
    assert all(item["active"] for item in listed)
    assert {item["account"]["email"] for item in listed} == {
        "a@example.test",
        "b@example.test",
    }

    save_a = client.get(API + "/save", headers=account_header(account_a))
    assert save_a.status_code == 200, save_a.text
    save_b = client.get(API + "/save", headers=account_header(account_b))
    assert save_b.status_code == 200, save_b.text

    # Volver a autenticar la misma identidad reutiliza el selector y no duplica.
    again = login(client, profile=profile_a.id)
    assert again.status_code == 200, again.text
    assert again.json()["account_id"] == account_a
    assert {item["id"] for item in accounts_of(client)} == {account_a, account_b}


def test_account_selector_is_scoped_to_the_browser(tmp_path):
    env = make_native(tmp_path)
    profile_b = add_account_b(env)
    profile_a = next(
        item for item in env["store"].list_profiles() if item.label == "Instalación Android Global"
    )
    owner = env["client"]
    first = login(owner, profile=profile_a.id)
    assert first.status_code == 200
    account_a = first.json()["account_id"]

    other = TestClient(env["app"], base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50001))
    assert login(other, email="b@example.test", password="pass-b", profile=profile_b.id).status_code == 200
    assert accounts_of(other)[0]["account"]["email"] == "b@example.test"

    foreign = other.get(API + "/save", headers=account_header(account_a))
    assert_error(foreign, 403, "native_account_denied")
    assert_error(
        other.post(API + f"/accounts/{account_a}/logout", headers=HEADERS, json={}),
        403,
        "native_account_denied",
    )
    assert owner.get(API + "/save", headers=account_header(account_a)).status_code == 200


def test_logout_one_account_preserves_the_others(tmp_path):
    env = make_native(tmp_path)
    profile_b = add_account_b(env)
    profile_a = next(
        item for item in env["store"].list_profiles() if item.label == "Instalación Android Global"
    )
    client = env["client"]
    account_a = login(client, profile=profile_a.id).json()["account_id"]
    account_b = login(client, email="b@example.test", password="pass-b", profile=profile_b.id).json()[
        "account_id"
    ]

    response = client.post(API + f"/accounts/{account_b}/logout", headers=HEADERS, json={})
    assert response.status_code == 204, response.text
    assert_error(
        client.get(API + "/save", headers=account_header(account_b)),
        403,
        "native_account_denied",
    )
    assert client.get(API + "/save", headers=account_header(account_a)).status_code == 200
    assert [item["id"] for item in accounts_of(client)] == [account_a]

    # Desvincular no borra el perfil persistente ni los respaldos.
    assert env["store"].profile(profile_b.id).subject is not None


def test_legacy_single_session_is_migrated_without_invalidating_it(tmp_path):
    env = make_native(tmp_path)
    profile = next(
        item for item in env["store"].list_profiles() if item.label == "Instalación Android Global"
    )
    subject = env["store"].identity_subject(email="a@example.test", uid=1, player_id=11)
    env["store"].bind(profile.id, subject)
    cookie = "c" * 43
    env["store"].create_session(
        cookie,
        profile_id=profile.id,
        subject=subject,
        token="legacy-token",
        session_expire=int(time.time()) + 3600,
        email_hash=env["store"].hash_email("a@example.test"),
        uid_hash=env["store"].hash_uid(1),
        player_hash=env["store"].hash_player(11),
        email="a@example.test",
    )
    legacy = TestClient(
        env["app"],
        base_url="http://127.0.0.1:8000",
        client=("127.0.0.1", 50000),
        cookies={COOKIE: cookie},
    )

    listed = accounts_of(legacy)
    assert len(listed) == 1 and listed[0]["active"] is True
    assert listed[0]["account"]["email"] == "a@example.test"
    account_id = listed[0]["id"]
    assert legacy.get(API + "/save", headers=account_header(account_id)).status_code == 200
    assert session_of(legacy)["active"] is True

    # La cookie histórica sigue siendo la cookie de navegador tras reautenticar.
    reauth = login(legacy)
    assert reauth.status_code == 200, reauth.text
    assert reauth.json()["account_id"] == account_id
    assert legacy.cookies.get(COOKIE, domain="127.0.0.1") == cookie
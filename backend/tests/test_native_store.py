import hashlib
import hmac
import json
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.native.distributions import require_enabled
from app.native.errors import (
    NativeInstallationInvalid,
    NativeLoginThrottled,
    NativeProfileIdentityMismatch,
    NativeSaveIdentityMismatch,
    NativeSessionExpired,
    NativeSessionRequired,
    NativeStoreMisconfigured,
)
from app.native.store import NativeStore

KEY = bytes.fromhex("ab" * 32)
DISTRO = "distro-fixture"
UNIQUE = "unique-fixture"


def make_store(tmp_path: Path, **options) -> NativeStore:
    defaults = {
        "idle_seconds": 600,
        "absolute_seconds": 3600,
        "login_attempts": 3,
        "login_window_seconds": 60,
    }
    defaults.update(options)
    return NativeStore(tmp_path / "native", KEY, **defaults)


def profile(store: NativeStore, label="Cuenta A", *, unique=UNIQUE, allow_write=True):
    return store.create_profile(
        label=label,
        distribution_id="android-global",
        distro_id="distro-" + label.lower().replace(" ", "-"),
        unique_id=unique,
        allow_write=allow_write,
    )


def session_values(**changes):
    values = {
        "token": "t" * 32,
        "session_expire": int(time.time()) + 3600,
        "email_hash": "e" * 64,
        "uid_hash": "u" * 64,
        "player_hash": "p" * 64,
    }
    values.update(changes)
    return values


def test_profile_and_session_are_encrypted_and_bind_identity(tmp_path):
    store = make_store(tmp_path)
    item = profile(store)
    assert item.distro_id == "distro-cuenta-a"
    assert item.unique_id == UNIQUE
    assert item.public() == {
        "id": item.id, "label": "Cuenta A", "distribution": "android-global",
        "installation_ready": True, "bound": False, "write_allowed": True,
        "auto_generated": False, "binding_pending": False,
        "binding_wait_until": None, "last_save_error": None,
    }
    subject = store.identity_subject(email="holder@example.test", uid=42, player_id=77)
    bound = store.bind(item.id, subject)
    assert bound.bound and bound.subject == subject
    assert store.bind(item.id, subject).id == item.id
    other = store.identity_subject(email="other@example.test", uid=43, player_id=78)
    with pytest.raises(NativeProfileIdentityMismatch):
        store.bind(item.id, other)

    cookie = "c" * 43
    expires = store.create_session(
        cookie, profile_id=item.id, subject=subject, **session_values()
    )
    assert expires > int(time.time())
    current = store.session(cookie)
    assert current.profile.id == item.id and current.token == "t" * 32
    assert current.unique_id == UNIQUE
    raw = store.database.read_bytes()
    assert DISTRO.encode() not in raw and UNIQUE.encode() not in raw
    assert b"t" * 32 not in raw and cookie.encode() not in raw
    assert store.database.stat().st_mode & 0o777 == 0o600
    assert store.root.stat().st_mode & 0o777 == 0o700


def test_wrong_key_does_not_open_the_store(tmp_path):
    make_store(tmp_path)
    with pytest.raises(NativeStoreMisconfigured):
        NativeStore(tmp_path / "native", bytes.fromhex("cd" * 32))


def test_session_expiry_idle_and_revocation(tmp_path):
    store = make_store(tmp_path, idle_seconds=60)
    item = profile(store)
    subject = store.identity_subject(email="holder@example.test", uid=42, player_id=77)
    store.bind(item.id, subject)
    cookie = "d" * 43
    store.create_session(cookie, profile_id=item.id, subject=subject, **session_values())
    with sqlite3.connect(store.database) as db:
        db.execute("UPDATE sessions SET last_seen = ?", (int(time.time()) - 120,))
    with pytest.raises(NativeSessionExpired):
        store.session(cookie)
    with pytest.raises(NativeSessionRequired):
        store.session("f" * 43)

    cookie = "e" * 43
    store.create_session(cookie, profile_id=item.id, subject=subject, **session_values())
    with sqlite3.connect(store.database) as db:
        db.execute("UPDATE sessions SET session_expires = ?", (int(time.time()) - 1,))
    with pytest.raises(NativeSessionExpired):
        store.session(cookie)
    assert store.session_stats()[1] == 0

    cookie = "g" * 43
    store.create_session(cookie, profile_id=item.id, subject=subject, **session_values())
    store.revoke(cookie)
    with pytest.raises(NativeSessionRequired):
        store.session(cookie)


def test_installation_requires_the_bound_identity(tmp_path):
    store = make_store(tmp_path)
    item = profile(store, unique=None)
    subject = store.identity_subject(email="holder@example.test", uid=42, player_id=77)
    with pytest.raises(NativeProfileIdentityMismatch):
        store.set_installation(item.id, "unique-new", subject)
    store.bind(item.id, subject)
    updated = store.set_installation(item.id, "unique-new", subject)
    assert updated.unique_id == "unique-new"
    assert store.profile(item.id).installation_ready
    with pytest.raises(NativeInstallationInvalid):
        store.set_installation(item.id, "bad value", subject)


def test_save_identity_is_fixed_on_first_download(tmp_path):
    store = make_store(tmp_path)
    first = json.dumps({"cloudSaveId": "save-a", "platformId": "android"}).encode()
    second = json.dumps({"cloudSaveId": "save-b", "platformId": "android"}).encode()
    subject = store.identity_subject(email="holder@example.test", uid=42, player_id=77)
    save_subject = store.save_subject("android-global", first)
    store.bind_save_subject(subject, "android-global", save_subject)
    store.bind_save_subject(subject, "android-global", save_subject)
    with pytest.raises(NativeSaveIdentityMismatch):
        store.bind_save_subject(subject, "android-global", store.save_subject("android-global", second))
    with pytest.raises(NativeSaveIdentityMismatch):
        store.save_subject("android-global", b'{"cloudSaveId": ""}')


def test_login_rate_limit_is_per_identity_or_address(tmp_path):
    store = make_store(tmp_path, login_attempts=2, login_window_seconds=60)
    ip = store.hash_ip("127.0.0.1")
    email = store.hash_email("holder@example.test")
    store.check_login_rate(ip, email)
    store.record_attempt(ip, email, "native_credentials_rejected")
    store.check_login_rate(ip, email)
    store.record_attempt(ip, email, "native_credentials_rejected")
    with pytest.raises(NativeLoginThrottled) as error:
        store.check_login_rate(ip, email)
    assert 1 <= error.value.retry_after <= 60
    other_email = store.hash_email("other@example.test")
    with pytest.raises(NativeLoginThrottled):
        store.check_login_rate(ip, other_email)  # la IP ya está limitada
    store.check_login_rate(store.hash_ip("127.0.0.2"), other_email)  # otra IP no está limitada


def test_distribution_registry_only_enables_validated_global():
    distribution = require_enabled("android-global")
    assert distribution.enabled and distribution.validated
    from app.native.errors import NativeDistributionDisabled

    with pytest.raises(NativeDistributionDisabled):
        require_enabled("ios-global")


def test_email_hash_maps_one_profile_per_account_and_distribution(tmp_path):
    store = make_store(tmp_path)
    email_hash = store.hash_email("holder@example.test")
    created = store.create_profile(
        label="Cuenta automática", distribution_id="android-global",
        distro_id="44444444-4444-4444-8444-444444444444",
        unique_id="xiaomioutseas_" + "a" * 16,
        email_hash=email_hash, auto_generated=True,
    )
    assert store.profile_by_email_hash(email_hash, "android-global").id == created.id
    assert store.profile_by_email_hash(store.hash_email("other@example.test"), "android-global") is None
    subject = store.identity_subject(email="holder@example.test", uid=42, player_id=77)
    bound = store.bind(created.id, subject, email_hash=email_hash)
    assert bound.email_hash == email_hash
    with pytest.raises(NativeProfileIdentityMismatch):
        store.bind(created.id, subject, email_hash=store.hash_email("other@example.test"))
    with pytest.raises(NativeProfileIdentityMismatch):
        store.create_profile(
            label="Otra", distribution_id="android-global", distro_id=DISTRO,
            unique_id=UNIQUE, email_hash=email_hash, auto_generated=True,
        )


def test_old_profile_table_is_migrated_without_rewriting_sealed_values(tmp_path):
    root = tmp_path / "native"
    root.mkdir(mode=0o700)
    db = sqlite3.connect(root / "native.sqlite3")
    db.executescript(
        """
        CREATE TABLE encryption (id INTEGER PRIMARY KEY CHECK (id = 1), verifier BLOB NOT NULL);
        CREATE TABLE profiles (
            id TEXT PRIMARY KEY, label TEXT NOT NULL, distribution TEXT NOT NULL,
            sealed BLOB NOT NULL, subject TEXT, allow_write INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL, bound_at INTEGER,
            UNIQUE (label, distribution)
        );
        """
    )
    verifier = hmac.new(KEY, b"sk-under/native-store", hashlib.sha256).digest()
    db.execute("INSERT INTO encryption VALUES (1, ?)", (verifier,))
    db.commit()
    db.close()
    os.chmod(root / "native.sqlite3", 0o600)
    store = NativeStore(root, KEY)
    created = store.create_profile(
        label="Migrada", distribution_id="android-global", distro_id=DISTRO,
        unique_id=UNIQUE, email_hash="f" * 64, auto_generated=True,
    )
    assert created.auto_generated is True
    assert created.email_hash == "f" * 64
    assert store.profile_by_email_hash("f" * 64, "android-global").id == created.id


def test_atomic_reservation_counts_concurrent_pending_attempts(tmp_path):
    store = make_store(tmp_path, login_attempts=3, login_window_seconds=600)
    ip = store.hash_ip("127.0.0.1")
    email = store.hash_email("holder@example.test")

    def reserve(_):
        try:
            return ("ok", store.reserve_login_attempt(ip, email))
        except NativeLoginThrottled:
            return ("blocked", None)

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(reserve, range(10)))
    accepted = [item for item in results if item[0] == "ok"]
    blocked = [item for item in results if item[0] == "blocked"]
    assert len(accepted) == 3
    assert len(blocked) == 7
    # Al resolver los intentos como fallidos, sigue bloqueado hasta la ventana.
    for _, attempt_id in accepted:
        store.finish_login_attempt(attempt_id, "native_credentials_rejected")
    with pytest.raises(NativeLoginThrottled):
        store.reserve_login_attempt(ip, email)


def test_cleanup_removes_only_old_unbound_auto_profiles(tmp_path):
    now = [1_800_000_000]
    store = make_store(tmp_path, now=lambda: now[0])
    old = store.create_profile(
        label="Vieja", distribution_id="android-global", distro_id=DISTRO,
        unique_id=UNIQUE, email_hash="a" * 64, auto_generated=True,
    )
    bound = store.create_profile(
        label="Vinculada", distribution_id="android-global", distro_id=DISTRO,
        unique_id=UNIQUE, email_hash="b" * 64, auto_generated=True,
    )
    subject = store.identity_subject(email="holder@example.test", uid=1, player_id=2)
    store.bind(bound.id, subject, email_hash="b" * 64)
    now[0] += 8 * 86400
    store.cleanup()
    remaining = {item.id for item in store.list_profiles()}
    assert old.id not in remaining
    assert bound.id in remaining

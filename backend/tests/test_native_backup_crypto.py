"""Respaldos nativos cifrados en reposo y migración desde la Fase 6.8."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cloud.backup_store import BackupIntegrityError, BackupStoreError, LabBackupStore
from app.cloud.gems_editor import prepare_gems_edit

KEY = bytes.fromhex("cd" * 32)
FIXTURE = Path(__file__).parent / "fixtures" / "cloud-save-gems.json"
PAYLOAD = FIXTURE.read_bytes()


def _edit():
    return prepare_gems_edit(PAYLOAD, 4321)


def _save(store: LabBackupStore):
    edit = _edit()
    return store.save(
        edit,
        remote_source="modern-cloud",
        remote_size=len(edit.original),
        remote_sha256=edit.original_sha256,
    )


def test_encrypted_backup_does_not_contain_plaintext_and_roundtrips(tmp_path):
    root = tmp_path / "backups"
    store = LabBackupStore(root, cipher_key=KEY)
    bundle = _save(store)
    directory = root / bundle.record.id
    for name in ("original.json", "candidate.json", "record.json"):
        raw = (directory / name).read_bytes()
        assert raw.startswith(b"SKB1")
        assert b'"gems"' not in raw
        assert b"cloudSaveId" not in raw
        assert b"serialzedVersion" not in raw
    loaded = store.load(bundle.record.id)
    assert loaded.record == bundle.record
    assert loaded.original == bundle.original
    assert loaded.candidate == bundle.candidate
    assert store.list()[0].id == bundle.record.id
    assert store.confirmation(bundle.record.id) is None


def test_wrong_key_cannot_open_a_backup(tmp_path):
    root = tmp_path / "backups"
    bundle = _save(LabBackupStore(root, cipher_key=KEY))
    other = LabBackupStore(root, cipher_key=bytes.fromhex("ef" * 32))
    with pytest.raises(BackupIntegrityError):
        other.load(bundle.record.id)


def test_legacy_plaintext_is_rejected_until_migrated(tmp_path):
    root = tmp_path / "backups"
    legacy = LabBackupStore(root)
    bundle = _save(legacy)
    encrypted = LabBackupStore(root, cipher_key=KEY)
    with pytest.raises(BackupIntegrityError):
        encrypted.load(bundle.record.id)
    migrated = encrypted.migrate_legacy()
    assert migrated >= 3
    loaded = encrypted.load(bundle.record.id)
    assert loaded.original == bundle.original
    assert loaded.candidate == bundle.candidate


def test_migration_requires_a_key(tmp_path):
    with pytest.raises(BackupStoreError):
        LabBackupStore(tmp_path / "backups").migrate_legacy()


def test_confirmation_is_encrypted(tmp_path):
    root = tmp_path / "backups"
    store = LabBackupStore(root, cipher_key=KEY)
    bundle = _save(store)
    store.save_confirmation(bundle.record.id, {"status": "verified", "sha256": bundle.record.candidate_sha256})
    raw = (root / bundle.record.id / "confirmation.json").read_bytes()
    assert raw.startswith(b"SKB1")
    assert b"verified" not in raw
    assert store.confirmation(bundle.record.id)["status"] == "verified"

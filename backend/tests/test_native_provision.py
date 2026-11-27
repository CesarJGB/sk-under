import json

from app.native.provision import run
from app.native.store import NativeStore
from app.settings import Settings


def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        native_store_key="ef" * 32,
        native_store_dir=tmp_path / "native",
        native_backup_dir=tmp_path / "native-backups",
    )


def test_provision_cli_creates_a_profile_without_printing_identifiers(tmp_path, capsys):
    configuration = settings(tmp_path)
    lines = iter(["distro-cli", "unique-cli"])
    code = run(
        configuration,
        ["--label", "Cuenta CLI", "--distro-stdin", "--unique-stdin", "--allow-write"],
        stdin_reader=lambda: next(lines),
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "distro-cli" not in captured.out and "unique-cli" not in captured.out
    body = json.loads(captured.out)
    assert body["profile"]["label"] == "Cuenta CLI"
    assert body["profile"]["installation_ready"] is True
    assert body["profile"]["write_allowed"] is True
    store = NativeStore(tmp_path / "native", bytes.fromhex("ef" * 32))
    stored = store.list_profiles()[0]
    assert stored.distro_id == "distro-cli" and stored.unique_id == "unique-cli"


def test_provision_cli_can_leave_the_installation_pending(tmp_path, capsys):
    configuration = settings(tmp_path)
    code = run(
        configuration,
        ["--label", "Pendiente", "--distro-stdin", "--no-unique"],
        stdin_reader=lambda: "distro-only",
    )
    assert code == 0
    body = json.loads(capsys.readouterr().out)
    assert body["profile"]["installation_ready"] is False
    store = NativeStore(tmp_path / "native", bytes.fromhex("ef" * 32))
    assert store.list_profiles()[0].unique_id is None


def test_provision_cli_rejects_an_unvalidated_distribution(tmp_path, capsys):
    configuration = settings(tmp_path)
    code = run(
        configuration,
        ["--label", "iOS", "--distribution", "ios-vietnam", "--distro-stdin", "--no-unique"],
        stdin_reader=lambda: "distro-ios",
    )
    assert code == 1
    assert "validadas" in capsys.readouterr().err

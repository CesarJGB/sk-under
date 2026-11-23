import os
from hashlib import sha256
from pathlib import Path

import pytest

from app.settings import Settings
from conftest import make_client
from test_api import FILES, TEST_TOKEN, envelope

SAMPLE_TYPES = (
    "bp_data",
    "item_data",
    "misc_data",
    "monsrise_data",
    "pvp_data",
    "season_data",
    "statistic",
    "task",
    "weapon_evolution_data",
)
AUTH = {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture(scope="module")
def private_samples():
    directory = os.environ.get("SK_PHASE4_SAMPLES_DIR")
    if not directory:
        pytest.skip("Configura SK_PHASE4_SAMPLES_DIR para probar las muestras privadas de 8.6.0.")
    path = Path(directory)
    if not path.is_dir():
        pytest.fail("El directorio de muestras privadas configurado no existe.")
    return path


@pytest.fixture(scope="module")
def private_client(private_samples):
    config = os.environ.get("SK_PHASE4_CIPHER_ENV_FILE")
    if not config or not Path(config).is_file():
        pytest.fail("Configura SK_PHASE4_CIPHER_ENV_FILE con el archivo privado del códec de Fase 3.")
    settings = Settings(_env_file=config)
    if settings.save_cipher is None:
        pytest.fail("Falta la configuración del códec local en el archivo indicado.")
    with make_client(
        env="production",
        access_token=TEST_TOKEN,
        save_general_key_hex=settings.save_general_key_hex,
        save_statistics_key_hex=settings.save_statistics_key_hex,
        save_iv_hex=settings.save_iv_hex,
    ) as client:
        yield client


@pytest.mark.parametrize("kind", SAMPLE_TYPES)
def test_private_save_roundtrip(private_samples, private_client, kind):
    path = private_samples / f"{kind}_111_.data"
    original = path.read_bytes()
    digest = sha256(original).hexdigest()

    response = private_client.post(FILES + "/inspect", headers=AUTH, json=envelope(original))
    assert response.status_code == 200
    inspection = response.json()
    assert inspection["format"]["id"] == "sk-local-des-cbc"
    assert inspection["format"]["compatibility"] == "read_only"
    assert inspection["byte_size"] == len(original)
    assert inspection["sha256"] == digest
    assert all(not field["editable"] for field in inspection["fields"])

    request = envelope(original, changes={})
    response = private_client.post(FILES + "/validate", headers=AUTH, json=request)
    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "changes": [],
        "output_byte_size": len(original),
        "output_sha256": digest,
    }

    result = private_client.post(FILES + "/export", headers=AUTH, json=request)
    assert result.status_code == 200
    assert result.headers["Content-Disposition"] == f'attachment; filename="copia-{kind}.data"'
    assert result.headers["Cache-Control"] == "no-store"
    if result.content != original:
        pytest.fail("La copia difiere de la muestra original.")

    reopened = private_client.post(FILES + "/inspect", headers=AUTH, json=envelope(result.content))
    assert reopened.status_code == 200
    if reopened.json() != inspection:
        pytest.fail("La inspección de la copia difiere de la inspección original.")

    edited = private_client.post(
        FILES + "/export", headers=AUTH, json=envelope(original, changes={"save_type": "prueba"})
    )
    assert edited.status_code == 422
    assert edited.json()["error"]["code"] == "invalid_changes"
    if path.read_bytes() != original:
        pytest.fail("La muestra original cambió durante la prueba.")

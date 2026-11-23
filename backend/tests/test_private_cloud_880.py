"""Prueba optativa con agregado privado obtenido del cliente y copia restaurada."""
import json
import os
from pathlib import Path

import pytest

from app.cloud_save import reconstruct_cloud_save
from app.parsers.real_save import decode_game_data


def test_private_cloud_aggregate_matches_restored_game_gems() -> None:
    aggregate_path = os.environ.get('SK_PHASE58_CLOUD_JSON')
    local_path = os.environ.get('SK_PHASE58_RESTORED_GAME')
    if not aggregate_path or not local_path:
        pytest.skip('Configura las dos rutas privadas de la Fase 5.8.')
    payload = Path(aggregate_path).read_bytes()
    reconstructed = reconstruct_cloud_save(payload)
    cloud = json.loads(payload)
    local = decode_game_data(Path(local_path).read_bytes())
    assert reconstructed.data.game_data == cloud['gameData']
    assert isinstance(local, dict)
    assert isinstance(cloud['gameData']['gems'], int)
    assert cloud['gameData']['gems'] > 0
    assert cloud['gameData']['gems'] == local['gems']

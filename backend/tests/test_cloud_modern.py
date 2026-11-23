import gzip
import http.client
import json
import os
from pathlib import Path

import pytest

from app.cloud.modern import ModernCloudSaveProvider, URL, _fetch
from app.cloud.provider import CloudProviderProtocolError, CloudProviderUnauthenticated, CloudProviderUnavailable
from app.cloud_save import CopyLimitError, reconstruct_cloud_save

DOCUMENT = {'serialzedVersion': 1, 'cloudSaveId': 'synthetic-id', 'platformId': 'android',
            'gameData': {'gems': 7}, 'itemData': {}}
PAYLOAD = json.dumps(DOCUMENT).encode()
ENVELOPE = json.dumps({'data': PAYLOAD.decode()}).encode()


def provider(status=200, encoding='gzip', body=None):
    body = gzip.compress(ENVELOPE, mtime=0) if body is None else body
    def fetch(url, headers, timeout):
        assert url == URL
        assert headers['Authorization'] == 'Bearer synthetic-token'
        assert headers['x-unique-id'] == 'synthetic-device'
        assert headers['x-distro-id'] == 'synthetic-distro'
        return status, encoding, body
    return ModernCloudSaveProvider('synthetic-token', 'synthetic-device', 'synthetic-distro', fetch=fetch)


def test_gzip_envelope_returns_verified_aggregate():
    p = provider()
    acquired = p.download()
    assert acquired.payload == PAYLOAD
    assert acquired.metadata.source == 'modern-cloud'
    assert reconstruct_cloud_save(acquired.payload).data.game_data['gems'] == 7
    assert 'synthetic-token' not in repr(p) and 'synthetic-device' not in repr(p)


@pytest.mark.parametrize('body,encoding', [
    (b'bad gzip', 'gzip'),
    (gzip.compress(ENVELOPE)[:-1], 'gzip'),
    (gzip.compress(ENVELOPE) + b'extra', 'gzip'),
    (gzip.compress(ENVELOPE)[:-8] + b'\x00' * 8, 'gzip'),
    (b'{"data":{}}', ''),
    (b'{"data":"{}"}', ''),
    (b'{"data":"{}","data":"{}"}', ''),
    (b'{', ''),
    (ENVELOPE, 'br'),
])
def test_rejects_incomplete_corrupt_or_invalid_response(body, encoding):
    with pytest.raises(CloudProviderProtocolError):
        provider(body=body, encoding=encoding).download()


def test_rejects_limits_and_missing_credentials():
    with pytest.raises(CopyLimitError):
        provider().download(10)
    with pytest.raises(CloudProviderUnauthenticated):
        ModernCloudSaveProvider('', 'device', 'distro')
    with pytest.raises(CloudProviderProtocolError):
        ModernCloudSaveProvider('token', 'device\nother', 'distro')
    with pytest.raises(CloudProviderUnavailable):
        provider(status=400).download()
    with pytest.raises(CloudProviderUnauthenticated):
        provider(status=401).download()


def test_truncated_http_response_is_a_protocol_error(monkeypatch):
    class Response:
        headers = {'Content-Length': '100'}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            raise http.client.IncompleteRead(b'partial', 93)

    class Opener:
        def open(self, request, timeout):
            return Response()

    monkeypatch.setattr('urllib.request.build_opener', lambda *args: Opener())
    with pytest.raises(CloudProviderProtocolError, match='incompleta'):
        _fetch(URL, {}, 10)


def test_transport_error_does_not_expose_details():
    def fetch(*args):
        raise OSError('synthetic-secret')

    p = ModernCloudSaveProvider('token', 'device', 'distro', fetch=fetch)
    with pytest.raises(CloudProviderUnavailable) as error:
        p.download()
    assert 'synthetic-secret' not in str(error.value)
    assert error.value.__suppress_context__


@pytest.mark.parametrize('status', [401, 403])
def test_authentication_failure_is_typed(status):
    with pytest.raises(CloudProviderUnauthenticated):
        provider(status=status).download()


def test_optional_private_service_response():
    path = os.getenv('SK_PHASE59_WIRE_RESPONSE')
    if not path:
        pytest.skip('Configura una respuesta privada capturada por Linux.')
    wire = Path(path).read_bytes()
    acquired = provider(body=wire).download()
    save = reconstruct_cloud_save(acquired.payload)
    assert save.data.game_data.get('gems') == 1000
    assert len(json.loads(acquired.payload)) == 17

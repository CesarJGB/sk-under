import json
import pytest
from app.cloud.legacy import LegacyGatewayReader
from app.cloud.provider import CloudProviderProtocolError, CloudProviderUnauthenticated, CloudProviderUnavailable

FIELDS = ('heroData', 'petData', 'plantPotData', 'heroRoomData', 'gameItemData')

def test_legacy_response_is_separate_and_never_claims_progress():
    data = {key: {} for key in FIELDS}
    data['heroData'] = {'private-id': {'level': 2}}
    def fetch(url, headers, timeout):
        assert url.endswith('/Backup/FetchGameData')
        assert headers['Content-Type'] == 'application/json'
        assert headers['x-distro-id'] == 'private-distro'
        return 200, json.dumps(data).encode()
    reader = LegacyGatewayReader('secret-token', 'private-distro', fetch=fetch)
    aggregate = reader.read()
    assert aggregate.summary()['progress'] == 'unknown'
    assert aggregate.summary()['collection_counts']['heroData'] == 1
    assert 'private-id' not in repr(aggregate)
    assert 'secret-token' not in repr(reader)
    assert 'private-distro' not in repr(reader)

@pytest.mark.parametrize('status,body,error', [
    (200, b'{}', CloudProviderProtocolError),
    (200, b'not json', CloudProviderProtocolError),
    (400, b'{"errorCode":10001}', CloudProviderUnauthenticated),
    (503, b'<html/>', CloudProviderUnavailable),
])
def test_legacy_errors(status, body, error):
    with pytest.raises(error):
        LegacyGatewayReader('t', 'd', fetch=lambda *_: (status, body)).read()

def test_legacy_rejects_header_injection():
    with pytest.raises(CloudProviderProtocolError):
        LegacyGatewayReader('t', 'bad\r\nheader')

def test_legacy_reader_rejects_non_https():
    with pytest.raises(CloudProviderProtocolError):
        LegacyGatewayReader('t', 'd', base_url='http://example.test')

def test_legacy_oversized_response():
    from app.cloud_save import MAX_INPUT_BYTES, CopyLimitError
    with pytest.raises(CopyLimitError):
        LegacyGatewayReader('t', 'd', fetch=lambda *_: (200, b' ' * (MAX_INPUT_BYTES + 1))).read()

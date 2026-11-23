import gzip
import json
import threading
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.cloud.blob_roundtrip import upload_and_verify
from app.cloud.blob_upload import (
    UPLOAD_URL,
    BlobSaveUploader,
    CloudUploadRejected,
    CloudWriteDisabled,
)
from app.cloud.blob_wire import BlobWireError, build_blob_headers, decode_response
from app.main import create_app
from app.cloud.provider import (
    AcquiredCloudSave,
    CloudProviderProtocolError,
    CloudProviderUnauthenticated,
    CloudProviderUnavailable,
    CloudSaveMetadata,
)
from app.cloud.upload_dry_run import prepare_upload_candidate
from app.cloud_save import AggregateFormatError
from app.settings import Settings

AGGREGATE = b'{"serialzedVersion": 1, "cloudSaveId": "synthetic", "platformId": "android", "gameData": {"gems": 7}}'


def uploader(send=None, **options):
    defaults = dict(
        session_token='synthetic-token',
        unique_id='synthetic-device',
        distro_id='synthetic-distro',
        enabled=True,
    )
    defaults.update(options)
    if send is not None:
        defaults['send'] = send
    return BlobSaveUploader(**defaults)


def reply(status=200, body=b'true', encoding='gzip'):
    wire = gzip.compress(body, mtime=0) if encoding == 'gzip' else body
    calls = {}

    def send(url, headers, payload, timeout):
        calls['url'] = url
        calls['headers'] = headers
        calls['payload'] = payload
        calls['timeout'] = timeout
        return status, encoding, wire

    return send, calls


def test_write_is_disabled_unless_explicitly_enabled():
    with pytest.raises(CloudWriteDisabled):
        uploader(enabled=False).upload(AGGREGATE)


def test_successful_request_matches_the_observed_contract():
    send, calls = reply()
    result = uploader(send).upload(AGGREGATE)
    candidate = prepare_upload_candidate(AGGREGATE)
    assert result.accepted is True and result.status == 200
    assert calls['url'] == UPLOAD_URL
    assert calls['headers']['Authorization'] == 'Bearer synthetic-token'
    assert calls['headers']['x-unique-id'] == 'synthetic-device'
    assert calls['headers']['x-distro-id'] == 'synthetic-distro'
    assert calls['headers']['Content-Type'] == 'application/json'
    assert calls['headers']['Content-Encoding'] == 'gzip'
    assert int(calls['headers']['Content-Length']) == len(calls['payload']) == len(candidate.body)
    assert 'x-request-token' not in calls['headers']
    assert gzip.decompress(calls['payload']).startswith(b'{"data":"')
    assert json.loads(gzip.decompress(calls['payload']))['data'].encode() == AGGREGATE
    assert result.aggregate_sha256 == sha256(AGGREGATE).hexdigest()
    assert 'synthetic-token' not in repr(result) and 'synthetic-device' not in repr(result)


def test_positive_request_token_is_sent_but_absent_by_default():
    send, calls = reply()
    uploader(send, request_token=7).upload(AGGREGATE)
    assert calls['headers']['x-request-token'] == '7'
    with pytest.raises(CloudProviderProtocolError):
        uploader(request_token=0)


def test_server_false_or_non_boolean_answer_is_not_success():
    send, _ = reply(body=b'false')
    with pytest.raises(CloudUploadRejected):
        uploader(send).upload(AGGREGATE)
    send, _ = reply(body=b'1')
    with pytest.raises(CloudProviderProtocolError):
        uploader(send).upload(AGGREGATE)
    send, _ = reply(body=b'"true"')
    with pytest.raises(CloudProviderProtocolError):
        uploader(send).upload(AGGREGATE)


@pytest.mark.parametrize('status', [401, 403])
def test_authentication_failure_is_typed(status):
    send, _ = reply(status=status, body=b'')
    with pytest.raises(CloudProviderUnauthenticated):
        uploader(send).upload(AGGREGATE)


def test_non_200_is_a_rejection_with_the_real_status():
    send, _ = reply(status=500, body=b'error')
    with pytest.raises(CloudUploadRejected) as caught:
        uploader(send).upload(AGGREGATE)
    assert caught.value.status == 500


def test_transport_failure_does_not_expose_details():
    def send(*args):
        raise OSError('synthetic-secret')

    with pytest.raises(CloudProviderUnavailable) as error:
        uploader(send).upload(AGGREGATE)
    assert 'synthetic-secret' not in str(error.value)
    assert error.value.__suppress_context__


def test_corrupt_response_is_a_protocol_error():
    send, _ = reply(body=b'true', encoding='gzip')
    def broken(url, headers, payload, timeout):
        return 200, 'gzip', b'not gzip'
    with pytest.raises(CloudProviderProtocolError):
        uploader(broken).upload(AGGREGATE)


def test_invalid_aggregate_never_reaches_the_wire():
    called = False

    def send(*args):
        nonlocal called
        called = True
        return 200, 'gzip', gzip.compress(b'true')

    with pytest.raises(AggregateFormatError):
        uploader(send).upload(b'{"data":"not an aggregate"}')
    assert called is False


def test_credentials_and_url_are_validated_without_echoing_them():
    with pytest.raises(CloudProviderUnauthenticated):
        uploader(session_token='')
    with pytest.raises(CloudProviderProtocolError):
        uploader(unique_id='device\nother')
    with pytest.raises(CloudProviderProtocolError):
        uploader(url='http://example.com/upload')


def test_headers_helper_can_omit_body_specific_values():
    headers = build_blob_headers('token', 'device', 'distro')
    assert headers['Content-Type'] == 'application/json; charset=utf-8'
    assert 'Content-Encoding' not in headers and 'Content-Length' not in headers


@pytest.mark.parametrize('body,encoding', [
    (b'bad gzip', 'gzip'),
    (gzip.compress(b'true')[:-1], 'gzip'),
    (gzip.compress(b'true') + b'extra', 'gzip'),
    (b'true', 'br'),
])
def test_response_decoder_rejects_invalid_wire(body, encoding):
    with pytest.raises(BlobWireError):
        decode_response(body, encoding)


def test_local_http_integration_preserves_wire_bytes_and_headers():
    received = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers['Content-Length'])
            received['path'] = self.path
            received['headers'] = dict(self.headers.items())
            received['body'] = self.rfile.read(length)
            wire = gzip.compress(b'true', mtime=0)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Encoding', 'gzip')
            self.send_header('Content-Length', str(len(wire)))
            self.end_headers()
            self.wfile.write(wire)

        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f'http://127.0.0.1:{server.server_port}/BlobSave/Upload'
        result = uploader(url=url).upload(AGGREGATE)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    candidate = prepare_upload_candidate(AGGREGATE)
    assert result.accepted is True
    assert received['path'] == '/BlobSave/Upload'
    assert received['body'] == candidate.body
    assert received['headers']['Content-Encoding'] == 'gzip'
    assert received['headers']['Content-Type'] == 'application/json'
    assert received['headers']['Authorization'] == 'Bearer synthetic-token'


def metadata(payload):
    return CloudSaveMetadata('remote', len(payload), sha256(payload).hexdigest(), source='modern-cloud')


class FakeProvider:
    def __init__(self, payload):
        self.payload = payload
        self.limit = None

    def download(self, limit=8 * 1024 * 1024):
        self.limit = limit
        return AcquiredCloudSave(metadata(self.payload), self.payload)

    def metadata(self):
        return metadata(self.payload)


def test_roundtrip_confirms_only_identical_remote_bytes():
    send, _ = reply()
    provider = FakeProvider(AGGREGATE)
    result = upload_and_verify(AGGREGATE, uploader(send), provider)
    assert result.matches is True and result.remote_sha256 == sha256(AGGREGATE).hexdigest()

    changed = AGGREGATE.replace(b'"gems": 7', b'"gems": 8')
    send, _ = reply()
    result = upload_and_verify(AGGREGATE, uploader(send), FakeProvider(changed))
    assert result.matches is False
    assert result.remote_sha256 != sha256(AGGREGATE).hexdigest()


def test_public_api_does_not_expose_the_write_transport():
    app = create_app(Settings(_env_file=None, env='development', allowed_origins=[]))
    paths = app.openapi()['paths']
    assert not any('blob' in path.lower() or 'cloud' in path.lower() for path in paths)

import gzip
import json

import pytest

from app.cloud.upload_dry_run import prepare_upload_candidate
from app.cloud_save import CloudSaveError


def test_candidate_preserves_aggregate_exactly():
    original = b'{"serialzedVersion":1,"cloudSaveId":"synthetic","platformId":"android","gameData":{"gems":7}}'
    candidate = prepare_upload_candidate(original)
    assert json.loads(gzip.decompress(candidate.body))['data'].encode() == original
    assert candidate.content_encoding == 'gzip'
    assert original.decode() not in repr(candidate)


def test_candidate_uses_json_net_default_unicode_escaping():
    original = ('{"serialzedVersion":1,"cloudSaveId":"synthetic",'
                '"platformId":"android","gameData":{"name":"\u0085\u2028\u2029"}}').encode()
    body = gzip.decompress(prepare_upload_candidate(original).body)
    # Confirmado con Json.NET 13 y StringEscapeHandling.Default.
    assert b'\\u0085\\u2028\\u2029' in body
    assert json.loads(body)['data'].encode() == original


def test_candidate_rejects_invalid_input():
    with pytest.raises(CloudSaveError):
        prepare_upload_candidate(b'{"data":"not an aggregate"}')

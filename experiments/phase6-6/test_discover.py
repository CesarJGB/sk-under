import io
import unittest
from email.message import Message
from discover import probe

class Response:
    status = 200
    def __init__(self, content_type, body):
        self.headers = Message()
        self.headers['Content-Type'] = content_type
        self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, size): return self.body[:size]

class Opener:
    def __init__(self, response): self.response = response
    def open(self, request, timeout): return self.response

class DiscoveryTests(unittest.TestCase):
    def test_html_success_is_not_metadata(self):
        result = probe(Opener(Response('text/html', b'<html></html>')), 'https://example.org')
        self.assertEqual(result['result'], 'not_authorization_metadata')
    def test_metadata_is_only_a_candidate(self):
        body = b'{"issuer":"https://example.org","authorization_endpoint":"https://example.org/a","token_endpoint":"https://example.org/t"}'
        result = probe(Opener(Response('application/json', body)), 'https://example.org')
        self.assertEqual(result['result'], 'candidate_metadata_requires_manual_validation')
    def test_large_response_is_rejected(self):
        result = probe(Opener(Response('application/json', b' ' * 65537)), 'https://example.org')
        self.assertEqual(result['result'], 'response_too_large')

if __name__ == '__main__': unittest.main()

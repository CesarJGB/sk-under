"""Simulated contracts only; no remote service or real credentials."""
import gzip
import importlib.util
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('native_login', Path(__file__).with_name('native_login.py'))
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)

class Server(BaseHTTPRequestHandler):
    status = 200
    payload = b''
    encoding = None
    length = None
    requests = []
    last_headers = None

    def log_message(self, *_):
        pass

    def do_POST(self):
        self.__class__.last_headers = dict(self.headers)
        self.__class__.requests.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
        self.send_response(self.status)
        if self.encoding:
            self.send_header('Content-Encoding', self.encoding)
        if self.length is not None:
            self.send_header('Content-Length', self.length)
        if self.status == 302:
            self.send_header('Location', '/redirected')
        self.end_headers()
        try:
            self.wfile.write(self.payload)
        except BrokenPipeError:
            pass

class LoginTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Server)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/login'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        Server.requests = []
        Server.status = 200
        Server.encoding = None
        Server.length = None
        self.good = {'session': {'token': 'synthetic-token', 'expire': int(time.time()) + 300, 'uid': 7},
                     'user': {'id': 7, 'email': 'example@example.invalid'}}
        Server.payload = json.dumps(self.good).encode()

    def auth(self):
        with patch.object(client, 'URL', self.url):
            return client.authenticate('example@example.invalid', 'synthetic-password')

    def test_success_and_serialization_are_hypothetical(self):
        self.assertEqual(self.auth(), 'synthetic-token')
        self.assertEqual(Server.requests, [('/login', {'loginType': 3, 'account': 'example@example.invalid',
                                                        'password': 'synthetic-password', 'credential': None})])

    def test_optional_save_context_headers(self):
        with patch.object(client, 'URL', self.url):
            self.assertEqual(client.authenticate('example@example.invalid', 'synthetic-password', save_context=True), 'synthetic-token')
        headers = {k.lower(): v for k, v in Server.last_headers.items()}
        self.assertEqual(headers['x-app-version'], '8.8.0')
        self.assertEqual(headers['x-platform'], 'android')
        self.assertNotIn('x-unique-id', headers)

    def test_gzip(self):
        Server.encoding = 'gzip'
        Server.payload = gzip.compress(Server.payload)
        self.assertEqual(self.auth(), 'synthetic-token')

    def test_compressed_bomb_bounded(self):
        Server.encoding = 'gzip'
        Server.payload = gzip.compress(b'x' * (client.LIMIT + 1))
        with self.assertRaises(client.ExperimentError): self.auth()

    def test_malformed_gzip(self):
        Server.encoding = 'gzip'
        Server.payload = b'bad'
        with self.assertRaises(client.ExperimentError): self.auth()

    def test_invalid_content_length(self):
        Server.length = 'invalid'
        with self.assertRaises(client.ExperimentError): self.auth()

    def test_unknown_encoding(self):
        Server.encoding = 'br'
        with self.assertRaises(client.ExperimentError): self.auth()

    def test_redirect_does_not_send_credentials_again(self):
        Server.status = 302
        with self.assertRaises(client.ExperimentError): self.auth()
        self.assertEqual(len(Server.requests), 1)

    def test_http_error_does_not_echo_remote_body(self):
        Server.status = 502
        Server.payload = b'synthetic-secret'
        with self.assertRaises(client.ExperimentError) as caught: self.auth()
        self.assertNotIn('synthetic-secret', str(caught.exception))

    def test_identity_mismatch_and_bad_expiry(self):
        for key, value in [('id', 8), ('email', 'other@example.invalid')]:
            obj = json.loads(json.dumps(self.good))
            obj['user'][key] = value
            Server.payload = json.dumps(obj).encode()
            with self.assertRaises(client.ExperimentError): self.auth()
        self.good['session']['expire'] = True
        Server.payload = json.dumps(self.good).encode()
        with self.assertRaises(client.ExperimentError): self.auth()

    def test_unknown_shape(self):
        Server.payload = b'{"challenge": true}'
        with self.assertRaises(client.ExperimentError): self.auth()

if __name__ == '__main__':
    unittest.main()

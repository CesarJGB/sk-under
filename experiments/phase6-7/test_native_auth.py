"""Pruebas simuladas del cliente Linux; no usan la red ni credenciales reales."""

from __future__ import annotations

import gzip
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import native_auth


class _Server(BaseHTTPRequestHandler):
    status = 200
    payload = b""
    encoding = None
    length = None
    requests: list[tuple[str, bytes, dict[str, str]]] = []
    last_headers: dict[str, str] | None = None

    def log_message(self, *_args):  # noqa: ANN002
        pass

    def do_POST(self):  # noqa: N802
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        type(self).last_headers = {k.lower(): v for k, v in self.headers.items()}
        type(self).requests.append((self.path, raw, dict(self.headers)))
        self.send_response(self.status)
        if self.encoding:
            self.send_header("Content-Encoding", self.encoding)
        if self.length is not None:
            self.send_header("Content-Length", str(self.length))
        if self.status == 302:
            self.send_header("Location", "/redirected")
        self.end_headers()
        try:
            self.wfile.write(self.payload)
        except BrokenPipeError:
            pass


class NativeAuthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Server)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/login"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        _Server.requests = []
        _Server.status = 200
        _Server.encoding = None
        _Server.length = None
        _Server.last_headers = None
        self.good = {
            "session": {
                "uid": "7",
                "token": "synthetic-token",
                "expire": str(int(time.time()) + 300),
            },
            "user": {"id": "7", "email": "player@example.invalid"},
            "player": {"id": "99", "status": 0},
            "legacyGateway": {
                "host": "legacy.example.invalid",
                "token": "synthetic-legacy-token",
            },
        }
        _Server.payload = json.dumps(self.good).encode()

    def auth(self, **kwargs):
        return native_auth.authenticate(
            "player@example.invalid",
            "synthetic-password",
            distro_id="11111111-2222-4333-8444-555555555555",
            url=self.url,
            **kwargs,
        )

    def test_success_contract_and_headers(self):
        session = self.auth()
        self.assertEqual(session.token, "synthetic-token")
        self.assertEqual(session.uid, 7)
        self.assertEqual(session.player_id, 99)
        self.assertTrue(session.is_valid())
        path, raw, headers = _Server.requests[0]
        self.assertEqual(path, "/login")
        self.assertEqual(
            json.loads(raw),
            {
                "loginType": 3,
                "account": "player@example.invalid",
                "password": "synthetic-password",
                "credential": None,
            },
        )
        lowered = {k.lower(): v for k, v in headers.items()}
        self.assertEqual(lowered["x-distro-id"], "11111111-2222-4333-8444-555555555555")
        self.assertNotIn("x-unique-id", lowered)
        self.assertEqual(lowered["x-platform"], "android")
        self.assertEqual(lowered["x-app-version"], "8.8.0")
        self.assertIn("application/json", lowered["content-type"])

    def test_gzip_response(self):
        _Server.encoding = "gzip"
        _Server.payload = gzip.compress(_Server.payload)
        self.assertEqual(self.auth().token, "synthetic-token")

    def test_rejected_10003_does_not_echo_body(self):
        _Server.status = 502
        _Server.payload = json.dumps(
            {"ok": False, "errorCode": 10003, "message": "unexpected error"}
        ).encode()
        with self.assertRaises(native_auth.AuthRejected) as caught:
            self.auth()
        self.assertEqual(caught.exception.status, 502)
        self.assertEqual(caught.exception.code, 10003)
        self.assertNotIn("unexpected", str(caught.exception))

    def test_identity_mismatch(self):
        for key, value in (("id", "8"), ("email", "other@example.invalid")):
            document = json.loads(json.dumps(self.good))
            document["user"][key] = value
            _Server.payload = json.dumps(document).encode()
            with self.assertRaises(native_auth.AuthIdentityError):
                self.auth()

    def test_expired(self):
        document = json.loads(json.dumps(self.good))
        document["session"]["expire"] = str(int(time.time()) - 1)
        _Server.payload = json.dumps(document).encode()
        with self.assertRaises(native_auth.AuthIdentityError):
            self.auth()

    def test_redirect_does_not_repeat_credentials(self):
        _Server.status = 302
        _Server.payload = b""
        with self.assertRaises(native_auth.AuthRejected):
            self.auth()
        self.assertEqual(len(_Server.requests), 1)

    def test_unknown_encoding(self):
        _Server.encoding = "br"
        with self.assertRaises(native_auth.AuthProtocolError):
            self.auth()

    def test_malformed_gzip(self):
        _Server.encoding = "gzip"
        _Server.payload = b"not-gzip"
        with self.assertRaises(native_auth.AuthProtocolError):
            self.auth()

    def test_oversized_response(self):
        _Server.payload = b"x" * (native_auth.MAX_RESPONSE_BYTES + 1)
        with self.assertRaises(native_auth.AuthProtocolError):
            self.auth()

    def test_content_length_mismatch(self):
        _Server.length = 999
        with self.assertRaises(native_auth.AuthProtocolError):
            self.auth()

    def test_unknown_shape(self):
        _Server.payload = b'{"challenge": true}'
        with self.assertRaises(native_auth.AuthProtocolError):
            self.auth()

    def test_invalid_distro(self):
        with self.assertRaises(native_auth.AuthProtocolError):
            native_auth.build_login_headers("bad distro with spaces")

    def test_summary_redacts_secrets(self):
        summary = self.auth().summary()
        encoded = json.dumps(summary)
        for secret in ("synthetic-token", "player@example.invalid", "synthetic-legacy-token"):
            self.assertNotIn(secret, encoded)
        self.assertIn("expire_iso", summary)


if __name__ == "__main__":
    unittest.main()

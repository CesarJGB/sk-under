"""Cabeceras de seguridad de la API y del editor."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


def test_api_responses_have_csp_and_security_headers(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "camera=()" in response.headers["Permissions-Policy"]
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Cross-Origin-Resource-Policy"] == "same-site"
    assert "Cache-Control" in response.headers


def test_hsts_only_in_production_over_https():
    settings = Settings(
        _env_file=None,
        env="production",
        allowed_origins=["https://editor.example.test"],
    )
    app = create_app(settings)
    https = TestClient(app, base_url="https://api.example.test", client=("127.0.0.1", 50000))
    response = https.get("/api/v1/health")
    assert response.headers["Strict-Transport-Security"].startswith("max-age=31536000")
    http = TestClient(app, base_url="http://api.example.test", client=("127.0.0.1", 50000))
    assert "Strict-Transport-Security" not in http.get("/api/v1/health").headers

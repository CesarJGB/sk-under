import base64
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.parsers.demo import DEMO_SIGNATURE
from app.settings import Settings
from conftest import ORIGIN, make_client

V1 = "/api/v1"
FILES = V1 + "/files"
DEMO = "sk-editor-demo-v1"
TEST_TOKEN = "t" * 32


def envelope(data: bytes, **extra) -> dict:
    return {"content_base64": base64.b64encode(data).decode("ascii"), **extra}


def assert_error(response, status: int, code: str):
    assert response.status_code == status, response.text
    assert response.headers["Cache-Control"] == "no-store"
    error = response.json()["error"]
    assert error["code"] == code
    assert isinstance(error["issues"], list)
    return error


def test_metadata(client):
    assert client.get(V1 + "/health").json() == {
        "status": "ok", "access_mode": "local", "max_file_bytes": 1_048_576,
    }
    formats = client.get(V1 + "/formats").json()["formats"]
    assert [(f["id"], f["version"], f["extensions"], f["compatibility"]) for f in formats] == [
        (DEMO, "1", [".skdemo"], "synthetic")
    ]


def test_inspection(client, original):
    response = client.post(FILES + "/inspect", json=envelope(original))
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    result = response.json()
    assert result["sha256"] == sha256(original).hexdigest()
    assert result["byte_size"] == len(original)
    assert result["format"]["id"] == DEMO
    fields = {field["id"]: field for field in result["fields"]}
    assert set(fields) == {"fixture_id", "label", "sample_count", "sample_limit"}
    assert fields["label"]["type"] == "string"
    assert fields["sample_count"]["value"] == 4
    assert fields["sample_count"]["maximum"] == 100
    assert fields["fixture_id"]["editable"] is False


def test_export_roundtrip_and_original_remain_intact(client, original, fixture_path):
    payload = envelope(original, changes={"label": "Muestra revisada", "sample_count": 14, "sample_limit": 16})
    validate = client.post(FILES + "/validate", json=payload)
    assert validate.status_code == 200, validate.text

    result = client.post(FILES + "/export", json=payload)
    assert result.status_code == 200, result.text
    assert result.headers["Content-Disposition"] == 'attachment; filename="copia-editada.skdemo"'
    assert result.headers["Content-Type"] == "application/octet-stream"
    assert result.headers["Cache-Control"] == "no-store"
    assert validate.json() == {
        "valid": True,
        "changes": [
            {"field_id": "label", "original": "Ejemplo sintético", "modified": "Muestra revisada"},
            {"field_id": "sample_count", "original": 4, "modified": 14},
            {"field_id": "sample_limit", "original": 10, "modified": 16},
        ],
        "output_byte_size": len(result.content),
        "output_sha256": sha256(result.content).hexdigest(),
    }
    reinspected = client.post(FILES + "/inspect", json=envelope(result.content))
    assert reinspected.status_code == 200, reinspected.text
    assert {field["id"]: field["value"] for field in reinspected.json()["fields"]} == {
        "fixture_id": "fixture-backend", "label": "Muestra revisada", "sample_count": 14, "sample_limit": 16,
    }
    assert fixture_path.read_bytes() == original
    assert client.post(FILES + "/inspect", json=envelope(original)).json()["sha256"] != validate.json()["output_sha256"]


def test_noop_export_preserves_bytes(client):
    compact = DEMO_SIGNATURE + b'{"fixture_id":"demo","label":"Prueba","sample_count":2,"sample_limit":2}'
    result = client.post(FILES + "/export", json=envelope(compact, changes={"sample_count": 2}))
    assert result.status_code == 200
    assert result.content == compact


@pytest.mark.parametrize("data", [
    b"any opaque backup",
    b'<map><string name="test">1</string></map>',
    b'{"fixture_id":"demo","label":"Prueba","sample_count":2,"sample_limit":2}',
    b"SK-EDITOR-DEMO/2\n{}",
])
def test_unknown_formats_are_rejected(client, data):
    assert_error(client.post(FILES + "/inspect", json=envelope(data)), 415, "unsupported_format")


@pytest.mark.parametrize("body", [
    b"",
    b"{",
    b"\xff",
    b"[" * 1000,
    b'{"fixture_id":"x","label":"x","label":"duplicada","sample_count":0,"sample_limit":1}',
    b'{"fixture_id":"x","label":"x","sample_count":NaN,"sample_limit":1}',
    b'{"fixture_id":"x","label":"x","sample_count":true,"sample_limit":1}',
    b'{"fixture_id":"x","label":"x","sample_count":2,"sample_limit":1}',
    b'{"fixture_id":"x","label":"x","sample_count":0,"sample_limit":1,"secret_payload":"do-not-echo"}',
    b'{"fixture_id":"x","label":"\\ud800","sample_count":0,"sample_limit":1}',
])
def test_malformed_demo(client, body):
    response = client.post(FILES + "/inspect", json=envelope(DEMO_SIGNATURE + body))
    assert_error(response, 422, "malformed_file")
    assert "do-not-echo" not in response.text and "secret_payload" not in response.text


@pytest.mark.parametrize(("value", "code"), [("", "empty_file"), ("***", "invalid_base64"), ("☃", "invalid_base64")])
def test_base64_validation(client, value, code):
    assert_error(client.post(FILES + "/inspect", json={"content_base64": value}), 422, code)


@pytest.mark.parametrize(("changes", "code", "issue"), [
    ({"sample_count": -1}, "invalid_changes", "invalid_field"),
    ({"sample_count": 5.0}, "invalid_request", None),
    ({"sample_count": True}, "invalid_request", None),
    ({"sample_count": "4"}, "invalid_changes", "invalid_field"),
    ({"sample_count": 11}, "invalid_changes", "dependency_failed"),
    ({"sample_limit": 2}, "invalid_changes", "dependency_failed"),
    ({"label": "a" * 49}, "invalid_changes", "invalid_field"),
    ({"label": "linea\nmalformada"}, "invalid_changes", "invalid_field"),
    ({"fixture_id": "new"}, "invalid_changes", "field_not_editable"),
    ({"../../secret_payload": 10}, "invalid_changes", "field_not_editable"),
])
def test_invalid_edits_for_validation_and_export(client, original, changes, code, issue):
    for operation in ("/validate", "/export"):
        response = client.post(FILES + operation, json=envelope(original, changes=changes))
        error = assert_error(response, 422, code)
        if issue:
            assert error["issues"][0]["code"] == issue
        assert "secret_payload" not in response.text


def test_limits_with_and_without_content_length(client):
    limited = make_client(env="development", max_file_bytes=4)
    # El quinto byte comparte longitud Base64 con cuatro bytes.
    assert_error(limited.post(FILES + "/inspect", json=envelope(b"abcde")), 413, "file_too_large")
    assert_error(limited.post(FILES + "/inspect", json=envelope(b"x" * 100)), 413, "file_too_large")
    assert_error(limited.post(FILES + "/inspect", content=b"x" * 18_000,
                              headers={"content-type": "application/json"}), 413, "request_too_large")
    assert_error(limited.post(FILES + "/inspect", content=iter([b" " * 9000, b" " * 9000]),
                              headers={"content-type": "application/json"}), 413, "request_too_large")


def test_export_limit_applies_to_serialized_result(client):
    compact = DEMO_SIGNATURE + b'{"fixture_id":"x","label":"x","sample_count":2,"sample_limit":3}'
    limited = make_client(env="development", max_file_bytes=len(compact))
    assert limited.post(FILES + "/inspect", json=envelope(compact)).status_code == 200
    assert_error(limited.post(FILES + "/export", json=envelope(compact, changes={"label": "larger"})),
                 413, "file_too_large")


def test_malformed_requests_do_not_echo_payload(client, original):
    assert_error(client.post(FILES + "/inspect", content=b"secret_payload"), 415, "invalid_content_type")
    assert_error(client.post(FILES + "/inspect", content=b"x",
                             headers={"content-type": "application/json", "content-encoding": "gzip"}),
                 415, "invalid_content_type")
    assert_error(client.post(FILES + "/inspect", content=b'{"content_base64":"a","content_base64":"b"}',
                             headers={"content-type": "application/json"}), 400, "invalid_request")
    invalid = client.post(FILES + "/inspect", json=envelope(original, filename="../../secret_payload"))
    assert_error(invalid, 422, "invalid_request")
    assert "secret_payload" not in invalid.text


def test_production_fails_closed(client, original):
    production = make_client(env="production")
    assert production.get(V1 + "/health").json()["access_mode"] == "disabled"
    for operation in ("/inspect", "/validate", "/export"):
        assert_error(production.post(FILES + operation, content=b"not parsed"), 503, "access_disabled")
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, env="production", access_token="too-short")
    assert "too-short" not in str(caught.value)


def test_token_protects_every_file_route(client, original):
    private = make_client(env="production", access_token=TEST_TOKEN)
    assert private.get(V1 + "/health").json()["access_mode"] == "token"
    for operation in ("/inspect", "/validate", "/export"):
        missing = private.post(FILES + operation, content=b"not parsed")
        assert_error(missing, 401, "access_denied")
        assert missing.headers["www-authenticate"] == "Bearer"
        assert_error(private.post(FILES + operation, headers={"Authorization": "Bearer wrong"}),
                     401, "access_denied")
        payload = envelope(original) if operation == "/inspect" else envelope(original, changes={})
        assert private.post(FILES + operation, json=payload,
                            headers={"Authorization": f"Bearer {TEST_TOKEN}"}).status_code == 200


def test_local_mode_requires_loopback_and_local_host(client, original):
    remote = TestClient(create_app(Settings(_env_file=None, env="development")),
                        base_url="http://127.0.0.1", client=("192.0.2.1", 50000))
    assert_error(remote.post(FILES + "/inspect", json=envelope(original),
                             headers={"X-Forwarded-For": "127.0.0.1"}), 403, "local_access_only")
    assert_error(client.post(FILES + "/inspect", json=envelope(original),
                             headers={"Host": "public.example"}), 403, "local_access_only")


def test_cors(client, original):
    preflight = client.options(FILES + "/export", headers={
        "Origin": ORIGIN, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    })
    assert preflight.status_code == 200
    assert preflight.headers["Access-Control-Allow-Origin"] == ORIGIN
    denied = client.options(FILES + "/export", headers={
        "Origin": "https://foreign.example", "Access-Control-Request-Method": "POST",
    })
    assert denied.status_code == 400
    assert "Access-Control-Allow-Origin" not in denied.headers
    download = client.post(FILES + "/export", json=envelope(original, changes={}), headers={"Origin": ORIGIN})
    assert download.headers["Access-Control-Expose-Headers"] == "Content-Disposition"


def test_openapi_contract(client):
    schema = client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["EditorBearer"]["scheme"] == "bearer"
    for operation in ("/inspect", "/validate", "/export"):
        contract = schema["paths"][FILES + operation]["post"]
        assert contract["security"] == [{"EditorBearer": []}]
        assert "application/json" in contract["requestBody"]["content"]
        errors = contract["responses"]["422"]["content"]["application/json"]["schema"]
        assert errors["$ref"].endswith("/ErrorResponse")
    export = schema["paths"][FILES + "/export"]["post"]["responses"]["200"]["content"]
    assert export["application/octet-stream"]["schema"]["format"] == "binary"

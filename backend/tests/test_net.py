"""Resolución de IP con proxies confiables explícitos."""

from __future__ import annotations

from starlette.requests import Request

from app.net import client_ip, parse_trusted_proxies


def request(host: str, headers: dict[str, str] | None = None) -> Request:
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": raw_headers,
            "client": (host, 12345),
            "scheme": "https",
            "server": ("api.example.test", 443),
        }
    )


def test_forwarded_headers_are_ignored_for_untrusted_sockets():
    value = client_ip(
        request("198.51.100.20", {"x-forwarded-for": "203.0.113.9", "x-real-ip": "203.0.113.10"}),
        ["10.0.0.0/8"],
    )
    assert value == "198.51.100.20"


def test_trusted_proxy_uses_rightmost_untrusted_hop():
    value = client_ip(
        request(
            "10.0.0.5",
            {"x-forwarded-for": "192.0.2.1, 203.0.113.9, 10.0.0.4"},
        ),
        ["10.0.0.0/8"],
    )
    assert value == "203.0.113.9"


def test_trusted_proxy_accepts_a_single_hop_and_ipv6():
    assert client_ip(request("10.0.0.5", {"x-forwarded-for": "203.0.113.7"}), ["10.0.0.0/8"]) == "203.0.113.7"
    assert client_ip(request("fd00::1", {"x-forwarded-for": "2001:db8::7"}), ["fd00::/8"]) == "2001:db8::7"


def test_trusted_proxy_falls_back_to_socket_when_header_is_invalid():
    assert client_ip(request("10.0.0.5", {"x-forwarded-for": "not-an-ip"}), ["10.0.0.0/8"]) == "10.0.0.5"


def test_parse_trusted_proxies_ignores_invalid_and_normalizes():
    values = parse_trusted_proxies(["10.0.0.5", "10.0.0.0/8", "invalid", ""])
    assert [str(value) for value in values] == ["10.0.0.5/32", "10.0.0.0/8"]

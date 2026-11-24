"""Resolución de la IP del cliente detrás de proxies confiables.

No se acepta ``X-Forwarded-For`` de cualquier origen: solo se interpreta
cuando el socket pertenece a una red listada en ``SK_NATIVE_TRUSTED_PROXIES``.
En ese caso se recorre la cadena de derecha a izquierda, se descartan los
proxies confiables y se devuelve el primer salto no confiable. Un cliente no
puede falsificar su IP para el limitador de intentos.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable

from fastapi import Request

type Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def parse_trusted_proxies(values: Iterable[str] | None) -> tuple[Network, ...]:
    networks: list[Network] = []
    for value in values or ():
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            networks.append(ipaddress.ip_network(value.strip(), strict=False))
        except ValueError:
            continue
    return tuple(networks)


def _address(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1:candidate.index("]")]
    elif candidate.count(":") == 1 and "." in candidate:
        # IPv4 con puerto, por ejemplo 203.0.113.7:443.
        candidate = candidate.rsplit(":", 1)[0]
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        return None


def _trusted(address: ipaddress.IPv4Address | ipaddress.IPv6Address, networks: tuple[Network, ...]) -> bool:
    return any(address in network for network in networks if network.version == address.version)


def client_ip(request: Request, trusted_proxies: Iterable[str] | None = None) -> str:
    """IP efectiva del cliente, con proxies confiables explícitos."""

    socket_host = request.client.host if request.client else ""
    socket_address = _address(socket_host)
    networks = parse_trusted_proxies(trusted_proxies)
    if socket_address is None:
        return "unknown"
    if not networks or not _trusted(socket_address, networks):
        return str(socket_address)

    forwarded = request.headers.get("x-forwarded-for", "")
    hops = [part for part in (item.strip() for item in forwarded.split(",")) if part]
    if hops:
        # El proxy más cercano añade su salto al final. Se ignora todo lo que
        # esté a la derecha de un proxy confiable y se devuelve el primer
        # cliente no confiable.
        chain = hops + [socket_host]
        for raw in reversed(chain):
            address = _address(raw)
            if address is None:
                continue
            if _trusted(address, networks):
                continue
            return str(address)
        first = _address(chain[0])
        return str(first) if first is not None else str(socket_address)

    real_ip = _address(request.headers.get("x-real-ip", ""))
    if real_ip is not None:
        return str(real_ip)
    return str(socket_address)

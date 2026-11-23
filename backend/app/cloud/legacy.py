"""Lectura de solo lectura del agregado legacy observado en el cliente 8.8.0.

Esta respuesta no es CloudSaveGameData y no debe pasar al importador de copias.
Los campos contados son indicios; su ausencia no demuestra ausencia de progreso.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .provider import CloudProviderProtocolError, CloudProviderUnauthenticated, CloudProviderUnavailable
from ..cloud_save import MAX_INPUT_BYTES, CopyLimitError

LegacyFetch = Callable[[str, dict[str, str], float], tuple[int, bytes]]


def _post(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=b'{}', headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read(MAX_INPUT_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(MAX_INPUT_BYTES + 1)


@dataclass(frozen=True)
class LegacyAggregate:
    document: dict[str, object] = field(repr=False)

    def summary(self) -> dict[str, object]:
        # No se incluyen contenido, identidad, timestamps ni IDs.
        return {'kind': 'legacy', 'collection_counts': {
            name: len(self.document[name]) for name in
            ('heroData', 'petData', 'plantPotData', 'heroRoomData', 'gameItemData')
        }, 'progress': 'unknown'}


@dataclass(frozen=True)
class LegacyGatewayReader:
    token: str = field(repr=False)
    distro_id: str = field(repr=False)
    base_url: str = 'https://api-gateway.soulknight.chillyroom.com'
    timeout: float = 20.0
    fetch: LegacyFetch = field(default=_post, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.token, str) or not self.token.strip() or any(c in self.token for c in '\r\n'):
            raise CloudProviderUnauthenticated('Falta un token válido.')
        if not isinstance(self.distro_id, str) or not self.distro_id.strip() or any(c in self.distro_id for c in '\r\n'):
            raise CloudProviderProtocolError('Falta el identificador de distribución.')
        if not isinstance(self.base_url, str):
            raise CloudProviderProtocolError('URL del gateway inválida.')
        u = urlsplit(self.base_url)
        if u.scheme != 'https' or not u.hostname or u.username is not None or u.password is not None or u.query or u.fragment or u.path not in ('', '/'):
            raise CloudProviderProtocolError('URL del gateway inválida.')
        if isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float)) or not 0 < self.timeout <= 60:
            raise CloudProviderProtocolError('Tiempo de espera inválido.')

    def read(self) -> LegacyAggregate:
        headers = {'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json',
                   'Accept': 'application/json', 'x-game-id': '1', 'x-game': 'Soulknight',
                   'x-app-version': '8.8.0', 'x-game-version': '8.8.0', 'x-platform': 'android',
                   'x-game-lang': 'en', 'x-locale': 'en_US', 'x-distro-id': self.distro_id}
        try:
            status, body = self.fetch(self.base_url.rstrip('/') + '/Backup/FetchGameData', headers, self.timeout)
        except (OSError, urllib.error.URLError) as exc:
            raise CloudProviderUnavailable('No se pudo contactar con el gateway.') from exc
        if len(body) > MAX_INPUT_BYTES:
            raise CopyLimitError('La respuesta supera el límite permitido.')
        try:
            document = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            document = None
        code = document.get('errorCode') if isinstance(document, dict) else None
        if status in (401, 403) or code == 10001:
            raise CloudProviderUnauthenticated('El gateway rechazó la sesión.')
        if status != 200 or (isinstance(document, dict) and document.get('ok') is False):
            raise CloudProviderUnavailable(f'El gateway devolvió un error HTTP {status}.')
        required = ('heroData', 'petData', 'plantPotData', 'heroRoomData', 'gameItemData')
        if not isinstance(document, dict) or any(not isinstance(document.get(k), dict) for k in required):
            raise CloudProviderProtocolError('La respuesta no tiene la estructura legacy observada.')
        return LegacyAggregate(document)

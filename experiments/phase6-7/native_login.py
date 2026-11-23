#!/usr/bin/env python3
"""Hypothesis-driven Linux login experiment. The success contract is unverified."""
import getpass
import http.client
import zlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

URL = 'https://api-gateway.soulknight.chillyroom.com/UserAuth/Login'
LIMIT = 1024 * 1024

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class ExperimentError(Exception):
    pass

def authenticate(email, password, *, save_context=False):
    body = json.dumps({'loginType': 3, 'account': email, 'password': password,
                       'credential': None}).encode('utf-8')
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json; charset=utf-8'}
    if save_context:
        # Observed for BlobSave; inclusion in login remains an unverified hypothesis.
        headers.update({'x-game-id': '1', 'x-game': 'Soulknight', 'x-app-version': '8.8.0',
                        'x-game-version': '8.8.0', 'x-platform': 'android',
                        'x-game-lang': 'en', 'x-locale': 'en_US'})
    request = urllib.request.Request(URL, data=body, method='POST', headers=headers)
    try:
        response = urllib.request.build_opener(NoRedirect()).open(request, timeout=20)
    except urllib.error.HTTPError as exc:
        response = exc
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
        raise ExperimentError('No se pudo contactar con el gateway.') from None
    with response:
        if response.status != 200:
            # Avoid response bodies: they may contain credentials or personal details.
            raise ExperimentError(f'Gateway HTTP {response.status}; sin sesión validada.')
        try:
            raw = response.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise ExperimentError('Respuesta demasiado grande.')
            length = response.headers.get('Content-Length')
            if length is not None:
                try:
                    expected = int(length)
                except ValueError:
                    raise ExperimentError('Longitud HTTP inválida.') from None
                if expected < 0 or expected != len(raw):
                    raise ExperimentError('Respuesta HTTP incompleta.')
            encoding = response.headers.get('Content-Encoding', '').strip().lower()
            if encoding == 'gzip':
                decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
                raw = decoder.decompress(raw, LIMIT + 1)
                if len(raw) > LIMIT:
                    raise ExperimentError('Respuesta descomprimida demasiado grande.')
                if not decoder.eof or decoder.unused_data:
                    raise ExperimentError('Respuesta gzip incompleta o con datos adicionales.')
            elif encoding not in ('', 'identity'):
                raise ExperimentError('Codificación de respuesta desconocida.')
            result = json.loads(raw)
        except (ValueError, UnicodeDecodeError, OSError, EOFError, RecursionError, zlib.error, http.client.HTTPException):
            raise ExperimentError('Respuesta JSON inválida.') from None
    if not isinstance(result, dict):
        raise ExperimentError('Respuesta inesperada.')
    session, user = result.get('session'), result.get('user')
    if not isinstance(session, dict) or not isinstance(user, dict):
        raise ExperimentError('Contrato de sesión o desafío desconocido; detener y revisar.')
    token, expiry, uid = session.get('token'), session.get('expire'), session.get('uid')
    if not isinstance(token, str) or not token or type(expiry) is not int or expiry <= time.time():
        raise ExperimentError('Sesión ausente o caducada.')
    if not isinstance(user.get('email'), str) or user['email'].casefold() != email.casefold():
        raise ExperimentError('La identidad de correo no coincide.')
    if type(uid) is not int or type(user.get('id')) is not int or uid != user['id']:
        raise ExperimentError('No se pudo verificar la vinculación de identidad y sesión.')
    return token

def main():
    if sys.argv[1:] not in ([], ['--save-context']) or not sys.stdin.isatty():
        print('Uso interactivo: python native_login.py [--save-context]', file=sys.stderr)
        return 2
    email = input('Correo de laboratorio: ').strip()
    password = getpass.getpass('Contraseña: ')
    try:
        token = authenticate(email, password, save_context=(sys.argv[1:] == ['--save-context']))
        del password
        unique_id = getpass.getpass('Identificador de instalación autorizada: ')
        distro_id = getpass.getpass('Identificador de distribución autorizada: ')
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
        from app.cloud.modern import ModernCloudSaveProvider
        from app.cloud_save import CloudSaveError
        try:
            copy = ModernCloudSaveProvider(token, unique_id, distro_id).download()
        except (CloudSaveError, OSError):
            raise ExperimentError('No se pudo validar la descarga de la partida.') from None
        print(json.dumps({'identity_matches_hypothesis': True, 'download_structurally_valid': True,
                          'bytes': copy.metadata.size}))
        return 0
    except ExperimentError as exc:
        print(str(exc), file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())

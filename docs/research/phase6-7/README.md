# Fase 6.7 · Autenticación nativa desde Linux

**Estado: objetivos A–E verificados en el laboratorio; objetivo F propuesto, no integrado en producción.**

La fase obtuvo una **sesión nueva y válida desde Linux** con la cuenta de laboratorio, verificó su identidad y descargó la partida real con el proveedor existente, sin emulador activo ni reutilización de una sesión de Android. El cliente experimental vive en `experiments/phase6-7/native_auth.py`.

La diferencia decisiva frente a la Fase 6.6 fue la cabecera **`x-distro-id`**. Sin ella el gateway devuelve `502` con `errorCode=10003`. El cuerpo correcto es **JSON plano**; el gateway rechaza un cuerpo gzip con `400 Input validation failed`. La cabecera `x-unique-id` **no** es necesaria para el login, pero BlobSave sí exige el identificador de instalación válido para descargar.

## Evidencia real

| Comprobación | Resultado |
| --- | --- |
| Ejecución | Linux, 24 de noviembre de 2026, 00:05 UTC. Emulador detenido y sin sesión de Android en el proceso. |
| Login | `POST https://api-gateway.soulknight.chillyroom.com/UserAuth/Login`, HTTP `200`, sesión nueva de 32 caracteres. |
| Vigencia | `expire=1796083540` / `2026-12-01T00:05:40Z` (aproximadamente siete días), igual que la sesión observada del cliente oficial. |
| Token nuevo | SHA-256 `a8004db6…`; distinto del token de la sesión de Android (SHA-256 `f8afe27a…`). No se reutilizó ninguna sesión. |
| Identidad | `user.email` coincide con el correo introducido; `session.uid == user.id`; `player.id` coincide con la cuenta de laboratorio. |
| Descarga | HTTP `200`, `114.779` bytes, `17` secciones, `gameData.gems=99999`, SHA-256 `ace7c58b3c7776ce26afe4f18a362d819b804984b7ca37b3e4aab2bc5d82cfb1`. El proveedor `ModernCloudSaveProvider` validó el agregado. |
| Comparación cruzada | La sesión de Android, usada como control separado, descargó el mismo SHA-256 y el mismo tamaño. Esto no se usó como sesión para el login Linux. |
| CLI | `native_auth_cli.py` repitió el ciclo completo y descargó el mismo SHA-256, con otro token nuevo (`6bf0f95e…`). |
| Pruebas simuladas | 13 pruebas nuevas del cliente (24 con las 11 de la Fase 6.6) pasan sin red ni credenciales reales. |

Los valores completos y saneados están en [evidence.json](evidence.json). No se incluyen correo, UID, `player.id`, token, `distro_id` ni `unique_id` en claro.

## Contrato observado

### Endpoint y transporte

```text
POST https://api-gateway.soulknight.chillyroom.com/UserAuth/Login
```

HTTPS con verificación TLS normal, sin seguir redirecciones y con límite de respuesta. El cliente oficial usa el SDK `ChillyRoom.Services.UserAuthService.UserAuthClient`; el login por correo y contraseña llega a `PasswordAuthService.BaseLogin` y al estado asíncrono de `UserAuthClient.LoginAsync`. La observación directa del tráfico del cliente estuvo limitada por la validación estricta de certificado (`CheckCertHashTrusted`); **no se eludió esa validación**. El contrato se reconstruyó con la respuesta real, pruebas controladas de cabeceras y el análisis de metadatos, y se confirmó con una autenticación Linux real.

### Cabeceras

| Cabecera | Valor observado | Necesidad para login |
| --- | --- | --- |
| `Content-Type` | `application/json; charset=utf-8` | sí |
| `Accept` | `application/json` | sí |
| `Accept-Encoding` | `gzip` | observada |
| `User-Agent` | `Dalvik/2.1.0 (Linux; U; Android 11; sdk_gphone_x86_64 Build/RSR1.240422.006)` | observada |
| `x-game-id` | `1` | observada |
| `x-game` | `Soulknight` | observada |
| `x-app-version` | `8.8.0` | observada |
| `x-game-version` | `8.8.0` | observada |
| `x-platform` | `android` | observada |
| `x-game-lang` | `en` | observada |
| `x-locale` | `en_US` | observada |
| `x-distro-id` | UUID de la instalación | **obligatoria** |
| `x-unique-id` | identificador de instalación | no necesaria para login |

La omisión de `x-distro-id` devolvió `502` con `errorCode=10003`. Un UUID aleatorio devolvió `400` con `errorCode=10003`: el servidor valida el valor, no acepta uno arbitrario. La omisión de `x-unique-id` devolvió `200`.

### Cuerpo

JSON plano, sin compresión:

```json
{"loginType":3,"account":"<correo>","password":"<contraseña>","credential":null}
```

`loginType=3` es el selector de correo observado en el DTO. El cuerpo gzip, aunque el SDK contiene rutinas `Compress` y `ContentIsGzipEncoded`, fue rechazado por el gateway con `400` y el detalle `'0x1F' is an invalid start of a value`: el endpoint espera JSON directamente.

### Respuesta de éxito

```json
{
  "session": {"uid": "...", "token": "...", "expire": "..."},
  "user": {"id": "...", "email": "...", "isEmailValidated": true, "...": "..."},
  "player": {"id": "...", "status": 0, "betaAccess": true},
  "legacyGateway": {"token": "...", "host": "legacy-save.soulknight.chillyroom.com"},
  "isNewUser": false,
  "isNewPlayer": false
}
```

La sesión se considera válida solo si el token no está vacío, `expire` es futuro, `session.uid == user.id` y `user.email` coincide con el correo solicitado. La respuesta puede venir con `Content-Encoding: gzip`; el cliente la descomprime con límites.

## Matriz de hipótesis

| Hipótesis | Experimento | Resultado | Conclusión |
| --- | --- | --- | --- |
| El `502/10003` se debe a la falta de cabeceras de contexto | Login Linux con JSON plano y cabeceras de juego, sin `x-distro-id` | `502`, `errorCode=10003` | La cabecera de distribución es necesaria. |
| Cualquier UUID sirve como distribución | Login con UUID v4 aleatorio | `400`, `errorCode=10003` | El valor se valida contra la cuenta/instalación; no es arbitrario. |
| El cuerpo debe ir comprimido | Login con cuerpo gzip y `Content-Encoding: gzip` | `400 Input validation failed`, `0x1F` inválido | El gateway espera JSON plano; la compresión no es el requisito. |
| `x-unique-id` es obligatoria para login | Login sin `x-unique-id` | `200`, sesión nueva | No es necesaria para autenticar. |
| La respuesta contiene identidad verificable | Login real | `email`, `uid`, `player.id` coherentes | La identidad se puede comprobar localmente. |
| La sesión Linux sirve para BlobSave | Descarga con `ModernCloudSaveProvider` | `200`, `114.779` bytes, `17` secciones | El token es aceptado por el servicio de guardado. |
| La sesión Linux es independiente de Android | Emulador detenido, token nuevo, comparación de hashes | Login y descarga correctos; token distinto | No se reutilizó la sesión de Android. |
| El login exige un `unique_id` de instalación | Login sin `x-unique-id` | `200` | No para login; BlobSave sí lo exige. |
| Un `unique_id` nuevo sirve para descargar | Descarga con `linux_<uuid>` | `400` | BlobSave valida el identificador de instalación. |
| La validación TLS se puede observar con MITM | Proxy con CA de sistema | `Root Cert:false`, `CheckCertHashTrusted`, handshake rechazado | El cliente fija/valida el certificado; no se intentó eludirlo. |

## Cliente Linux

Archivos:

- [`native_auth.py`](../../../experiments/phase6-7/native_auth.py): autenticación, sesión, validación, descompresión y errores tipados.
- [`native_auth_cli.py`](../../../experiments/phase6-7/native_auth_cli.py): CLI interactiva, descarga opcional y archivo de sesión opcional con modo `0600`.
- [`test_native_auth.py`](../../../experiments/phase6-7/test_native_auth.py): pruebas simuladas.
- [`diagnostics/`](../../../experiments/phase6-7/diagnostics/README.md): escáner Frida de cadenas y límites de uso.

Características:

- La contraseña se lee con `getpass` (sin eco) o por `--password-stdin` para automatización controlada; nunca por argumento.
- No se persiste la contraseña. El token solo se escribe si se pide `--session-file`, con modo `0600` y sin correo.
- TLS se verifica normalmente; no se siguen redirecciones; se limita el tamaño y se rechazan codificaciones desconocidas.
- No hay reintentos automáticos; el proveedor aplica control de frecuencia.
- Los resúmenes usan SHA-256 de correo, UID, `player.id` y token, nunca los valores en claro.

### Uso

```bash
backend/.venv/bin/python experiments/phase6-7/native_auth_cli.py \
  --distro-id '<uuid de distribución>' \
  --unique-id '<identificador de instalación>' \
  --email '<correo>' \
  --password-stdin \
  --download /ruta/privada/partida.json \
  --json
```

Sin `--download`, el cliente solo autentica y muestra el resumen de identidad. `--distro-id` y `--unique-id` también se pueden pasar por `SK_NATIVE_DISTRO_ID` y `SK_NATIVE_UNIQUE_ID`. No se aceptan credenciales por variables de entorno.

## Pruebas

```bash
python3 -m unittest discover -s experiments/phase6-7 -v
backend/.venv/bin/python -m pytest -q backend/tests/test_cloud_modern.py backend/tests/test_cloud_blob_upload.py
```

Las pruebas simuladas cubren serialización, cabeceras, gzip de respuesta, error `502/10003`, identidad contradictoria, caducidad, redirecciones, tamaños, codificaciones y redacción de secretos. La prueba real se ejecutó con la cuenta de laboratorio y el emulador detenido; sus resultados están en [evidence.json](evidence.json).

## Objetivos

| Objetivo | Estado | Evidencia |
| --- | --- | --- |
| A · Comprensión del mecanismo | **Cumplido con límites** | Endpoint, cabeceras, cuerpo, respuesta, identidad y causas de `502/10003`; la captura TLS directa no fue posible por la validación estricta del certificado y no se eludió. |
| B · Autenticación real | **Cumplido** | Login Linux HTTP `200`, token nuevo, sin emulador. |
| C · Verificación de identidad | **Cumplido** | Correo, `uid`, `player.id` y comparación cruzada con la sesión de Android. |
| D · Descarga real | **Cumplido** | `114.779` bytes, `17` secciones, `gems=99999`, SHA-256 validado. |
| E · Autonomía | **Cumplido con aprovisionamiento** | Login y descarga desde Linux con el emulador detenido; `distro_id` y `unique_id` se configuran una vez y no son sesiones. |
| F · Preparación para producción | **Propuesta** | [integration.md](integration.md); no se modificó producción ni `main`. |

## Limitaciones verificadas

1. **`distro_id` es obligatorio y validado.** No se deriva del correo ni de la contraseña; un UUID aleatorio devuelve `10003`. En el laboratorio se obtuvo del cliente oficial (`LastLoginHostWithDistroId`). Una integración de producción necesita un canal autorizado del proveedor para aprovisionarlo.
2. **`unique_id` es obligatorio para BlobSave.** El login funciona sin él, pero la descarga con un identificador nuevo devolvió `400`. Para operar sin Android hace falta el identificador de instalación válido del titular.
3. **No se implementó registro ni recuperación de cuenta.** El flujo parte de una cuenta existente. Tampoco se probaron correos de verificación, 2FA, captchas ni desafíos del proveedor.
4. **No se verificó renovación.** La sesión dura aproximadamente siete días; no se observó un endpoint de renovación aceptado. El cliente vuelve a autenticar cuando caduca.
5. **Límite de intentos.** El cliente oficial registra `LoginTag throttleData`; el cliente Linux no reintenta y debe respetar `429` o bloqueos. No se hicieron pruebas masivas.
6. **Validación estricta del certificado.** El cliente oficial usa `CheckCertHashTrusted`; un proxy con CA propia fue rechazado. No se intentó eludir la validación ni la atestación.
7. **Alcance Android Global 8.8.0.** Las cabeceras, `loginType=3` y el `User-Agent` son observados para esa distribución. iOS y otras distribuciones quedan fuera.
8. **El cliente es experimental.** No es producción: no hay almacenamiento cifrado de sesiones, rotación, auditoría, límites por IP, ni integración con el backend existente.

## Reproducción

1. Obtener de una instalación propia y autorizada el `distro_id` y el `unique_id`; no publicarlos.
2. Ejecutar las pruebas simuladas.
3. Ejecutar la CLI con la cuenta de laboratorio y `--download` a una ruta privada.
4. Verificar tamaño, SHA-256, secciones y gemas con `reconstruct_cloud_save`.
5. No ejecutar reintentos si el gateway responde `10003`, `429` o un desafío.

La reproducción real requiere credenciales de la cuenta de laboratorio; no se incluyen.

## Integración futura

La propuesta está en [integration.md](integration.md): endpoint HTTPS del backend, recepción sin eco, autenticación con este módulo, validación de identidad, cifrado de la sesión en reposo, descarga con el proveedor existente, caducidad/revocación, límites y auditoría. No se integró en `main` porque el aprovisionamiento de `distro_id`/`unique_id` y la autorización del proveedor para terceros siguen pendientes.

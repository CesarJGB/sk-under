# Fase 6.8 · Seguridad de la autenticación nativa y del editor por cuenta

**Estado: revisión de seguridad sobre el código de la rama, no una declaración de producción.** Este documento describe lo que está implementado en `backend/app/native/`, `backend/app/api/native.py` y las piezas de nube que usa el flujo. No se ejecutaron pruebas reales contra ChillyRoom ni se desplegó nada; la evidencia automatizada es la suite local. Se distingue de forma explícita:

- **Implementado y probado:** el control existe y un test automatizado lo ejerce en verde.
- **Implementado, pendiente de prueba real:** el código existe, pero solo se ha ejercido con dobles de prueba o no se ha probado contra el proveedor, el navegador o el despliegue reales.
- **No implementado:** no hay control; no debe anunciarse.

Verificación local de la suite citada: `pytest tests/test_native_api.py tests/test_native_store.py tests/test_native_auth_client.py tests/test_native_provision.py -q` → **40 passed** (37 funciones, una parametrizada con cuatro variantes), el 2026-11-24.

## 1. Activos y modelo de amenazas

### 1.1 Activos

| Activo | Dónde vive | Sensibilidad | Tratamiento en el código |
| --- | --- | --- | --- |
| Credenciales ChillyRoom (correo y contraseña) | Cuerpo JSON de `POST /api/v1/cloud/native/login`; memoria del proceso; petición saliente | Crítica | Solo en memoria; no se persiste ni se registra; el campo se limpia en el formulario |
| Token de sesión del proveedor | AES-SIV en `sessions.token`; cabecera `Authorization` hacia BlobSave | Crítica | Cifrado y ligado al SHA-256 de la cookie; nunca se devuelve al navegador |
| Identificadores de instalación (`x-distro-id`, `x-unique-id`) | AES-SIV en `profiles.sealed`; cabeceras hacia el proveedor | Privados, no secretos de sesión | Cifrados y ligados al id de perfil; no se aceptan desde una URL |
| Cookie de navegador | Navegador; el servidor solo guarda su SHA-256 | Crítica mientras vive | `__Host-sk_native` con origen HTTPS (o `sk_native_dev` en desarrollo), `HttpOnly`, `Secure`, `SameSite=Strict` |
| Partidas y respaldos | `native-backups/<subject>/original.json`, `candidate.json`, `record.json`, `events.jsonl` | Alta (progreso real) | Directorio por subject, archivos `0600`; sin cifrado adicional |
| Clave `SK_NATIVE_STORE_KEY` | Variable de entorno y memoria del proceso | Crítica | 32 bytes; verificador HMAC en la base para fallar cerrado con otra clave |
| Metadatos de identidad e intentos | SQLite: hashes HMAC de correo, IP, uid, player; eventos | Media | Sin valores en claro; los hashes no son reversibles sin la clave |

### 1.2 Atacantes y superficies

| Atacante | Capacidad supuesta | Objetivo | Mitigación principal | Riesgo residual |
| --- | --- | --- | --- | --- |
| Internet sin credenciales | Alcanza la API pública y `GET /config` | Descubrir perfiles, forzar login, agotar recursos | Validación de entrada, límite de cuerpo, rate limit, errores genéricos | `/config` y `/session` son públicos; revelan etiquetas e ids de perfil no secretos y si hay login disponible |
| Otro usuario del editor | Tiene su propia cuenta y sesión | Leer o modificar la partida de otro | Sesión resuelta a perfil y subject; sin `account_id` en URLs; respaldos por subject; binding de identidad | Comparte el mismo proceso y volumen; el aislamiento es lógico, no criptográfico entre usuarios |
| Otro navegador | Roba o replica una cookie válida | Suplantar al titular | Cookie `HttpOnly`, `SameSite=Strict`, caducidad y revocación | La cookie es un portador: una copia robada funciona hasta caducar o cerrar sesión; no hay binding a dispositivo |
| Operador con acceso al volumen | Lee el volumen y, según el caso, el entorno | Extraer tokens, IDs o partidas | AES-SIV, permisos `0700/0600`, hashes HMAC | Ve los respaldos en claro; con la clave de entorno descifra las sesiones; con acceso al proceso, la clave en memoria |
| Sitio cruzado / CSRF | Induce peticiones desde otro origen | Ejecutar login, confirm o restore como el usuario | Origen exacto, `SameSite=Strict`, JSON obligatorio, `Sec-Fetch-Site` | No hay token CSRF; depende del navegador y de que el origen exacto no se comprometa |
| XSS en el editor | Ejecuta JavaScript en el origen del editor | Actuar como el usuario y leer la partida | `HttpOnly` impide leer la cookie; CORS exacto | Sin CSP: un XSS puede llamar a la API con `credentials: "include"` y operar como el titular |
| Fuerza bruta | Prueba credenciales y rota IP/correo | Adivinar contraseña | Rate limit por hash de IP y de correo, solo fallos, `429` con `Retry-After`, sin reintentos | Sin 2FA ni captcha; la comprobación y el registro no son atómicos; el proveedor puede imponer sus propios límites |
| Fugas por logs | Lee logs de la app, Uvicorn, proxy o panel | Obtener correo, token o IDs | Mensajes genéricos, hashes, subject truncado, sin cuerpos | Los logs de infraestructura y el panel de Coolify quedan fuera del control del código |

### 1.3 Fronteras de confianza

1. Navegador → API: HTTPS, origen exacto, cookie `HttpOnly`; el navegador nunca ve el token del proveedor.
2. API → SQLite y volumen: mismo contenedor; la confidencialidad depende de AES-SIV y de los permisos del volumen.
3. API → ChillyRoom: HTTPS saliente con validación TLS normal; el token y los identificadores viajan en cabeceras, no en la URL.

## 2. Controles implementados

### 2.1 Transporte saliente

- `backend/app/native/client.py · urllib_transport` usa TLS normal, desactiva los proxies del entorno con `urllib.request.ProxyHandler({})`, no sigue redirecciones (`_NoRedirect.redirect_request` devuelve `None`) y limita cada respuesta a `MAX_RESPONSE_BYTES = 1_048_576` bytes.
- `decode_response` solo acepta `identity` o `gzip`; rechaza codificaciones desconocidas, gzip corrupto, truncado o con bytes adicionales (`decoder.eof` y `decoder.unused_data`) y limita el tamaño descomprimido. También comprueba que `Content-Length`, si existe, coincida con lo leído.
- `NativeAuthClient.authenticate` hace una sola petición, sin reintentos, con timeout mayor que 0 y hasta 60 segundos. La contraseña viaja en el cuerpo del login; el token del proveedor, en `Authorization: Bearer` hacia BlobSave; ninguno se coloca en la URL.
- `backend/app/cloud/modern.py · _fetch` y `backend/app/cloud/blob_upload.py · _send/_validate_url` validan HTTPS (o loopback de prueba), usan `ssl.create_default_context()` en la subida y no siguen redirecciones. La respuesta de subida se limita a 64 KiB.
- **Precisión verificada:** `modern.py` usa el opener por defecto de `urllib` y no instala `ProxyHandler({})`; por tanto, la descarga BlobSave sí puede usar proxies de entorno. `client.py` y `blob_upload.py` no los usan. No se desactiva TLS en ningún caso.

### 2.2 Credenciales

- `backend/app/api/native.py · LoginInput` exige `distribution`, `email`, `password` y `profile_id` opcional, con `extra="forbid"`; el correo se valida además con `valid_email`.
- `backend/app/native/service.py · login` recibe la contraseña, la pasa a `NativeAuthClient.authenticate` y no la escribe, registra, devuelve ni incluye en eventos. No hay campo de contraseña en SQLite.
- `backend/app/native/client.py · build_login_body` construye el JSON con `loginType`, `account`, `password` y `credential`; `NativeAuthRejected` no conserva ni muestra el cuerpo remoto.
- `frontend/src/pages/NativeAuthPage.tsx` limpia el campo de contraseña justo después de leerlo y antes de enviar; los errores no incluyen la contraseña. `frontend/tests/native-auth.spec.ts` lo comprueba con API simulada.
- **Límite honesto:** Python no borra de forma garantizada la cadena de memoria; la contraseña también existe en el cuerpo de la petición y en el proveedor. No se ha auditado el volcado de memoria ni el swap.

### 2.3 Almacenamiento en reposo

- `backend/app/native/store.py · NativeStore.__init__` crea la raíz con `0700`, rechaza symlinks y permisos de grupo/otros, crea `native.sqlite3` con `0600` y `O_NOFOLLOW`, y falla si la base ya tiene permisos laxos.
- `_seal` y `_open` usan AES-SIV con dato asociado: `profile:<id>` para `distro`/`unique` y `session:<sha256(cookie)>` para el token. Un registro movido a otro perfil o sesión no descifra.
- La tabla `encryption` guarda `HMAC(key, "sk-under/native-store")`; con una clave distinta el arranque lanza `NativeStoreMisconfigured` en vez de abrir la base. `connect` activa `foreign_keys` y `secure_delete`.
- Solo se persisten hashes HMAC (`_digest`: IP, correo normalizado, identidad, uid, player) y la identidad de guardado (`save_subject`). El valor de la cookie no se guarda, solo su SHA-256 como clave primaria de `sessions`.
- **Probado:** `backend/tests/test_native_store.py · test_profile_and_session_are_encrypted_and_bind_identity` lee los bytes crudos de la base y comprueba que no aparecen `distro`, `unique`, el token ni la cookie, y que los modos son `0600/0700`.

### 2.4 Cookie y ciclo de sesión

- `backend/app/native/service.py · NativeAuthService.__init__` elige `__Host-sk_native` si el origen configurado es HTTPS; en desarrollo con loopback usa `sk_native_dev`. `build_native` rechaza orígenes no HTTPS fuera de desarrollo local.
- `backend/app/api/native.py · login` emite la cookie con `secure`, `httponly=True`, `samesite="strict"`, `path="/"`, sin `Domain`, y `max_age` limitado por la caducidad efectiva. `logout` borra la fila de sesión y la cookie con los mismos atributos.
- El identificador de sesión es `sha256(cookie)`; la cookie es `token_urlsafe(32)` y solo el hash se usa para buscar. `_cookie` lee exclusivamente el nombre esperado.
- La sesión resultante se resuelve por cookie; no hay identificador de cuenta ni de sesión elegible en la URL.

### 2.5 Aislamiento por identidad

- Las rutas de `backend/app/api/native.py` no incluyen `account_id`, `profile_id` ni `subject` en la URL: `login` acepta un `profile_id` opcional en el cuerpo, pero la sesión posterior se resuelve siempre por cookie.
- `store.identity_subject` deriva el subject de `correo normalizado + uid + player.id` con HMAC. `client.authenticate` ya exige `session.uid == user.id`, correo coincidente, `player.id > 0` y sesión no caducada. `service.login` vuelve a comparar correo y `distro_id`.
- `store.bind` fija el subject en el perfil en el primer login y lanza `NativeProfileIdentityMismatch` si otro subject intenta reutilizarlo. El índice único parcial `profiles_subject` refuerza la regla.
- `NativeSaveProvider.download` calcula `save_subject` desde `cloudSaveId`/`platformId` y llama a `store.bind_save_subject`; la primera descarga fija la identidad de guardado y un cambio posterior lanza `NativeSaveIdentityMismatch` antes de completar el login/operación.
- `service._lab` y `service.backups` construyen `LabBackupStore(self.backup_root / session.subject)`; un subject solo ve su directorio. `_subject_lock` usa `flock` sobre `_locks/<subject>.lock` (`0700`/`0600`, `O_NOFOLLOW`) para serializar `confirm` y `restore`.
- `store.claim_confirmation_attempt` crea `upload-attempt` con `O_EXCL`; `service.confirm` pasa `single_attempt=True`, de modo que un mismo respaldo no se sube dos veces, incluso con dos sesiones concurrentes.

### 2.6 Superficie HTTP, CSRF y límites

- `backend/app/api/native.py · NativeRoute.guarded` exige que el `Origin` sea exactamente `service.origin` en todo `POST`; en `GET`/`HEAD`, si el origen viene, también debe coincidir. Si el servicio no está disponible, los `POST` solo aceptan orígenes de `SK_ALLOWED_ORIGINS`.
- `Sec-Fetch-Site`, si está presente, solo admite `same-origin`, `same-site` o `none`. Un valor `cross-site` se rechaza.
- Los `POST` exigen `Content-Type: application/json` (se ignora el parámetro `charset`) y `Content-Encoding: identity`; en otro caso devuelven `415`. `BoundedJSONRequest` corta el cuerpo en `JSON_LIMIT = 8192` bytes, antes de parsear, y devuelve `413 request_too_large`. También valida un único `Content-Length` numérico.
- `backend/app/main.py` configura CORS con `allow_origins` exactos (validados sin ruta, comodines ni credenciales embebidas), `allow_credentials=True`, `allow_methods=["GET", "POST"]` y una lista cerrada de cabeceras. `PRIVATE_HEADERS` añade `Cache-Control: no-store` y `X-Content-Type-Options: nosniff`.
- `backend/app/errors.py` centraliza los errores: `RequestValidationError` se convierte en un `422` genérico para no devolver fragmentos de entrada; `NativeRoute` convierte excepciones no previstas en `500 native_error` sin detalles y registra solo el nombre de la ruta y el tipo de excepción.
- **CSRF:** no hay token CSRF. La defensa es la combinación de `Origin` exacto, `SameSite=Strict`, `HttpOnly`, JSON obligatorio y CORS cerrado. Es un control válido para este flujo, pero no equivale a un token anti-CSRF y depende del navegador.

### 2.7 Límite de intentos

- `store.check_login_rate` cuenta solo intentos con `outcome != 'ok'` en la ventana configurable, por hash HMAC de IP y de correo; aplica el máximo de ambos contadores y calcula `Retry-After` desde el intento más antiguo. `service.login` lo invoca antes de autenticar y `record_attempt` registra el resultado en `finally`.
- `backend/app/api/native.py` traduce `NativeError` a `EditorError` y copia `retry_after` a la cabecera `Retry-After`; el proveedor `429` también se tipa como `NativeProviderThrottled` con `retry_after=60`.
- No hay reintento automático en el cliente, en el servicio ni en el frontend; `confirm` además consume un único intento por respaldo.
- **Precisión verificada:** el contador vive en SQLite, no en memoria, y sobrevive reinicios; pero `check_login_rate` y `record_attempt` son transacciones separadas, así que una ráfaga concurrente puede superar el umbral antes de que se registre el fallo. Tampoco hay límite distribuido: la fase asume una réplica y la IP que ve Uvicorn (`request.client.host`), que detrás del proxy puede ser la del proxy si no se configura `--forwarded-allow-ips`.

### 2.8 Caducidad y revocación

- `NativeStore` combina `idle_seconds` (por defecto 1800) y `absolute_seconds` (por defecto 7 días); `create_session` guarda `min(session.expire, now + absolute_seconds)` y `session` rechaza sesiones revocadas, caducadas o inactivas.
- `service.logout` borra la fila (y con ella el token cifrado) y `api/native.py` borra la cookie. No se llama a ningún endpoint del proveedor: **no se afirma revocación remota**.
- En las operaciones del editor (`load`, `prepare`, `confirm`, `restore`, `verify`), `service._operate` captura `CloudProviderUnauthenticated`, revoca la sesión local y responde `401 native_session_expired`.
- El login y `complete_installation` también fallan cerrados ante `CloudProviderUnauthenticated`: el login devuelve `native_session_rejected` sin crear sesión y la instalación revoca la sesión y devuelve `native_session_expired`. Ambos casos están cubiertos por `test_login_fails_closed_when_blob_save_rejects_the_token` y `test_installation_fails_closed_when_blob_save_rejects_the_token`.

### 2.9 Logs y diagnóstico

- `GatewaySession` oculta token, correo y `distro_id` en `repr`; `summary` solo expone SHA-256. `store.recent_events` devuelve el subject truncado a 12 caracteres. `service.diagnostics` devuelve contadores, configuración y eventos, sin correo, token ni identificadores.
- Los mensajes de error nativos son textos fijos y genéricos; los cuerpos remotos no se conservan. Los `events` guardan el subject HMAC completo, que no es reversible sin la clave.
- **Límite:** no hay una prueba automática que capture los logs de la aplicación; la garantía es por inspección del código. Los logs de Uvicorn, Cloudflare, Traefik y Coolify no los controla este repositorio.

### 2.10 Aprovisionamiento

- `backend/app/native/provision.py` es una CLI local: no importa clientes de red, lee `distro`/`unique` con `getpass` (sin eco) o desde `stdin` (`--distro-stdin`, `--unique-stdin`), y no acepta esos valores como argumentos. `--list` y el JSON de salida solo muestran campos públicos.
- `store.create_profile` exige una distribución `enabled` y `validated`; el registro solo valida `android-global`. Un test crea `ios-global` y comprueba el rechazo.
- Los identificadores son opcionales por entorno (`SK_NATIVE_DISTRO_ID`, `SK_NATIVE_UNIQUE_ID`); el backend crea el perfil inicial si el primero está presente. No se generan `distro_id`/`unique_id` aleatorios: `uuid4` se usa solo para el id de perfil y el id de respaldo.
- La CLI real acepta `--label`, `--distribution`, `--allow-write`, `--no-unique`, `--distro-stdin` y `--unique-stdin`; los identificadores no se pasan como argumentos visibles. `deployment.md` se corrigió para usar estos nombres.

### 2.11 Escritura opt-in

- `service._require_write` exige el interruptor global `native_write_enabled`, el permiso del perfil (`allow_write`) y una instalación completa. `_lab` solo construye el uploader si ambos interruptores están activos; `CloudLabService.confirm/restore` vuelven a comprobarlo.
- `backend/app/models.py` exige la frase literal `SUBIR` para confirmar y `RESTAURAR` para restaurar (`Literal`). El frontend la envía desde `frontend/src/api.ts`.
- `prepare` descarga, valida `source_sha256`, crea el respaldo con original y candidato exactos y lo verifica de nuevo al cargarlo. `confirm` comprueba la huella esperada, que la nube siga en el original, que no haya confirmación previa, consume el intento único, sube, descarga y solo registra persistencia si el SHA-256 y el tamaño coinciden.
- `restore` solo actúa si la nube conserva el candidato confirmado; si ya tiene el original, no sube nada. La restauración no se permite si la nube cambió a un tercer estado.
- **Límite:** un intento de subida fallido consume el `upload-attempt`; para reintentar hace falta preparar otro respaldo. Es deliberado (evita reintentos automáticos), pero operativamente exige volver a descargar y preparar.

## 3. Mapa de pruebas automatizadas

La suite backend usa transportes y proveedores inyectados: valida contratos y controles, no TLS real, ni el gateway, ni el navegador.

| Control | Prueba | Archivo |
| --- | --- | --- |
| Sin secretos en respuesta de login; cookie `HttpOnly`/`SameSite`/`Path`; DB `0600` | `test_login_sets_an_isolated_cookie_and_never_echoes_secrets` | `backend/tests/test_native_api.py` |
| Cookie `Secure` y `__Host-` con origen HTTPS | `test_secure_cookie_and_https_origin` | `backend/tests/test_native_api.py` |
| `Origin` ausente, ajeno y `Sec-Fetch-Site: cross-site`; `Content-Type`; cuerpo > 8192; `GET` con origen ajeno | `test_origin_content_type_and_body_limits_are_enforced` | `backend/tests/test_native_api.py` |
| Identidad contradictoria no crea sesión ni filtra el correo | `test_identity_mismatch_does_not_create_a_session` | `backend/tests/test_native_api.py` |
| Perfil no reutilizable por otra cuenta; segundo perfil duplicado rechazado sin 500 | `test_profile_cannot_be_reused_for_another_account`, `test_a_second_profile_for_the_same_identity_is_rejected_cleanly` | `backend/tests/test_native_api.py` |
| Aislamiento de sesiones, respaldos y partidas; replay de cookie; logout | `test_two_accounts_have_isolated_sessions_backups_and_saves` | `backend/tests/test_native_api.py` |
| BlobSave rechaza el token: login sin sesión y revocación al completar instalación | `test_login_fails_closed_when_blob_save_rejects_the_token`, `test_installation_fails_closed_when_blob_save_rejects_the_token` | `backend/tests/test_native_api.py` |
| Partida de otra cuenta rechazada tras el binding | `test_a_save_from_another_account_is_rejected_after_binding` | `backend/tests/test_native_api.py` |
| Caducidad absoluta y por inactividad; persistencia tras reinicio | `test_session_expiry_idle_and_restart_persistence` | `backend/tests/test_native_api.py` |
| Tres interruptores de escritura y frase `SUBIR`; restore | `test_write_requires_global_flag_profile_permission_and_confirmation` | `backend/tests/test_native_api.py` |
| Varios perfiles exigen elección explícita | `test_multiple_profiles_require_an_explicit_choice` | `backend/tests/test_native_api.py` |
| Concurrencia: una sola subida por respaldo | `test_concurrent_confirmation_uploads_exactly_once` | `backend/tests/test_native_api.py` |
| Diagnóstico saneado y privado | `test_diagnostics_are_sanitized_and_private` | `backend/tests/test_native_api.py` |
| Deshabilitado por defecto sin parsear credenciales | `test_native_auth_is_disabled_by_default_and_does_not_parse_credentials` | `backend/tests/test_native_api.py` |
| Cifrado y binding de perfil/sesión; modos `0600/0700`; cookie no guardada | `test_profile_and_session_are_encrypted_and_bind_identity` | `backend/tests/test_native_store.py` |
| Clave incorrecta cierra el almacén | `test_wrong_key_does_not_open_the_store` | `backend/tests/test_native_store.py` |
| Caducidad, inactividad y revocación local | `test_session_expiry_idle_and_revocation` | `backend/tests/test_native_store.py` |
| Instalación solo desde la identidad vinculada | `test_installation_requires_the_bound_identity` | `backend/tests/test_native_store.py` |
| Identidad de guardado fijada en la primera descarga | `test_save_identity_is_fixed_on_first_download` | `backend/tests/test_native_store.py` |
| Rate limit por IP o correo | `test_login_rate_limit_is_per_identity_or_address` | `backend/tests/test_native_store.py` |
| Solo `android-global` habilitada | `test_distribution_registry_only_enables_validated_global` | `backend/tests/test_native_store.py` |
| Cabeceras y cuerpo observados; sin `x-unique-id` en login | `test_headers_and_body_follow_the_observed_contract` | `backend/tests/test_native_auth_client.py` |
| Gzip con límites | `test_gzip_response_is_decompressed_with_limits` | `backend/tests/test_native_auth_client.py` |
| `10003` y `429` tipados | `test_distribution_rejection_and_throttling_are_typed` | `backend/tests/test_native_auth_client.py` |
| Cuerpo remoto no se filtra | `test_credentials_are_rejected_without_echoing_the_upstream_body` | `backend/tests/test_native_auth_client.py` |
| Error de red, respuesta > 1 MiB, JSON inválido, codificación desconocida | `test_network_and_protocol_errors_are_typed` | `backend/tests/test_native_auth_client.py` |
| `uid`, correo, caducidad y `player.id` inconsistentes | `test_identity_checks_reject_inconsistent_responses` | `backend/tests/test_native_auth_client.py` |
| Argumentos inválidos no tocan el transporte | `test_invalid_arguments_do_not_reach_the_transport` | `backend/tests/test_native_auth_client.py` |
| `repr` de sesión sin secretos | `test_session_repr_hides_secrets` | `backend/tests/test_native_auth_client.py` |
| CLI sin eco; pendiente; distribución no validada | `test_provision_cli_creates_a_profile_without_printing_identifiers`, `test_provision_cli_can_leave_the_installation_pending`, `test_provision_cli_rejects_an_unvalidated_distribution` | `backend/tests/test_native_provision.py` |
| Contraseña limpiada y frase de confirmación en UI (API simulada) | `rechaza credenciales sin filtrar detalles y limpia la contraseña`; `inicia sesión, descarga, prepara, confirma y cierra sesión` | `frontend/tests/native-auth.spec.ts` |

**No cubierto por pruebas:** TLS y certificado reales; preflight CORS real; navegador real; logs; aprovisionamiento con identificadores reales; cuentas reales y proveedor real. El rate limit concurrente no se prueba con una ráfaga; la prueba de concurrencia es de confirmación.

## 4. Riesgos residuales y limitaciones verificadas

### 4.1 Identidad, sesión y proveedor

- **Sin 2FA, captcha ni renovación.** No hay segundo factor, desafío anti-bot ni refresh token. Cuando el token del proveedor caduca (aproximadamente siete días), el usuario debe volver a introducir su contraseña. La sesión local puede durar hasta el mínimo entre la caducidad del proveedor y siete días; la inactividad la corta a los 30 minutos por defecto.
- **Logout no revoca el token remoto.** Se borra la copia local y la cookie; el token de ChillyRoom sigue siendo válido para el proveedor hasta su caducidad. No se ha verificado ningún endpoint de revocación.
- **El proveedor puede limitar o desafiar.** Un `429` o un `10003` se tipan y no se reintentan, pero no se puede garantizar que ChillyRoom no aplique límites, captchas o bloqueos por dispositivo/IP. Tampoco hay autorización del proveedor para uso de terceros ni mecanismo oficial de aprovisionamiento.
- **La primera descarga no tiene referencia previa.** El binding de `cloudSaveId`/`platformId` fija la identidad en la primera descarga; si un titular con sesión sustituye su `unique_id` antes de esa primera descarga, no hay un valor anterior contra el que comparar. Se asume que BlobSave autoriza por token y que `x-unique-id` no selecciona por sí solo la partida de otra cuenta; no está verificado con el proveedor.

### 4.2 Datos y volumen

- **Respaldos con progreso real, sin cifrado adicional.** `original.json` y `candidate.json` contienen la partida; están en un directorio `0700` y archivos `0600`, pero no se cifran con la clave nativa. Quien lea el volumen los lee en claro.
- **La clave vive en la memoria del proceso.** No hay KMS, enclave ni rotación automática. Un operador con acceso al proceso o al entorno puede extraerla y descifrar tokens e identificadores. La rotación es destructiva: una clave nueva no descifra el volumen anterior y el verificador impide abrirlo; hay que archivar el volumen y re-aprovisionar.
- **SQLite y una sola réplica.** El almacén, los intentos y los eventos viven en SQLite; no hay alta disponibilidad ni escritura multi-proceso probada. El despliegue previsto usa una réplica y sin `--workers`. Un volumen perdido detiene el servicio y borra perfiles, sesiones y respaldos.

### 4.3 Superficie web

- **Sin CSP fuerte.** `frontend/public/_headers` solo define `X-Content-Type-Options`, `X-Frame-Options` y `Referrer-Policy`; no hay `Content-Security-Policy`. `docs/research/phase6-8/deployment.md` propone un bloque CSP, pero no está en el archivo actual. Un XSS en el editor podría llamar a la API como el titular; `HttpOnly` protege la cookie, no impide las peticiones autenticadas.
- **Sin token CSRF.** La protección es `Origin` exacto, `SameSite=Strict` y JSON obligatorio. Es razonable para este flujo, pero no cubre un navegador con un fallo de same-site ni un compromiso del origen exacto.
- **Cookie portadora.** No hay binding a dispositivo ni a TLS del cliente; una cookie robada se puede reutilizar hasta la caducidad o el logout. `HttpOnly` y `SameSite=Strict` reducen el robo, no lo eliminan.
- **`/config` y `/session` son públicos.** `GET /config` lista etiquetas e ids de perfil y distribuciones habilitadas. No son secretos, pero revelan la existencia y los nombres de los perfiles. El resto de operaciones exige cookie; `/diagnostics` exige cookie o `SK_ACCESS_TOKEN`.
- **Rate limit con ventana de carrera.** La comprobación y el registro no son atómicos; una ráfaga concurrente puede superar el umbral. La IP es la que ve Uvicorn; detrás de Traefik/Cloudflare puede ser la del proxy si no se ajusta `--forwarded-allow-ips`. El registro persiste en SQLite y sobrevive reinicios, pero no es un límite distribuido. `deployment.md` ya describe esta misma limitación.

### 4.4 Operación y documentación

- **Aprovisionamiento manual y confianza en el propietario.** La CLI debe ejecutarse en un proceso privado con la misma clave y el mismo volumen; el propietario introduce los identificadores. No hay flujo de autoservicio ni verificación de que la instalación pertenezca al titular.
- **`x-distro-id`/`x-unique-id` no son secretos, pero son privados.** No se publican en el repositorio ni en las respuestas, y `unique_id` se guarda cifrado; aun así, quien los obtenga puede intentar reutilizarlos. No se generan aleatoriamente.
- **Documentación alineada:** `GET /config` emite `native_auth_ready`; la CLI del runbook usa `--label`/`--distribution` con lectura sin eco; el preflight usa `Content-Type` y ya no menciona `x-csrf-token`. Las comprobaciones de `deployment.md` coinciden con el contrato actual.
- **Auditoría best-effort.** `record_attempt` y `_event` se invocan de forma que un fallo del diario no oculta el resultado; a cambio, una base bloqueada o llena puede perder intentos y eventos, debilitando el rate limit y la auditoría.

## 5. Reglas operativas

1. No activar `SK_NATIVE_WRITE_ENABLED` ni `SK_NATIVE_PROFILE_ALLOW_WRITE` por defecto. La fase es de lectura; `confirm` y `restore` solo se prueban con autorización explícita y cuenta propia.
2. No publicar `SK_NATIVE_STORE_KEY`, `SK_CLOUD_ACCOUNTS_KEY`, tokens, correos ni identificadores de instalación en Git, issues, capturas, logs, historial de shell o variables `VITE_*`.
3. Tratar la rotación de `SK_NATIVE_STORE_KEY` como destructiva: detener la app, archivar el volumen `native/`, conservar la clave anterior, generar la nueva, re-aprovisionar y volver a iniciar sesión. No mezclar volumen viejo con clave nueva.
4. Limitar el acceso al panel de Coolify y a las variables de runtime; usar variables bloqueadas, sin exposición en build, y revisar quién puede leerlas.
5. Revisar los logs de la aplicación y del proxy sin volcar el entorno; recordar que los logs de infraestructura quedan fuera del saneamiento del código.
6. Respaldar el volumen completo con la aplicación detenida, conservar propietario y modos, guardar una copia fuera del servidor y probar una restauración en un destino desechable. La copia incluye partidas reales: trátala como dato sensible.
7. Usar solo cuentas propias y autorizadas. No reutilizar `distro_id`, `unique_id` ni tokens entre perfiles; no automatizar reintentos ante `429` o `10003`; no ejecutar pruebas de carga contra ChillyRoom.

## 6. Cumplimiento de la sección 10 del encargo

| Requisito | Estado | Evidencia / limitación |
| --- | --- | --- |
| HTTPS | Implementado; verificación real pendiente | TLS normal y sin proxies de entorno en `client.py`; `_send` con `ssl.create_default_context`; origen HTTPS exigido por `build_native`. Los tests inyectan el transporte: no prueban handshake real. `modern.py` sí puede usar proxies de entorno. |
| Sesiones | Implementado y probado | `store.create_session/session`, `service.login`; `test_session_expiry_idle_and_restart_persistence`, `test_session_expiry_idle_and_revocation`. |
| Cookies | Implementado y probado (atributos); navegador real pendiente | `__Host-sk_native`, `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, sin `Domain`; `test_secure_cookie_and_https_origin`, `test_login_sets_an_isolated_cookie_and_never_echoes_secrets`. |
| CORS | Implementado; preflight real pendiente | Orígenes exactos, credenciales, métodos `GET/POST` y cabeceras cerradas en `main.py`; el guard de origen sí está probado, el preflight del navegador no. |
| CSRF | Implementado sin token; prueba real pendiente | `Origin` exacto, `SameSite=Strict`, JSON obligatorio, `Sec-Fetch-Site`; `test_origin_content_type_and_body_limits_are_enforced`. No hay token CSRF ni CSP. |
| Límites | Implementado y probado | 8192 bytes de cuerpo, 1 MiB de respuesta de login, 64 KiB de respuesta de subida, timeout y gzip estricto; `test_origin_content_type_and_body_limits_are_enforced`, `test_network_and_protocol_errors_are_typed`. |
| Cruce de cuentas | Implementado y probado | Subject por identidad, binding de perfil y de guardado, respaldos por subject, sin `account_id` en URLs; `test_two_accounts_have_isolated_sessions_backups_and_saves`, `test_profile_cannot_be_reused_for_another_account`, `test_a_save_from_another_account_is_rejected_after_binding`. |
| Caducidad y revocación | Implementado y probado en local; revocación remota no implementada | Inactividad + absoluta, logout local, revocación ante `CloudProviderUnauthenticated` en operaciones, login y completar instalación; no hay endpoint de revocación del proveedor. |
| Saneamiento | Implementado; logs sin prueba automatizada | Respuestas y DB sin correo/token/IDs; `test_login_sets_an_isolated_cookie_and_never_echoes_secrets`, `test_diagnostics_are_sanitized_and_private`, `test_credentials_are_rejected_without_echoing_the_upstream_body`. No se inspeccionan logs en tests. |
| Validación de entradas | Implementado y probado | Pydantic con `extra="forbid"`, patrones, límites, `profile_id`/`backup_id` con regex, `confirmation` literal; `test_origin_content_type_and_body_limits_are_enforced`, `test_write_requires_global_flag_profile_permission_and_confirmation`. |
| Acceso privado | Parcial | Operaciones exigen cookie; `/diagnostics` exige cookie o `SK_ACCESS_TOKEN`; `/config` y `/session` son públicos por diseño y `/config` revela etiquetas/ids no secretos. No hay 2FA ni control de usuarios. |
| No almacenar contraseñas | Implementado y probado | Sin columna ni archivo; `test_login_sets_an_isolated_cookie_and_never_echoes_secrets` lee la DB cruda; el frontend limpia el campo. |
| No registrar secretos | Implementado por diseño; sin prueba automática | Mensajes genéricos, sin cuerpos remotos; `Client` no registra credenciales; `NativeAuthRejected` no conserva el cuerpo. Falta una prueba que capture logs. |
| No publicar secretos | Operativo, depende del propietario | `.env.example` usa valores vacíos o placeholders; no hay secretos reales en el repositorio. La garantía es de proceso, no técnica. |
| No reintentos automáticos | Implementado y probado | Una sola petición en `client.py`; `429`/`10003` tipados; `single_attempt` consume el intento; `test_distribution_rejection_and_throttling_are_typed`, `test_concurrent_confirmation_uploads_exactly_once`. |

## 7. Conclusión honesta

**Listo para pruebas privadas, en lectura, con la cuenta del propietario:** el flujo tiene aislamiento por identidad, cifrado en reposo, cookie endurecida, límites de entrada, rate limit persistido, errores saneados y escritura cerrada por dos interruptores y una frase explícita. La suite de 40 casos cubre los controles principales con dobles de prueba.

**No debe considerarse producción multiusuario todavía:** faltan autorización del proveedor para terceros, 2FA/captcha, CSP, prueba real de TLS/CORS/navegador, revocación remota, alta disponibilidad y un rate limit atómico/distribuido. Un XSS en el editor o una cookie robada pueden actuar como el titular; un operador con el volumen y la clave puede leer todo; los respaldos contienen progreso real sin cifrado adicional. Antes de abrir el flujo a terceros: cerrar las discrepancias de `deployment.md`, añadir CSP y pruebas E2E reales, decidir el modelo de confianza del aprovisionamiento y obtener la autorización de ChillyRoom.

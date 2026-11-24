# Seguridad de la Fase 6.9

**Alcance:** servicio privado de una sola instancia para cuentas propias. **Estado:** controles implementados y probados; el despliegue público y la autorización de terceros siguen fuera de alcance.

## 1. Modelo de confianza

El backend maneja tres secretos distintos:

1. **Contraseña de ChillyRoom.** Se usa en memoria para el gateway y el portal. No se guarda, no se registra y no se devuelve al navegador.
2. **Token de sesión del gateway.** Se cifra con AES-SIV y se asocia a la cookie de sesión. No se expone al navegador.
3. **Identidad de instalación (`distro_id`, `unique_id`).** Se cifra con AES-SIV y se reutiliza. No se devuelve al navegador.

La cookie del navegador es opaca; el servidor guarda solo su SHA-256. El correo, el UID y el `player.id` se guardan como hashes/HMAC. La identidad de guardado se deriva de `cloudSaveId` y `platformId` con HMAC-SHA-256.

## 2. Controles implementados

### 2.1 Cifrado en reposo

- Perfiles, tokens e identificadores: AES-SIV con una clave de 32 bytes (`SK_NATIVE_STORE_KEY`).
- Respaldos: AES-SIV por archivo, con contexto `sk-under/backup\0<id>\0<archivo>`; cabecera `SKB1` y etiqueta de autenticación. Si no se configura `SK_NATIVE_BACKUP_KEY`, se deriva de la clave del almacén con HMAC-SHA-256 y el dominio `sk-under/native-backups`.
- Los respaldos de la Fase 6.8 en claro se rechazan con una clave configurada; `python -m app.native.maintenance migrate-backups` los cifra de forma atómica.
- El directorio de respaldos sigue siendo `0700` y los archivos `0600`.

### 2.2 Límite de intentos resistente a carreras

`NativeStore.reserve_login_attempt` abre `BEGIN IMMEDIATE`, cuenta los intentos no exitosos de la ventana, inserta un intento `pending` y solo después libera la transacción. La autenticación ocurre después; el intento se cierra con `finish_login_attempt`. Dos solicitudes concurrentes no pueden leer un contador obsoleto. La prueba con 10 hilos y límite 3 acepta exactamente 3.

El límite se aplica por IP efectiva y por hash de correo. Un fallo de credenciales, portal o red cuenta; un éxito no.

### 2.3 IP real tras proxies confiables

`app/net.py` solo interpreta `X-Forwarded-For` si el socket pertenece a `SK_NATIVE_TRUSTED_PROXIES` (IP o CIDR). Recorre la cadena de derecha a izquierda, descarta los proxies confiables y devuelve el primer salto no confiable. Si el socket no es confiable, la cabecera se ignora. `X-Real-IP` se usa solo en ese caso y como respaldo.

Esto evita que un cliente falsifique su IP para el limitador. En Coolify/Traefik hay que declarar la red del proxy, no confiar en cualquier cabecera.

### 2.4 CSRF, origen y cookies

- Las rutas nativas POST exigen el origen exacto configurado (`SK_NATIVE_ORIGIN`, incluido en `SK_ALLOWED_ORIGINS`) y `Sec-Fetch-Site` permitido.
- El cuerpo debe ser JSON UTF-8 sin compresión y con límite de 8192 bytes.
- Cookie `__Host-sk_native` en HTTPS: `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`. En desarrollo local se usa `sk_native_dev`.
- Logout revoca la sesión local y borra la cookie; no se afirma revocar el token en ChillyRoom.

### 2.5 CSP y cabeceras

- El frontend genera una meta CSP con `connect-src` limitado al origen exacto de `VITE_API_BASE_URL`; `_headers` añade una política base y cabeceras.
- La API responde con `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'` en `/api/`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy`, `Cross-Origin-Opener-Policy` y `Cross-Origin-Resource-Policy`.
- En producción HTTPS se añade HSTS. En desarrollo no se envía para no fijar HTTP local.

### 2.6 Sesiones y aislamiento

- Una cookie resuelve un único perfil y subject; no hay `account_id` en la URL.
- El perfil se liga al subject de identidad (correo normalizado, UID y `player.id`) en el primer acceso y no se reutiliza para otra cuenta.
- El subject de guardado se fija en la primera descarga y se compara en cada descarga. Una partida con otro `cloudSaveId`/`platformId` se rechaza.
- Los respaldos viven bajo `backup_root/<subject>`; una cuenta no puede listar ni leer los de otra.
- La sesión caduca por inactividad y por plazo absoluto; el token del proveedor se borra al revocar.

### 2.7 Redacción de secretos

- Los errores del gateway, del portal y de BlobSave no conservan ni muestran el cuerpo remoto; solo el código y un mensaje estable.
- Las excepciones no incluyen correo, contraseña, token, `distro_id`, `unique_id`, `cloudSaveId` ni `player.id`.
- Los logs de la API registran el nombre de la ruta y el tipo de excepción, no el cuerpo.
- El portal usa una sesión efímera en memoria y la descarta en `finally`.

### 2.8 Descubrimiento concurrente

La primera resolución de una cuenta (portal + prueba de jugadores + vinculación) se serializa con un bloqueo de proceso y se vuelve a comprobar el perfil por hash de correo. Dos pestañas no generan dos pares ni dos vinculaciones. Si ya existe un perfil de la Fase 6.8 vinculado al mismo subject, se reutiliza; el índice único de subject impide un segundo perfil y el par solo se actualiza tras verificar la identidad.

### 2.9 Persistencia

El almacén SQLite y los respaldos viven en el volumen. La clave externa permite reabrir el almacén tras recrear el contenedor. La prueba real reinició el proceso, conservó la cookie y los respaldos y volvió a descargar la partida. El `cleanup` de arranque elimina sesiones caducadas, intentos viejos y perfiles automáticos no vinculados, sin tocar perfiles activos.

## 3. Riesgos residuales

| Riesgo | Impacto | Mitigación / límite |
| --- | --- | --- |
| La contraseña también autentica el portal | Un compromiso del proceso durante el login podría exponerla. | No se persiste; el portal se usa en la misma llamada; no se registra. |
| Automatización del portal sin contrato | Riesgo de cumplimiento o bloqueo por parte de ChillyRoom. | Uso privado, solo lectura, con cuentas propias; falta autorización del proveedor. |
| Captcha, 2FA o bloqueo | El login autónomo no puede completarse. | Se devuelve `native_portal_challenge_required`; no se intenta resolver. |
| Límite de vinculación `100509` | El usuario debe esperar. | Se guarda el par y la espera; no se regenera ni se reintenta. |
| Varios jugadores por cuenta | Se elige el que devuelve partida o la primera espera. | Se prueban hasta 8; falta una etiqueta humana del portal. |
| Cierre de sesión local | El token del proveedor puede seguir vigente hasta su caducidad. | Se borra del almacén; no se afirma revocación remota. |
| XSS en el frontend | Podría actuar como el usuario mientras la cookie esté activa. | CSP, cookies HttpOnly, sin tokens en JavaScript. |
| Clave de respaldos perdida | Los respaldos no se pueden descifrar. | Conservar `SK_NATIVE_STORE_KEY`/`SK_NATIVE_BACKUP_KEY` fuera de la imagen; migrar antes de rotar. |
| Una sola réplica | Rate limit y bloqueo de descubrimiento son de proceso. | Un worker; para escalar, almacén y limitador compartidos. |
| Volumen comprometido | El atacante con la clave puede descifrar perfiles y respaldos. | Cifrado en reposo, permisos `0700/0600`, clave fuera del volumen. |
| Correo del portal | El portal devuelve el correo; se compara y no se guarda. | Solo hash/HMAC en el almacén. |

## 4. Recomendaciones operativas

1. Mantener el servicio privado y con `SK_NATIVE_WRITE_ENABLED=false` hasta que el propietario autorice escritura.
2. Configurar `SK_NATIVE_TRUSTED_PROXIES` con la red exacta del proxy; no usar `0.0.0.0/0`.
3. Rotar la clave de sesión de ChillyRoom iniciando sesión de nuevo; no hay endpoint de renovación observado.
4. Programar `python -m app.native.maintenance cleanup` y `migrate-backups` en el volumen.
5. Revisar los eventos saneados y los intentos; no habilitar logs de cuerpo.
6. No publicar `distro_id`, `unique_id`, tokens, correos ni partidas.

## 5. Conclusión

La Fase 6.9 corrige los huecos más importantes de la Fase 6.8: respaldos cifrados, CSP, límite atómico, IP de proxy, aislamiento, redacción, caducidad y persistencia. El riesgo principal que queda no es técnico del backend, sino externo: la autorización del proveedor y la validez de las credenciales de las cuentas que se quieran validar.

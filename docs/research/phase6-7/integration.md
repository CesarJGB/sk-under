# Propuesta de integración de autenticación nativa en el backend

**Estado: propuesta experimental; no implementada en `main`.** El cliente Linux de esta fase demuestra el contrato, pero faltan el aprovisionamiento autorizado de `distro_id`/`unique_id` y la confirmación de ChillyRoom para el uso de terceros.

## Objetivo

Permitir que un usuario autorizado introduzca su correo y contraseña en SK Under, obtenga una sesión de ChillyRoom emitida por el gateway y descargue su partida, sin mantener un emulador ni reutilizar sesiones extraídas de Android.

## Flujo propuesto

```text
Navegador
  │  HTTPS + cookie de sesión de SK Under
  ▼
Backend SK Under
  │  1. valida origen, CSRF, Content-Type y límites
  │  2. recibe correo/contraseña solo en memoria
  │  3. native_auth.authenticate(...)  ──►  api-gateway.soulknight.chillyroom.com
  │  4. valida session.uid == user.id y user.email
  │  5. cifra el token (AES-SIV/almacén existente)
  │  6. ModernCloudSaveProvider(token, unique_id, distro_id).download()
  ▼
Partida validada + metadatos; el token nunca llega al navegador
```

## Endpoint experimental

```http
POST /api/v1/cloud/native/login
Content-Type: application/json
Origin: https://sk.underdive.space
X-CSRF-Token: <token de la sesión del navegador>

{
  "email": "titular@example.com",
  "password": "…",
  "distro_id": "<uuid de distribución autorizado>",
  "unique_id": "<identificador de instalación autorizado>"
}
```

Respuesta exitosa (sin token ni correo):

```json
{
  "account_id": "<id local opaco>",
  "session_expires_at": "2026-12-01T00:05:40Z",
  "identity_verified": true,
  "save": {"bytes": 114779, "sha256": "…", "gems": 99999}
}
```

Errores:

- `400 invalid_request`: falta un campo, formato inválido o `distro_id` inválido.
- `401 auth_rejected`: credenciales incorrectas; no repetir automáticamente.
- `429 auth_throttled`: límite del proveedor o del backend.
- `502 provider_unavailable`: fallo del gateway o de BlobSave.
- `503 native_auth_disabled`: función desactivada por configuración.

## Reglas de seguridad

1. **Contraseña solo en memoria.** No se registra, no se escribe en SQLite, no se incluye en trazas, métricas ni respuestas. El backend no debe aceptar la contraseña por query string ni por cabecera.
2. **TLS normal.** No se desactiva la verificación ni se elude la validación estricta del cliente oficial. El backend habla con el host real, no con un proxy de inspección.
3. **Token cifrado en reposo.** Reutilizar el almacén AES-SIV de la Fase 6.4; el token no se envía al navegador, que solo recibe una cookie `HttpOnly`, `Secure`, `SameSite=Strict` con prefijo `__Host-`.
4. **Identidad antes de descargar.** Exigir `session.uid == user.id`, coincidencia de correo y, cuando esté disponible, `player.id` estable. Guardar solo hashes y la fecha de verificación.
5. **Aprovisionamiento explícito.** `distro_id` y `unique_id` son identificadores de instalación, no secretos de sesión, pero tampoco son arbitrarios: el servidor rechaza valores aleatorios. Deben obtenerse de una instalación autorizada o de un flujo que ChillyRoom habilite. No se hardcodean en el repositorio.
6. **Sin reintentos automáticos.** Respetar `429`, `10003` y los desafíos. Un `10003` no se interpreta como contraseña incorrecta sin evidencia.
7. **Límites.** Rate limit por cuenta, IP y ventana temporal; tamaño máximo de cuerpo; timeout; bloqueo temporal tras fallos repetidos.
8. **Auditoría sanitizada.** Registrar evento, resultado, código HTTP, hash de identidad y duración; nunca correo, contraseña, token, UID ni `player.id` en claro.
9. **CSRF y origen.** El endpoint de login nativo solo acepta el origen exacto configurado, JSON y la cookie de SK Under; no se expone a CORS abierto.
10. **Revocación.** El cierre de sesión de SK Under borra el token cifrado y el permiso de lectura; no se afirma que revoque la sesión del cliente oficial.

## Modelo de datos propuesto

Tabla `native_cloud_accounts` (separada de las cuentas vinculadas por ticket):

| Campo | Contenido |
| --- | --- |
| `id` | UUID local opaco |
| `owner_session_hash` | hash de la sesión del navegador |
| `identity_hash` | SHA-256 de `uid`/correo normalizado, sin valores en claro |
| `player_id_hash` | SHA-256 de `player.id` |
| `distro_id_encrypted` | AES-SIV; no se devuelve |
| `unique_id_encrypted` | AES-SIV; no se devuelve |
| `token_encrypted` | AES-SIV; caduca con la sesión |
| `expires_at` | fecha UTC |
| `verified_at` | fecha UTC |
| `last_result` | `ok`, `rejected`, `throttled`, `unavailable` |
| `write_allowed` | `false` por defecto |

No se guarda la contraseña ni el cuerpo del login.

## Aprovisionamiento pendiente

El laboratorio usó un `distro_id` y un `unique_id` ya presentes en la instalación oficial. Para un usuario nuevo, el backend necesita una de estas vías, ninguna verificada todavía:

1. Un flujo oficial de ChillyRoom que entregue la distribución y el identificador de instalación al backend.
2. Una importación única desde el cliente oficial, con consentimiento del titular, que no reutilice una sesión.
3. Una confirmación del proveedor de que el login acepta una distribución registrada por el backend para esa cuenta.

Mientras no exista una de estas vías, el endpoint debe permanecer deshabilitado y el flujo limitado al laboratorio.

## Plan de pruebas

- Simuladas: mismas pruebas que `test_native_auth.py` más el adaptador del backend y el cifrado del almacén.
- Reales: cuenta de laboratorio, `distro_id`/`unique_id` privados, emulador detenido, descarga y comparación de SHA-256; una segunda cuenta para aislamiento.
- Negativas: contraseña incorrecta, `10003`, `429`, timeout, certificado inválido, respuesta gzip corrupta, identidad contradictoria.
- No se ejecutan pruebas de carga contra el gateway del proveedor.

## Rollout

1. Mantener la rama `research/phase6-7-native-auth-deep` sin merge a `main`.
2. Añadir el módulo al backend detrás de `SK_NATIVE_AUTH_ENABLED=false`.
3. Probar en un entorno aislado con la cuenta de laboratorio.
4. Solicitar al proveedor la autorización y el mecanismo de aprovisionamiento.
5. Solo entonces evaluar producción, con revisión de seguridad y límites.

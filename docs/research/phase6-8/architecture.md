# Arquitectura de la Fase 6.8 · autenticación nativa web

**Estado:** implementado y probado con transporte simulado; el login real con la cuenta de laboratorio queda pendiente de ejecución manual del propietario. La rama es `feature/phase6-8-web-native-auth`; no hay merge a `main` ni despliegue automático.

## 1. Vista general

```text
Navegador (React)
  │  fetch same-site con credentials: "include"
  │  Origin exacto · JSON · cookie __Host-sk_native
  ▼
Cloudflare Pages (SPA)
  │  HTTPS
  ▼
Cloudflare / Coolify (FastAPI, 1 worker)
  │  POST /api/v1/cloud/native/login
  │    ├─ NativeAuthClient ──► api-gateway.soulknight.chillyroom.com
  │    ├─ NativeStore (AES-SIV + SQLite)
  │    └─ ModernCloudSaveProvider ──► save.soulknight.chillyroom.com
  ▼
Volumen /var/lib/sk-under
  ├── native/native.sqlite3
  └── native-backups/<subject>/...
```

La Fase 6.8 no reemplaza los componentes anteriores: reutiliza el cliente HTTP de la Fase 6.7, `ModernCloudSaveProvider`, `BlobSaveUploader`, `CloudLabService`, `LabBackupStore`, el editor de gemas y los modelos de validación. Añade la capa que faltaba: sesión web por cuenta, perfiles de instalación cifrados, autorización y aislamiento.

## 2. Módulos

### 2.1 `app/native/distributions.py`

Registro único y extensible de distribuciones. Contiene las seis distribuciones solicitadas:

| ID | Etiqueta | Estado |
| --- | --- | --- |
| `android-global` | Android Global (GP) | habilitada y validada |
| `android-vietnam` | Android Vietnam (GP_VNM) | deshabilitada |
| `ios-global` | iOS Global (IOS) | deshabilitada |
| `ios-vietnam` | iOS Vietnam (IOS_VNM) | deshabilitada |
| `ios-china` | iOS China (IOS_CN) | deshabilitada |
| `taptap` | TapTap | deshabilitada |

`require_enabled()` es el único punto que decide si una distribución puede autenticar. No hay condicionales de distribución repartidos por rutas o servicios.

### 2.2 `app/native/client.py`

Cliente del contrato verificado en la Fase 6.7:

- `POST https://api-gateway.soulknight.chillyroom.com/UserAuth/Login`.
- JSON plano `{loginType: 3, account, password, credential: null}`.
- Cabeceras de juego observadas y `x-distro-id` obligatoria.
- Sin `x-unique-id` en el login (no es necesario para autenticar).
- TLS normal, sin proxies del entorno, sin seguir redirecciones, límite de respuesta y gzip estricto.
- Sin reintentos automáticos. `429` se propaga como límite; `10003` como distribución rechazada; el resto de rechazos no revela el cuerpo remoto.
- Valida `session.uid == user.id`, correo normalizado, `player.id > 0` y `expire` futuro.
- `GatewaySession` oculta token y correo en `repr`; `summary()` solo devuelve SHA-256.

El transporte es inyectable (`transport`), lo que permite probar el contrato sin red ni credenciales.

### 2.3 `app/native/store.py`

Almacén SQLite privado con AES-SIV. Directorio `0700`, base `0600`, verificador HMAC de la clave.

| Tabla | Contenido | Datos sensibles |
| --- | --- | --- |
| `profiles` | etiqueta, distribución, `distro_id`/`unique_id` cifrados, subject, permiso de escritura | identificadores cifrados |
| `sessions` | hash de cookie, perfil, subject, token cifrado, caducidades, hashes de identidad | token cifrado |
| `accounts` | subject HMAC y subject de guardado HMAC | ninguno en claro |
| `attempts` | hashes HMAC de IP y correo, resultado | ninguno en claro |
| `events` | evento, resultado, código, subject truncado | ninguno en claro |

Derivaciones:

- `subject = HMAC(key, "native-identity\0email_normalizado\0uid\0player_id")`.
- `save_subject = HMAC(key, "native-save\0distribución\0cloudSaveId\0platformId")`.
- Cookie de sesión: 32 bytes aleatorios (43 caracteres URL-safe). En la base solo se guarda `SHA-256(cookie)`.
- Token: AES-SIV con contexto `session:<id>`. Perfiles: AES-SIV con contexto `profile:<id>`.

### 2.4 `app/native/service.py`

Orquestador de login, sesión, perfiles y editor:

1. Resuelve la distribución y el perfil (uno solo automáticamente; varios exigen elección explícita).
2. Aplica el límite de intentos por IP y correo antes de llamar al proveedor.
3. Autentica con `NativeAuthClient`.
4. Revalida el correo y la distribución en el servicio (defensa en profundidad).
5. Deriva el subject y vincula el perfil **solo si estaba libre**; si ya pertenece a otra identidad, rechaza.
6. Descarga una copia con `ModernCloudSaveProvider` y fija el `save_subject` en la primera lectura. Una descarga posterior con otra identidad de guardado se rechaza.
7. Crea la sesión, cifra el token y emite la cookie.
8. Para el editor, construye un `CloudLabService` por sesión con:
   - proveedor por token de esa sesión,
   - respaldos en `native-backups/<subject>`,
   - uploader solo si `SK_NATIVE_WRITE_ENABLED=true` y el perfil tiene `allow_write`.
9. Serializa `confirm`/`restore` por subject con `flock`; `claim_confirmation_attempt` impide una segunda subida del mismo candidato.

La escritura exige tres condiciones simultáneas: interruptor global, permiso del perfil y frase explícita. El frontend no puede activar ninguna.

### 2.5 `app/api/native.py`

API privada (`/api/v1/cloud/native`). La clase `NativeRoute` aplica, antes de leer el cuerpo:

- Origen exacto del editor (si el servicio está configurado).
- `Sec-Fetch-Site` limitado a `same-origin`, `same-site` o `none`.
- `Content-Type: application/json` sin compresión y cuerpo máximo de 8 KiB.
- Errores centralizados: `NativeError` → código/estado; `CloudSaveError` → mapeo existente; errores inesperados → 500 saneado.

| Método | Ruta | Autenticación | Función |
| --- | --- | --- | --- |
| GET | `/config` | pública (sin secretos) | distribuciones, perfiles, disponibilidad y sesión |
| GET | `/session` | cookie opcional | estado de la sesión |
| POST | `/login` | origen + JSON | autentica y crea sesión |
| POST | `/logout` | cookie + origen | revoca la sesión local |
| POST | `/installation` | cookie + origen | completa `unique_id` del perfil vinculado |
| GET | `/save` | cookie | descarga y valida la partida |
| POST | `/prepare` | cookie + origen | prepara gemas y respaldo |
| POST | `/confirm` | cookie + origen | sube y verifica persistencia |
| POST | `/restore` | cookie + origen | restaura el original |
| POST | `/verify` | cookie + origen | compara la nube con el respaldo |
| GET | `/backups` | cookie | lista respaldos del subject |
| GET | `/diagnostics` | cookie o Bearer existente | métricas y eventos saneados |

No existe ningún `account_id` en la URL. El sujeto se obtiene exclusivamente de la cookie; por eso no hay una ruta que permita pedir datos de otra cuenta.

### 2.6 `app/native/provision.py`

CLI de aprovisionamiento sin red y sin contraseñas:

```bash
cd backend
uv run --locked python -m app.native.provision --label "Cuenta A" --distro-stdin --unique-stdin
```

Los identificadores se leen sin eco o por `stdin`; nunca se imprimen. `--list` no revela valores. `--no-unique` crea un perfil con la instalación pendiente; el titular la completa desde la web tras verificar su identidad.

También se puede crear el perfil inicial con `SK_NATIVE_DISTRO_ID` y `SK_NATIVE_UNIQUE_ID`; el arranque lo inserta si no existe. No se aceptan distribuciones no validadas.

## 3. Ciclo de vida de la sesión

```text
sin sesión
  │ POST /login (origen, JSON, límite de intentos)
  ▼
autenticando
  │ proveedor 200 + identidad coherente
  ▼
identidad verificada ──► perfil sin unique_id ──► instalación pendiente
  │                                                   │ POST /installation
  │                                                   ▼
  └──────────────────────────────────────────► sesión activa
                                                     │ GET /save, prepare, ...
                                                     │ inactividad / caducidad / logout
                                                     ▼
                                             sesión caducada o revocada
```

- Caducidad absoluta: mínimo entre `expire` del proveedor y 7 días.
- Caducidad por inactividad: `SK_NATIVE_IDLE_SECONDS` (1800 por defecto).
- `GET /session` devuelve `reason=expired` si la fila existe pero caducó; así el frontend muestra el aviso correcto.
- El logout borra la fila y la cookie. No se afirma que revoque el token en ChillyRoom.

## 4. Estados del frontend

`NativeAuthPage` reutiliza la estética y las clases `lab-*` existentes. Cubre:

| Estado | Presentación |
| --- | --- |
| sin sesión | formulario con distribución, correo, contraseña y mostrar/ocultar |
| autenticando | botón deshabilitado con indicador |
| identidad verificada | distintivo en la tarjeta de sesión |
| configuración pendiente | formulario de `unique_id` |
| sesión activa | tarjeta de cuenta, caducidades y editor de gemas |
| descarga en proceso | botón con indicador y texto |
| error de autenticación | mensaje comprensible mapeado por código |
| sesión caducada | aviso y retorno al formulario |
| servicio no disponible | aviso, sin solicitar credenciales, y reintento manual |

El editor conserva el flujo de la Fase 6.2/6.3: descarga, lectura de gemas, preparación determinista, respaldo, validación, confirmación explícita, subida y verificación posterior. No se añadieron personajes, skins, armas ni otras propiedades.

## 5. Aislamiento multicuenta

Garantías implementadas:

1. **Sesión única por cookie.** No hay sesión global; cada cookie resuelve una fila con perfil y subject propios.
2. **Perfil ligado a identidad.** El primer login fija el subject del perfil. Otro correo/uid/player no puede reutilizarlo (`native_profile_identity_mismatch`).
3. **Respaldos por subject.** La ruta no acepta otro sujeto; un `backup_id` de otra cuenta devuelve `404 backup_not_found`.
4. **Identidad de guardado.** El primer `cloudSaveId`/`platformId` se fija por subject; una copia distinta se rechaza (`native_save_identity_mismatch`).
5. **Escritura serializada.** `flock` por subject y claim atómico por respaldo; dos sesiones de la misma cuenta no suben dos veces.
6. **Logout local.** Cierra solo la sesión de esa cookie; otra cuenta conserva la suya.

Las pruebas automatizadas cubren dos identidades simuladas, sesiones simultáneas, cruce de respaldos, caducidad, cierre de sesión y escritura concurrente. La validación con dos cuentas reales queda pendiente del propietario.

## 6. Contrato de errores

| Código | HTTP | Significado |
| --- | --- | --- |
| `native_auth_disabled` | 503 | función apagada por configuración |
| `native_auth_misconfigured` | 503 | falta origen, clave o almacén |
| `native_store_unavailable` | 503 | almacén privado inaccesible |
| `native_profile_missing` | 503 | no hay perfil aprovisionado |
| `native_profile_required` | 409 | hay varios perfiles y falta elegir |
| `native_credentials_rejected` | 401 | credenciales rechazadas |
| `native_login_throttled` | 429 | límite local de intentos |
| `native_auth_throttled` | 429 | límite del proveedor |
| `native_auth_unavailable` | 502 | gateway no disponible |
| `native_distribution_rejected` | 502 | `10003` o distribución no aceptada |
| `native_identity_mismatch` | 409 | identidad contradictoria |
| `native_session_rejected` | 502 | BlobSave rechazó el token emitido; no se crea sesión |
| `native_profile_identity_mismatch` | 409 | perfil ya ligado a otra cuenta |
| `native_installation_required` | 409 | falta `unique_id` para descargar |
| `native_session_required` | 401 | no hay cookie válida |
| `native_session_expired` | 401 | caducidad o rechazo del token |
| `native_save_identity_mismatch` | 422 | la partida no corresponde |
| `native_write_disabled` | 503 | interruptor global apagado |
| `native_write_denied` | 403 | perfil sin permiso de escritura |
| `native_origin_denied` | 403 | origen o `Sec-Fetch-Site` no autorizado |

## 7. Despliegue

La imagen Docker ya crea `/var/lib/sk-under/native` y `/var/lib/sk-under/native-backups` con UID/GID `10001` y modo `0700`. Un único volumen `/var/lib/sk-under` cubre cuentas, respaldos administrativos, sesiones nativas y respaldos nativos.

La guía operativa está en [deployment.md](deployment.md). El servicio debe ejecutarse con **un solo worker y una sola réplica** mientras use SQLite y el límite de intentos en proceso.

## 8. Pruebas

- Backend: 380 pruebas aprobadas y 16 omitidas (muestras privadas) al cierre de la fase.
- Nuevas pruebas nativas: cliente (11), almacén (7), API (19), aprovisionamiento (3).
- Frontend: TypeScript y Vite compilan; 22 pruebas Playwright en Chromium, 8 de ellas del acceso nativo.
- No se ejecutó red real ni login real en esta fase; ver [README.md](README.md).

## 9. Archivos principales

| Ruta | Papel |
| --- | --- |
| `backend/app/native/client.py` | contrato de login nativo |
| `backend/app/native/distributions.py` | registro de distribuciones |
| `backend/app/native/store.py` | perfiles, sesiones y cifrado |
| `backend/app/native/service.py` | orquestación y aislamiento |
| `backend/app/native/provision.py` | CLI de aprovisionamiento |
| `backend/app/api/native.py` | API y guardas HTTP |
| `backend/app/settings.py` | configuración `SK_NATIVE_*` |
| `backend/app/main.py` | composición y CORS |
| `frontend/src/pages/NativeAuthPage.tsx` | acceso y editor |
| `frontend/src/api.ts` | cliente de la API nativa |
| `backend/tests/test_native_*.py` | pruebas del backend |
| `frontend/tests/native-auth.spec.ts` | pruebas de navegador |

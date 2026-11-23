# Adquisición de la partida de nube

**Estado: PARCIAL; LECTURA `FetchGameData` CONSEGUIDA.** Se obtuvo una sesión
auténtica en el portal oficial, se caracterizó el gateway y, en la revisión del
2026-11-23, se extrajo el token de la sesión del cliente oficial y se ejecutó
`POST /Backup/FetchGameData` desde Linux: **`200` con 600 bytes de agregado
legacy vacío**. **No se obtuvo `CloudSaveGameData`**: `/Backup/GetBlobSave`
devolvió `500` y `/BlobSave/Download` `404`. El detalle nuevo está en
[lectura auténtica](authentic-cloud-read.md). Las secciones 1–5 conservan la
primera tanda del portal y del gateway.

## 0. Addendum 2026-11-23: token del cliente y lectura real

| Elemento | Resultado |
| --- | --- |
| Token | Extraído del `shared_prefs` del cliente; archivo privado `0600`; no publicado |
| Host operativo | `api-gateway.soulknight.chillyroom.com` (el host legacy devuelve `503`) |
| Petición | `POST /Backup/FetchGameData` con `Authorization: Bearer <token>` |
| Respuesta | **`200`**, `application/json`, **600 bytes**, 17 claves, colecciones vacías |
| Cuenta invitado | Mismo esquema vacío |
| Cuenta del titular | Mismo esquema vacío; la cuenta no tiene progreso en este endpoint |
| `CloudSaveGameData` | **No obtenido**; `GetBlobSave` `500`, `BlobSave/Download` `404` |
| Escrituras | **Ninguna**; solo lecturas |

La respuesta no contiene `serialzedVersion`, `cloudSaveId` ni `platformId`; es
el agregado legacy de `FetchGameData`, no el wrapper nuevo. No se debe
presentar como “partida de nube” completa. La lectura demuestra que el token
del cliente es aceptado desde Linux y que la ruta es reproducible; no demuestra
que exista una copia no vacía ni que el cliente acepte una modificación.

## 1. Hipótesis

La cuenta de laboratorio, creada por el titular, tiene un primer guardado
subido. Si el portal de cuentas y el gateway comparten identidad, una sesión
oficial debería permitir consultar los metadatos y descargar la copia. La
descarga sería la entrada para el decodificador y el puente Linux.

## 2. Procedimiento

### 2.1 Sesión en el portal oficial

Se abrió `https://accounts.chillyroom.com/login` en Chromium headless y se
enviaron las credenciales de laboratorio desde un archivo local `0600`, nunca
desde el repositorio ni desde la línea de comandos. El portal usa `dbAuth` de
Redwood:

```text
POST https://accounts.chillyroom.com/.redwood/functions/auth
{"account":"<cuenta>","password":"<secreto>","type":3,"method":"login"}
GET  https://accounts.chillyroom.com/.redwood/functions/auth
POST https://accounts.chillyroom.com/.redwood/functions/graphql
```

La operación `Profile` devolvió:

| Campo | Resultado |
| --- | --- |
| Cuenta | Creada el 2026-11-23; correo de laboratorio asociado |
| Juego | `gameId=1`, nombre `Soulknight` |
| Jugador | Existe un `pid` asociado a la cuenta |
| Distro | Un UUID de registro y otro de último login (no publicados) |
| Guardado | La operación Profile y las rutas de migración no ofrecen una descarga de contenido, tamaño ni hash |

El portal solo ofrece identidad, juegos y migración de archivos
(`migrateSaves`, `archiveMigrationInfo`). La migración es destructiva e
irreversible; no se ejecutó.

### 2.2 Probes del gateway

Se usó el host que el propio cliente guarda en
`LastLoginHostWithDistroId`: `api-gateway.soulknight.chillyroom.com`. Las
peticiones fueron de solo lectura y sin credenciales, salvo el ensayo explícito
con la sesión web descrito abajo.

| Petición | Resultado |
| --- | --- |
| `POST /GameWorld/Time` | `200` · `{"timestamp":...}` |
| `POST /UserAuth/Login` (cuerpo vacío) | `400` · `{"error":10000,"msg":null}` |
| `POST /UserProfile/GetUserProfile` | `400` · `10001 Unauthenticated` |
| `POST /Backup/FetchGameData` | `400` · `10001 Unauthenticated` |
| `GET/POST /AccessToken/Get` | `404` |
| `GET/POST /BlobSave/Download` | `404` en este host |
| `GET/POST /Backup/GetBlobSave` | `400` · `10001 Unauthenticated` |

### 2.3 Ensayo con la sesión web

La cookie de sesión del portal es un valor opaco de 32 caracteres. Se envió
como `Authorization: Bearer <sesión>` a `/UserProfile/GetUserProfile` y
`/Backup/FetchGameData`:

| Token enviado | Respuesta |
| --- | --- |
| Ausente o inválido | `400` · `10001 Unauthenticated` |
| Sesión web del portal | `400` · `10015 unexpected error` |
| Token de juego válido | **No disponible** |

El cambio de `10001` a `10015` demuestra que el gateway **parsea** el token,
pero la sesión web no es un token de juego. No se siguió probando con la cuenta
real para no arriesgar bloqueos ni agotar las vinculaciones.

### 2.4 Límite oficial de vinculaciones

La página oficial de Cloud Save documenta:

- 5 vinculaciones de dispositivo por cuenta cada 90 días.
- Al menos 24 horas entre vinculaciones.
- Cada login en un emulador consume una vinculación.

Por eso no se lanzó un login de cuenta en el emulador solo para “ver si
funciona”. La prueba de aceptación en cliente debe hacerse en un dispositivo
estable y contar la vinculación.

## 3. Resultado

| Objetivo | Resultado |
| --- | --- |
| Iniciar sesión en el portal oficial | **Sí** |
| Identificar la cuenta y el juego | **Sí** (`gameId=1`) |
| Consultar metadatos del guardado | **No** |
| Descargar el guardado | **No** |
| Obtener `serialzedVersion`, `cloudSaveId`, `platformId` | **No** |
| Confirmar que la sesión web sirve para el gateway | **No** |

## 4. Limitaciones

- En la primera tanda no se obtuvo un token de juego: el login del cliente
  (`/UserAuth/Login`) devolvió `10000` con el cuerpo probado y no se siguió
  adivinando el esquema para no bloquear la cuenta. La revisión posterior sí
  obtuvo el token de la sesión del cliente y ejecutó `FetchGameData`; ver el
  addendum 0.
- El portal de cuentas no es una interfaz de descarga de partidas.
- `/BlobSave/Download` no existe en el host del gateway; puede vivir en otro
  servicio o requerir otro método/cabeceras. No se inventó una ruta.
- No se capturó tráfico TLS del cliente. El cliente se cierra antes de un
  login estable y no se instaló una CA ni se alteró el pinning.

## 5. Conclusión de la primera tanda

La adquisición de `CloudSaveGameData` **no se completó en la primera tanda**.
La evidencia nueva de entonces es la sesión oficial, el `gameId`, el contrato
de error del gateway y la distinción entre sesión web y token de juego. La
revisión del 2026-11-23 añadió una lectura auténtica de `FetchGameData` con el
token del cliente (agregado legacy vacío); el wrapper nuevo sigue siendo el
bloqueo principal. Ver el addendum 0 y
[lectura auténtica](authentic-cloud-read.md).

# Adquisición de la partida de nube

**Estado: PARCIAL.** Se obtuvo una sesión auténtica en el portal oficial de
cuentas y se caracterizó el gateway del juego. **No se obtuvo una copia de
`CloudSaveGameData`.** El portal no expone el contenido del guardado y el
gateway rechazó la sesión web como token de juego.

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

- No se obtuvo un token de juego. El login del cliente (`/UserAuth/Login`)
  devolvió `10000` con el cuerpo probado; no se siguió adivinando el esquema
  para no bloquear la cuenta.
- El portal de cuentas no es una interfaz de descarga de partidas.
- `/BlobSave/Download` no existe en el host del gateway; puede vivir en otro
  servicio o requerir otro método/cabeceras. No se inventó una ruta.
- No se capturó tráfico TLS del cliente. El cliente se cierra antes de un
  login estable y no se instaló una CA ni se alteró el pinning.

## 5. Conclusión

La adquisición auténtica de nube **no se completó**. La evidencia nueva es la
sesión oficial, el `gameId`, el contrato de error del gateway y la distinción
entre sesión web y token de juego. La copia de nube sigue siendo el bloqueo
principal de la fase.

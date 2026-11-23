# Fase 5.7 · Validación real y protocolo de nube

**Resultado en una frase:** la Fase 5.7 obtuvo evidencia auténtica de la cuenta
oficial y de la superficie del gateway, pero **no** consiguió una partida de
nube, **no** capturó un `NetPack` real y **no** demostró que el cliente acepte
una copia modificada. El cliente oficial se cierra con `SIGSEGV` durante el
arranque en el emulador de laboratorio.

Fecha de trabajo: 2026-11-23. Punto de partida: `aac7d75`. Entorno: Linux
x86-64, AVD Android 11 `google_apis` x86_64, APK oficial 8.8.0
(`versionCode=1080800`, ABI `armeabi-v7a`). Cuenta de laboratorio autorizada
por el titular; sus credenciales, tokens, identificadores y partidas no se
publican.

## 1. Clasificación

**Progreso parcial por debajo del éxito mínimo.** Se confirmó que el portal
oficial de cuentas acepta la cuenta de laboratorio y que el gateway del juego
responde; se recuperaron las rutas y firmas del cliente para el login y el
guardado; se añadió una interfaz de proveedor de nube y un prototipo de solo
lectura con pruebas sintéticas. No se alcanzó ninguno de los tres resultados
que exige el mínimo: restauración no-op en el cliente, aceptación/rechazo
observado de una modificación y una muestra de nube auténtica.

No se presenta como éxito completo ni significativo. El bloqueo principal es
ambiental y de contrato: el cliente no sobrevive el arranque en este AVD y no
se obtuvo un token de juego válido ni el esquema de éxito de la descarga.

## 2. Matriz de objetivos

| Objetivo | Estado | Evidencia |
| --- | --- | --- |
| A.1 Referencia local reproducible 8.8.0 | **Sí, heredada de 5.6** | 20 archivos inventariados, 18 decodificados, hashes privados fuera de Git |
| A.2 Restauración no-op en cliente oficial | **No concluyente** | El cliente se cierra antes de mostrar el menú; [validación](official-client-validation.md) |
| A.3 Primera modificación aceptada por el cliente | **No probada** | Sin A.2 no se introduce una edición |
| A.4 Subida y recuperación de la modificación | **No ejecutada** | Sin lectura ni aceptación local; [escritura](cloud-write-validation.md) |
| B.1 Referencia auténtica de Cloud Save | **No obtenida** | Sin descarga; [adquisición](cloud-save-acquisition.md) |
| B.2 Captura de NetPack real | **No obtenida** | Solo superficie estática y contratos de error; [RPC](rpc-netpack-capture.md) |
| B.3 Comparación local/nube | **Bloqueada** | Falta la muestra de nube; [comparación](cloud-local-comparison.md) |
| B.4 FixData | **Parcial, estático** | Nombres y call sites; sin transformaciones confirmadas; [FixData](fixdata-analysis.md) |
| C.1 Interfaz de proveedor remoto | **Sí** | `CloudSaveAcquisitionProvider` y `CloudBridge`; [proveedor](linux-cloud-provider.md) |
| C.2 Lectura remota desde Linux | **No** | Sin token de juego ni esquema de éxito verificado |
| C.3 Escritura remota | **No implementada** | Bloqueo explícito; [escritura](cloud-write-validation.md) |
| D. Pruebas de los componentes nuevos | **Sí, sintéticas** | 14 pruebas nuevas; la suite completa pasa |
| E. Informes y publicación | **Sí** | Este directorio y el commit de la fase |

## 3. Qué se ejecutó de verdad

### 3.1 Portal oficial de cuentas

Se inició sesión en `https://accounts.chillyroom.com` con el mecanismo oficial
`dbAuth` desde un navegador headless. El portal mostró la cuenta creada el
2026-11-23, el juego `Soulknight` con `gameId=1` y un jugador asociado. La
sesión web se guardó en un archivo privado `0600` fuera de Git. **El portal no
expone el contenido del guardado**: solo identidad, juegos y migración de
archivos, que es una operación destructiva y no una descarga.

### 3.2 Gateway del juego

`POST https://api-gateway.soulknight.chillyroom.com/GameWorld/Time` devolvió
`200` con `{"timestamp":...}` sin autenticación. Las rutas de perfil y respaldo
respondieron con el contrato de error del gateway:

| Ruta | Sin token | Con la sesión web |
| --- | --- | --- |
| `/UserProfile/GetUserProfile` | `400` · `10001 Unauthenticated` | `400` · `10015 unexpected error` |
| `/Backup/FetchGameData` | `400` · `10001 Unauthenticated` | `400` · `10015 unexpected error` |
| `/UserAuth/Login` | `400` · `10000` (cuerpo nulo) | No aplica |
| `/AccessToken/Get` | `404` | `404` |

La sesión web **no** es un token de juego: el gateway la reconoce como un
formato distinto y la rechaza con `10015`. No se intentó adivinar la
contraseña, el token ni el cuerpo de `AccountLogin` con la cuenta real más de
una vez.

### 3.3 Superficie del cliente

La metadata descifrada de 8.8.0 y los literales del binario confirman las
rutas y firmas que el cliente usa. Las más relevantes:

| Elemento | Evidencia |
| --- | --- |
| `LoginApi.AccountLogin` | `(string account, string password, callback, exp)` |
| `LoginApi.PostAsync` | `(string url, object data)` |
| `LoginApi.CallRpc` | `(rid, func, callback, exp)` / `(client, rid, func, callback, exp)` |
| `LoginApi.DnloadSave` | `(onSuccess, onFail)` |
| `LoginApi.CheckSaveMac` | `(callback)` |
| Rutas de guardado | `/BlobSave/Download`, `/BlobSave/Upload`, `/Backup/GetBlobSave`, `/Backup/FetchGameData`, `/Migration/Saves` |
| Cabeceras del cliente | `x-game-id`, `x-game`, `x-distro-id`, `x-app-version`, `x-game-version`, `x-game-lang`, `x-locale`, `x-platform` |
| Agregado | `serialzedVersion`, `cloudSaveId`, `platformId`, `gameData`, 12 secciones opcionales |

### 3.4 Intento de restauración en el cliente

Se copió el perfil local auténtico de 5.6 en
`/data/data/com.ChillyRoom.DungeonShooter/files/` del AVD y se lanzó el
cliente. El cliente se cerró con `SIGSEGV` antes de mostrar el menú. Se
observaron dos firmas:

1. `ndk_translation::RunGuestJNIFunction` al pulsar el consentimiento o al
   terminar la pantalla de título.
2. `libil2cpp.so` con desreferencia nula en `IL2CPP Threadpool` tras
   `LoadInitBundles`.

No se puede atribuir el cierre a los bytes restaurados: el mismo cliente
también se cierra con el perfil de invitado de fábrica y con los servicios de
Google desactivados. El detalle está en [validación del cliente](official-client-validation.md).

### 3.5 Proveedor Linux

Se añadió `CloudSaveAcquisitionProvider` con tres implementaciones:

- `DisabledCloudSaveProvider`: estado por defecto, sin red.
- `LocalFixtureCloudSaveProvider`: lee una copia ya extraída y la etiqueta
  `source="fixture"`.
- `GatewayCloudSaveProvider`: prototipo de solo lectura que exige un token de
  juego aportado fuera de banda y no implementa login.

`CloudBridge` conecta el proveedor con el importador y el exportador
existentes. Las pruebas usan respuestas sintéticas; **no se ejecutó una
descarga real**. Detalle en [proveedor Linux](linux-cloud-provider.md).

## 4. Respuestas expresas

### 1. ¿Soul Knight aceptó nuestros archivos modificados?

**No hay evidencia de aceptación.** No se llegó a una restauración no-op
estable: el cliente se cierra durante el arranque. No se introdujo una
modificación en el cliente oficial. La respuesta honesta es **no probado**, no
un sí ni un no del juego.

### 2. ¿Se pudo subir y recuperar una modificación?

**No.** No hubo lectura de nube, no hubo escritura y no se ejecutó el flujo de
subida. No se simuló una subida.

### 3. ¿Se obtuvo una partida auténtica desde ChillyRoom Cloud?

**No.** Se obtuvo una sesión auténtica del portal de cuentas y respuestas del
gateway, pero ninguna representación de `CloudSaveGameData` de la cuenta. El
portal no descarga el guardado.

### 4. ¿Se capturó y decodificó un NetPack real?

**No.** Se confirmaron las rutas, las firmas de los métodos, las cabeceras y el
contrato de error del gateway. No se observó un `NetPack` real, ni `MsgId`, ni
`ReqIdx`, ni `BodySize`, ni el marcador `00 00 00 80` en una respuesta.

### 5. ¿Se consiguió implementar lectura de nube directamente desde Linux?

**No.** Existe el prototipo `GatewayCloudSaveProvider` y su contrato de solo
lectura, pero no se obtuvo un token de juego válido ni se verificó el esquema
de éxito. Una prueba con el fixture local no sustituye una descarga.

### 6. ¿Qué falta para completar el ciclo remoto?

1. Un cliente oficial estable, o un token de juego emitido por el mecanismo
   oficial, para ejecutar una descarga real.
2. El cuerpo exacto de `AccountLogin` y el contrato de éxito de
   `/Backup/GetBlobSave` o `/BlobSave/Download`.
3. Una muestra auténtica de `CloudSaveGameData` con `serialzedVersion`,
   `cloudSaveId` y `platformId`.
4. La restauración no-op y la modificación controlada en el cliente, con
   observación de persistencia.
5. La decisión sobre `CheckSaveMac`/MAC y la política de conflicto antes de
   cualquier escritura.

### 7. ¿Qué evidencia concreta respalda cada afirmación?

| Afirmación | Evidencia |
| --- | --- |
| La cuenta oficial funciona en el portal | Login `dbAuth` real y perfil con `gameId=1`; [adquisición](cloud-save-acquisition.md) |
| El gateway responde y distingue tokens | `/GameWorld/Time` `200`; `10001` sin token y `10015` con la sesión web; [adquisición](cloud-save-acquisition.md) |
| El cliente conoce las rutas y firmas | Metadata descifrada y literales; [RPC](rpc-netpack-capture.md) |
| El cliente no acepta el perfil en este AVD | Dos cierres reproducibles con trazas; [validación](official-client-validation.md) |
| No hay muestra de nube | Ninguna respuesta con `CloudSaveGameData`; [comparación](cloud-local-comparison.md) |
| El proveedor Linux existe y está probado | 14 pruebas nuevas; [proveedor](linux-cloud-provider.md) |
| No hay escritura remota | Bloqueo explícito y ausencia de intentos; [escritura](cloud-write-validation.md) |

## 5. Seguridad y datos privados

- Las credenciales viven en `~/.config/sk-under/phase5-7/account.json`
  (`0600`), fuera del repositorio. No se incluyen en Git, logs, informes ni
  GitHub Actions.
- La sesión web se guardó en un archivo privado `0600`; no se publica.
- No se publican correos, tokens, `cloudSaveId`, `platformId`, IDs de jugador,
  distro ni hashes de la partida.
- No se desactivó TLS, no se intentó saltar el pinning, no se usaron cuentas de
  terceros y no se modificó el cliente para eludir controles.
- No se ejecutó ninguna escritura remota ni se agotaron las vinculaciones de
  dispositivo que documenta el proveedor.

## 6. Pruebas y verificación

| Comprobación | Resultado |
| --- | --- |
| `backend/.venv/bin/pytest -q` | **229 pasan, 14 omitidas** |
| `frontend/npm run build` | **Pasa** (2218 módulos) |
| `frontend/npm run test:browser` | **4 pasan** |
| `git diff --check` | **Limpio** |
| Higiene de secretos/artefactos | Verificado localmente; CI tras el push |

Las pruebas privadas de las muestras 8.6.0/8.8.0 se omiten cuando no existe el
directorio privado, como en CI. Las pruebas nuevas usan únicamente datos
sintéticos.

## 7. Conclusión

La Fase 5.7 aporta evidencia nueva y verificable sobre la **cuenta**, el
**gateway** y la **superficie del cliente**, y deja un proveedor Linux
desacoplado con pruebas. No cierra el objetivo principal: la partida de nube,
la captura RPC y la aceptación por el cliente siguen bloqueadas. El siguiente
paso de mayor valor es estabilizar el cliente o conseguir un token de juego
por el mecanismo oficial, no ampliar el editor local.

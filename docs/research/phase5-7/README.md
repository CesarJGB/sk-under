# Fase 5.7 · Validación real y protocolo de nube

**Resultado en una frase:** se estabilizó el cliente oficial 8.8.0 en un AVD
Android 11 limpio con ABI `arm64-v8a`, se inició sesión con la cuenta
ChillyRoom por email y se ejecutó una **lectura auténtica de
`/Backup/FetchGameData` desde Linux** con el token emitido por el cliente. La
cuenta de laboratorio no tiene progreso en ese endpoint (agregado vacío de
600 bytes) y **no** se obtuvo `CloudSaveGameData` ni se demostró que una
modificación se refleje en el cliente.

Fecha de trabajo: 2026-11-23. Punto de partida de la primera tanda:
`aac7d75`; revisión de estabilización: `9dc9fc2`. Entorno: Linux
x86-64, KVM, AVD Android 11 `google_apis` x86_64, APK oficial 8.8.0
(`versionCode=1080800`, ABI elegida `arm64-v8a`). Cuenta de laboratorio
autorizada por el titular; credenciales, tokens, identificadores y partidas no
se publican.

**Addenda de esta revisión:**

- [Estabilización del emulador](emulator-stabilization.md): configuración
  reproducible, crash de primer arranque y crash del login de Google Play.
- [Lectura auténtica de nube](authentic-cloud-read.md): token del cliente y
  `FetchGameData` desde Linux.
- [Aceptación de archivos](modification-acceptance.md): restauración no-op y
  modificación controlada de `game.data`.

## 1. Clasificación

**Progreso parcial significativo, por debajo del éxito mínimo.** La fase ya no
está bloqueada por “el cliente no arranca”: arranca de forma reproducible en
una configuración concreta y permite iniciar sesión. Lo que falta es una
partida de nube no vacía, el contrato de `/Backup/GetBlobSave` y una prueba
visible de aceptación de una copia editada.

La evidencia separa tres fallos que antes se atribuían al entorno sin
clasificar:

1. **Primer arranque en frío:** `SIGSEGV` en `IL2CPP Threadpool` dentro de
   `lib/arm64/libil2cpp.so`. El segundo arranque llega al menú. No depende de
   los bytes de la partida.
2. **Login de Google Play:** `NoClassDefFoundError:
   androidx.core.app.PendingIntentCompat` en el propio APK, activado porque
   GMS está por debajo de la versión requerida. No es root ni detección de
   emulador.
3. **Sesión guardada obsoleta:** el relanzamiento con un token de una sesión
   anterior puede quedarse en `LoginInit`/100 %. El login manual fresco sí
   funciona.

## 2. Matriz de objetivos

| Objetivo | Estado | Evidencia |
| --- | --- | --- |
| A.1 Referencia local reproducible 8.8.0 | **Sí, heredada de 5.6** | 20 archivos inventariados, 18 decodificados, hashes privados fuera de Git |
| A.2 Restauración no-op en cliente oficial | **No concluyente** | El perfil 5.6 carga hasta la escena de login sin `SIGSEGV`, pero el auto-login con token obsoleto se detiene en `LoginInit`; [validación](modification-acceptance.md) |
| A.3 Primera modificación aceptada por el cliente | **No demostrada visiblemente** | `game.data.gems` modificado se conserva en disco y no hay error de integridad, pero el tutorial mostró 1.000 gemas en memoria y no se observó 424.242 en el HUD; [aceptación](modification-acceptance.md) |
| A.4 Subida y recuperación de la modificación | **No ejecutada** | Sin escritura remota; [escritura](cloud-write-validation.md) |
| B.1 Referencia auténtica de Cloud Save | **Parcial** | `FetchGameData` 200 auténtico, agregado legacy vacío de 600 bytes; no `CloudSaveGameData`; [lectura](authentic-cloud-read.md) |
| B.2 Captura de NetPack real | **No obtenida** | Solo superficie estática y contratos de error; [RPC](rpc-netpack-capture.md) |
| B.3 Comparación local/nube | **Bloqueada** | La nube disponible está vacía y no es el agregado nuevo; [comparación](cloud-local-comparison.md) |
| B.4 FixData | **Parcial, estático** | Nombres y call sites; sin transformaciones confirmadas; [FixData](fixdata-analysis.md) |
| C.1 Interfaz de proveedor remoto | **Sí** | `CloudSaveAcquisitionProvider` y `CloudBridge`; [proveedor](linux-cloud-provider.md) |
| C.2 Lectura remota desde Linux | **Sí para `FetchGameData`; no para `GetBlobSave`** | Token de cliente aceptado; `FetchGameData` 200; `GetBlobSave` 500; [lectura](authentic-cloud-read.md) |
| C.3 Escritura remota | **No implementada** | Bloqueo explícito; [escritura](cloud-write-validation.md) |
| D. Pruebas de los componentes nuevos | **Sí, sintéticas** | 14 pruebas del proveedor; la suite completa pasa |
| E. Informes y publicación | **Sí** | Este directorio y las addendas |

## 3. Qué se ejecutó de verdad

### 3.1 Primer intento (histórico, 32 bits)

La primera tanda usó el AVD de 5.6 con ABI efectiva `armeabi-v7a` sobre
traducción ARM de 32 bits y restauró el perfil local de 5.6. Se observaron
`SIGSEGV` en `ndk_translation::RunGuestJNIFunction` y en `libil2cpp.so`
(`IL2CPP Threadpool`). El cliente también caía con el perfil de fábrica, por lo
que el cierre no se podía atribuir a los bytes restaurados. Se documentó como
bloqueo ambiental. El detalle histórico se conserva en
[validación del cliente](official-client-validation.md).

### 3.2 AVD limpio y ABI de 64 bits

Se creó un AVD nuevo `sk57` con `android-30/google_apis/x86_64` r16, 4 vCPU,
4 GiB de RAM, 6 GiB de partición de datos y `-gpu swiftshader_indirect`. El
dispositivo anuncia:

```text
ro.product.cpu.abilist = x86_64,x86,arm64-v8a,armeabi-v7a,armeabi
```

El APK contiene `lib/arm64-v8a` y `lib/armeabi-v7a`; el instalador eligió
`primaryCpuAbi=arm64-v8a` y el proceso mapeó
`/lib/arm64/libil2cpp.so`. Esto corrige la premisa de la primera tanda, que
atribuía el fallo a una traducción de 32 bits sin probar la variante de 64 bits.

El arranque del sistema tardó ~80 s. El cliente mostró el menú de login, el
diálogo de consentimiento UMP, el menú principal, el tutorial y el hall. El
primer arranque tras `pm clear` cayó a los ~105 s con `SIGSEGV` en
`IL2CPP Threadpool`; el segundo arranque alcanzó el menú. La clasificación
completa está en [estabilización del emulador](emulator-stabilization.md).

### 3.3 Login de ChillyRoom

El botón “账号登录” (icono de gamepad) es el login de **Google Play Games**:
llama a `GooglePlayAccountAgent` y el proceso muere con
`NoClassDefFoundError: androidx.core.app.PendingIntentCompat`, precedido por
`Google Play services out of date ... Requires 213000000 but found 201817023`.
No es un fallo de credenciales ni de root.

El botón “ChillyRoom Account” abre el formulario de email/contraseña. El login
con la cuenta de laboratorio devolvió:

```text
[UserAuthClient] received response: OK
login success, type: Email
LifeCycleManager RunEvent OnAccountLoginFirst <cuenta>
CloudPackageData:ProcessData(FetchGameDataResp, ...)
```

El cliente cargó el menú principal, el tutorial y el hall. La cuenta de
laboratorio apareció sin progreso previo.

### 3.4 Lectura auténtica desde Linux

Del `shared_prefs` de la sesión se extrajo, en un archivo privado `0600`, el
token de `LegacyGateway` y el `LastLoginHostWithDistroId`. Desde Linux se
ejecutó, solo lectura:

```text
POST https://api-gateway.soulknight.chillyroom.com/Backup/FetchGameData
Authorization: Bearer <token>
Content-Type: application/json
{}
```

La respuesta fue `200`, `application/json`, **600 bytes**, con 17 claves de
agregado legacy (`heroData`, `petData`, `gameItemData`, `weaponUpgradeData`,
`battlePassData`, `createdAt`, `lastLoginTime`, `migratedInfo`, etc.). Las
colecciones estaban vacías. Se repitió con la cuenta invitado y con la cuenta
del titular: ambos agregados vacíos. La evidencia se conserva en el directorio
privado, con SHA-256 y sin publicar el token ni los identificadores.

`/Backup/GetBlobSave` devolvió `500` con el token del titular en todas las
variantes de cuerpo probadas; `/BlobSave/Download` devolvió `404`;
`/UserProfile/GetUserProfile` devolvió `500` con `Bearer`. El detalle está en
[lectura auténtica](authentic-cloud-read.md).

### 3.5 Restauración y modificación

Se restauró el perfil completo de 5.6 (archivos + `shared_prefs`) en el AVD
limpio. El cliente llegó a la escena de login sin `SIGSEGV`, pero se quedó en
`LoginInit`/100 % por el token y el estado de nube obsoletos. No se observó
aceptación ni rechazo del contenido.

Se editó `game.data.gems` de `0` a `424242` conservando las otras 40 claves
(25.460 → 25.465 bytes). El cliente cargó la cuenta del titular con ese archivo,
no emitió error de integridad y no lo reescribió mientras estuvo en ejecución.
Sin embargo, el tutorial otorgó 1.000 gemas en memoria y el HUD mostró 1.000,
no 424.242. Un relanzamiento limpio post-tutorial quedó bloqueado por el
requisito de hotfix al bloquear la nube. La modificación se revirtió al hash
original. Detalle y límites en [aceptación](modification-acceptance.md).

### 3.6 Proveedor Linux

Se mantiene `CloudSaveAcquisitionProvider` con:

- `DisabledCloudSaveProvider`: estado por defecto, sin red.
- `LocalFixtureCloudSaveProvider`: lee una copia ya extraída y la etiqueta
  `source="fixture"`.
- `GatewayCloudSaveProvider`: prototipo de solo lectura para
  `/Backup/GetBlobSave`, con token aportado fuera de banda.

La ruta de éxito de `GatewayCloudSaveProvider` sigue sin verificarse:
`/Backup/GetBlobSave` devuelve `500`. La lectura que **sí** se verificó es
`/Backup/FetchGameData`, que devuelve un agregado legacy distinto y no se
importa como `CloudSaveGameData`. Detalle en
[proveedor Linux](linux-cloud-provider.md).

## 4. Respuestas expresas

### 1. ¿Podemos ejecutar de forma estable Soul Knight 8.8.0 en nuestro entorno virtualizado?

**Sí, en una configuración concreta y reproducible:** AVD API 30
`google_apis` x86_64, KVM, 4 vCPU/4 GiB, `swiftshader_indirect`, ABI
`arm64-v8a`, primer arranque tras borrar datos que cae y segundo arranque que
alcanza el menú. No es estable “en cualquier AVD”: el login de Google Play
tiene un fallo de empaquetado del APK y la reejecución con una sesión guardada
obsoleta puede quedarse en `LoginInit`. El login de ChillyRoom por email sí
funciona.

### 2. ¿El juego acepta los archivos reconstruidos por SK-Under?

**No está demostrado visiblemente.** El cliente carga el perfil restaurado y el
`game.data` modificado sin error de integridad y no los borra, lo que indica
**aceptación estructural**. Pero no se observó el valor modificado en el HUD:
el tutorial mostró 1.000 gemas y no se completó un ciclo limpio post-tutorial
de guardado/recarga. No se declara aceptación.

### 3. ¿Podemos observar una descarga auténtica desde ChillyRoom Cloud?

**Sí, una lectura auténtica de `/Backup/FetchGameData`** con el token emitido
por el cliente, desde Linux, para la cuenta invitado y para la cuenta del
titular. Es un agregado legacy de 600 bytes con colecciones vacías. **No** se
obtuvo una copia no vacía de `CloudSaveGameData` ni el cuerpo de
`/Backup/GetBlobSave` (500).

### 4. ¿Podemos reproducir la adquisición autorizada desde Linux sin Android?

**Sí para `FetchGameData`:** el token del cliente es aceptado por el gateway y
la petición se ejecuta desde Linux. **No para `GetBlobSave`/`BlobSave`:** esas
rutas siguen sin contrato de éxito y devuelven 500/404. El proveedor Linux
existe y está probado con datos sintéticos, pero su ruta de éxito no está
validada.

### 5. ¿Qué obstáculos concretos impiden completar el ciclo de nube?

1. La cuenta de laboratorio no tiene progreso en el agregado legacy; no hay una
   muestra no vacía que comparar.
2. `/Backup/GetBlobSave` devuelve 500 y no se conoce su cuerpo exacto;
   `/BlobSave/Download` devuelve 404.
3. No se capturó un `NetPack` real ni el `CloudSaveGameData` con
   `serialzedVersion`, `cloudSaveId` y `platformId`.
4. El login de Google Play del APK falla por
   `NoClassDefFoundError: androidx.core.app.PendingIntentCompat` con GMS
   20.18.17 (requiere 21.30.00). La imagen `google_apis` no trae Play Store
   real ni Play Games.
5. El primer arranque en frío cae en `IL2CPP Threadpool`; el segundo funciona.
6. La reejecución con una sesión guardada obsoleta puede quedarse en
   `LoginInit`; hay que iniciar sesión de nuevo.
7. No hay dispositivo ARM físico ni GPU; el emulador es una herramienta de
   investigación, no el producto.

## 5. Seguridad y datos privados

- Las credenciales viven en `~/.config/sk-under/phase5-7/account.json`
  (`0600`), fuera del repositorio.
- Los tokens de invitado y de la cuenta se guardaron en archivos privados
  `0600`; no se incluyen en Git, logs, informes ni GitHub Actions.
- La evidencia auténtica de `FetchGameData` y los perfiles están en
  `~/.config/sk-under/phase5-7/evidence/2026-11-23/` (`0700`).
- No se publican correos, tokens, `cloudSaveId`, `platformId`, IDs de jugador,
  distro ni hashes de la partida.
- No se desactivó TLS, no se intentó saltar el pinning, no se usaron cuentas de
  terceros y no se modificó el cliente para eludir controles.
- No se ejecutó ninguna escritura remota (`Upload`, `Migration`); la
  modificación local se revirtió al hash original.
- El acceso al gateway fue de solo lectura (`FetchGameData`,
  `GetBlobSave`, `GameWorld/Time`).

## 6. Pruebas y verificación

| Comprobación | Resultado |
| --- | --- |
| `backend/.venv/bin/pytest -q` | **229 pasan, 14 omitidas** (sin muestras privadas) |
| `frontend/npm run build` | **Pasa** |
| `frontend/npm run test:browser` | **4 pasan** |
| `git diff --check` | **Limpio** |
| Higiene de secretos/artefactos | Verificada localmente; CI tras el push |

Las pruebas privadas de 8.6.0/8.8.0 se omiten cuando no existe el directorio
privado, como en CI. No se añadieron dependencias de producción ni rutas HTTP
nuevas en esta revisión.

## 7. Conclusión

La Fase 5.7 deja de estar bloqueada en el arranque: hay un cliente estable en
`arm64-v8a`, login ChillyRoom funcional y una lectura auténtica de
`FetchGameData` desde Linux. No se cierra el objetivo principal: falta una
partida de nube no vacía, el contrato de `GetBlobSave` y una prueba visible de
aceptación de una copia editada. El siguiente paso de mayor valor es obtener
una cuenta con progreso o el cuerpo exacto de `GetBlobSave`, no seguir
ajustando el emulador.

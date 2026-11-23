# Estabilización del cliente en el AVD

**Estado: ESTABLE EN UNA CONFIGURACIÓN CONCRETA, CON DOS FALLOS
REPRODUCIBLES.** El cliente oficial 8.8.0 arranca, muestra el menú de login,
permite iniciar sesión con ChillyRoom por email y llega al tutorial y al hall.
El primer arranque tras borrar datos cae en `IL2CPP Threadpool`; el segundo
arranca. El login de Google Play no se puede usar por un fallo de empaquetado
del APK. Ninguno de los dos fallos es root, Play Services por sí solo ni
detección de emulador.

## 1. Entorno observado

| Elemento | Valor |
| --- | --- |
| Host | Linux x86-64, AMD EPYC 9534, 6 vCPU, 11 GiB RAM, `/dev/kvm` |
| Virtualización | KVM dentro de un contenedor Docker con `--device /dev/kvm` |
| GPU | Sin `/dev/dri`; renderizado software |
| SDK | `~/.cache/sk-phase51/sdk` (18 G), emulador 37.3.10 |
| Imagen | `system-images/android-30/google_apis/x86_64` r16 (Android 11, API 30) |
| AVD | `sk57`, 4 vCPU, 4 GiB RAM, 6 GiB de datos, 720×1280, landscape |
| GPU del AVD | `swiftshader_indirect` |
| Cliente | APK oficial 8.8.0, `versionCode=1080800`, 781 MB, ABI `arm64-v8a` |

El AVD se creó con un `config.ini` mínimo:

```ini
AvdId=sk57
abi.type=x86_64
hw.cpu.arch=x86_64
hw.cpu.ncore=4
hw.ramSize=4096
hw.lcd.width=720
hw.lcd.height=1280
hw.lcd.density=320
disk.dataPartition.size=6G
hw.gpu.enabled=yes
hw.gpu.mode=swiftshader_indirect
image.sysdir.1=system-images/android-30/google_apis/x86_64/
tag.id=google_apis
PlayStore.enabled=false
```

Arranque usado:

```bash
emulator -avd sk57 -accel on -no-window -gpu swiftshader_indirect \
  -no-snapshot -no-audio -no-boot-anim -cores 4 -memory 4096
```

`sys.boot_completed=1` en ~80 s. El sistema es `userdebug`, `ro.debuggable=1`;
`adb root` funciona, pero no se usó para ejecutar el juego.

## 2. ABI: la premisa de 32 bits era incompleta

El dispositivo anuncia:

```text
ro.product.cpu.abilist   = x86_64,x86,arm64-v8a,armeabi-v7a,armeabi
ro.product.cpu.abilist32 = x86,armeabi-v7a,armeabi
ro.product.cpu.abilist64 = x86_64,arm64-v8a
```

El APK contiene **las dos** familias (`lib/arm64-v8a` y `lib/armeabi-v7a`). El
instalador eligió `primaryCpuAbi=arm64-v8a`; el proceso mapeó
`/data/app/.../lib/arm64/libil2cpp.so` y `libunity.so`. La primera tanda de
5.7 había ejecutado la variante de 32 bits sobre `ndk_translation` y había
atribuido el fallo a esa capa sin probar 64 bits. En este AVD limpio, 64 bits
es la variante que llega al menú.

## 3. Servicios Google y Play Store

| Elemento | Observación |
| --- | --- |
| GMS | `com.google.android.gms` 20.18.17 (201817023) |
| Play Store real | **No**. `com.android.vending` es `LicenseChecker` 1.8, no la tienda |
| Play Games | **No instalado** |
| Imagen | `google_apis`, no `google_apis_playstore` |
| `PlayStore.enabled` | `false` |

La imagen no es un entorno de Play Store. El cliente incluye agentes de Google
Play (`GooglePlaySpecialAgent`, `GooglePlayAccountAgent`) y el APK declara una
dependencia de GMS superior a la instalada:

```text
Google Play services out of date ... Requires 213000000 but found 201817023
```

## 4. Crash n.º 1: primer arranque en frío

Reproducción: `pm clear com.ChillyRoom.DungeonShooter`, instalar el APK y
lanzar la actividad principal. A los ~105 s, durante la carga de bundles y
antes de `LoadInitBundles`, el proceso muere:

```text
F libc: Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR),
        fault addr 0x20000001d in tid ... (IL2CPP Threadpo)
F DEBUG: ABI: 'x86_64'
F DEBUG: signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x20000001d
F DEBUG:     rax 0 ... rsp 0 ... rip 0
F DEBUG: backtrace:
F DEBUG:     #00 pc 0000000000000000  <unknown>
```

El hilo `IL2CPP Threadpo` ejecuta `lib/arm64/libil2cpp.so`. No hay un mensaje
de esquema, `FixData`, archivo corrupto ni `CheckSaveMac`; el fallo ocurre en
la carga de recursos, antes de que la partida se evalúe. El **segundo**
arranque de la misma instalación llega al menú de login. Es un fallo de
inicialización/traducción del primer arranque, no un rechazo de los bytes
restaurados.

Evidencia: `~/.config/sk-under/phase5-7/evidence/2026-11-23/logs/clean_login.log`.

## 5. Crash n.º 2: login de Google Play

El botón “账号登录” (icono de gamepad) ejecuta
`GooglePlayAccountAgent:callLogin`. Con GMS 20.18.17 el cliente lanza:

```text
W GooglePlayServicesUtil: Google Play services out of date ...
  Requires 213000000 but found 201817023
E AndroidRuntime: FATAL EXCEPTION: GoogleApiHandler
E AndroidRuntime: java.lang.NoClassDefFoundError:
  Failed resolution of: Landroidx/core/app/PendingIntentCompat;
E AndroidRuntime:  at com.google.android.gms.common.GoogleApiAvailabilityLight
  .getErrorResolutionPendingIntent(play-services-basement@@18.9.0)
...
E AndroidRuntime: Caused by: java.lang.ClassNotFoundException:
  androidx.core.app.PendingIntentCompat
```

El proceso muere. Es un fallo de empaquetado del APK: el código de
`play-services-basement` incluido referencia `PendingIntentCompat`, que no está
en el APK, y esa ruta se activa cuando GMS pide actualización. No es root, no es
detección de emulador y no es un rechazo de credenciales. Actualizar GMS a
≥ 21.30.00 podría evitar la ruta de resolución, pero la imagen no trae Play
Store real y no hay cuenta Google autorizada para completar esa vía.

Evidencia: `~/.config/sk-under/phase5-7/evidence/2026-11-23/logs/account_crash.log`.

## 6. Login ChillyRoom y sesión estable

“ChillyRoom Account” abre el formulario email/contraseña. El login con la
cuenta de laboratorio devolvió:

```text
[UserAuthClient] received response: OK
login success, type: Email
RunEvent OnAccountLoginFirst <cuenta>
RGSaveManager:ReloadAllData ...
CloudPackageData:ProcessData(FetchGameDataResp, ...)
LoginProcessOverAction after load title scene_login
```

El cliente mostró el aviso de consentimiento UMP, el menú principal, el
tutorial (“Can you take back the magic stones?”), el hall (“Select a hero”) y
el HUD. El juego es jugable con renderizado software, a costa de una carga
lenta y de un uso alto de CPU.

## 7. Relanzamiento con sesión guardada

Con un token de sesión guardado, el relanzamiento puede quedarse en el splash
al 100 % después de cargar la escena de login (`LoginInit:Start`), sin avanzar
al menú. Se observó con el perfil de 5.6 restaurado y con la sesión invitado
guardada. El login manual fresco sí funciona. No se atribuye a los bytes de la
partida: es la ruta de auto-login/nube con un token o host obsoletos.

Para una prueba de aceptación hay que evitar ese estado: iniciar sesión de
nuevo o limpiar la sesión, no restaurar un `shared_prefs` con tokens viejos.

## 8. Clasificación de causas

| Síntoma | Causa demostrada | Evidencia | No atribuir a |
| --- | --- | --- | --- |
| SIGSEGV en primer arranque | Inicialización nativa IL2CPP/traducción ARM64 en carga de bundles | Backtrace en `libil2cpp.so`, `IL2CPP Threadpool`, RIP 0 | Root, Play Services, detección de emulador |
| Crash al pulsar login Google Play | `NoClassDefFoundError` en el APK + GMS antiguo | `PendingIntentCompat`, `SERVICE_VERSION_UPDATE_REQUIRED` | Credenciales, root, anti-emulador |
| Splash 100 % al relanzar | Auto-login con token/sesión obsoletos | `LoginInit:Start`, sin avance; login fresco funciona | Bytes de la partida |
| `503` del host legacy | ALB sin servicio utilizable | Respuesta HTML `503` incluso sin token | Token del cliente |
| `500` en `GetBlobSave` | Contrato/cuerpo no conocido o servicio | `500` con token y varias variantes | Permisos de root |

## 9. Límites

- No hay dispositivo ARM físico ni GPU; el AVD es una herramienta temporal.
- La imagen es `google_apis`, no Play Store; no hay Play Games ni cuenta Google.
- GMS 20.18.17 no cumple el requisito 21.30.00 del cliente.
- El primer arranque en frío requiere un segundo intento; no es un entorno
  “production-grade”.
- No se capturó TLS ni se instrumentó el cliente; las conclusiones de red se
  basan en respuestas del gateway y en logs de Unity/Android.

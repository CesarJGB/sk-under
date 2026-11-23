# Validación en el cliente oficial

**Estado: BLOQUEADO.** El cliente oficial 8.8.0 no completa el arranque en el
AVD de laboratorio. Se intentó una restauración no-op del perfil local
auténtico de la Fase 5.6 y el proceso terminó con `SIGSEGV` antes de mostrar el
menú. No se observó aceptación, reparación ni persistencia de la partida.

## 1. Hipótesis

Si el puente Linux reconstruye sin cambios los 18 archivos locales de 8.8.0,
el cliente oficial debería cargarlos, conservar el progreso y no marcar error
de integridad. Una copia no-op restaurada en el mismo perfil de invitado es el
control necesario antes de probar cualquier edición.

## 2. Entorno

| Elemento | Valor |
| --- | --- |
| Host | Linux x86-64, 6 vCPU, 11 GiB de RAM, KVM disponible |
| Emulador | AVD Android 11 `google_apis` x86_64, `userdebug`, sin ventana |
| Cliente | APK oficial Soul Knight 8.8.0, `versionCode=1080800`, APK de 781 MB |
| ABI ejecutada | `armeabi-v7a` sobre traducción ARM del emulador |
| Canal del APK | Build Xiaomi global; incluye `XiaoMiGlobalPayAgent` |
| Perfil | Invitado local, 20 archivos inventariados; 18 decodificados |
| Claves/hashes | Conservados en el laboratorio privado, fuera de Git |

Se probaron dos configuraciones del emulador: la original y una con
`-cores 2 -memory 4096`. El comportamiento fue el mismo.

## 3. Procedimiento

1. Se conservó una copia inmutable del perfil auténtico de 5.6 y se calculó su
   inventario SHA-256 en el directorio privado.
2. Se detuvo el cliente y se reemplazó únicamente
   `/data/data/com.ChillyRoom.DungeonShooter/files/` por el contenido
   auténtico, preservando propietario `u0_a168` y contexto SELinux.
3. Se lanzó
   `com.ChillyRoom.DungeonShooter/com.chillyroomsdk.sdkbridge.BasePlayerActivity`.
4. Se capturaron `logcat`, una captura de pantalla y el estado del proceso a
   los 100–105 s.
5. Se repitió con el perfil de invitado de fábrica como control.

## 4. Evidencia observada

### 4.1 Cierre en la capa de traducción ARM

En la primera tanda, al pulsar el consentimiento o al terminar la pantalla de
título, el proceso murió en:

```text
Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR)
backtrace:
  #00 libndk_translation.so (ndk_translation::ExecuteGuest+288)
  #01 libndk_translation.so (RunGuestCall+254)
  #02 libndk_translation.so (RunGuestCall+42)
  #03 libndk_translation.so (RunGuestJNIFunction+74)
  #04 <anonymous:ba400000>
```

El fallo se repitió con “Do not consent”, con “Consent”, con los servicios de
Google desactivados y con el emulador de dos núcleos. No es un fallo del
consentimiento en sí: es una carrera de la traducción ARM en una llamada JNI.

### 4.2 Cierre dentro de `libil2cpp.so` tras la restauración

Con el perfil auténtico restaurado, el cierre ocurrió antes, en el hilo
`IL2CPP Threadpool`:

```text
signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0
Cause: null pointer dereference
#00 libil2cpp.so +0x02f74864
#01 libil2cpp.so +0x09f95748
...
```

Los últimos mensajes de Unity fueron:

```text
[ForcePatchManager] Deferred localization hotfix applied: .../files/loc/localize.csv
[Localization] Full localization source registered
[LoadInitBundles]Load Complete, time : 39.77204
```

No apareció un mensaje de error de esquema, de `FixData` ni de archivo
corrupto. El cierre ocurrió en la transición posterior a la carga de bundles.

### 4.3 Control con el perfil de fábrica

El mismo AVD, sin restaurar el perfil, también terminó con `SIGSEGV` en la
pantalla de título. Por tanto, **el cierre no se puede atribuir a los bytes
restaurados**. La diferencia de pila entre ambos intentos indica que hay al
menos dos caminos de fallo, pero no permite separar el efecto del perfil.

## 5. Resultado

| Comprobación | Resultado |
| --- | --- |
| ¿El juego inicia? | No completa el arranque; se cierra |
| ¿Reconoce la partida? | No observable |
| ¿Conserva el progreso? | No observable |
| ¿Errores de integridad? | No se observó ninguno |
| ¿Sobrescribe o repara archivos? | No se pudo medir después de un arranque estable |
| ¿Persiste tras cerrar y reabrir? | No probado |

## 6. Limitaciones

- El cierre es del entorno (traducción ARM, SDK Xiaomi, servicios del
  emulador), no una decisión del juego sobre la partida.
- No se dispone de un dispositivo ARM físico ni de un AVD estable para repetir
  la prueba.
- No se capturó el contenido de la pantalla de carga previa al cierre; solo los
  mensajes de `logcat`.
- El perfil restaurado es de invitado. No se usó la cuenta de nube en esta
  prueba para no consumir una vinculación de dispositivo.

## 7. Conclusión

**A.2 no se cumple.** No se puede declarar que el cliente acepte la copia
no-op. La afirmación correcta es: el cliente oficial 8.8.0 se cierra durante el
arranque en este laboratorio, antes de que sea posible atribuir el resultado a
los archivos restaurados. Sin un arranque estable no se debe intentar A.3 ni
A.4.

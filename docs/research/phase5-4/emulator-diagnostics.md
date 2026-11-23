# Diagnóstico del emulador Android

**El laboratorio Android está disponible y arranca, pero no contiene una
sesión autenticada utilizable.** El 23 de noviembre de 2026 UTC se reinició el
AVD de 5.2 y se midió su consumo en reposo: 52–55 s hasta
`sys.boot_completed`, 2,7–3,5 GiB de RAM y ~210 % de CPU en el contenedor. No
se inició sesión: el AVD quedó en el formulario vacío y no se dispone de
credenciales ni de un token autorizado para 5.4.

## Entorno actual

| Elemento | Estado observado |
| --- | --- |
| Host | Linux x86-64, kernel 6.8.0-142, AMD EPYC 9534, 6 vCPU, 11 GiB de RAM. |
| Virtualización | `/dev/kvm` presente; `systemd-detect-virt` informa `kvm`. El usuario del host no pertenece al grupo `kvm`; el contenedor recibe el dispositivo. |
| Docker | 29.8.1. Imagen `sk-phase51-android-lab:local` (564 MB virtuales, 200 MB de capa escribible) y contenedor `sk52-lab`. |
| SDK | `~/.cache/sk-phase51/sdk` (15 GB): emulador 853 MB, platform-tools 22 MB, system-images 14 GB. |
| AVD | `/tmp/sk52.ImGrMw` (2,8 GB), `userdata-qemu.img.qcow2` de 2,8 GB y `userdata-qemu.img` disperso de 6 GB. |
| Herramientas en el host | `adb`, `java` y `emulator` no están en `PATH`; se usan los del SDK montado. |
| AVD registrado en `~/.android/avd` | Ninguno. El AVD vive en el directorio temporal del laboratorio. |

El contenedor monta el APK en solo lectura, el SDK en solo lectura y el
directorio del AVD con escritura. Su comando arranca el emulador con
`-accel on -no-window -gpu swiftshader -no-snapshot -no-audio -no-boot-anim`.
No hay snapshots guardados.

## Fallos históricos

| Ensayo | Imagen y ABI | Resultado | Lectura |
| --- | --- | --- | --- |
| 5.1, Android 15 | API 35, x86_64 con traducción `arm64-v8a` | `SIGABRT`, `Abort message: 'Guest call didn't restore sp'`, marcos de `libndk_translation.so` y `force-crash`. | Fallo del puente de traducción al ejecutar código ARM64; no se atribuyó a un agente del SDK. |
| 5.1, ARM64 nativa | API 34 ARM64 en host x86_64 | El emulador no arranca: `Avd's CPU Architecture 'arm64' is not supported by the QEMU2 emulator on x86_64 host`. | Limitación de QEMU, no del juego. |
| 5.1, Android 11 | API 30, x86_64 con `armeabi-v7a` | Primer arranque: `SIGSEGV` (`SEGV_MAPERR`) en un hilo IL2CPP. Segundo arranque de la misma instalación: menú y formulario. | El fallo es reproducible en el primer arranque; el segundo conserva recursos descargados. |
| 5.2 / 5.3, Android 11 | API 30, `armeabi-v7a` | Primera ejecución con crash; relanzamiento hasta el formulario vacío. No se envió login en 5.3. | La sesión autenticada de 5.1 no se conservó. |

La evidencia no permite atribuir el `SIGSEGV` a una biblioteca concreta ni a
una dependencia gráfica. El fallo ocurre en código nativo traducido, después de
`JNI_OnLoad` e `InitSDK`, y el relanzamiento de la misma instalación llega a la
interfaz. Es compatible con un problema de traducción ABI o de inicialización
del proceso, no con una causa demostrada por los logs conservados.

## Qué se descartó y qué sigue abierto

| Hipótesis | Estado | Evidencia |
| --- | --- | --- |
| ABI incompatible | **Confirmado como limitación** para ARM64 nativa; el ABI de 32 bits sí ejecuta el juego. | QEMU rechaza ARM64; `armeabi-v7a` llega al menú. |
| Dependencias gráficas ausentes | **Descartado como causa principal** en el laboratorio: `swiftshader` y las bibliotecas del contenedor permiten arrancar y mostrar la UI. | El AVD arranca y la UI responde; no se aisló un fallo gráfico. |
| KVM ausente | **Descartado** en el contenedor actual: `/dev/kvm` está disponible y el arranque completa. | `sys.boot_completed=1` en 52–55 s. |
| Memoria insuficiente | **Parcial**: el contenedor limita a 4,395 GiB y el uso sube de 2,7 a 3,5 GiB en reposo. No se observó OOM en esta medición. | `docker stats`; `MemTotal` del invitado 2,9 GiB. |
| Conectividad | **No fue la causa del formulario vacío**: el cliente abrió el formulario sin login. Los SNI del proveedor ya aparecían antes de autenticar. | [Red de 5.2](../phase5-trace/network.md). |
| Credenciales o sesión | **Bloqueo actual**: no hay sesión autorizada ni credenciales en el repositorio. | El AVD quedó en el formulario; 5.1 descartó su sesión. |

## Medición de reposo

Se arrancó `sk52-lab`, se esperó `sys.boot_completed=1`, se dejaron 30 s de
estabilización y se tomaron tres muestras separadas por 10 s. No se lanzó el
juego; por tanto, la medición es una **cota inferior** del coste del
laboratorio, no del proceso del juego.

| Muestra | CPU del contenedor | RAM del contenedor | RSS de QEMU en el host | PIDs |
| --- | ---: | ---: | ---: | ---: |
| 1 | 215,5 % | 2,69 GiB | 2,86 GB | 181 |
| 2 | 215,9 % | 2,99 GiB | 3,17 GB | 182 |
| 3 | 209,7 % | 3,30 GiB | 3,49 GB | 190 |

La RAM creció durante la ventana; no se demostró que se estabilizara. El AVD
no se dejó encendido. Los detalles de metodología y la comparación con Python
están en [consumo de recursos](resource-benchmark.md).

## Por qué no se repitió la autenticación

1. El AVD disponible está en el formulario de acceso, no en una sesión
   autenticada.
2. La sesión de 5.1 se descartó al terminar aquel ensayo y no se conservó
   ningún token utilizable.
3. Enviar credenciales exige una acción interactiva del titular. No se
   solicitan, almacenan ni escriben credenciales en el repositorio.
4. No existe una interfaz remota autorizada que sustituya al cliente.
5. El objetivo de 5.4 no autoriza a eludir autenticación, controles ni
   protecciones del servicio.

Repetir la prueba requiere que el titular inicie sesión manualmente en el AVD
(o en un dispositivo propio) y que después se instrumenten las etapas con
metadatos permitidos. La [sesión autenticada](authenticated-session.md)
documenta ese bloqueo y el protocolo previsto.

## Reproducción del laboratorio

Con el SDK y el AVD del directorio temporal, el arranque observado fue:

```bash
docker start sk52-lab
# Esperar a que el invitado esté listo.
docker exec sk52-lab /sdk/platform-tools/adb shell getprop sys.boot_completed
docker stats --no-stream sk52-lab
docker stop sk52-lab
```

El comando no instala el APK, no inicia sesión y no modifica el APK. El AVD y
su `userdata-qemu.img.qcow2` son datos privados del laboratorio; no se
publican. El APK se identifica por SHA-256 en el
[informe de Fase 4](../phase4/apk.md).

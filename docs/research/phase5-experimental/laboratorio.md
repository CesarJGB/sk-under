# Laboratorio Android y reproducción

Se verificó el APK de 818 758 969 bytes con SHA-256 `54bb332be9444596501ec99f745f21adfa55265feea3a15331c735009b517f34`. Contiene binarios `arm64-v8a` y `armeabi-v7a`. El manifiesto y la firma del archivo entregado están descritos en la Fase 4. [Identificación del APK](../phase4/apk.md)

| Componente | Instalación o prueba |
| --- | --- |
| Host | Linux x86-64 bajo KVM. Al inicio faltaban el SDK y el emulador, el servidor ADB no estaba activo y el bus USB no mostraba ningún dispositivo Android. |
| KVM | El usuario del host no podía abrir `/dev/kvm`. Un contenedor sin modo privilegiado, con ese dispositivo y el grupo correspondiente, abrió KVM y creó una VM de prueba. El emulador devolvió `KVM (version 12) is installed and usable.` No se cambió la pertenencia a grupos en el host. |
| SDK | ADB 37.0.3 (1.0.41) y Android Emulator 37.3.10 (16970787), obtenidos del repositorio de Google. Se verificaron los checksums publicados de las herramientas e imágenes descargadas. |
| Aislamiento | AVD nuevo y sin cuenta de Google, APK y SDK montados en solo lectura, ADB sin puertos publicados y sin snapshots. Las imágenes arrancadas conservaron el tipo `user` y SELinux `Enforcing`. |
| Observabilidad | ADB para actividad, paquete, eventos y buffer de fallos. `tcpdump` se ejecutó dentro del espacio de red del contenedor. Para el arranque se inspeccionaron consultas DNS y solo se conservaron conteos y dominios del proveedor que aparecieran. |

## Repetición en un host Linux con KVM

Con las herramientas oficiales en `PATH`, la secuencia de instalación y arranque es la siguiente. El laboratorio original ejecutó los mismos binarios dentro del contenedor. Un host ARM64 con una imagen oficial equivalente permite verificar si el fallo persiste fuera del puente de traducción. [Aceleración](https://developer.android.com/studio/run/emulator-acceleration) · [Opciones de arranque](https://developer.android.com/studio/run/emulator-commandline)

```bash
sdkmanager 'platform-tools' 'emulator' 'system-images;android-35;google_apis_playstore;x86_64'
avdmanager create avd --name sk51 --package 'system-images;android-35;google_apis_playstore;x86_64'
emulator -avd sk51 -accel on -no-window -gpu swiftshader -no-snapshot -no-audio -no-boot-anim -port 5554
```

En otra terminal, confirmar `sys.boot_completed=1` y realizar la instalación. Usar una instancia vacía y sustituir la ruta al APK por la del archivo de referencia.

```bash
adb -s emulator-5554 shell getprop sys.boot_completed
adb -s emulator-5554 install --no-streaming /ruta/soul-knight-8-8-0.apk
adb -s emulator-5554 shell am start -W -n com.ChillyRoom.DungeonShooter/com.chillyroomsdk.sdkbridge.BasePlayerActivity
adb -s emulator-5554 logcat -b crash -d
bash docs/research/phase5-experimental/sondeo-android.sh emulator-5554
```

`am start -W` registra el arranque de la actividad. Comprobar después que el proceso sigue vivo y que la pantalla de acceso al juego permanece visible. El [sondeo](sondeo-android.sh) se limita a propiedades del sistema, metadatos de versión y disponibilidad de rutas. La prueba de `run-as` utiliza `id` y respeta el resultado de Android. Para pasos autenticados, trabajar con observaciones de pantalla redactadas y metadatos de red separados por etapa. Los buffers de logs, pantallas y datos del AVD se tratan como privados.

## Variante que restauró la partida

Crear otro AVD con `system-images;android-30;google_apis_playstore;x86_64` (revisión 10 para este ensayo) y arrancarlo con las mismas opciones. Esta imagen ofrece `armeabi-v7a`. Una vez iniciado Android, seleccionar el ABI contenido en el APK al instalarlo.

```bash
adb -s emulator-5554 install --abi armeabi-v7a /ruta/soul-knight-8-8-0.apk
adb -s emulator-5554 shell am start -W -n com.ChillyRoom.DungeonShooter/com.chillyroomsdk.sdkbridge.BasePlayerActivity
```

Si falla la primera apertura, intentar un segundo arranque en la misma instalación para conservar los recursos que descargó el juego. En el ensayo el segundo arranque abrió **ChillyRoom Account**. Desde el menú autenticado, abrir el panel de nube, confirmar que el resumen superior corresponde al respaldo y usar **Retrieve Progress**. El primer intento falló antes de pedir confirmación. Abrir el tutorial sin conexión, volver al menú y restablecer Wi-Fi permitió completar el segundo intento en ese AVD. [Registro de experimentos](experimentos.md)

# Registro de experimentos

## Instalación y arranque

El primer ensayo arrancó una imagen Google Play de Android 15 (API 35, revisión 9) en el host x86-64 con KVM. Android ofreció `x86_64,arm64-v8a` mediante `libndk_translation.so`. La instalación por ADB devolvió `Success`, y Android registró `versionName=8.8.0`, `versionCode=1080800` y `primaryCpuAbi=arm64-v8a`. `am start -W` devolvió `Status: ok`, `LaunchState: COLD`, `TotalTime: 10367` y la actividad `com.chillyroomsdk.sdkbridge.BasePlayerActivity`.

El registro del proceso muestra `IL2CPP: JNI_OnLoad`, Unity 2022.3.62f2 Release y la creación de `XiaoMiGlobalPayAgent` y `GooglePlaySpecialAgent` durante el inicio. A las 02:55:22 UTC se produjo `SIGABRT` en un hilo del juego. El buffer `crash` registró el diagnóstico y los eventos de Android confirmaron `Native crash` y `force-crash`. El prefijo del mensaje y los marcos relevantes se conservaron sin direcciones de memoria.

```text
Fatal signal 6 (SIGABRT)
Abort message: 'Guest call didn't restore sp'
/system/lib64/libndk_translation.so (berberis::ExecuteGuestCall)
/system/lib64/libndk_translation.so (berberis::RunGuestCall)
wm_finish_activity ... BasePlayerActivity,force-crash
```

La pantalla volvió al lanzador de Android. Los agentes que se inicializaron antes del fallo no permiten atribuirlo a un agente específico ni identificar el canal del respaldo. Tampoco hubo una respuesta de autenticación de ChillyRoom en esta ventana.

La imagen ARM64 nativa de Google Play (API 34, revisión 14) se probó en el mismo host con `-accel off` y `ANDROID_I_WANT_MY_TCG=yes`. Android Emulator se detuvo antes de arrancar el invitado con el mensaje `Avd's CPU Architecture 'arm64' is not supported by the QEMU2 emulator on x86_64 host`.

## Arranque alternativo de 32 bits

La imagen Google Play de Android 11 (API 30, revisión 10) ofrece `armeabi-v7a` mediante `libndk_translation.so`. `adb install --abi armeabi-v7a` instaló el mismo archivo con éxito. El gestor de paquetes confirmó ese ABI y la versión 8.8.0. El primer `am start -W` agotó su espera. Android mostró un aviso de aplicación sin respuesta para System UI. Tras seleccionar **Wait**, la actividad del juego siguió en primer plano.

El proceso alcanzó `RGScript.Other.NewSDK.InitSDK`, `Generated.ChillyRoomSdkClient.ChillyRoomService.Bootstrap` y la inicialización de WebView. La interfaz llegó a mostrar una descarga de recursos de arranque al 69 % y la etiqueta de contenido `8.8.0.11`. Después aparecieron `WaitInitResourcesState` y `LifeCycleManager.SetInitSuccessAndChannelConfirmedAndResourcesPrepared` en Unity. El cliente falló con `SIGSEGV` (`SEGV_MAPERR`) en un hilo de IL2CPP y Android volvió al lanzador. La traza de este segundo fallo no atribuye su origen a una biblioteca con símbolos.

El segundo arranque de la misma instalación alcanzó el 100 % de carga y mostró el menú de acceso de Soul Knight. El cliente abrió el formulario oficial de **ChillyRoom Account**. La instalación conservó el APK original.

La imagen Google Play x86-64 de Android 16 (API 36, revisión 7) también arrancó con SELinux en modo `Enforcing`. El laboratorio mostró un aviso de System UI sin respuesta durante la instalación en paralelo. Se interrumpió el intento de instalación para liberar recursos y continuar por la variante de Android 11, que ya había abierto el juego. El ensayo de Android 16 queda incompleto y no acredita un fallo de ejecución del juego en esa imagen.

## Inicio de sesión, consulta y primer intento de restauración

Se envió un solo intento desde el formulario oficial a las 03:11:06 UTC. En el registro se observaron `EmailOrPhoneLogin` y `OnLoginResultAction`. El formulario dio paso al menú. Se rechazó un aviso de consentimiento opcional y se abrió el panel de nube a las 03:13:41 UTC. El panel mostró el resumen remoto, distinto del estado local, y el botón **Retrieve Progress**. Esto confirma el acceso de la cuenta y que el juego pudo consultar y presentar su respaldo. No apareció un desafío de identidad.

Se pulsó **Retrieve Progress** a las 03:14:44 UTC. En el reloj del emulador se registró `CloudSaveGameData.CreateFromPlayerPref` dentro de `NewCloudSaveAgent.LoadGame` a las 04:14:48.366. A las 04:14:48.817 el cliente registró `ArgumentNullException: Value cannot be null.`, con `CloudSaveExtraData.GetExtraDescribe` y `NewCloudSaveAgent.LoadGame` en la traza. El panel siguió mostrando ambos estados y no mostró confirmación ni progreso aplicado. El código AArch64 de referencia construye ambos resúmenes y llama a `GetExceptRMBPayDescribe` antes del diálogo de restauración. El fallo observado ocurre al preparar la descripción de diferencias. El valor nulo y su procedencia quedan sin determinar con esta traza.

## Restauración confirmada

Se desconectó el AVD mediante el modo avión y se desactivaron Wi-Fi y datos. Con la sesión del juego ya abierta, el cliente inició el tutorial. Se abrió un cofre local y se regresó al menú con la opción de salida del tutorial. Después se restableció Wi-Fi. Se mantuvieron el APK, la cuenta, el idioma y el AVD. La intervención inicializó parte del estado local, aunque el ensayo no aísla qué paso exacto permitió evitar la excepción.

En el segundo intento, a las 03:23:01 UTC, **Retrieve Progress** abrió el diálogo oficial de descarga y reemplazo de progreso local. Se confirmó a las 03:23:53 UTC. El log filtrado registró `CloudSaveRunner` y `CoverPlayerPref` a partir de las 03:24:07. El control de recuperación desapareció y el panel local cambió para mostrar los mismos retratos e indicadores de progreso que el panel de nube. Al alinear ambos paneles y comparar una región común de la pantalla en memoria, el error medio normalizado de los canales de color fue de 0,0001 sobre una escala de 0 a 1. La comparación mide coincidencia de lo mostrado por el cliente. La verificación de bytes y datos internos requiere una copia permitida. [Pruebas de acceso a archivos](archivos.md)

## Matriz experimental

| Orden y prueba | Ejecutada y resultado | Evidencia | Limitación y siguiente experimento |
| --- | --- | --- | --- |
| 1. Instalar y ejecutar | Sí. Instalación en Android 15 y Android 11. Menú y formulario operativos en el segundo arranque de Android 11 con el ABI de 32 bits. | `adb install`, ABI de Package Manager, `am start -W`, log de Unity e interfaz. | La prueba ARM64 nativa requiere un host compatible. Replicar en un dispositivo físico del canal original. |
| 2. Iniciar sesión | Sí. La sesión de la cuenta propia permitió abrir el panel. | Formulario oficial y eventos `EmailOrPhoneLogin` y `OnLoginResultAction`. | Se verificó la sesión desde la UI. La duración y la renovación quedan por medir. |
| 3. Consultar respaldo | Sí. El panel mostró progreso de nube diferenciado del local. | Resumen de nube y botón **Retrieve Progress** visibles. | La UI confirma existencia. El formato y el transporte exactos requieren evidencia autorizada adicional. |
| 4. Restaurar | Sí. Primer intento con excepción y segundo intento completado. | `GetExtraDescribe` en el fallo. En el segundo intento hubo confirmación, `CoverPlayerPref` y coincidencia visual de los paneles. | Repetir desde instalación limpia y acotar la condición local que causa el primer fallo. |
| 5. Verificar archivos | Sí, antes y después de restaurar. | `run-as` rechazado, `adb pull` denegado sobre las rutas candidatas de `game.data` y `adb backup` con cero bytes. Descargas carecía de archivos candidatos. [Archivos](archivos.md) | Hace falta una salida permitida desde el juego o una exportación que entregue el proveedor. |
| 6. Reconstruir con datos de la cuenta | Sin ejecutar por falta de copia accesible. | El cliente reconstruyó y presentó el progreso. Al backend le faltan los bytes. | Obtener una exportación que conserve procedencia y formato, contrastarla con 8.6.0 y compararla con la interfaz restaurada. |
| 7. Evaluar automatización | Sí como evaluación de interfaces y permisos. La UI y la restauración se probaron de forma supervisada. | Secuencia de interfaz demostrada en el AVD y sondeo de permisos reproducible. [Arquitecturas](arquitecturas.md) | La extracción automatizada está bloqueada y el acceso web delegado requiere el contrato del proveedor. |

El experimento utilizó la sesión de prueba para lectura y restauración. No se seleccionó **Upload Progress**. Al finalizar se descartaron el AVD, su sesión local y las capturas temporales.

## Observación de red

Durante el arranque de Android 11 se observó la descarga de recursos desde la interfaz. Una ventana de 35 segundos de DNS UDP dentro del contenedor dio cero paquetes en el filtro. Una consulta de control separada al sitio público de Soul Knight confirmó que la técnica podía observar DNS en el laboratorio. El método solo observa DNS visible y puede perder consultas en caché o tráfico resuelto de otra forma. El log de inicio mostró la activación de PDNS en el WebView, sin una atribución verificable de dominio para esa descarga.

En las ventanas de acceso y restauración se muestreó el número de conexiones TCP activas al puerto 443 y los contadores agregados de recepción, sin inspeccionar el contenido de los paquetes. El proceso de juego registró `FetchData` y `NewCloudSaveAgent` en la sesión. El panel demuestra que el cliente recibió datos suficientes para representar la partida. Los contadores son del contenedor y no atribuyen una conexión a una operación específica. Siguen sin determinarse el dominio, la solicitud exacta y la elección de RPC o BlobSave para este respaldo.

## Comprobaciones del repositorio

| Prueba | Resultado |
| --- | --- |
| Backend con las nueve referencias privadas de 8.6.0 | `uv run --locked pytest -q` · 124 aprobadas. |
| Instalación y compilación del frontend | `npm ci` y `npm run build` completados. |
| Navegador | `npm run test:browser` · 4 aprobadas. |
| Herramienta de sondeo | `bash -n` y ejecución contra el AVD Android 15 comprobadas. Incluye detección de ruta denegada y ruta visible. |

# FetchData, ForceFetchData y el panel

**El panel puede iniciar FetchData antes de la confirmación y la vista previa puede reutilizar el agregado en memoria.** Se identificó el campo que escribe la ruta de éxito y se siguió su lectura hasta la comparación. El momento en que se llenó ese campo en la sesión del titular sigue abierto.

| Pregunta | FetchData | ForceFetchData |
| --- | --- | --- |
| ¿Quién puede iniciarlo? | En ARM de 32 bits, al mostrar el panel se comprueba HasFetchData. Si vale cero, se llama a UseOldLogic, que bajo otra condición puede iniciar FetchData(false). También existen llamadores de migración en AArch64. | Se conoce la máquina asíncrona y su llamada RPC. Sigue sin identificarse un evento de la UI que obligue a elegirla. |
| Entrada y transporte | `FetchData(bool showUI)`. La máquina crea un origen de cancelación y llama al slot BlobSave con un `CancellationToken`. | `ForceFetchData()`. Registra los callbacks de éxito y fallo para `LoginApi.DnloadSave` y hay una llamada a `DelayedTask`. |
| Resultado interno y público | El cliente devuelve `Task<JsonPayload>`. El agente usa el texto de Data, parsea y devuelve una tarea con `(bool, ErrorResponse)`. | El callback recibe texto o `(Err, Exception)`. El método externo devuelve una tarea con `(bool, Err)`. |
| Fallo | Hay ramas de timeout, nulo y error. El cliente examina 200, 400, 401 y 500. El estado del respaldo concreto sigue sin medirse. | El callback de fallo despacha a `onLoadGameFail`. El texto de éxito pasa por código que contempla serializador, canal y aplicación automática. |
| Caché | Al tener éxito, la sobrecarga de objeto almacena el agregado y marca el fetch. Hay una invalidación explícita. Se desconoce la política de vigencia. | El nombre del método y su transporte no establecen que invalide, ignore o repueble ese campo en cada invocación. |
| Restauración | El agente lee el agregado retenido para construir la comparación y contempla una alternativa si el campo es nulo. | El RPC puede desembocar en el runner. Falta una pareja solicitud–respuesta que identifique el camino ejercido por el titular. |

## Comprobaciones nuevas en el APK de referencia

Direcciones virtuales AArch64 anteriores a reubicación. Para repetir, verificar el APK y extraer `lib/arm64-v8a/libil2cpp.so` en privado. Desensamblar los rangos con `llvm-objdump -d --start-address=0x7ef3894 --stop-address=0x7ef38d8 libil2cpp.so`, sustituyendo los límites por cada punto de la tabla. Resolver los tokens y tablas con el procedimiento de 5.2. El SHA-256 del ELF es `4cef1adecda2ed7c523d683df1412a88d43e0704b2c230f5a962b54c569921b9`. [Identidad del APK](../phase4/apk.md) · [Resolución IL2CPP](../phase5-trace/blobsave.md)

| Sitio | Observación |
| --- | --- |
| `0x07f57294`, `0x07f5a930`, `0x07f5cd20` | Tres `bl 0x07ef59dc` a FetchData. En los tres, `w0=0`. El primero está en `MoveCloudSaveManager.<MoveData>d__75`, el último en `OptionalMoveCloudSaveManager.<MoveData>d__22`. El recuento de saltos directos omite delegados, tablas virtuales y parches. |
| `0x07eec50c`, `0x07eecdf4`, `0x07eece40` | Los accesores ubican HasFetchData en el byte estático +1 y LoadedGameData en +0x70. |
| `0x07ef3748`, `0x07ef38a4`, `0x07ef38d0` | `onLoadGameSuccess(CloudSaveGameData)` conserva el argumento de entrada, escribe 1 en el indicador y guarda la referencia en +0x70. |
| `0x07ef30ec`, `0x07ef30f4`, `0x07ef82c8` | `RefreshFetchDataTag` limpia el indicador y salta a `SetLoadedDataToNull`, que escribe nulo en +0x70. |
| `0x07ef7080–0x07ef70bc` | `LoadGame` lee el mismo +0x70. Si está vacío llama a `CloudSaveGameData.CreateNew`. El valor seleccionado entra en el primer `CreateExtraData`. Sigue la captura de preferencias locales. |
| `0x07f1ba6c–0x07f1ba78` | La máquina del callback de LoadGame pasa a `AutoDnloadAsync(tempLocalData, clearEscapeRunSave)` los campos de la clausura. El objeto en +0x18 proviene de la captura local (`0x07ef70c8–0x07ef70d4`). El flujo posterior incluye comprobaciones de identidad y plan de consumo. |
| ARM de 32 bits, `0x05880df4` y `0x05881130` | La máquina `<ShowView>d__80.MoveNext` llama a `CloudSaveDataView.ShowView`. Más adelante, en `0x05881120`, lee el byte estático +1, y si vale cero llama a `UseOldLogic`. El getter `get_HasFetchData` lee ese byte en `0x0583f474`. Las cargas en `0x058810c4` y `0x0583f464` resuelven la misma entrada GOT `0x0e5e1b1c`. |

En el ABI de 32 bits, `UseOldLogic` empieza en `0x05846d30`. Tras `FixHuaWeiOHSave` y `FuncForHotFixBeforeFetch`, el código compara con cero el resultado de una llamada en `0x058471ec`. Si ese resultado es distinto de cero, pone r0 a cero y llama en `0x058471fc` a `0x0584b664`, entrada de `FetchData(bool showUI)` (token `0x06021bff`). La semántica del segundo predicado sigue abierta. Para reproducir esta lectura usar `lib/armeabi-v7a/libil2cpp.so` del mismo APK, SHA-256 `53bcf36052c2deb0959f57f2e1773dff93efdaa8d6b0b085db62652fba3824b7`, y las direcciones ARM anteriores.

Esto demuestra una ruta condicional de **precarga desde la presentación del panel**, además de la posibilidad de reutilizar el resultado. Un resumen visible también es compatible con datos parciales. Para decidir entre precarga, segunda adquisición o caché en una restauración concreta se necesita identificar la revisión entregada y consumida en ambas ventanas. [Contratos RPC](../phase5-trace/rpc.md) · [Cronología y prueba discriminante](session-timeline.md)

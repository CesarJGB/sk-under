# Sincronización en la nube

## Cuenta y selección de ruta

En `classes2.dex`, `BasePlayerActivity` integra agentes de Android y reenvía mensajes a Unity mediante `UnityPlayer.UnitySendMessage`. `BaseAccountAgent` declara inicio y cierre de sesión, cambio de usuario y vinculación del invitado. Sus métodos `sendLogin`, `sendLoginFail` y `sendSwitchUser` devuelven resultados a Unity. En IL2CPP, `GooglePlayLoginAndCloudSaveAgent.Login` llega a `ChillyRoom.Services.Accounts.AccountSdk.Login`. `CloudSaveUtil` distingue el inicio de sesión de ChillyRoom y el de canal, y declara comprobaciones del identificador local y del identificador de guardado. `assets/DefineCloudSaveID.json` contiene un mapa de 44 etiquetas de canal a identificadores de formato de guardado.

ChillyRoom documenta inicio de sesión con Google o cuenta ChillyRoom para Android, migración de respaldos de Google a su servidor a partir de 5.5.3, y límites por cuenta y dispositivo. El APK contiene adaptadores heredados de Google Play y Apple, `MoveCloudSaveManager` y `MigrationClient`. La documentación del proveedor describe respaldos y recuperación mediante soporte. Las ramas de legado y migración siguen presentes en el binario. [Manual de Android](https://soulknight.chillyroom.com/et/article/base/3) · [Límites de sincronización](https://soulknight.chillyroom.com/et/article/base/4) · [Guardado por canal](https://www.chillyroom.com/zh/article/4)

Los métodos `BlobCloudSaveAndNewLogOffUtil.UseBlobCloudSave` y `HuaWeiOhUseBlobCloudSave` son evidencia de selección por configuración y canal. La ruta que elegiría este cliente con una cuenta, canal y configuración remota concretos queda por medir.

## Camino del agregado remoto

| Etapa | Evidencia estática |
| --- | --- |
| Construcción | `NewCloudSaveAgent.SaveGame` (`0x06021c07`) llama a `CloudSaveGameData.CreateFromPlayerPref`. La clase `CloudSaveGameData` (`0x02000bcb`) reúne `gameData`, inventario, estadísticas, preferencias, tareas, mapas, temporada, modo PvP, evolución, pase de batalla y otros subsistemas. Contiene `serialzedVersion` con esa grafía, `cloudSaveId` y `platformId`. |
| Subida RPC | `CloudSaveRunner.DoUploadByRpc` (`0x0602235a`, VA `0x07fac35c`) verifica la cuenta, consulta la opción de serializador y contiene llamadas a `NewtonJsonUtil.ToJson`, `Abo.JsonUtil.ToJson` y UTF-8. `LoginApi.UploadSave` recibe un arreglo de bytes, texto auxiliar y un callback. `CallUploadGameRpcAction` denomina `compressedBytes` a su arreglo. El algoritmo exacto de compresión para cada rama y la estructura de transporte quedan pendientes. |
| Descarga RPC | La máquina de estados de `NewCloudSaveAgent.ForceFetchData` (`0x06021c71`) llama a `LoginApi.DnloadSave`. El método acepta callbacks de respuesta de texto y fallo. `NewCloudSaveAgent` tiene tratamientos de éxito, error, timeout o respuesta nula. `ParseJsonToCloudSaveGameData` recibe texto JSON, llama a `FixData` y declara el agregado como tipo de retorno. `LoginApi.GetSaveTimeInfo` consulta información separada sobre el guardado. |
| Subida y descarga por blob | `CloudSaveRunner` declara `DoUploadByBlobSave`. `ChillyRoom.SoulKnight.BlobSaveService.V1.BlobSaveClient` declara `UploadAsync(JsonPayload)`, `DownloadAsync` y `ReadObjectResponseAsync`. El modelo `JsonPayload` tiene una propiedad de texto `Data`. La máquina de estados de subida (`0x0601f1d1`) llama a `JsonConvert.SerializeObject`, `Compress` y `HttpClient.SendAsync`. La de descarga (`0x0601f1cd`) llama a `HttpClient.SendAsync` y lee cabeceras de la respuesta. Existe `ContentIsGzipEncoded`, indicio de manejo de gzip. El nombre exacto de las propiedades serializadas y el contrato HTTP quedan por verificar. |
| Aplicación local | `NewCloudSaveAgent.LoadGame` (`0x06021c0b`) construye una vista de diferencias con `CloudSaveExtraData` y compara progreso. `CloudSaveGameData.CoverPlayerPref` (`0x060072db`) llama a `AboGameData.CoverPlayerPref`, `MergePaymentHistoryCacheForSameAccount` y `CloudSaveUtil.SetLocalSaveId`. Existen rutas de recuperación para pase de batalla y tienda activa. |

El APK también declara `ChillyRoom.SoulKnight.CloudPackage.V1.FetchGameDataReq` (`0x02003bf8`) y `FetchGameDataResp` (`0x02003b1e`). La solicitud tipada tiene `EventType` y `DateTimeUtcOffsetOfMinutes`. La respuesta incluye héroes, mascotas, habitación, objetos, mejoras de armas, pase de batalla, estado de tienda, última sesión y `MigratedInfo`. Estos modelos describen otra superficie de datos. Su relación exacta con cada operación de respaldo queda sin determinar.

## Validación y versiones

- `LoginApi.CheckSaveMac` (`0x06009dec`) usa identificadores de cuenta y plataforma y un valor denominado `mac` en una operación RPC. El manual del proveedor confirma reglas de vinculación y pertenencia de guardados. Quedan abiertos el significado criptográfico de ese valor, el algoritmo de integridad remota y la validación del servidor. [Límites de sincronización](https://soulknight.chillyroom.com/et/article/base/4)
- `CloudSaveRunner.IsUploadAccountValid` y `CanApplyUploadResult` consultan la cuenta vigente. `DoUploadByRpc` verifica la cuenta antes de enviar y contiene ramas de cancelación. Esto confirma comprobaciones del cliente durante cambios de cuenta. La política del servidor para concurrencia, conflictos y compatibilidad entre versiones queda pendiente de verificación.
- Los `.data` de 8.6.0 contienen documentos locales individuales. Para el remoto, el APK evidencia un agregado con datos de varias familias, identidad, versión y una envoltura de transporte. Un archivo de inventario individual ofrece una vista parcial del progreso. Una igualdad byte por byte en el editor local comprueba preservación del archivo que se importó.

## Integración autorizada

El flujo verificable para el usuario es la copia y restauración desde el cliente oficial con su propia cuenta. En la documentación pública consultada se encontraron instrucciones para usuarios y recuperación por soporte. Una integración directa requeriría un contrato autorizado del proveedor, un mecanismo de consentimiento y, para pruebas, una cuenta propia y un entorno aprobado. La ruta verificable para el editor actual es procesar los archivos locales que facilite el titular. [Manual de Android](https://soulknight.chillyroom.com/et/article/base/3) · [Preguntas frecuentes oficiales](https://soulknight.chillyroom.com/et/article/base/6)

La investigación de sincronización se realizó con el APK y documentación pública. Las pruebas del editor usaron una API local en memoria y el navegador en loopback.

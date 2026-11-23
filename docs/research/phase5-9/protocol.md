# Protocolo: continuación experimental

## Del panel a los datos

La hipótesis, ya planteada en 5.3, era que el panel precarga la copia antes de pulsar recuperación. En esta continuación se arrancó el AVD y el cliente 8.8.0 con la sesión conservada, se capturó TCP desde el arranque, se muestrearon los sockets del proceso y se usó `inotifyd` para registrar escrituras. El reloj Android y el del host se compararon al segundo antes de la operación.

| Hora UTC | Observación nueva |
| --- | --- |
| 19:44:16.445 | Marca de pulsación de apertura del panel |
| 19:44:18.500 | Registro `CloudSaveDataView:ShowView` |
| 19:44:19.384 | Inicio de flujo TLS/443 del proceso con SNI `save.soulknight.chillyroom.com` |
| 19:44:42.425 | Pulsación de recuperación; `NewCloudSaveAgent:LoadGame()` a las 19:44:43.693 |
| 19:44:54.837 | Marca de confirmación de la advertencia |
| 19:44:59.230 | `CloudSaveGameData:CoverPlayerPref()` dentro de `CloudSaveRunner:AutoDnloadAsync` |
| 19:45:00–01 | Eventos de escritura/renombrado de archivos y preferencias |

Entre apertura y pulsación de recuperación, el flujo identificado recibió 25.309 bytes y envió 998 bytes de carga TCP, incluidos TLS y posibles retransmisiones; no es el tamaño de una respuesta HTTP. El panel mostraba en ambas filas 1.000 gemas y contador 5. La correlación temporal y el SNI no revelan por sí solos la ruta HTTP ni el contenido del TLS.

El análisis ARM64 de `BlobSaveClient::<DownloadAsync>d__16.MoveNext` resolvió los literales `POST`, `/BlobSave/Download`, `application/json` y `gzip`; construye `StringContent` con cadena vacía y llama `HttpClient.SendAsync`. El flujo base de `NewCloudSaveAgent.FetchData` hacia `BlobSaveClient.DownloadAsync` y de `JsonPayload.Data` al parser estaba documentado en [5.8](../phase5-8/protocol.md) y [5.4](../phase5-4/rpc-transport-analysis.md); sigue siendo análisis estático, sujeto a ramas y parches. `RefreshUniqueId` añade `x-unique-id` derivado de `CloudSaveUtil.mac`. El código también construye `x-request-token`; no se ha establecido su semántica y las lecturas Linux descritas funcionaron sin enviarlo explícitamente.

## Contrato ejercitado en Linux

`POST https://save.soulknight.chillyroom.com/BlobSave/Download`, cuerpo vacío, `Accept: application/json`, `Accept-Encoding: gzip`, `Content-Type: application/json; charset=utf-8`; Bearer de sesión SDK, `x-unique-id`, `x-distro-id` y cabeceras de juego/plataforma. Se usaron valores de la sesión y dispositivo autorizados. La respuesta exitosa fue HTTP 200, `Content-Encoding: gzip`, 18.760 bytes en el cable HTTP; el JSON descomprimido tiene una propiedad `data` que contiene un JSON de agregado como texto. No se demuestra que todas las cabeceras enviadas sean obligatorias ni que el contrato sea universal.

Se verifican TLS normal, longitud HTTP cuando está declarada, CRC/truncamiento gzip, límites y esquema del agregado. El SHA-256 se calcula localmente: el servicio no proporcionó una huella independiente, por lo que no demuestra integridad extremo a extremo frente a un hash anunciado. Las firmas y respuestas del gateway legacy describen otra ruta y no se usan para identificar esta copia.

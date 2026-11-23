# Fase 5.2 · Trazabilidad de Soul Knight 8.8.0

**Se identificó el transporte de dos métodos del cliente.** En el código base, `NewCloudSaveAgent.FetchData` usa `BlobSaveClient.DownloadAsync(CancellationToken)` y pasa el texto de `JsonPayload.Data` al parser del agregado. `NewCloudSaveAgent.ForceFetchData` llama a `LoginApi.DnloadSave`, con un callback de éxito que recibe texto y otro de error que recibe código y excepción. Se comprobó el receptor BlobSave de la llamada en los dos ABI del APK, incluido el ejecutado por el AVD. El informe de la sesión de 5.1 sitúa FetchData en la sesión; la evidencia conservada no permite decidir si ese fetch produjo la copia finalmente aplicada o si la confirmación inició otra transferencia. [BlobSave](blobsave.md) · [RPC](rpc.md)

| Criterio | Resultado | Evidencia y límite |
| --- | --- | --- |
| A · Cronología y red | Parcial | Laboratorio reproducido en Android 11. Setenta muestras con sockets por UID, tiempos de Unity y dos ClientHello del proveedor antes del login. La sesión anterior se descartó en 5.1. El nuevo ensayo alcanzó el formulario vacío; faltan mediciones autenticadas. [Cronología](timeline.md) · [Red](network.md) |
| B · Transporte del respaldo de prueba | Pendiente en ejecución | Se identifica la ruta base de FetchData y el camino RPC de ForceFetchData. Falta asociar una respuesta concreta al agregado restaurado en la cuenta. |
| C · Procesamiento del guardado remoto | Parcial | Se resolvieron el DTO de descarga, su uso por el parser, las firmas genéricas y dos marcadores RPC. La reconstrucción fuera de Android funciona con agregado sintético. Falta una muestra remota autorizada para verificar codificación, esquema y correspondencia con progreso real. [Serialización](serialization.md) |
| D · Lectura remota independiente | Pendiente | Se verificó el contrato de entrada del backend. El censo del manifiesto, la UI y la documentación pública revisada no identificaron una salida autorizada con bytes para ese contrato. [Arquitectura](architecture.md) |

La dependencia reducida es la **validación de una copia ya entregada**. El adaptador comprueba la revisión por tamaño y SHA-256 antes de invocar al reconstructor y entrega un resumen estructurado sin ejecutar Android. La adquisición del respaldo continúa dependiendo de una salida del cliente o del proveedor. La PoC opera en memoria y su única fuente de prueba es sintética.

La revisión de la vista previa identificó cinco colecciones concretas que llegan al formateador y el papel de las opciones de comparación. Sigue abierta la identidad del argumento nulo. El diseño multiplataforma conserva el origen de la copia y exige evidencia aparte para iOS. [Error de restauración](restore-error.md) · [Autenticación y plataformas](authentication.md) · [Siguientes experimentos](next-steps.md)

## Verificación

Base `7f61a4b`. Se ejecutó la suite completa del backend con las nueve referencias privadas 8.6.0 habilitadas (132 pruebas aprobadas), instalación y build del frontend, y las cuatro pruebas Playwright. El sondeo se ejecutó contra la instalación de producción del APK en el AVD de laboratorio. Las únicas mediciones en bruto incluidas son columnas numéricas agregadas. El repositorio no necesita el APK, una cuenta ni Android para ejecutar los tests sintéticos.

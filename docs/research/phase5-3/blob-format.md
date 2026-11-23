# Capas de BlobSave, RPC y agregado

| Capa | Evidencia y operación reproducible | Límite |
| --- | --- | --- |
| 1. Transporte | El cliente BlobSave maneja HttpResponseMessage, cabeceras y estado. | Faltan cuerpo y cabeceras de una respuesta del titular. |
| 2. RPC | En la ruta RPC genérica el discriminador little-endian opera sobre un array. El clasificador local conserva el array y delimita el cuerpo. | La presencia de RPC en una restauración determinada y el códec interno siguen pendientes. |
| 3. DTO externo | El retorno administrado de la ruta BlobSave es JsonPayload. | El nombre de propiedad administrado no determina la grafía de una clave en la red. |
| 4. Data | Se observó el paso de un string a ParseJsonToCloudSaveGameData. `parse_blobsave_data(text)` permite probar desde ese límite. | La huella del UTF-8 generado aquí corresponde al texto suministrado. |
| 5. Transformación | El agente llama a FixData. Python reconoce un documento UTF-8 o un único miembro gzip suministrado, verifica fin de stream, CRC y límites. | Faltan las migraciones aplicadas al respaldo real. El gzip de los fixtures prueba el formato de archivo aceptado por Python. |
| 6. Agregado | El objeto contiene versión, identidad, gameData y subsistemas. El prototipo valida las reglas de Fase 5. | El orden de campos, obligatoriedad y tipos admitidos por el servicio aún requieren muestra. |
| 7. Secciones | Extracción de gameData y subsistemas presentes. Se conservan los tres estados presente, nulo y ausente, las claves adicionales y el original. | Un objeto extraído es una sección JSON lógica. |
| 8. Archivos del editor | El adaptador local existente reconoce nueve esquemas independientes en Base64/DES-CBC. En 8.6.0 se verificó la reconstrucción desde árboles JSON reales. | Convertir una sección de 8.8.0 a un archivo aceptado por el juego requiere una pareja agregado–salida del mismo cliente. |

[Transporte BlobSave](../phase5-trace/blobsave.md) · [Serialización](../phase5-trace/serialization.md) · [Agregado y correspondencias](../phase5/reconstruccion.md) · [Medición real](real-save-validation.md)

## Vectores RPC

Se revisó de nuevo `LoginApi._Decompress` en AArch64. En `0x0636cf7c` una referencia nula salta a `0x0636d054`, que llama a un helper. La rama `FF FF FF FF` llega a `0x0636d04c` y pone a cero el registro de retorno. Son caminos distintos. Python informa por separado `null_input` y `null_marker`. El clasificador describe los bytes disponibles, sin atribuir un estado de cuenta a ninguno.

Con al menos cuatro bytes, `00 00 00 80` pasa a ZipHelper el segmento **desde el offset 4**, de longitud total menos cuatro (`0x0636cfac–0x0636cfbc`). Incluso un encabezado sin cuerpo selecciona esa rama. El resultado de descomprimir cero bytes es desconocido. Con cualquier otro entero, o con cero a tres bytes, los bytes disponibles pasan íntegros a la envoltura. Una marca nula seguida de datos conserva el original en Python para inspección. El cuerpo comprimido se mantiene opaco. La identidad del algoritmo necesita una muestra autorizada con salida conocida o evidencia del helper exacto `0x06002663`. Hay métodos homónimos en otro namespace. [Contraste de ambos ABI](../phase5-trace/rpc.md) · [Clasificador](../../../backend/app/cloud_envelope.py)

## Casos ejecutables

El [fixture de agregado](../../../backend/tests/fixtures/cloud-save-sintetico.json) y los [once vectores RPC](../../../backend/tests/fixtures/rpc-frames-sinteticos.json) se pueden distribuir. Las pruebas generan tamaños esperados erróneos, duplicados, UTF-8 inválido, encabezados parciales, gzip con CRC dañado, truncado y basura posterior, documento plano, nulos y formatos desconocidos. La entrada binaria RPC exige un punto de entrada explícito. Un agregado inválido produce un error tipado y el archivo fuente conserva sus bytes. [Pruebas del parser](../../../backend/tests/test_cloud_save.py) · [Pruebas de la fuente y CLI](../../../backend/tests/test_local_cloud_import.py)

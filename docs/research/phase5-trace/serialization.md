# Dónde empieza la reconstrucción independiente

| Límite | Representación comprobable | Qué falta para unos bytes remotos |
| --- | --- | --- |
| HTTP de BlobSave | La tarea resuelve un DTO con un campo administrado string; la máquina contempla respuesta tipada o de error. | Cabeceras, grafía JSON, codificación del cuerpo y si se comprimió esa respuesta. |
| RPC genérico | Discriminador de 32 bits, bloque desde offset 4 en la rama comprimida; el callback de descarga entrega texto. | Algoritmo del bloque y unión completa entre respuesta RPC y callback para este respaldo. |
| Agente | El callback de FetchData pasa el texto de Data a `ParseJsonToCloudSaveGameData(string)`. El parser usa `FixData(string) → string`. Agente y runner tienen entradas de parser distintas. | Correcciones de esquema efectivas, serializador elegido y contenido aceptado para esa cuenta. |
| Agregado | `serialzedVersion` es un entero. Identidad de guardado y plataforma son texto. El progreso general incluye preferencias; inventario, estadísticas, tareas, temporada y otros subsistemas tienen modelos propios. | Versión efectiva y campos omitidos o nulos de una copia recuperada. [Correspondencia completa por subsistema](../phase5/reconstruccion.md) |
| Aplicación local | `CreateFromPlayerPref() → CloudSaveGameData` captura lo local para comparar. `CoverPlayerPref() → void` persiste el agregado y subsistemas. El runner tiene un camino automático que comprueba login e identidad y calcula un plan de consumo. | Bytes locales 8.8.0 comparables antes y después, verificaciones de integridad del proveedor y migraciones ejercidas. |

## Experimento fuera de Android

El [adaptador](../../../backend/app/cloud_import.py) acepta una fuente de una revisión concreta. `metadata()` entrega tamaño y SHA-256 esperados. `read(limit)` entrega bytes completos ya extraídos del transporte. El consumidor comprueba el límite antes de leer, compara tamaño y huella, llama al reconstructor existente y devuelve solo el resumen de esquema y presencia de secciones. La huella permite detectar cambios respecto de la descripción recibida. La autenticidad depende de quién entrega esa descripción.

Las [pruebas](../../../backend/tests/test_cloud_import.py) ejercen agregado sintético en JSON y gzip, sustitución de igual longitud, truncado, exceso de tamaño y dos prefijos RPC sobre datos sintéticos. Estos últimos deben rechazarse en el límite del agregado. Los ensayos cubren la transferencia entre una fuente y el backend sin suponer que comprimir el fixture reproduzca el blob del juego. Desde `backend/` se pueden ejecutar con `uv run --locked pytest -q tests/test_cloud_import.py tests/test_cloud_save.py`.

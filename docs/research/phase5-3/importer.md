# Importación de un agregado local

Desde `backend/`, el siguiente ejemplo funciona en Linux con Python 3.12 o posterior y el fixture público. La primera orden emite versión, codificación y presencia de secciones. La segunda emite el JSON de inventario, que en una partida propia puede contener progreso privado.

```bash
python -m app.cloud_import tests/fixtures/cloud-save-sintetico.json
python -m app.cloud_import tests/fixtures/cloud-save-sintetico.json --section itemData
```

Salida para la segunda orden, `{"materials": {}}`. Para una revisión con manifiesto externo, añadir `--size "$EXPECTED_BYTES" --sha256 "$EXPECTED_SHA256"`. El proceso devuelve 0 al completar y 1 si falla la lectura, la integridad, el reconocimiento o la extracción. Los errores de datos se emiten en stderr como un objeto con `error` y `message`. Los valores posibles incluyen `unreadable_source`, `size_limit`, `integrity_mismatch`, `unknown_format`, `invalid_aggregate` y `absent_section`. La petición de una sección explícitamente nula devuelve el JSON `null`.

```python
from pathlib import Path
from app.cloud_import import LocalFileSource, import_copy

result = import_copy(LocalFileSource(Path("tests/fixtures/cloud-save-sintetico.json")))
assert result.section("itemData") == {"materials": {}}
assert result.section("taskData") is None
assert result.aggregate.data.extra_fields["campoSintetico"]["entero"] == 9007199254740993
assert result.original.startswith(b"{")
```

`AggregateSource.metadata()` describe una revisión. Su `read(limit)` entrega bytes completos dentro del límite. La fuente local usa el manifiesto suministrado o calcula uno en una primera lectura acotada. El importador compara tamaño y SHA-256 con la lectura consumida antes del parseo. La medición propia permite detectar una sustitución entre las dos lecturas. Para comprobar procedencia hace falta confiar en el manifiesto de origen. El resultado conserva los bytes exactos, incluso si son gzip. Los resúmenes omiten los valores de progreso, las identidades y la huella.

El reconstructor reconoce el contenido sin depender de la extensión. Acepta hasta 8 MiB de entrada, 16 MiB inflados y 64 niveles de anidación. Conserva campos JSON desconocidos y permite distinguir una sección nula de una omitida. El llamador administra en privado los bytes y cualquier salida de sección. Para un archivo desconocido la fuente queda intacta. `summarize_copy` mantiene su contrato anterior.

Para procesar un string Data ya suministrado existe `parse_blobsave_data`. Para una entrada que el suministrador identifica como RPC, `inspect_rpc_frame` devuelve la clasificación, el original y la vista del cuerpo. Pasar un RPC marcado directamente al importador de agregados produce un error de formato. Estos límites son locales, sin llamadas de red ni accesos a Android. El editor de archivos individuales conserva sus entradas HTTP actuales. [Fuente y CLI](../../../backend/app/cloud_import.py) · [Límites de datos](../../../backend/app/cloud_envelope.py) · [Contrato experimental del agregado](blob-format.md)

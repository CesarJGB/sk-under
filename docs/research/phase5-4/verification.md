# Verificación de la Fase 5.4

**Todas las pruebas ejecutadas pasaron; las que dependen de una sesión
autenticada o de una muestra real de 8.8.0 no se ejecutaron y no se marcan como
superadas.** Este documento registra comandos, resultados y límites.

## Línea base antes de los cambios

Desde `backend/` en el commit `4053539`:

| Comando | Resultado |
| --- | --- |
| `uv run --locked pytest -q` | 154 aprobadas, 9 omitidas. Las omitidas son las nueve muestras privadas de 8.6.0. |
| `SK_PHASE4_SAMPLES_DIR=... SK_PHASE4_CIPHER_ENV_FILE=... uv run --locked pytest -q` | 163 aprobadas. |
| `npm run build` en `frontend/` | Correcto. |

No se observaron fallos previos. Las nueve omisiones son esperadas sin el
entorno privado; no se contaron como aprobadas.

## Después de los cambios

| Comando | Resultado |
| --- | --- |
| `cd backend && uv run --locked pytest -q` | **169 aprobadas, 9 omitidas**. |
| Suite con las nueve muestras privadas | **178 aprobadas**. |
| `cd frontend && npm run build` | Correcto (TypeScript y Vite). |
| `cd frontend && npm run test:browser` | **4 aprobadas** en Chromium. |
| `python -m compileall -q app` | Correcto. |
| `docker build -t soul-knight-editor:phase5-4 backend` | Correcto; imagen de 211 MB. |
| `docker run --rm soul-knight-editor:phase5-4 python -c "import app.cloud.importer, app.main"` | `cloud-ok`; el paquete nuevo se importa con el usuario sin privilegios. |
| Reconstrucción exacta de las nueve referencias 8.6.0 | **9/9** `inventory_match=true` y `original_roundtrip=true`. |
| `git diff --check` | Sin errores de espacios. |

La suite pública incluye 15 pruebas nuevas del prototipo. Las 9 privadas
requieren las variables documentadas en
[validación real](../phase5-3/real-save-validation.md) y no se publican.

## Cobertura de entradas inválidas

| Caso | Resultado | Prueba |
| --- | --- | --- |
| Hash incorrecto | `CopyIntegrityError` (`integrity_mismatch`). | `test_importer_rejects_a_changed_declaration` |
| Tamaño incorrecto | `CopyIntegrityError`. | Igual. |
| Copia vacía | `CopyLimitError` (`size_limit`). | `test_empty_copy_is_rejected` |
| Copia mayor que el límite | `CopyLimitError`. | `test_importer_rejects_a_limit_lower_than_the_copy` |
| Archivo ausente, directorio o FIFO | `TransportUnavailable`. | `test_simulated_provider_rejects_non_regular_paths` |
| JSON truncado | `AggregateFormatError`. | `test_unknown_and_truncated_inputs_are_typed` |
| Formato desconocido | `UnsupportedEncoding`. | Igual. |
| Sobre RPC comprimido | `RpcBodyUnknown` (`rpc_codec_unknown`). | `test_rpc_markers_are_classified_and_not_guessed` |
| Marca nula RPC | `RpcNullMarker` (`rpc_null_marker`). | Igual. |
| Sección ausente | `MissingSection` (`absent_section`). | `test_importer_accepts_a_local_revision` |
| Sección nula vs ausente | Distinguidas. | `test_preview_issues_distinguish_null_from_missing` |
| Fixture 8.8.0 sintético | Aceptado; campos desconocidos conservados. | `test_synthetic_880_fixture_is_stable_and_forward_compatible` |
| Proveedor simulado sin red | No abre sockets. | `test_simulated_import_does_not_open_sockets` |

Los casos existentes de JSON/gzip, CRC, truncado, basura posterior, claves
duplicadas, números no finitos y profundidad siguen cubiertos por
`test_cloud_save.py` y `test_cloud_import.py`.

## Reconstrucción 8.6.0

```bash
cd backend
PYTHONPATH=. uv run --locked python ../docs/research/phase5-3/check-local-reference.py \
  --cipher-env "$HOME/.config/sk-under/phase3/cipher.env" \
  --inventory "$HOME/.config/sk-under/phase3/INVENTORY.md" \
  "/ruta/privada"/*_111_.data
```

Resultado: nueve filas con `inventory_match=true` y
`original_roundtrip=true`; perfiles `compact`, `indent2` y
`original_line_indent`. No se publican nombres completos, huellas ni contenido.
Los tamaños y familias están en el [inventario público](../../phase3/INVENTORY.md).

## Comprobaciones de secretos y datos privados

| Comprobación | Resultado |
| --- | --- |
| `.env`, `*.data`, `*.apk`, `cipher.env` rastreados | Ninguno. `docs/phase3/INVENTORY.md` es público y solo contiene familias y tamaños. |
| Variables con valor en el diff | Ninguna; solo nombres de variables y ejemplos vacíos. |
| Credenciales, tokens o cookies en el código | No se añadieron. |
| Respaldos o fixtures reales nuevos | Ninguno; el único fixture nuevo es sintético. |
| Salida de pruebas con contenido privado | No se imprime; los resúmenes omiten identidad, hash y progreso. |
| AVD/APK en Git | No; están fuera del checkout. |

Las pruebas privadas se ejecutaron con el entorno del operador y no se
incluyeron en el repositorio.

## No ejecutado

| Prueba | Motivo |
| --- | --- |
| Inicio de sesión y panel en 5.4 | Sin sesión autorizada ni credenciales; el AVD está en el formulario. |
| Descarga y restauración reales | Dependen de la sesión anterior. |
| Validación de un agregado real de 8.8.0 | No hay muestra autorizada. |
| Reproducción de `ArgumentNullException` | Requiere el cliente IL2CPP y sus recursos; no se modificó el cliente. |
| Medición del emulador con el juego en ejecución | No se lanzó una sesión no autorizada. |

Estas pruebas quedan pendientes o bloqueadas según la
[matriz del informe](README.md). No se declara compatibilidad de 8.8.0 ni
eliminación total del emulador.

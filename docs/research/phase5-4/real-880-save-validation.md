# Referencia real de 8.8.0: estado y requisitos

**No se obtuvo una muestra auténtica de 8.8.0.** Se localizó el APK oficial y
se identificó por SHA-256, pero no se encontró un agregado, un archivo `.data`
ni una exportación de la cuenta de 8.8.0. La referencia disponible sigue siendo
el conjunto de nueve archivos locales de 8.6.0. Para no confundir formatos, se
añadió un fixture **sintético** con forma de 8.8.0 que no es una muestra real.

## Búsqueda realizada

| Fuente | Resultado | Evidencia |
| --- | --- | --- |
| APK oficial 8.8.0 | Presente; 818 758 969 bytes; SHA-256 `54bb332be9444596501ec99f745f21adfa55265feea3a15331c735009b517f34`. | `sha256sum`; coincide con [Fase 4](../phase4/apk.md). |
| Interior del APK | No contiene archivos `.data` de partida ni `game.data`; solo recursos y metadatos. | `unzip -l`. |
| AVD de laboratorio | Instalación del juego; no se exportó un agregado. Las rutas internas y `adb backup` dieron cero bytes en 5.1. | [Archivos](../phase5-experimental/archivos.md). |
| Panel de nube | Muestra el resumen, pero no ofrece una descarga de archivo al usuario. | [Flujo](../phase5/flujo-descarga.md). |
| Soporte/manual/FAQ | No se localizó una exportación machine-readable ni una API pública. | [Dependencias](../phase5-3/emulator-dependency.md). |
| Repositorio | No hay `.data` de 8.8.0; los `.data` están ignorados por `.gitignore`. | `git ls-files`; reglas del repositorio. |
| Directorios privados del operador | Solo nueve muestras de 8.6.0. | Inventario privado de Fase 3. |

El APK permite el análisis estático, no una partida. Un APK no contiene el
progreso de una cuenta.

## Referencia 8.6.0 verificada

Las nueve muestras locales se reconstruyeron byte a byte en Linux. La
verificación privada se ejecutó con el códec de Fase 3 y el inventario del
operador:

```bash
cd backend
PYTHONPATH=. uv run --locked python ../docs/research/phase5-3/check-local-reference.py \
  --cipher-env "$HOME/.config/sk-under/phase3/cipher.env" \
  --inventory "$HOME/.config/sk-under/phase3/INVENTORY.md" \
  "/ruta/privada"/*_111_.data
```

Resultado: 9/9 con `inventory_match=true`, `original_roundtrip=true` y los
perfiles de serialización ya documentados (compacto, dos espacios y sangría
original por línea). La suite completa con las nueve muestras pasó: **178
pruebas**. Los nombres, tamaños y huellas privadas no se publican.

## Fixture sintético de 8.8.0

Para probar compatibilidad hacia adelante sin afirmar que representa una
cuenta real, se añadió
`backend/tests/fixtures/cloud-save-880-sintetico.json`:

| Propiedad | Valor |
| --- | --- |
| Tamaño | 875 bytes |
| SHA-256 | `77bd5fb754b9ebc990f8033c314a338d67760045f51dc46d398a8852148c565c` |
| `serialzedVersion` | 1 |
| Identidad | `sintetico-880-cuenta` / `sintetico-880-plataforma` |
| Secciones | Todas las de objeto excepto `mallReloadData`; `settingData` y `maps` nulos. |
| Campos desconocidos | `campoSintetico880` con un entero > 2^53; `seccionNuevaSintetica`. |
| Propósito | Verificar versión, secciones nulas/ausentes, campos desconocidos y gzip. |

El fixture **no** es una muestra de 8.8.0 ni reproduce su esquema. Se marcó
como sintético en el nombre y en las pruebas.

## Compatibilidad del importador

| Caso | Resultado | Prueba |
| --- | --- | --- |
| JSON del fixture 8.8.0 sintético | Aceptado; versión 1; campos desconocidos conservados. | `test_synthetic_880_fixture_is_stable_and_forward_compatible` |
| gzip del agregado sintético | Aceptado; el original comprimido se conserva. | `test_importer_accepts_a_local_revision` |
| Sección nula vs ausente | Distinguidas en `summary()` y `preview_issues`. | `test_preview_issues_distinguish_null_from_missing` |
| SHA-256 o tamaño incorrectos | Rechazados antes de interpretar. | `test_importer_rejects_a_changed_declaration` |
| Truncado, basura, marcador RPC | Errores tipados; el original no se modifica. | `test_unknown_and_truncated_inputs_are_typed`, `test_rpc_markers_are_classified_and_not_guessed` |

El adaptador de archivos locales sigue siendo de 8.6.0 y solo lectura. No se
declaró compatibilidad de 8.8.0 para `.data` ni para la restauración.

## Qué no se puede concluir

- No se conoce el esquema efectivo de `gameData` ni de los subsistemas de
  8.8.0.
- No se sabe si `serialzedVersion` cambió, ni qué migraciones aplica `FixData`.
- No se conoce la representación JSON de `maps`/`sandboxConfig` en una cuenta.
- No se demostró que el importador acepte un agregado remoto real.
- No se demostró que los archivos locales 8.8.0 se reconstruyan desde el
  agregado.

## Requisito pendiente

La primera entrega medible de 5.4/5.5 es una **revisión propia autorizada de
8.8.0** con procedencia verificable. El titular o el proveedor deben entregar:

1. Una copia del agregado o de los archivos locales, obtenida por una función
   oficial, una exportación del titular o soporte.
2. Versión del juego, plataforma/canal, cuenta y método de acceso (sin
   credenciales).
3. Tamaño, SHA-256 y formato exterior de la copia.
4. Confirmación de que la copia puede conservarse fuera de Git y procesarse en
   privado.

No se debe publicar la copia, sus identificadores ni contenido de progreso. El
operador la guarda fuera del checkout, con permisos restringidos, y ejecuta el
importador en local. Si el proveedor solo ofrece restauración dentro del
juego, la adquisición independiente sigue bloqueada.

## Procedimiento al recibir una muestra

1. Calcular SHA-256 y tamaño; registrar el método de obtención.
2. Identificar el formato exterior (`file`, primeros bytes, gzip).
3. Ejecutar `python -m app.cloud_import <archivo> --size ... --sha256 ...`.
4. Comparar secciones con los modelos de 8.6.0 y registrar diferencias.
5. Probar el importador de transporte con un proveedor simulado y la muestra.
6. No habilitar escritura remota ni restauración.

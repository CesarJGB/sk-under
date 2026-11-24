# Herramientas del Save Knowledge Engine

CLI independientes, sin autenticación, red ni escritura de guardados. La
biblioteca compartida vive en `sk_knowledge/common.py` y solo usa la biblioteca
estándar de Python 3.12.

## `build_catalog.py`

Genera catálogos normalizados, índice de traducciones y diferencias de versión
desde una copia local de SKDFE.

```bash
python3 knowledge/tools/build_catalog.py --skdfe /ruta/a/skdfe
python3 knowledge/tools/build_catalog.py --skdfe /ruta/a/skdfe --check
python3 knowledge/tools/build_catalog.py --skdfe backend/tests/fixtures/skdfe-mini \
  --no-version-diffs --commit fixture-commit
```

`--check` no escribe y devuelve código 1 si algún artefacto difiere. La fixture
sintética permite probar la generación determinista sin git ni datos reales.

## `build_fields.py`

Construye `knowledge/fields/fields.json` a partir del registro histórico, la
metadata 8.8.0, el diff 8.6/8.8 y `overrides.json`.

```bash
python3 knowledge/tools/build_fields.py
python3 knowledge/tools/build_fields.py --check
python3 knowledge/tools/build_fields.py --write-legacy
```

`--write-legacy` solo debe usarse para reproducir la proyección histórica; las
pruebas exigen que coincida byte a byte con
`docs/save-research/field-registry.json`.

## `build_backend_items.py` y `build_backend_pets.py`

Generan las proyecciones empaquetadas que consume el backend, sin copiar listas
manualmente:

```bash
python3 knowledge/tools/build_backend_items.py
python3 knowledge/tools/build_backend_items.py --check
python3 knowledge/tools/build_backend_pets.py
python3 knowledge/tools/build_backend_pets.py --check
```

`items-880.json` cubre materiales y semillas; `pets-880.json` cubre las 58
mascotas y sus 12 variantes de skin. Las pruebas y la construcción fallan si las
proyecciones se desincronizan de `knowledge/catalogs`.

## `search_knowledge.py`

```bash
python3 knowledge/tools/search_knowledge.py knight
python3 knowledge/tools/search_knowledge.py "Bastón" --catalog weapons
python3 knowledge/tools/search_knowledge.py --field gameData.fishChip
python3 knowledge/tools/search_knowledge.py --path gameData.hero --type fields
python3 knowledge/tools/search_knowledge.py --id weapon_000 --json
```

Filtros: `--catalog`, `--category`, `--id`, `--path`, `--field`, `--type`,
`--limit`, `--json`. Devuelve 1 si no hay resultados.

## `compare_versions.py`

```bash
python3 knowledge/tools/compare_versions.py --list
python3 knowledge/tools/compare_versions.py --family weapons --from 8.6.0 --to 8.8.0
python3 knowledge/tools/compare_versions.py --from-file a.json --to-file b.json
```

Compara snapshots de SKDFE o dos catálogos normalizados e informa elementos
añadidos, eliminados, comunes y modificados. `--json` produce salida legible por
máquinas.

## `validate_knowledge.py`

```bash
python3 knowledge/tools/validate_knowledge.py
python3 knowledge/tools/validate_knowledge.py --no-manifest-check
python3 knowledge/tools/validate_knowledge.py --write-manifest
```

Comprueba esquemas, IDs duplicados, referencias entre catálogos, fuentes
existentes, aspectos de evidencia, proyección histórica, coherencia de
versiones, índice de traducciones, higiene de archivos y hashes del manifiesto.

## `generate_report.py`

```bash
python3 knowledge/tools/generate_report.py
python3 knowledge/tools/generate_report.py --family materials
python3 knowledge/tools/generate_report.py --field gameData.gems
python3 knowledge/tools/generate_report.py --version 8.8.0 --json
python3 knowledge/tools/generate_report.py --output knowledge/reports/coverage.md
```

Genera Markdown o JSON con cobertura, categorías, dependencias y fuentes.
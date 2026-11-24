# Save Knowledge Engine

Base de conocimiento técnica, trazable y reutilizable sobre los guardados de
Soul Knight. La Fase 7.0 la introduce para que las siguientes fases consulten
estructuras, catálogos, dependencias y evidencia antes de investigar o
implementar una función del editor.

El conocimiento describe el juego y las muestras estudiadas. **No habilita
escrituras nuevas ni demuestra posesión**: que un personaje, arma o mascota
aparezca en un catálogo no significa que una cuenta lo tenga desbloqueado.

## Estado

- Versión de referencia: **Soul Knight 8.8.0**.
- Compatibilidad histórica analizada: **8.6.0 → 8.7.0 → 8.8.0**.
- 616 campos técnicos (66 del registro histórico + 550 declarados en metadata).
- 24 catálogos normalizados con 4.286 elementos.
- 8.526 entradas de nombres en inglés, español y chino simplificado.
- 32 relaciones documentadas y 16 fuentes con procedencia.
- Políticas de escritura experimentales E2 para materiales, semillas, monedas de temporada, tarjeta de renacimiento de nube y pase de batalla.
- Herramientas CLI sin autenticación, sin red y sin acceso a guardados reales.

Las cifras actualizadas se regeneran en [reports/coverage.md](reports/coverage.md).

## Estructura

```text
knowledge/
├── README.md
├── manifest.json              # inventario con SHA-256 y recuentos
├── schemas/                   # contratos JSON de los artefactos
├── catalogs/                  # 24 catálogos normalizados
├── fields/
│   ├── fields.json            # registro canónico ampliado
│   └── overrides.json         # curaduría y valores observados
├── dependencies/              # relaciones entre campos, secciones y catálogos
├── translations/              # índice invertido de nombres
├── version-diffs/             # comparación determinista 8.6/8.7/8.8
├── evidence/                  # clasificación de fuentes y limitaciones
├── sources/                   # procedencia, commits, licencia y uso
├── reports/                   # informes legibles por humanos
└── tools/                     # CLI y biblioteca estándar reutilizable
```

## Fuentes canónicas

| Ámbito | Fuente canónica | Artefacto derivado |
| --- | --- | --- |
| Personajes del backend | `backend/app/catalogs/characters-880.json` | Proyección validada por pruebas; no se modifica |
| Campos históricos | `docs/save-research/field-registry.json` | `fields.json` conserva cada registro y genera una proyección byte a byte |
| Campos declarados | `docs/research/phase5-5/metadata-880-inventory.json` | Registros `declared` de `fields.json` |
| Catálogos del juego | SKDFE 8.8.0, commit `57b9b86335c080caca55e178c8409cb67658ccf6` | `catalogs/*.json`, `translations/`, `version-diffs/` |
| Evidencia propia | `docs/research/phase6-*`, `docs/save-research/` | Niveles E2/E3/E4 y dependencias confirmadas |

`fields.json` es la fuente canónica hacia delante para el conocimiento
ampliado. El registro histórico se mantiene intacto porque las validaciones del
backend lo exigen; `build_fields.py --check` comprueba que la proyección siga
siendo idéntica.

## Niveles de evidencia

Se conservan los niveles existentes:

- **H**: hipótesis.
- **E1**: referencia comunitaria, externa o metadata estática.
- **E2**: estructura observada en un guardado real propio.
- **E3**: semántica comprobada mediante evidencia controlada.
- **E4**: persistencia y consistencia verificadas dentro del alcance documentado.

Cada campo puede tener niveles distintos para **existencia**, **tipo**,
**semántica**, **compatibilidad entre versiones**, **relaciones** y
**persistencia**. Un campo E2 no asciende a E3 por aparecer en un catálogo, y
una coincidencia de nombres no confirma una dependencia.

## Catálogos

Cada catálogo declara `schema`, `family`, `game_version`, `source_refs`,
`license_note`, `count` e `items`. Cada elemento incluye un `id` estable,
nombres disponibles, categoría, atributos, relaciones, referencias al guardado,
nivel de evidencia y fuente con commit.

| Familia | Elementos | Uso principal |
| --- | ---: | --- |
| `characters` | 42 | Códigos, habilidades y skins por personaje |
| `character_skills` | 105 | Habilidades y posición de slot |
| `character_skins` | 802 | Skins indexadas por personaje |
| `pets` | 58 | Códigos, identificadores numéricos y nombres |
| `pet_skills` | 57 | Habilidades y descripciones de mascota |
| `weapons` | 1.081 | Armas visibles, anillos, transformaciones y variantes |
| `weapon_skins` | 192 | Skins indexadas por arma |
| `materials` | 343 | Unión de `item.json` y `needed_data.json` |
| `seeds` / `plants` | 47 / 47 | Jardín y relación semilla-planta |
| `blueprints` | 265 | Planos, costes y objetivo |
| `enemies` / `bosses` | 593 / 74 | Enemigos, jefes y drops |
| `lobby` | 49 | Muebles, desbloqueos, skins de sala y jardín |
| `tokens`, `special_items`, `vouchers` | 19, 29, 136 | Tickets, objetos y vales |
| `jewelry`, `chips`, `mounts`, `followers` | 15, 18, 4, 6 | Sistemas complementarios |
| `trophies`, `season_content`, `collectibles` | 212, 10, 82 | Trofeos y contenido de modos |

Los catálogos construidos desde `data.json` se marcan como
`observed_in_reference_sample`. Esa muestra tiene forma de guardado, pero es
externa: se usa como referencia E1, no como observación propia.

## Campos y dependencias

`fields.json` documenta, cuando la evidencia lo permite:

- identificador, nombre interno, categoría y descripción funcional;
- ruta local y ruta dentro del agregado de nube;
- tipo declarado, estructura, valores observados y límites;
- semántica comprobada, valores iniciales y campos que deben conservarse;
- catálogo asociado, identificadores y dependencias;
- fuentes, versiones, política de edición y restricciones;
- preguntas abiertas y experimentos necesarios.

Los vacíos se representan explícitamente con `null`, listas vacías o textos
`No documentado`; no se rellenan por inferencia. `dependencies.json` clasifica
cada relación como `confirmed`, `observed`, `hypothesis` o `negative` y separa
la evidencia de la interpretación.

## Herramientas

Todas usan solo la biblioteca estándar de Python 3.12 y funcionan desde la raíz
del repositorio.

```bash
# Buscar por nombre, identificador, categoría o ruta
python3 knowledge/tools/search_knowledge.py "Bastón Increíble" --catalog weapons
python3 knowledge/tools/search_knowledge.py --field gameData.fishChip --json
python3 knowledge/tools/search_knowledge.py --path gameData.hero --type fields

# Comparar versiones o catálogos
python3 knowledge/tools/compare_versions.py --list
python3 knowledge/tools/compare_versions.py --family weapons --from 8.6.0 --to 8.8.0

# Informes
python3 knowledge/tools/generate_report.py
python3 knowledge/tools/generate_report.py --family pets
python3 knowledge/tools/generate_report.py --field gameData.heroUnlock --json

# Validar y actualizar el manifiesto
python3 knowledge/tools/validate_knowledge.py
python3 knowledge/tools/validate_knowledge.py --write-manifest

# Regenerar catálogos desde una copia local de SKDFE
python3 knowledge/tools/build_catalog.py --skdfe /ruta/a/skdfe --check
python3 knowledge/tools/build_fields.py --check
```

La validación comprueba esquemas, duplicados, referencias, fuentes, evidencias,
coherencia de versiones, proyección histórica, ausencia de extensiones de
guardado y secretos, tamaño de archivos y hashes del manifiesto.

## Flujo para una nueva función

1. Buscar la categoría y el campo en `search_knowledge.py`.
2. Leer su registro en `fields.json` y sus relaciones en `dependencies.json`.
3. Comprobar el nivel de evidencia de cada aspecto y la política de edición.
4. Consultar el catálogo asociado para resolver identificadores.
5. Diseñar el experimento indicado en `experiments_required` antes de editar.
6. Actualizar primero la fuente canónica y regenerar las representaciones.
7. Ejecutar `validate_knowledge.py` y las pruebas del backend.

## Privacidad, licencia y límites

- No se guardan guardados, credenciales, tokens, recibos ni identificadores de
  cuenta en el repositorio.
- Los estados de compra y derechos gestionados por servicios externos son de
  solo lectura.
- SKDFE no incluye archivo de licencia en el commit consultado. SK-Under
  conserva únicamente identificadores, nombres normalizados, recuentos y
  relaciones factuales con procedencia; no redistribuye CSV, sprites, la wiki
  ni volcados completos.
- La metadata IL2CPP declara tipos y campos, pero no demuestra que una partida
  los use ni qué significan.
- La compatibilidad estructural entre versiones no implica compatibilidad
  semántica.
- La cobertura de nombres no equivale a cobertura funcional.

Limitaciones detalladas: [evidence/limitations.md](evidence/limitations.md).
Procedencia: [sources/sources.json](sources/sources.json).
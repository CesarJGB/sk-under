# Historial del repositorio SKDFE

## Ramas, etiquetas y commits

- El clon consultado tiene 149 commits.
- Solo existe la rama `main` en el remoto.
- No hay etiquetas.
- Commits de versión relevantes:
  - `57b9b86335c080caca55e178c8409cb67658ccf6` — 8.8.0.
  - `8cfa5d5` — 8.7.0.
  - `e088a67` — 8.6.0.
  - Versiones anteriores: 8.5.1, 8.5.0, 8.4, 8.3 y 6.3.0.

## Archivos históricos eliminados o reemplazados

| Archivo | Commits donde aparece | Contenido | Uso |
| --- | --- | --- | --- |
| `itemlist.json` | `4fb25ba`, `8d1c88e`, `6be6e48` | Mapas antiguos de identificadores de objetos | No usado; los catálogos actuales son más completos. |
| `weaponlist.json` | `2edecfd`, `a6f07c0`, `1075182` | Mapas de identificadores de armas | No usado; reemplazado por `weapon_full.json`. |
| `weapons.json` | Presente hasta `fc5798c` | Lista antigua de armas | No usado; estructura histórica. |
| `weapon.aznoobnam` | `eab82b9`, `6c1f435` | Datos auxiliares de armas | No usado. |
| `exportskdata.yml` | `2f9445d`, `0b90673` | Configuración de exportación | No usado. |

En versiones antiguas, `data.json` comenzaba con una lista `weapon` de identificadores.
Esa estructura no se conserva en 8.8.0 y no se usa para los catálogos actuales.

## Diferencias por versión

Las diferencias se calculan con `git show <commit>:<archivo>` y se publican en
`knowledge/version-diffs/`:

- `8.6.0_to_8.7.0.json`
- `8.7.0_to_8.8.0.json`
- `snapshots.json`

Cada archivo contiene recuentos, añadidos y eliminados por familia. No contiene valores de
cuenta ni copia de los datos de origen.

## Lecciones para la compatibilidad

- No se descarta un identificador por pertenecer a una versión anterior.
- La coincidencia de ruta o nombre es solo un candidato.
- Los catálogos históricos sirven para detectar migraciones de identificadores, no para
  afirmar que el comportamiento persiste.
- Las diferencias de recuento no sustituyen una prueba de compatibilidad semántica.
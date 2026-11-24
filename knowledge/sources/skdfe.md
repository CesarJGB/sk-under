# Fuente externa principal: SKDFE

## Repositorio y commit examinado

- Repositorio: <https://github.com/aznoobnam/skdfe>
- Commit de referencia: `57b9b86335c080caca55e178c8409cb67658ccf6`
- Mensaje: `Updated to 8.8.0`
- Fecha de consulta: 2026-11-23
- `version.json`: `8.8.0`
- Ramas observadas: solo `main`. No se encontraron etiquetas.
- Historial completo: 149 commits tras `git fetch --unshallow`.

No existe archivo de licencia, `LICENSE`, `COPYING` ni aviso de reutilización en el árbol
del commit. El README contiene únicamente el nombre del proyecto. Por ese motivo SK-Under
no redistribuye los CSV, `Allinfo.txt`, `wiki.html`, sprites ni volcados completos de
SKDFE. El Save Knowledge Engine conserva identificadores, nombres normalizados, recuentos,
relaciones factuales y la referencia exacta al commit y archivo de origen.

## Estructura relevante del árbol

| Archivo o directorio | Clasificación | Uso en esta fase |
| --- | --- | --- |
| `version.json` | Configuración estática | Versión de juego del snapshot. |
| `char_code_name.json` | Catálogo de identificadores | 42 códigos de personaje ordenados por índice. |
| `pet_code_name.json` | Catálogo de identificadores | 57 códigos de mascota ordenados por índice. |
| `highest_skin_ids.json` | Catálogo derivado | Índice máximo de skin por personaje. |
| `needed_data.json` | Catálogo derivado de localización | Habilidades, materiales, mascotas, skins y skins de arma. |
| `needed_data_cn.json` | Catálogo derivado | Variante en chino; no se usó como fuente principal. |
| `weapon_full.json` | Catálogo enriquecido | 995 armas con nivel, tipo, etiquetas y propiedades. |
| `weapon_skins.json` | Muestra con forma de guardado generada | 182 armas con `CurrentSkinIndex` y `UnlockedSkins`; no es un guardado auténtico. |
| `item.json` | Catálogo agrupado | Materiales, planos, plantas, tokens, objetos activos y personalización. |
| `enemy.json` | Catálogo de claves | 593 claves de enemigo. |
| `data.json` | Muestra externa con forma de guardado | 21 grupos de estructuras de vestíbulo, temporada y modos. No se trata como guardado auténtico. |
| `I2language.csv` | Tabla de localización | 18.259 identificadores y 15 idiomas, incluidos inglés y español. |
| `weapons.decrypted.csv` | Configuración descifrada | 1.058 filas de armas, anillos, transformaciones y variantes internas. |
| `items.decrypted.csv` | Configuración descifrada | 691 objetos con tipo, subtipo y `DataStr`. |
| `enemies.decrypted.csv` | Configuración descifrada | 593 enemigos, jefes y drops. |
| `Allinfo.txt` | Documento generado para la wiki | Renderizado de `rendering.py`; no se usa como fuente primaria. |
| `wiki.html` | Cliente de wiki | Implementación de consulta y presentación; no se copia. |
| `skdata.py` | Orquestador | Pipeline de extracción, derivación y publicación. |
| `skdfe/acquisition/` | Extracción | Descarga y extracción del APK. |
| `skdfe/assetstudio/` | Extracción | Ejecución de AssetStudio. |
| `skdfe/code_names/` | Derivación | Nombres de personaje y descubrimiento de mascotas. |
| `skdfe/config/` | Configuración | Rutas y parámetros del proyecto. |
| `skdfe/config_exports/` | Transformación | Descifrado XOR de CSV, parseo de claves y agrupación. |
| `skdfe/derivations/` | Transformación | Diccionarios, evolución de armas y `needed_data`. |
| `skdfe/i2/` | Transformación | Parseo de localización. |
| `skdfe/rendering/` | Generación | `Allinfo.txt` y representaciones de wiki. |
| `skdfe/sprites/` | Extracción | Sprites y dibujos; no redistribuidos. |

## Pipeline observado

`skdata.py` ejecuta, en orden:

1. Obtener información del APK.
2. Extraer el APK.
3. Ejecutar AssetStudio.
4. Extraer nombres de personaje desde `common.ab` y `hero.manifest`.
5. Extraer sprites y dibujos.
6. Descubrir candidatos de origen de mascotas.
7. Extraer assets.
8. Descifrar `enemies.csv`, `items.csv` y `weapons.csv`.
9. Parsear localización `I2language.csv`.
10. Escribir CSV descifrados.
11. Cargar `WeaponInfo`.
12. Generar `Allinfo.txt` y `weapon_full.json`.
13. Construir datos de evolución de armas.
14. Generar `needed_data.json` y `needed_data_cn.json`.

`config_exports.py` aplica XOR a los tres CSV, omite la fila de tipos, lee la columna
`Key` y agrupa las claves de `item.json` por prefijo mediante `ITEM_PREFIX_GROUPS`.
`derivations.py` construye los diccionarios de `needed_data` y los datos de evolución.

## Recuentos verificados

| Familia | 8.6.0 | 8.7.0 | 8.8.0 |
| --- | ---: | ---: | ---: |
| Personajes | 42 | 42 | 42 |
| Mascotas (códigos) | 56 | 57 | 57 |
| Armas en `weapon_full` | 982 | 989 | 995 |
| Habilidades de personaje | 103 | 104 | 105 |
| Skins de personaje | 782 | 792 | 802 |
| Claves de skin de arma | 177 | 185 | 192 |
| Materiales filtrados | 130 | 130 | 130 |
| Enemigos | 592 | 592 | 593 |
| Armas con skins | 167 | 175 | 182 |

Los recuentos y las diferencias por familia están en
`knowledge/version-diffs/`. Las listas de añadidos y eliminados se generan con
`git show <commit>:<archivo>` y no incluyen valores de cuenta.

## Limitaciones de la fuente

- No hay licencia declarada.
- Los catálogos son estáticos: no demuestran posesión, desbloqueo ni progreso.
- `weapon_skins.json` y `data.json` tienen forma de guardado, pero son artefactos del
  repositorio, no capturas propias verificadas.
- Algunos nombres no existen en `I2language.csv`. Se conserva `null` y la clave; no se
  inventan traducciones.
- `OriginalWeapon` en `weapons.decrypted.csv` se conserva como valor en bruto porque su
  semántica no está confirmada.
- La wiki y `Allinfo.txt` son representaciones generadas; no se usan para elevar
  evidencia.
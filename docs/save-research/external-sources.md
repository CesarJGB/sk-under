# Fuentes externas

| Fuente | Referencia usada | Alcance |
| --- | --- | --- |
| Discord | [Extracto y huella del documento local](community-reference.txt) | Android 8.5.0 según el autor. La segunda tanda carece de versión identificada. |
| SKDFE | [`57b9b86335c080caca55e178c8409cb67658ccf6`](https://github.com/aznoobnam/skdfe/tree/57b9b86335c080caca55e178c8409cb67658ccf6) | `main` consultada el 23-11-2026. `version.json` declara 8.8.0 para la extracción. |
| Wiki pública | [Sitio](https://bweab.id.vn/wiki.html#/) · [Implementación fijada](https://github.com/aznoobnam/skdfe/blob/57b9b86335c080caca55e178c8409cb67658ccf6/wiki.html) | El sitio HTTP 200 descarga el `wiki.html` de `main` en GitHub y reemplaza el documento. El análisis se fijó al commit de SKDFE. |
| SK-Under | [Fase 5.6](../research/phase5-6/README.md), [6.1](../research/phase6-1/client-validation.md) y [6.11](../research/phase6-11/README.md) | Comparaciones propias de Android Global 8.6.0, 8.8.0 y hotfix 8.8.0.11. |

La fase 6.12 conserva una extracción saneada en [catalogs/characters-880.json](catalogs/characters-880.json): 42 códigos ordenados, 105 habilidades y 802 skins, sin valores de cuenta ni estados de posesión. Procede de `char_code_name.json` y `needed_data.json` del commit fijado. El archivo permite resolver índices y nombres; no se usa para decidir desbloqueos ni para escribir un guardado.

Se clonó SKDFE fuera de SK-Under y se inspeccionaron sus archivos como texto. El árbol de ese commit carece de un archivo de licencia o aviso de copia y su README solo identifica el proyecto. Esta fase usa los datos como referencia y conserva los enlaces, el commit y los resultados de verificaciones propias.

## Inventario reproducido

| Artefacto | Registros y estructura |
| --- | --- |
| `char_code_name.json` / `pet_code_name.json` | 42 y 57 códigos únicos respectivamente. La posición da el índice de catálogo. |
| `highest_skin_ids.json` | 42 máximos por `c<ID>`. El máximo es un identificador, no una cantidad ni un inventario. |
| `needed_data.json` / `needed_data_cn.json` | Cada idioma tiene 105 nombres de habilidad, 130 claves de material filtradas por el exportador, 57 nombres de mascota, 802 nombres de skin de personaje en 42 grupos y 192 nombres de skin de arma. |
| `weapon_full.json` | 995 armas de `WeaponInfo`, con `name` como ID y metadatos como `title`, `level` y `type`. |
| `weapon_skins.json` | 182 entradas de arma, todas en `weapon_full.json`. Sus 192 IDs únicos bajo `UnlockedSkins` coinciden con las claves de la tabla traducida de skins de arma. Los estados se generan a partir del catálogo. |
| `item.json` | Taxonomía por familias. Contiene 331 materiales en seis grupos, 265 planos en siete grupos, 47 claves `plant` y 19 claves `token`. |
| `enemy.json` | 593 claves únicas, con grafía conservada. |
| `I2language.csv` | 18.259 IDs únicos de traducción y 15 idiomas, entre ellos español. |
| `weapons.decrypted.csv` / `items.decrypted.csv` / `enemies.decrypted.csv` | 1.058, 691 y 593 IDs únicos tras la cabecera y una fila de tipos. El CSV de armas contiene materiales, vínculos a armas base y recetas. |
| `data.json` | 21 grupos de referencia, entre ellos semillas, planos, cupones, muebles y temporadas. Sus valores ilustran estados y cantidades. |
| `Allinfo.txt` | Informe legible generado por `rendering.py`, con listas y etiquetas de armas y otros elementos. |

Los conteos de CSV usan filas del lector CSV y omiten la cabecera. Los tres archivos de configuración omiten también su fila `string`; el de traducciones contiene datos inmediatamente después de la cabecera. Las 995 entradas de `WeaponInfo` y las 1.058 del CSV son universos de fuentes diferentes. Los 130 materiales traducidos de `needed_data` corresponden a un filtro sobre claves I2, distinto de los 331 IDs asignados a grupos en `item.json`. [Árbol de referencia](https://github.com/aznoobnam/skdfe/tree/57b9b86335c080caca55e178c8409cb67658ccf6)

## Extracción y uniones

`skdata.py` orquesta la obtención y extracción del APK y AssetStudio (`acquisition.py`, `assetstudio.py`), las exportaciones de configuraciones (`config_exports.py`), los códigos de personajes (`code_names.py`), el procesamiento de sprite y retrato (`sprites.py`), las traducciones (`i2.py`) y los derivados (`derivations.py`, `rendering.py`). La detección de recursos de mascotas es una etapa de descubrimiento. `weapon_skins.json` agrupa claves de traducción de skin y de descripción de evolución. Sus `Level`, `CurrentSkinIndex` y `UnlockedSkins` se rellenan al exportar el catálogo. [Punto de entrada](https://github.com/aznoobnam/skdfe/blob/57b9b86335c080caca55e178c8409cb67658ccf6/skdata.py) · [Derivaciones](https://github.com/aznoobnam/skdfe/blob/57b9b86335c080caca55e178c8409cb67658ccf6/skdfe/derivations.py)

La wiki une el código de personaje con `Character<ID>_name_skin<N>` y `Character<ID>_skill_<N>_name`, la mascota con `Pet_name_<ID>` y el arma con `weapon/<código>`. Vincula el arma base desde `OriginalWeapon`, agrupa recetas por origen y destino, y cruza los planos con el CSV de objetos, requisitos de materiales y su clave de traducción. Las traducciones admiten alias `{clave}` con límite de profundidad y detección de ciclos, y recuperación del nombre en inglés si falta la traducción. [Modelo de la wiki](https://github.com/aznoobnam/skdfe/blob/57b9b86335c080caca55e178c8409cb67658ccf6/wiki.html#L1436)

La wiki consulta primero el SHA, descarga el conjunto fijado si puede resolverlo y usa `main` como alternativa. Limita tamaños de descarga, comprueba cabeceras, anchos y claves únicas, valida claves sentinela, referencias de armas iniciales y correspondencia de planos entre JSON y CSV. Publica el modelo después de validar y conserva el último conjunto válido en IndexedDB. Estas comprobaciones verifican un catálogo. La integridad de un guardado sigue dependiendo de su esquema y de transacciones observadas. [Procesamiento de datos](https://github.com/aznoobnam/skdfe/blob/57b9b86335c080caca55e178c8409cb67658ccf6/wiki.html#L2269)

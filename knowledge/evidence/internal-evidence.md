# Evidencia interna acumulada

Este documento indexa la evidencia que ya existía en SK-Under antes de la fase
7.0. No vuelve a afirmar conclusiones que no estuvieran documentadas y no eleva
niveles de evidencia.

## Niveles

| Nivel | Significado |
| --- | --- |
| H | Hipótesis o inferencia sin comprobación |
| E1 | Referencia externa o comunitaria |
| E2 | Estructura observada en un guardado real propio |
| E3 | Semántica comprobada mediante una edición controlada |
| E4 | Persistencia y consistencia verificadas dentro del alcance documentado |

Una entrada puede tener niveles distintos para existencia, tipo, semántica,
compatibilidad, relaciones y persistencia. El registro ampliado
`knowledge/fields/fields.json` conserva esa separación.

## Registro legado

`docs/save-research/field-registry.json` contiene 66 campos con formato estable:

- 54 en E2, 6 en E4, 5 en E3 y 1 en E1.
- Categorías: fichas de pesca (11), inventario (10), progreso y acceso (9),
  evolución de armas (8), pase de batalla (7), temporada (6), estadísticas (5),
  gemas (5), vestíbulo (4), preferencia interna (1).
- La mayoría tiene política `solo lectura`.

La fase 7.0 no modifica ese archivo. `knowledge/fields/fields.json` es el
registro canónico ampliado y `build_fields.py --check` demuestra que la
proyección legada sigue siendo byte a byte idéntica.

## Hallazgos confirmados

| Área | Evidencia | Alcance |
| --- | --- | --- |
| `gameData.gems = lastGems + varGems` | E4 | Rama de consumo, 8.8.0, Android físico y nube |
| `gameData.fishChip` + `itemData.materials.material_fish` | E4 | Compra, descuento y guardado del cliente; no se validaron historiales ni `cumulativeFishCount` |
| `gameData.heroUnlock` | E3 | Desbloqueo de personaje confirmado por el propietario; persistencia tras nuevo guardado no demostrada |
| `gameData.heroSkillUnlock` | E3 | Desbloqueo de habilidad confirmado por el propietario |
| `gameData.skinLock` | E3 | Semántica de desbloqueo de skin confirmada por el propietario; valores negativos y positivos no explicados por completo |
| `gameData.heroLevel` | E3 | Subida de nivel de Knight verificada; proyección XML/JSON observada |
| `itemData.blueprints` | E2 | Estados `Got`/`Researched` observados, sin edición confirmada |
| Tarjeta de resurrección (`rebornCard`) | E2 | Estado local observado; no se demostró el derecho de nube ni una edición segura |

## Evidencia estructural

- Agregado de nube 8.8.0: 17 entradas, 13 secciones de estado, 114.778 bytes en
  la captura documentada.
- `gameData` tiene 38 claves observadas; `itemData` 78; `statisticData` 160;
  `seasonData` 67.
- `skinLock` contiene 42 listas y 802 posiciones, coincidentes con el catálogo de
  802 skins por personaje e índice.
- `heroUnlock`, `heroLevel`, `heroSkill` y `heroSkillUnlock` usan los 42 códigos
  de personaje.
- `petUnlock` contiene 58 códigos booleanos observados.
- La muestra local 8.6.0 permitió comparar 77 claves de `itemData` con 116 en
  8.8.0; no había `gameData` en esa muestra.

## Contradicciones y límites

- `data.json` y `weapon_skins.json` de SKDFE tienen forma de guardado, pero no
  son guardados propios ni se ha demostrado su autenticidad. Se tratan como E1.
- El `OriginalWeapon` de `weapons.decrypted.csv` no se interpreta como
  evolución: la relación no está confirmada.
- `skinLock` usa valores `1`, `0`, `-13`, `-6` y `12000`; no se debe reducir a un
  booleano sin un experimento.
- Los historiales de compra (`fishChipStore*`, `mallReloadData.*`) no se editan
  ni se presentan como derechos de compra.
- `seasonData.chips` y `chips` de Monster Rise son estructuras distintas; el
  nombre compartido no implica dependencia.

## Política

Toda la información de compras, recibos, identificadores de cuenta y estados de
pago es descriptiva y de solo lectura. No se incorporan guardados privados,
credenciales ni valores de cuentas reales al repositorio.
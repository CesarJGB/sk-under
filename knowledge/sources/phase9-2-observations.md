# Observaciones propias — fase 9.2

Comparación de solo lectura entre tres muestras autorizadas: una cuenta Android
avanzada (A), una cuenta Android nueva (B) y una cuenta iOS avanzada obtenida a
través del editor externo CRDE (C). No se conservan credenciales, tokens,
identificadores privados ni guardados completos en el repositorio.

## Metodología

- A y B se descargaron con los mecanismos existentes de SK-Under, sin subidas
  ni modificaciones remotas.
- C se obtuvo mediante el editor RAW de CRDE, con una sesión de solo lectura y
  su endpoint de visualización. No se envió ningún formulario de modificación ni
  se guardó ningún cambio remoto.
- Las tres muestras se compararon por secciones, rutas, tipos y valores; los
  hashes se calcularon sobre los documentos descodificados originales.
- Los identificadores publicados son claves de configuración del juego. No se
  publican identificadores de cuenta, correo, tokens ni valores privados.

## Muestras

| Muestra | Plataforma | Perfil | `gameVersion` | `itemData.AppVersion` | Tamaño | Secciones |
| --- | --- | --- | --- | --- | --- | --- |
| A | Android | Avanzada | 2145 | ausente | 912.375 B | 14 |
| B | Android | Nueva | 2155 | 80800 | 222.148 B | 17 |
| C | iOS | Avanzada | 2155 | 1531 | 235.438 B | 14 + `_crde_misc` |

Hashes SHA-256 de los documentos descodificados:

- A: `dd938340c39b96e4daf5bcb3c7362de949adf371ae5efda3999680c5bc82b0a4`
- B: `dcb8ab17c9c59a7544643a2b8184be7e3a9c463cbe5f83cc88ca76f3d25b7d5a`
- C: `c3e22a8c1e67580078583fffa1755dca6cf4a106b869e3a8e8f30fd5fe4cddee`

A y B incluyen `cloudSaveId`, `platformId`, `serialzedVersion` y `maps` en el
nivel superior. C no los incluye: CRDE los conserva dentro de `_crde_misc`
(`platformId` con valor de canal iOS y una lista de mapas vacía). `_crde_misc`
es metadato del editor externo y no forma parte del guardado del juego.

## Vestíbulo: posesión frente a disponibilidad

Las tres muestras separan dos conceptos:

1. **Posesión**: claves presentes en `itemData.roomDecorateDic`.
2. **Disponibilidad funcional**: banderas en `statisticData.event2Count` y, para
   los decorados investigables, estados en `itemData.blueprints`.

A y C contienen los mismos diez objetos en `roomDecorateDic`, todos con valor
`[0]`. B solo contiene `ItemEggMachine: [0]` y no tiene ninguna bandera
`room_unlock_*`. La máquina de huevos es, por tanto, el único objeto inicial
observado.

Banderas observadas en `statisticData.event2Count`:

| Clave | A | B | C |
| --- | --- | --- | --- |
| `room_unlock_book` | 1 | ausente | 1 |
| `room_unlock_safe` | 1 | ausente | 1 |
| `room_unlock_pet_food` | 1 | ausente | 1 |
| `room_unlock_trash_can` | 1 | ausente | 1 |
| `room_unlock_plant` | 1 | ausente | 1 |
| `room_unlock_cellar` | 1 | ausente | 1 |
| `room_unlock_magic_area` | 1 | ausente | 1 |
| `room_unlock_quest_board` | 1 | ausente | 1 |
| `room_unlock_work_shop` | 1 | ausente | 1 |
| `room_unlock_badass` | 1 | ausente | 1 |
| `room_unlock_defence_mode` | 1 | ausente | 1 |
| `room_unlock_garden` | 1 | ausente | 1 |
| `room_unlock_season_mode` | 1 | ausente | 1 |
| `room_unlock_monster_rise` | ausente | ausente | 1 |
| `room_unlock_road` | 4 | ausente | ausente |
| `room_unlock_road_before` | 0 | ausente | ausente |
| `room_unlock_level_index_10` | ausente | ausente | 2 |
| `room_unlock_level_index_15` | ausente | ausente | 2 |
| `room_unlock_level_index_20` | ausente | ausente | 2 |
| `room_unlock_statements_count` | ausente | ausente | 85 |
| `room_decorate_fishbowl_level` | 3 | ausente | 3 |

`gameData.unlockRoomDecorate` está vacío en las tres cuentas y no sirve como
indicador. `gameData.roomLevel` vale 1 en A y 0 en B y C, de modo que tampoco
indica desbloqueo.

### Planos de decorados

`itemData.blueprints` usa texto en A (`Got`/`Researched`) y enteros en B y C
(`1`/`2`). C contiene 24 valores `1` y 174 valores `2`, lo que confirma que
`2` representa `Researched`. Planos `room_decorate_*` observados:

| Plano | A | C |
| --- | --- | --- |
| `blueprint_room_decorate_drink_seller` | Researched | 2 |
| `blueprint_room_decorate_egg_machine` | Researched | ausente |
| `blueprint_room_decorate_fishbowl` | Researched | 2 |
| `blueprint_room_decorate_magic_well` | Researched | 2 |
| `blueprint_room_decorate_mysteriou_statue` | Researched | 2 |
| `blueprint_room_decorate_safe` | Researched | ausente |

El catálogo de configuración solo define cuatro planos `room_decorate_*`
(expendedora, pecera, pozo mágico y estatua). La estantería, la caja fuerte, la
zona de comida, la papelera y la planta son instalaciones cuya bandera
`room_unlock_*` aparece en las cuentas avanzadas.

### Niveles de mobiliario

`gameData.roomObjectLevel`:

| Clave | A | B | C |
| --- | --- | --- | --- |
| `Book` | 5 | 0 | 5 |
| `CatFood` | 5 | 0 | 5 |
| `Chest` | 1 | 0 | 5 |
| `Planet` | 5 | 0 | 5 |
| `Safe` | 5 | 0 | 5 |

El máximo observado es 5 para las cinco claves. `Chest` en 5 en C corrige la
observación anterior, que solo disponía de A con 1. `Planet` no tiene bandera
`room_unlock_*` identificada.

## Otras diferencias estructurales

- **Personajes**: A tiene 37 entradas en `heroLevel` y 37 desbloqueos; B y C
  tienen 42. El nivel máximo observado es 8 (A: ocho personajes en 8; C:
  `Knight` en 8), no 7. La maximización al 7 está confirmada en Android físico;
  el nivel 8 observado no se ha validado con un escritor.
- **Habilidades**: `heroSkill` es el índice de la habilidad seleccionada, no un
  nivel. `heroSkillUnlock` es un mapa por personaje con entradas
  `{Key, Value}`. C selecciona índices 0, 1 y 2 según el personaje.
- **Skins**: `skinLock` es un mapa por personaje con entradas `{Key, Value: 1}`.
  `currentSkinDatas` es un mapa personaje → índice de skin seleccionada (A: 3
  entradas, B: 10, C: 19). El mapa entre índice y catálogo de skins no está
  determinado.
- **Mascotas**: `petUnlock` tiene 46 entradas en A y 58 en B y C. La intimidad
  de C incluye `pet_0 = 100`, `pet_8 = 129` y `pet_57 = 240` con
  `_full_intimacy = 1` y `_action_unlock = 1`. Confirma el máximo 240 para el id
  57; los ids 27 y 56 siguen sin máximo observado.
- **Colecciones**: `handbookCollectionUserPropertiesInitialized` está ausente en
  A y es `true` en B y C. `handbookEnemyCollectionTrackedLevels` está ausente en
  A, vacío en B y contiene enemigos con valor 6 en C. Su semántica de progreso
  no está demostrada.
- **Joyas**: A contiene nueve joyas con `durability = 100` y runas `None`; B y
  C no contienen joyas. No se conoce el máximo de durabilidad.
- **Plantas**: A tiene ocho parcelas con estados 1, 2 y 4; B y C tienen tres
  plantas con estado 1 y cinco posiciones nulas. No se conoce la semántica de
  los estados.
- **Forja**: `forgeWeapons` contiene tres armas y un `null` en las tres
  cuentas. Sigue sin identificarse un contador permanente por arma.
- **Selección de decoración**: `roomDecorateCurSkinDic` está vacío en A, B y C;
  `currentRoomDecorate` es texto en A y entero en B y C. El mapa de selección no
  está determinado.

## Límites

- La presencia de una clave no demuestra causalidad ni la eficacia de un
  escritor. La hipótesis de las banderas está respaldada por la correlación
  perfecta entre cuentas avanzadas y cuenta nueva, pero requiere validación
  física.
- No se identificaron banderas para `ObjectDrinkSeller` ni
  `ObjectMysteriouStatue`; solo se observaron sus planos.
- `room_decorate_fishbowl_level` es un nivel, no una bandera de desbloqueo; su
  rango y efecto no están demostrados.
- Las diferencias entre A y C no se atribuyen solo a iOS: A usa una versión de
  juego anterior y C una cuenta con otro progreso.
- No se publican guardados completos, credenciales ni identificadores privados.
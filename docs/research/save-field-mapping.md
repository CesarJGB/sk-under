# Mapa de campos de guardado — fase 9.2

Este documento resume las rutas investigadas y su estado. No sustituye a
`knowledge/fields/fields.json`, que es la fuente canónica para el editor y el
Save Knowledge Engine.

## Funcionalidades investigadas

| Funcionalidad | Campos principales | Tipo | Valores observados | Dependencias | Compatibilidad A/B/C | Certeza | Riesgo | Implementación | Prueba manual |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Niveles de personaje | `gameData.heroLevel` | mapa código → entero | 0..8; B todo 7; A 8 héroes en 8; C Knight 8 | `heroUnlock` para usar el personaje | Idéntica en las tres | 7 confirmado; 8 observado | Medio: el juego podría validar coste o máximo por personaje | Escritor activo hasta 8, experimental | Subir un héroe y comprobar nivel y siguiente mejora |
| Desbloqueo de personaje | `gameData.heroUnlock` | mapa código → bool | A 37; B/C 42 | Catálogo de personajes | Idéntica | Fases previas | Bajo | Escritor existente | Desbloquear uno y entrar al vestíbulo |
| Habilidades y skins de personaje | `heroSkillUnlock`, `skinLock`, `heroSkill`, `currentSkinDatas` | mapas y listas `{Key,Value}` | Habilidades y skins poseídas; selección por índice | `heroUnlock` | Idéntica | Desbloqueo E2; selección desconocida | Medio en selección | Desbloqueo existente; selección no implementada | Desbloquear una habilidad/skin y revisar |
| Niveles y afinidad de mascotas | `petUnlock`, `event2Count.pet_<id>_*` | mapa bool; enteros | Intimidad 100/129/240; máximos 180/240/300 | Mascota desbloqueada | Idéntica; C confirma id 57 | E2 | Medio: acción especial y contador global | Afinidad existente; sin nivel de mascota separado | Subir intimidad y comprobar acción |
| Desbloqueo de máquinas | `roomDecorateDic`, `event2Count.room_unlock_*`, `blueprints` | mapa `[0]`; entero 1; estado | A/C poseen y tienen banderas; B solo máquina de huevos | Posesión + bandera/plano | Idéntica | Probable E2 | Alto: puede requerir estado adicional | Corregido en fase 9.2, experimental | Desbloquear caja fuerte y expendedora |
| Decoraciones del vestíbulo | `roomDecorateDic`, `blueprints.blueprint_room_decorate_*` | mapa; texto/entero | 10 objetos; 4 planos investigables | Plano investigado | Idéntica | E2 | Medio | Escritor de decoraciones | Comprobar aparición y uso |
| Objetos interactivos del vestíbulo | `event2Count.room_unlock_*` | entero | 1 en A/C; ausente B | Instalación poseída | Idéntica | Probable E2 | Alto en estatua/expendedora | Solo pares con evidencia | Probar cada objeto |
| Skins | `skinLock`, `currentSkinDatas` | lista `{Key,Value}`; índice | Skins poseídas por héroe | Personaje desbloqueado | Idéntica | Desbloqueo E2; índice desconocido | Bajo al desbloquear; alto al seleccionar | Desbloqueo existente | Desbloquear y equipar manualmente |
| Planos | `itemData.blueprints` | mapa id → `Got`/`Researched` o 1/2 | A 344 texto; C 198 entero; B 21 entero | Materiales de investigación | Texto y entero soportados | E2 | Bajo | Escritor existente | Investigar un plano y fabricar |
| Mejoras permanentes | `heroLevel`, `roomObjectLevel`, `rebornCard` | mapas y bool | Niveles 0..8 y 0..5 | Personaje/objeto existente | Idéntica | Niveles confirmados; otros E2 | Medio | Niveles y renacimiento existentes | Subir y reiniciar |
| Colecciones | `handbook*CollectionTrackedLevels`, `object2PassLevel`, `passInfo` | mapas | C enemigos con 6; A `"Badass"`; B/C vacío | Versión y progreso | Parcial | Desconocido | Alto: semántica no demostrada | Solo lectura | No modificar todavía |

## Vestíbulo

| Ruta | Tipo | Valores observados | Semántica | Certeza | Escritor |
| --- | --- | --- | --- | --- | --- |
| `itemData.roomDecorateDic` | mapa objeto → `[0]` | A/C: 10 objetos; B: solo `ItemEggMachine` | Posesión del objeto | E2 | Crea `[0]` al desbloquear |
| `statisticData.event2Count.room_unlock_<objeto>` | entero | 1 en A/C; ausente en B | Disponibilidad funcional | E2 probable | Crea/sube a 1 |
| `statisticData.event2Count.room_decorate_fishbowl_level` | entero | 3 en A y C | Nivel del acuario; no bandera | E2, efecto desconocido | Solo lectura |
| `itemData.blueprints.blueprint_room_decorate_<objeto>` | `Got`/`Researched` o 1/2 | A texto; C entero 2 | Plano investigado del decorado | E2 | Crea/eleva a Researched |
| `gameData.roomObjectLevel` | mapa clave → entero | 0..5 | Nivel de mejora | E2 | Sube sin bajar |
| `gameData.unlockRoomDecorate` | lista | vacía en A/B/C | No es indicador | E2 | Solo lectura |
| `gameData.roomLevel` | entero | 1 en A; 0 en B/C | Nivel de sala, no desbloqueo | E2 | Solo lectura |
| `gameData.currentRoomDecorate` | texto o entero | `"Common"` en A; 0 en B/C | Selección de apariencia | Desconocido | Solo lectura |
| `gameData.roomDecorateCurSkinDic` | mapa | `{}` en A/B/C | Skin por objeto | Desconocido | Solo lectura |

Mapa de requisitos observado:

| Objeto | Bandera | Plano |
| --- | --- | --- |
| `ItemEggMachine` | — | — (inicial) |
| `ItemTrashCan` | `room_unlock_trash_can` | — |
| `ObjectBooks` | `room_unlock_book` | — |
| `ObjectPlant` | `room_unlock_plant` | — |
| `ObjectSafe` | `room_unlock_safe` | — |
| `PetFood` | `room_unlock_pet_food` | — |
| `ObjectMagicWell` | `room_unlock_magic_area` | `blueprint_room_decorate_magic_well` |
| `ObjectDrinkSeller` | — conocida | `blueprint_room_decorate_drink_seller` |
| `ObjectFishBowl` | — conocida | `blueprint_room_decorate_fishbowl` |
| `ObjectMysteriouStatue` | — conocida | `blueprint_room_decorate_mysteriou_statue` |

Niveles y banderas asociadas: `Book → room_unlock_book`,
`CatFood → room_unlock_pet_food`, `Chest → room_unlock_cellar`,
`Safe → room_unlock_safe`. `Planet` no tiene bandera identificada.

## Personajes, habilidades y skins

| Ruta | Tipo | Observación | Certeza | Escritor |
| --- | --- | --- | --- | --- |
| `gameData.heroLevel` | mapa código → entero | 0..8 observado; 7 confirmado en juego | E3 para 7, E2 para 8 | Hasta 8, experimental |
| `gameData.heroUnlock` | mapa código → bool | A 37; B/C 42 | E3 de fases previas | Sí |
| `gameData.heroSkill` | mapa código → entero | Índice de habilidad seleccionada | E2 | No |
| `gameData.heroSkillUnlock` | mapa código → lista `{Key,Value}` | Habilidades desbloqueadas | E2 | Sí (desbloqueo) |
| `gameData.skinLock` | mapa código → lista `{Key,Value:1}` | Skins poseídas | E2 | Sí (desbloqueo) |
| `gameData.currentSkinDatas` | mapa código → entero | Índice de skin activa | Desconocido | No |

El mapa entre el índice de `currentSkinDatas` y el catálogo de skins no está
determinado. No se implementa selección de skin.

## Mascotas

| Ruta | Tipo | Observación | Certeza | Escritor |
| --- | --- | --- | --- | --- |
| `gameData.petUnlock` | mapa nombre → bool | A 46; B/C 58 | E3 de fases previas | Sí |
| `statisticData.event2Count.pet_<id>_intimacy` | entero | Máximos empíricos 180/240/300 | E2 | Sí |
| `statisticData.event2Count.pet_<id>_full_intimacy` | entero | 1 al máximo | E2 | Sí |
| `statisticData.event2Count.pet_<id>_action_unlock` | entero | 1 con acción especial | E2 | No |
| `statisticData.event2Count.pet_full_intimacy` | entero | Contador global; fórmula desconocida | E2 | No |

C confirma el id 57 con máximo 240. Los ids 27 y 56 no tienen máximo observado.

## Planos e items

| Ruta | Tipo | Observación | Certeza | Escritor |
| --- | --- | --- | --- | --- |
| `itemData.blueprints` | mapa id → texto/entero | `Got`/`Researched` o 1/2 | E2 | Sí |
| `itemData.itemUnlock` | lista de ids | `plant_pot3..7`, `Motorcycle` en A/C; vacía en B | E2 | No |
| `itemData.forgeWeapons` | lista de 4 | armas o `null`; no es desbloqueo permanente | E2 | No |
| `itemData.jewelryData` | mapa objeto → datos | A: 9 joyas, durabilidad 100 | E2 | No |
| `itemData.plants` | lista de 8 | estados 1, 2, 4; semántica desconocida | E2 | No |

`itemData.itemUnlock` no representa el desbloqueo del vestíbulo. Los objetos del
vestíbulo viven en `roomDecorateDic` y sus banderas.

## Colecciones y progreso auxiliar

| Ruta | Tipo | Observación | Certeza |
| --- | --- | --- | --- |
| `statisticData.handbookCollectionUserPropertiesInitialized` | bool | ausente A; true B/C | E2 |
| `statisticData.handbookEnemyCollectionTrackedLevels` | mapa enemigo → entero | C: valor 6 | E2, semántica desconocida |
| `statisticData.handbookWeaponCollectionTrackedLevels` | mapa | vacío B/C | E2 |
| `statisticData.object2PassLevel` | mapa objeto → texto/entero | A `"Badass"`; C enteros 1 | E2, no implementado |
| `statisticData.passInfo` | mapa clave → texto | A amplio; B/C vacío | E2, solo lectura |
| `statisticData.trainingJourney` | objeto | vacío en B/C | E2, sin escritor |

## Metadatos de plataforma

| Ruta | Observación | Implicación |
| --- | --- | --- |
| `serialzedVersion` | 1 en A/B; ausente en la respuesta CRDE | Sobre de nube, no estructura de juego |
| `platformId` | UUID/`GP` en A/B; en `_crde_misc` en C | No transferir entre cuentas |
| `cloudSaveId` | presente en A/B; ausente en C | Identificador privado de nube |
| `maps` | presente en A/B; ausente en C | Sobre de nube |
| `_crde_misc` | solo en C | Metadato del editor externo; no editar |

## Reglas de integridad

- Conservar todas las claves desconocidas.
- No cambiar el tipo de un valor existente.
- No crear contenedores ausentes (`statisticData.event2Count`,
  `itemData.blueprints`, `roomDecorateDic`) si la cuenta no los tiene.
- No bajar niveles, no degradar `Researched` a `Got`, no bajar banderas.
- Aplicar solo diferencias efectivas y exigir reversión byte a byte.
- No copiar estructuras completas entre cuentas.
- No declarar disponibilidad funcional sin validación en juego.
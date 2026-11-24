# Matriz de dependencias

La matriz separa lo comprobado de lo probable. Una coincidencia de nombres o de
IDs no es una dependencia. Una acción que cambia dos archivos a la vez tampoco
demuestra que el segundo cambio sea consecuencia de la acción.

## Matriz

| Relación | Evidencia | Confianza | Consecuencia para la edición |
| --- | --- | --- | --- |
| `gameData.gems = lastGems + varGems` en la rama de consumo 8.8.0 | E3/E4 en recompensa, mejora y compra; cuerpo estático de `ConsumeGem` | Alta | Un cambio de un solo campo puede revertirse. Ya está protegido. |
| `heroLevel.Knight` cambia con la mejora legítima y se proyecta en XML | E3: 0 → 1 tras pagar 500 gemas; HUD y persistencia | Alta para `Knight` | No generalizar a otros niveles sin prueba. |
| La recuperación aplica una copia anterior y puede no normalizar contadores | E3 en 6.1 y 6.11 | Alta | No se debe suponer que una recuperación repara una inconsistencia. |
| La nube y `game.data` comparten los mapas de personajes, habilidades y skins | E2: mismos nombres y formas | Alta para estructura | La proyección local existe; el orden de escritura no está confirmado. |
| `currentSkinDatas[código]` selecciona una skin del personaje | E2: entradas dispersas y valor entero | Media | H: requiere una skin poseída. No editar sin probar. |
| `heroSkill[código]` selecciona una habilidad | E2: entero por personaje | Media | H: debe corresponder a una entrada desbloqueada. |
| `skinLock[código][i].Value` representa posesión, precio o requisito | E2: valores 0, 1, negativos y positivos | Baja | No convertir por heurística. Solo lectura. |
| `heroUnlock[código]` indica disponibilidad | E2: bool por personaje | Media para “estado”, baja para el origen | No editar hasta distinguir compra, progreso e inicialización. |
| `heroSkillUnlock[código]` contiene tres desbloqueos | E2: 105 entradas, tres claves por personaje | Alta para forma; baja para significado | No editar. |
| `fishChip` es el saldo de fichas y la preferencia es su proyección | E2: entero y preferencia con el mismo valor 0; la preferencia aparece tras recuperar | Baja | H. Sin transacción positiva no se puede afirmar. Solo lectura. |
| Los historiales `fishChipStore*` pertenecen a la tienda de fichas | E2: nombres y configuración; valores vacíos o 0 | Media para pertenencia, baja para semántica | No se normalizan ni se editan. |
| `_buyItemUseFishChipTimes` cuenta compras con fichas | E2: nombre y valor histórico en 8.6.0 | Media para “contador histórico” | No es el saldo. Puede servir para localizar el flujo. |
| `material_fish` y `cumulativeFishCount` son recursos de pesca | E2: mapas y contadores separados | Alta para estructura | No son fichas. No mezclar. |
| `seasonData.chips` son chips de habilidad de temporada | E2: 20 objetos con nombre, nivel y refinamiento | Alta | No son fichas de pesca. |
| `materials`/`seeds`/`tokenTickets` comparten IDs con catálogos | E2/E1: cruces de 8.6.0 y 8.8.0 | Alta para nombres | El catálogo no demuestra posesión. |
| `object2ObtainTime` y `weaponEvolutionData` comparten códigos de arma | E2: códigos presentes en ambos | Media | No se escribe uno para “completar” el otro. |
| `blueprints` puede alimentar la evolución o la tienda | E1/E2: planos de evolución y textos `Researched` en 8.6.0 | Media para existencia, baja para flujo | Mantener valores y huecos. |
| `itemUnlock` y `roomDecorateDic` reflejan compras del vestíbulo | E2: listas y mapas; 8.6.0 incluye objetos de decoración | Media | No se sincronizan a mano. |
| `escapeSeasonData.money` es independiente de `seasonData.coin` | E2: secciones y campos separados | Media | No convertir entre monedas. |
| `settingData.ChillyUid` identifica al jugador | E2 | Alta | Dato privado. Nunca publicar. |

## Cambios simultáneos observados

La comparación estructural de la mejora del Caballero en Android 8.8.0.11
encontró estas rutas en `game.data`:

```text
cumulativeConsumeGems
cumulativeGems
currentSkinDatas.Knight        (añadido)
firstInRoom
generalSeed
heroLevel.Knight
lastGems
skinLock.Joker[1].Value
varGems
```

En `statistic_<perfil>_.data` cambió
`event2Count.tutorial_830_group_3_stage`. También cambió el XML de preferencias
y la metadata de los archivos.

No todas esas rutas son consecuencia de la mejora:

- `heroLevel.Knight`, los cinco campos de gemas y el evento de tutorial forman
  el núcleo compatible con la acción.
- `currentSkinDatas.Knight` y `skinLock.Joker[1].Value` pueden ser
  inicialización, selección de vestíbulo o un cambio de tutorial no aislado.
- `firstInRoom` puede ser estado de sesión.
- `generalSeed` varía entre capturas y **no se atribuye** a la mejora. Es un
  ejemplo de campo que se habría podido confundir con una dependencia.

En la compra del cofre solo cambió el XML de preferencias antes de la
recuperación. En la recuperación posterior se restauró un estado anterior de
`game.data` y de las preferencias. Esto demuestra que no todos los cambios
visibles pasan inmediatamente al archivo JSON.

## Posibles campos derivados o redundantes

| Campo | Relación posible | Estado |
| --- | --- | --- |
| `gems` | Suma de `lastGems + varGems` en la rama conocida | Comprobado en la rama de consumo, no en todas las rutas. |
| `currentSkinDatas` | Selección que también podría deducirse de `skinLock` | H; la selección es un campo propio y no siempre está presente. |
| Preferencias `<perfil>_gems`, `_last_gems`, `_var_gems` | Proyección local de `gameData` | Comprobado para varias transacciones; la sincronización exacta depende de la ruta. |
| `<perfil>_furniture_fish_chips` | Proyección de `fishChip` | H; coincidencia en 0 y aparición tras recuperar. |
| `heroSkill` | Índice seleccionado que debe existir en `heroSkillUnlock` | H. |
| Historiales `*Indexed` | Contador, índice de catálogo o marca de sincronización | Desconocido. No se reconstruyen. |
| `object2ObtainTime` | Estadística derivada de una obtención | La obtención y el inventario pueden guardarse en momentos distintos. |

Un campo derivado no se “arregla” escribiendo solo la copia. Si se desconoce la
dirección de la dependencia, la política es conservar ambos y no escribir.

## Protocolo para una dependencia nueva

1. Elegir una sola acción legítima y un personaje/objeto de prueba.
2. Capturar `files/`, `shared_prefs/` y, si es posible, la descarga de nube.
3. Guardar un control en reposo con la misma build y el mismo perfil.
4. Repetir la acción y capturar antes/después inmediatos.
5. Guardar desde el menú, reiniciar el proceso y recuperar la copia oficial.
6. Comparar por ruta exacta y revisar los cambios simultáneos no atribuibles.
7. Repetir al menos una vez antes de elevar el nivel de evidencia.
8. No publicar valores, IDs de cuenta, capturas ni claves.

El comando `compare` del analizador conserva índices de lista y distingue
ausencia, `null`, `false` y `0`. Es la herramienta prevista para este
protocolo.
# Inventario de archivos y secciones

Este inventario se basa en una copia auténtica de nube 8.8.0, un perfil local
8.8.0 del cliente oficial y nueve archivos 8.6.0. No se deduce una función solo
por el nombre: la columna de evidencia indica qué se observó y qué queda como
hipótesis.

## Agregado de nube 8.8.0

La descarga real tiene 114.778 bytes y 17 entradas superiores. Trece son
secciones con estado de juego, `maps` contiene el mapa de mapas, dos entradas
son identificadores de la copia y `serialzedVersion` es el metadato del sobre. `serialzedVersion` vale `1` en las
muestras modernas y se conserva como comprobación de formato.

| Sección | Tipo | Entradas directas | Proyección local observada |
| --- | --- | ---: | --- |
| `gameData` | objeto | 38 | `files/game.data` |
| `itemData` | objeto | 78 | `files/item_data.data` y `item_data_<perfil>_.data` |
| `seasonData` | objeto | 67 | `season_data.data` y `season_data_<perfil>_.data` |
| `statisticData` | objeto | 160 | `statistic.data` y `statistic_<perfil>_.data` |
| `taskData` | objeto | 10 | `task_<perfil>_.data` |
| `mallReloadData` | objeto | 23 | `mall_reload_data_LOCAL.data` y `mall_reload_data_<perfil>_.data` |
| `battlePassSaveData` | objeto | 3 | `bp_data_<perfil>_.data` |
| `escapeSeasonData` | objeto | 38 | `escape_season_data_<perfil>_.data` |
| `miscData` | objeto | 17 | `misc_data_<perfil>_.data` |
| `monsterRiseData` | objeto | 17 | `monsrise_data_<perfil>_.data` |
| `pvpData` | objeto | 10 | `pvp_data_<perfil>_.data` |
| `settingData` | objeto | 35 | `setting_<perfil>_.data` |
| `weaponEvolutionData` | objeto | 3 | `weapon_evolution_data.data` y `weapon_evolution_data_<perfil>_.data` |
| `maps` | objeto | 1 (`maps`) | Correspondencia no confirmada con `sandbox_maps_<perfil>_.data` |
| `cloudSaveId` | cadena | — | Sin archivo local equivalente confirmado |
| `platformId` | cadena | — | Sin archivo local equivalente confirmado |
| `serialzedVersion` | entero | — | Metadato del sobre |

`cloudSaveId` no se publica. La presencia de un campo en la nube no demuestra
que el cliente lo use: solo prueba que el agregado lo transporta.

### `gameData`

Las 38 claves observadas son:

```text
activeShopGemReceiptMarkers, certificates, checkUnlockWorkShopTime,
cumulativeConsumeGems, cumulativeGems, currentRoomDecorate,
currentSkinDatas, firstInRoom, fishChip, fontSettingValue, gameVersion, gems,
generalSeed, hasTutorial, heroLevel, heroSkill, heroSkillUnlock, heroUnlock,
isWaveMachineUpgraded, lastGems, lastPlayTime, lastPlayTimeWithNetworkTime,
lastTalentAdRefreshDay, normalModePassCertificates, petUnlock,
promotions2RewardVersion, rebornCard, retiredKnightGotAdItemTime, roomLevel,
roomObjectLevel, skinLock, superHeroInHeroRoom, totalGameTime, totalIndex,
tutorialEndTime, unlockRoomDecorate, usedSecretKeys, varGems
```

Formas relevantes:

- `heroUnlock`, `heroLevel`, `heroSkill`, `heroSkillUnlock` y `skinLock` son
  diccionarios con 42 códigos de personaje. `petUnlock` tiene 58 códigos.
- `skinLock[código]` es una lista de objetos `{Key, Value}`; `heroSkillUnlock`
  también usa `{Key, Value}`, con tres claves de habilidad.
- `currentSkinDatas` es un diccionario disperso: solo aparece el personaje que
  tiene una skin seleccionada.
- `roomObjectLevel` contiene cinco claves de mobiliario; `certificates` es una
  lista de objetos con tiempo, héroe, piedra mágica, nivel de pase y armas.
- `fishChip` es un entero. Su interpretación se trata en
  [fichas-de-pesca.md](fichas-de-pesca.md).

### `itemData`

Tiene 78 claves, entre ellas mapas de recursos, listas de objetos y registros
de compras. Las colecciones observadas incluyen `materials`, `seeds`,
`tokenTickets`, `blueprints`, `itemUnlock`, `plants`, `commodities`,
`forgeWeapons`, `roomDecorateDic`, `specialTickets`, `jewelryData` y los
historiales de tienda de fichas y temporada.

`AppVersion` observado es `80800` en la nube; la muestra 8.6.0 declara
`80300`. `fishChipConfigId` y `seasonStoreConfigId` son cadenas que identifican
la configuración de tienda, no saldos. Los historiales de compra son
diccionarios vacíos o con contadores; su semántica no está confirmada.

### `seasonData`

Además de `coin`, `gainedCoinToday` y `cumulativeCoinCount`, contiene 67 claves
de tareas, modificadores y tienda. `chips` y `chipSchemes` pertenecen a la
temporada: en 8.6.0 `chips` tenía 20 entradas con nombre, nivel y refinamiento.
No son las fichas de pesca. Los contadores `extraRewardChipTimesToday`,
`extraRewardChestNoChipTimes` y `extraRewardChestTimes` también son de
recompensas de temporada.

### `statisticData`

Tiene 160 claves. `StatisticsData` contiene subobjetos polimórficos con
`$type`: `BuffGameStatisticData`, `CharacterGameStatisticData`,
`EnemyGameStatisticData`, `HallGameStatisticData`,
`LegacyGameTimesStatisticData`, `LevelGameStatisticData`,
`MallConditionStatisticData`, `MechaGameStatisticData` y
`WeaponGameStatisticData`. Los mapas `object2ObtainTime`, `object2PassTime`,
`object2PassLevel` y `event2Count` son hermanos de `StatisticsData`.

El mapa `object2ObtainTime` de esta copia tiene 1.066 entradas enteras: la
mayoría son códigos de armas, pero también hay enemigos y jefes. No es un mapa
exclusivo de armas. `achieve_record` contiene 154 registros y `recordedEvents`
una lista de cadenas de eventos.

## Archivos locales 8.8.0

El perfil auténtico se extrajo de `files/`. Los tamaños son de la muestra; el
sufijo numérico se sustituye por `<perfil>` y no se publica.

| Archivo observado | Bytes | Sección | Nota |
| --- | ---: | --- | --- |
| `game.data` | 25.461 | `gameData` | JSON XOR, sin cifrado base64 |
| `item_data.data` | 3.552 | `itemData` | Copia sin sufijo |
| `item_data_<perfil>_.data` | 3.564 | `itemData` | Copia por perfil; puede diferir |
| `season_data.data` | 3.352 | `seasonData` | Copia sin sufijo |
| `season_data_<perfil>_.data` | 19.192 | `seasonData` | Copia por perfil, mucho mayor |
| `statistic.data` | 8.960 | `statisticData` | Copia sin sufijo |
| `statistic_<perfil>_.data` | 41.260 | `statisticData` | Copia por perfil |
| `mall_reload_data_LOCAL.data` | 1.528 | `mallReloadData` | Nombre especial `LOCAL` |
| `mall_reload_data_<perfil>_.data` | 768 | `mallReloadData` | Copia por perfil |
| `bp_data_<perfil>_.data` | 120 | `battlePassSaveData` | Sección pequeña |
| `escape_season_data_<perfil>_.data` | 1.504 | `escapeSeasonData` | Estado de escape |
| `misc_data_<perfil>_.data` | 728 | `miscData` | Efectos y retorno |
| `monsrise_data_<perfil>_.data` | 556 | `monsterRiseData` | Progreso del modo |
| `pvp_data_<perfil>_.data` | 608 | `pvpData` | Tareas y selección |
| `setting_<perfil>_.data` | 1.612 | `settingData` | Posiciones y preferencias |
| `task_<perfil>_.data` | 2.360 | `taskData` | Tareas |
| `weapon_evolution_data.data` | 128 | `weaponEvolutionData` | Copia sin sufijo |
| `weapon_evolution_data_<perfil>_.data` | 128 | `weaponEvolutionData` | Copia por perfil |
| `sandbox_config_<perfil>_.data` | 50 | Configuración de sandbox | No aparece en el agregado de nube inspeccionado |
| `sandbox_maps_<perfil>_.data` | 11 | Mapas de sandbox | Posible relación con `maps`, no confirmada |

También se observaron `escape_run_save_<perfil>_.data` y
`battles_<perfil>_.data` en capturas completas. No aparecieron como secciones
del agregado inspeccionado; su relación con la nube queda pendiente.

### Nombres efectivos y variantes

- `files/` contiene datos; `shared_prefs/com.ChillyRoom.DungeonShooter.v2.playerprefs.xml`
  contiene las preferencias Android.
- Los `.data` son texto base64 de un cifrado DES-CBC; `game.data` es JSON
  ofuscado con XOR. El analizador reutiliza el decodificador del proyecto.
- La convivencia de un archivo sin sufijo y otro `<sección>_<perfil>_.data` es
  un hecho observado. La hipótesis de que uno sea la copia base y otro el estado
  activo no está demostrada; hay que elegir por perfil y por contenido.
- Se observaron archivos `.new` en capturas. Se interpretan como una escritura
  preparada o incompleta, **hipótesis**, y el analizador los ignora para no
  mezclar dos generaciones. No se deben borrar ni promover sin entender el
  guardado.
- `mall_reload_data_LOCAL.data` no sigue el patrón de perfil. Su contenido es
  una sección `mallReloadData` válida, pero su prioridad frente a la copia por
  perfil no está confirmada.
- `ace_shell_di.dat` y `profileinstaller_profileWrittenFor_lastUpdateTime.dat`
  no son datos de partida y no se analizan.

## Archivos locales 8.6.0

La muestra histórica contiene nueve `.data` cifrados y no contiene
`game.data`, preferencias ni el agregado de nube.

| Archivo | Bytes | Claves superiores |
| --- | ---: | ---: |
| `bp_data_111_.data` | 71.456 | 3 |
| `item_data_111_.data` | 52.172 | 77 |
| `misc_data_111_.data` | 748 | 17 |
| `monsrise_data_111_.data` | 556 | 18 |
| `pvp_data_111_.data` | 5.944 | 10 |
| `season_data_111_.data` | 69.248 | 70 |
| `statistic_111_.data` | 487.168 | 157 |
| `task_111_.data` | 25.080 | 12 |
| `weapon_evolution_data_111_.data` | 22.872 | 4 |

La comparación de esquemas 8.6.0–8.8.0 está en
[la fase 5.5](../phase5-5/schema-diff-860-880.md). En 8.8.0 no se eliminaron
claves de esas secciones; se añadieron campos. Que no se eliminen no demuestra
que el cliente 8.8.0 acepte un agregado 8.6.0 ni que migre los valores.

## Comportamiento de recuperación observado

En la recuperación de 6.11 el cliente oficial restauró una copia anterior: el
agregado de nube conservaba 1.000 gemas y el estado local se revirtió a esa
base. La comparación de `game.data` mostró `firstInRoom`, `petUnlock.Dog` y un
valor de `skinLock.Knight`. También cambió el XML. No se observó una
reconstrucción completa de todas las secciones: la recuperación aplica la
proyección que corresponde a la copia y conserva otros archivos locales.

En 6.1 la recuperación de una copia con `gems=1001` actualizó el saldo y sus
preferencias, pero no los cuatro contadores acompañantes. Por eso no se debe
suponer que una recuperación normaliza todas las relaciones internas.

## Incógnitas

- Qué archivo gana cuando coexisten copia sin sufijo y copia por perfil.
- Si `maps` es el mismo objeto que `sandbox_maps` o un mapa de otra capa.
- Cuándo se escribe `escape_run_save` y `battles`, y si viajan en la nube.
- Si el servidor recalcula, rechaza o conserva un agregado con un esquema
  incompleto. Las subidas reales observadas conservaron bytes, pero no se probó
  una sección nueva ni una ausente.
- Si `serialzedVersion` distingue versiones de sobre o de modelo.
# Diferencias de esquema 8.6.0 → 8.8.0

**Método.** Las claves 8.6.0 se obtuvieron descifrando los nueve `.data`
privados (AES/DES local del cliente) y leyendo solo los **nombres** de las
claves superiores. Los campos 8.8.0 se obtuvieron de la metadata del APK. No se
publican valores, identidades ni huellas de las partidas.

## 1. Resultado global

| Sección | Claves 8.6.0 | Campos de instancia 8.8.0 | Comunes | Solo 8.6.0 | Solo 8.8.0 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `itemData` | 77 | 116 | 77 | 0 | 39 |
| `statisticData` | 157 | 169 | 157 | 0 | 12 |
| `taskData` | 12 | 14 | 12 | 0 | 2 |
| `seasonData` | 70 | 76 | 70 | 0 | 6 |
| `monsterRiseData` | 18 | 19 | 18 | 0 | 1 |
| `weaponEvolutionData` | 4 | 4 | 4 | 0 | 0 |
| `miscData` | 17 | 17 | 17 | 0 | 0 |
| `pvpData` | 10 | 10 | 10 | 0 | 0 |
| `battlePassSaveData` | 3 | 3 | 3 | 0 | 0 |

**Ninguna clave observada en 8.6.0 desaparece del modelo 8.8.0.** Eso es
compatibilidad hacia adelante a nivel de nombres; no demuestra que el cliente
8.8.0 acepte un archivo 8.6.0 ni que los tipos no hayan cambiado.

## 2. Campos nuevos en 8.8.0

### `itemData` (39)

`BatteryName`, `BpPointName`, `CanNotSaleWeapons`, `CellName`,
`ComboGunSparkCoinName`, `FeatureMoreBagCapacity`, `FeatureMoreSelectSeat`,
`FertilizeName`, `FishName`, `GearName`, `GemName`, `HopperTicket`, `IronName`,
`MagicNames`, `Plantpot_1`…`Plantpot_4`, `PostmanUpgrade`, `RebornCard`,
`SeasonCoinName`, `SeasonTreasureBoxName`, `SeasonTreasureBoxName1`…`3`,
`SeasonTreasureBoxTicketName2`, `SeedNameAliasMap`, `TokenEquipment`,
`TokenHero`, `TryTicketName`, `WeaponBlueprintFragmentUnidentified`,
`WoodName`, `_AllMythicWeaponIds`, `_deletingForgeItems`,
`forgeWeaponMaterialPayments`, `mechInRoomPaymentMaterials`,
`mechInRoomPaymentName`, `mechInRoomProductId`, `trainingJourney`.

Dominan nombres de monedas/objetos y datos de la sala de máquinas; no son
necesariamente campos nuevos de la partida, pueden ser nombres de recursos
serializados en el mismo modelo.

### `statisticData` (12)

`CommonCheckinRecords`, `HandbookCollectionUserPropertiesRecordedEvent`,
`HandbookSkinGoldenCollectionUserPropertiesRecordedEvent`,
`KrppCountedOrderIds`, `KrppVerifiedUsdCents`, `MultiGameHistoryMaxCount`,
`PassHistoryMaxCount`, `PaySignInRecords`, `cy`, `googlePlayClearedMaps`,
`googlePlayEventCounts`, `googlePlayHistoricalAchievementsSynced`.

### `seasonData` (6)

`MaxExtraReplaceHeroSeatCount`, `MaxReplaceHeroSeatCount`,
`troop2MaxAutoStoreLevelUpCount`, `troop2MaxExtraHeroSeatCount`,
`troop2MaxExtraTeamSize`, `troop2MaxInitPresentCount`.

### `taskData` (2)

`_rg_random`, `rewardGem`.

### `monsterRiseData` (1)

`WeeklyExchangeResetDay`.

## 3. Campos ausentes en 8.8.0

Ninguno de los nombres observados en 8.6.0 falta en el typeDef 8.8.0
correspondiente. Esto no prueba que el servidor siga emitiéndolos: un campo
puede seguir declarado y ya no serializarse, o puede haber cambiado de tipo.

## 4. Clasificación

| Afirmación | Nivel |
| --- | --- |
| Las 77/157/70/12/… claves existen en las muestras 8.6.0. | Confirmado por muestra. |
| Los typeDef 8.8.0 declaran esos nombres y los nuevos. | Identificado en código. |
| Los campos `_data`/`*Load` son estáticos y no viajan en el JSON. | Inferido por el patrón singleton; no verificado en una muestra 8.8.0. |
| Los campos de instancia son exactamente las claves JSON. | Inferido; el serializador puede renombrar u omitir. |
| Los tipos de los campos nuevos son los declarados. | Identificado en código; no contrastado con valores. |
| Una partida 8.6.0 se puede reimportar en 8.8.0. | Desconocido; requiere prueba en cliente oficial. |

## 5. Datos reproducibles

- [`schema-diff-860-880.json`](schema-diff-860-880.json): listas completas
  `common`, `only_860`, `only_880`, con typeDef y conteos.
- [`metadata-880-inventory.json`](metadata-880-inventory.json): campos y tipos
  declarados en 8.8.0.
- [`metadata-880-methods.json`](metadata-880-methods.json): métodos de
  `LoginApi`, `NewCloudSaveAgent`, `RGSaveManager`, `ZipHelper` y las secciones.

## 6. Límite

El diff es de **nombres y declaraciones**, no de valores. Sin una muestra real
8.8.0 no se puede saber qué campos se serializan, cuáles son opcionales, cuáles
cambiaron de tipo ni qué correcciones aplica `FixData`.

# Esquema de guardado de Soul Knight 8.8.0

**Fuente:** APK oficial 8.8.0 (`54bb332b…`), `global-metadata.dat` descifrado y
`libil2cpp.so` arm64. **No hay una partida real de 8.8.0**: este documento
describe el modelo declarado en código, no valores observados en una cuenta.

## 1. Descifrado de metadata

El archivo del APK no empieza por la firma IL2CPP `AF 1B B1 FA`; está protegido
por ACE. El esquema que produjo un archivo parseable es:

| Rango | Transformación |
| --- | --- |
| `[8, 0x1000)` | XOR `0x66`. |
| `[0x1000, 0x5000)` | AES-128-CBC, clave ASCII `d96603c0d96603c0`, IV `02030405060708090a0b0c0d0e0f1011`, IV reiniciado cada `0x800`. |
| Desde `0x11000`, cada bloque completo de `0x10000` | XOR `0x66` en los primeros `0x4000`. |
| Cola menor de `0x10000` | XOR `0x66` completa. |
| `[0, 8)` | Se repone `FAB11BAF` y versión `31`. |

La clave/IV se tomaron del esquema ACE documentado públicamente para otro
cliente Unity ([OurNotes](https://metamiku.com/posts/ournotes-reverse/)) y se
**validaron contra este archivo**: el patrón XOR `0x66` coincide, el encabezado
resultante tiene offsets y tamaños coherentes, las 46 649 definiciones de tipo
se leen sin desbordar y el resto de tablas encaja. La validación es la que
sostiene el resultado; la clave no se extrajo de una captura de Soul Knight. El
método reproducible está en
[`tools/metadata_inventory.py`](tools/metadata_inventory.py).

| Artefacto | SHA-256 |
| --- | --- |
| APK | `54bb332be9444596501ec99f745f21adfa55265feea3a15331c735009b517f34` |
| `global-metadata.dat` original | `bc56e0bb9efd9165aa708c4e4c715871d4817f5363e29e425676ccdf7d51ec15` |
| `global-metadata.dat` descifrado | `dbd07b72cee1f2188810841a4dbb2c11bc931cab4840a49e57baddd5463c48c0` |
| `libil2cpp.so` arm64 | `4cef1adecda2ed7c523d683df1412a88d43e0704b2c230f5a962b54c569921b9` |

## 2. Cabecera

| Dato | Valor |
| --- | ---: |
| Versión de metadata | 31 |
| Definiciones de tipo | 46 649 |
| Entradas en la tabla de tipos | 152 692 |
| Definiciones de método | 380 122 |
| Definiciones de campo | 350 248 |

## 3. `CloudSaveGameData`

typeDef 3018. Es la raíz que `ParseJsonToCloudSaveGameData(string)` devuelve.

| Campo | Tipo | Token |
| --- | --- | --- |
| `serialzedVersion` | `int` | `0x04005779` |
| `cloudSaveId` | `string` | `0x0400577a` |
| `platformId` | `string` | `0x0400577b` |
| `gameData` | `AboGameData` | `0x0400577c` |
| `itemData` | `ItemData` | `0x0400577d` |
| `statisticData` | `StatisticData` | `0x0400577e` |
| `settingData` | `SettingData` | `0x0400577f` |
| `taskData` | `RGScript.Data.TaskDatas` | `0x04005780` |
| `maps` | `SandboxMaps` | `0x04005781` |
| `sandboxConfig` | `SandboxConfigData` | `0x04005782` |
| `seasonData` | `SeasonData` | `0x04005783` |
| `mallReloadData` | `RGScript.Data.Mall.MallReloadData` | `0x04005784` |
| `monsterRiseData` | `MonsterRiseData` | `0x04005785` |
| `weaponEvolutionData` | `RGScript.WeaponEvolution.WeaponEvolutionData` | `0x04005786` |
| `miscData` | `RGScript.Data.MiscData` | `0x04005787` |
| `pvpData` | `RGScript.Data.PvpData` | `0x04005788` |
| `battlePassSaveData` | `RGScript.Data.BattlePassSaveData` | `0x04005789` |
| `escapeSeasonData` | `ModeSeason.Escape.Scripts.EscapeSeasonData` | `0x0400578a` |

Son exactamente las 18 claves que el contrato del prototipo ya reconocía. La
diferencia es que ahora están **identificadas en código 8.8.0**, no solo
inferidas de una muestra 8.6.0.

## 4. Modelos de sección

| Sección | typeDef | Campos declarados | Campos de instancia (sin `_data`/`*Load`) |
| --- | ---: | ---: | ---: |
| `gameData` (`AboGameData`) | 3056 | 41 | 41 |
| `itemData` (`ItemData`) | 3070 | 118 | 116 |
| `statisticData` (`StatisticData`) | 3163 | 171 | 169 |
| `seasonData` (`SeasonData`) | 3131 | 78 | 76 |
| `taskData` (`TaskDatas`) | 21783 | 16 | 14 |
| `monsterRiseData` | 3094 | 23 | 21 |
| `settingData` | 3146 | 47 | 45 |
| `miscData` | 21721 | 19 | 17 |
| `pvpData` | 21736 | 12 | 10 |
| `battlePassSaveData` | 21448 | 5 | 3 |
| `weaponEvolutionData` | 16235 | 6 | 4 |
| `escapeSeasonData` | 12862 | 42 | 40 |
| `mallReloadData` | 21925 | 28 | 26 |

La lista completa, con nombre, tipo y token de cada campo, está en
[`metadata-880-inventory.json`](metadata-880-inventory.json). Las firmas de
métodos seleccionadas están en
[`metadata-880-methods.json`](metadata-880-methods.json).

## 5. `AboGameData` (`gameData`)

41 campos. Los más relevantes para el editor:

| Campo | Tipo |
| --- | --- |
| `skinLock` | colección |
| `currentSkinDatas` | colección |
| `heroUnlock` | colección |
| `heroLevel` | colección |
| `heroSkill` | colección |
| `heroSkillUnlock` | colección |
| `petUnlock` | colección |
| `roomObjectLevel` | colección |
| `gems` | `int` |
| `lastGems` | `int` |
| `varGems` | `int` |
| `cumulativeGems` | `int` |
| `rebornCard` | `bool` |
| `hasTutorial` | `int` |
| `firstInRoom` | `int` |
| `roomLevel` | `int` |
| `fishChip` | `int` |
| `gameVersion` | `int` |
| `lastPlayTime` | `int` |
| `totalGameTime` | `int` |
| `generalSeed` | `int` |
| `tutorialEndTime` | `string` |
| `checkUnlockWorkShopTime` | `string` |
| `lastTalentAdRefreshDay` | `int` |

## 6. Clasificación de la evidencia

| Nivel | Qué incluye |
| --- | --- |
| **Confirmado por muestra** | Las claves superiores de los nueve `.data` 8.6.0 (77/157/70/12/…). No hay valores 8.8.0. |
| **Identificado en código** | Los 18 campos de `CloudSaveGameData`, los modelos de sección y sus campos/tokens. |
| **Inferido** | Que los campos `_data`/`*Load` sean estáticos; que los campos de instancia sean exactamente las claves JSON; que `maps`/`sandboxConfig` sean opcionales. |
| **Desconocido** | Valores, campos opcionales, orden de serialización, `serialzedVersion` efectivo y aceptación por el cliente 8.8.0. |

## 7. Lo que no se declara

No se declara compatibilidad 8.8.0. El modelo está identificado, pero sin una
partida real no se puede saber qué campos emite el servidor, cuáles omite, qué
tipos cambian en la práctica ni qué migra `FixData`.

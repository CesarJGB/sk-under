# Guardados locales y comparación con 8.6.0

## Rutas y flujo en el APK 8.8.0

El sistema distribuye el progreso entre preferencias, un objeto general y archivos por subsistema. Los literales de IL2CPP incluyen `/game.data`, `/backup.data`, `/item_data.data`, `/item_data_`, `/statistic.data`, `/task.data` y los prefijos por tipo de la tabla siguiente. También aparecen `_.data`, `.rij` y `.tmp`. En el código nativo, `ItemData.get_Path` y `BattlePassSaveData.get_Path` consultan el estado de inicio de sesión, `Abo.FileUtil.InternalPersistentPath` y `PrefixUID.uid`. Ambos tienen una ruta histórica `_43OldPath` y una variante `RijPath`. El directorio físico final y el prefijo concreto dependen del entorno y la cuenta. El sufijo observado en 8.6.0 debe tratarse como parte del nombre, sin atribuirle una versión.

| Componente en `Assembly-CSharp.dll` | Evidencia y alcance |
| --- | --- |
| `RGSaveManager` (`0x02000fcc`) | `LoadGameData` (`0x0600928a`, VA `0x06276bbc`) consulta la ruta actual y la histórica mediante `Abo.FileUtil`. Contiene llamadas a `ReadFile`, `AboGameData.CreateFromPlayerPref`, `SaveGameData` y `Abo.CryptUtil.DecryptXor`. El flujo corresponde al objeto general. `TrySaveGameDataAndVerify` existe, con cuerpo parcial en esta revisión. |
| `ItemData` (`0x02000bf5`) y los modelos por tipo | `ItemData.Load` (`0x0600736a`) comprueba ambas rutas, intenta cargar datos de cuenta y tiene una rama de inicialización. `ItemData.SaveWithResult` (`0x0600736b`) consulta las dos rutas y llama a `PlayerSaveData.set_has_item_data`. `BattlePassSaveData.Save`, `MiscData.Save`, `PvpData.Save` y `MonsterRiseData.Save` muestran el mismo patrón de rutas y marcadores específicos. |
| `RGScript.Manager.SDK.SaveUtil` (`0x020042b5`) | `SaveStr` pasa por UTF-8 y llama a `SaveData`. El cuerpo de `SaveData` para bytes (`0x0602283b`, VA `0x07ff9460`) llama a `File.WriteAllBytes`, `File.Delete` y `File.Move`. `LoadData` (`0x0602283d`) llama a `File.ReadAllBytes` en más de una rama. Esto evidencia manejo de archivos auxiliares y reemplazo. La atomicidad ante interrupciones queda por comprobar. |
| `PlayerSaveData`, `PlayerPrefsManager` y `AboGameData` | `PlayerSaveData` expone `gems`, gemas acumuladas, nivel de habitación, indicadores de archivos y `last_play_version`. Las llamadas de `get_gems` y `set_gems` llegan a `GetInt` y `SetInt`, que consultan `GetAccountKey`. `AboGameData` contiene gemas, héroes, aspectos, habilidades, mascotas y progreso. En Android, `PlayerPrefsHelper.getAllKeys` enumera claves de preferencias `<paquete>.v2.playerprefs` o `UnityPlayerPrefs`. |
| `RGSaveManager.UpdateVersion`, `MonsterRiseData.ApplyVersionMigration`, `PreLoadSaveUtil` | `UpdateVersion` (`0x0600929c`) lee y actualiza `last_play_version` y llama a rutinas de estadísticas, inventario y tareas. `MonsterRiseData.Load` transfiere el control a `ApplyVersionMigration` (`0x0600741a`), que tiene una rama de escritura. `PreLoadSaveUtil` declara selección por cuenta y versión de precarga. |

## Envoltura, cifrado y serialización

**Comprobado con 8.6.0.** Los nueve archivos contienen Base64 estándar canónico. Al decodificar se obtienen bloques DES-CBC alineados a 8 bytes, con una variante de clave para `statistic`. Al quitar PKCS#7, los bytes son directamente un objeto JSON UTF-8. Se reprodujo cada archivo con el cifrado y Base64 sobre el texto claro exacto. La envoltura observada va completa en ese flujo. Un SHA-256 calculado por el editor comprueba igualdad de copias. La autenticidad de un archivo y su coherencia semántica requieren evidencia adicional. [Análisis de Fase 3](../../phase3/FORMAT_ANALYSIS.md)

**Confirmado en el APK 8.8.0.** `Abo.CryptUtil` declara `EncryptDES` (`0x06010de5`) y `DecryptDES` (`0x06010de6`), además de XOR y Rijndael. Los identificadores de DES prueban su presencia, con cuerpo parcialmente legible. `SaveUtil.SaveDataWithRijndael` (`0x06022839`, VA `0x07ff9058`) llama a `Abo.CryptUtil.EncryptStringToBytesRijndael` y a `SaveData`. `SaveUtil.LoadRijndaelData` (`0x0602283c`, VA `0x07ff9b18`) llama a `LoadData` y `Abo.CryptUtil.DecryptStringFromBytesRijndael`. Las rutas genéricas `LoadCryptData<T>` y `SaveCryptData<T>` declaran un camino normal y otro Rijndael. `OpenRijTest`, `OpenNewtonJsonTest`, sus consultas por cuenta y los métodos de soporte por canal evidencian opciones de selección. La ruta de subida RPC sí muestra llamadas directas a los dos serializadores JSON, `Abo.JsonUtil` y `NewtonJsonUtil`.

**Hipótesis para archivos 8.8.0.** Puede seguir habiendo archivos con la envoltura DES de las muestras junto con variantes Rijndael, según la cuenta, el canal y los datos preexistentes. Queda por verificar qué rama local escribe cada tipo, qué serializador utiliza, cómo decide entre ambos archivos y si cambian los parámetros o la validación de integridad. Una biblioteca de compresión incluida o una ruta remota comprimida no basta para atribuir compresión al códec local.

## Modelos identificados

Todos los nombres de la segunda columna corresponden a tipos de `Assembly-CSharp.dll`. La coincidencia de miembros con JSON de 8.6.0 confirma parentesco estructural. La materialización de esos miembros y sus tipos de JSON en cada variante de 8.8.0 queda pendiente de una captura.

| Familia en las muestras | Modelo 8.8.0 y miembros compartidos | Interpretación comprobada por el editor en 8.6.0 |
| --- | --- | --- |
| `item_data` | `ItemData` (`0x02000bf5`). `AppVersion`, `materials`, `seeds`, `blueprints`, `itemUnlock`, `cumulativeFishCount` | Mapas de materiales, semillas y planos, lista de desbloqueos y contador de pesca |
| `season_data` | `SeasonData` (`0x02000c3b`). `coin`, `gainedCoinToday`, `cumulativeCoinCount`, `gainedCoinInSeason`, `chips` | Moneda de temporada, contadores y lista de chips con niveles |
| `statistic` | `StatisticData` (`0x02000c5a`). `StatisticsData`, `handbookWeaponCollectionTrackedLevels`, `achieve_record`, `passInfo` | Mapas de estadísticas y niveles de armas, pares clave y objeto para logros |
| `weapon_evolution_data` | `RGScript.WeaponEvolution.WeaponEvolutionData` (`0x02003f6c`). `weapons`, `favorWeapons`, `blindBoxOpenCount0` | Mapa de armas evolucionables con nombre, nivel, índice de aspecto y aspectos desbloqueados |
| `monsrise_data` | `MonsterRiseData` (`0x02000c14`). `version`, `maxClearLevel`, `pveGameTimes`, `monsterTeams`, `CollectedMonsters` | Versión del subsistema, progreso PvE, lista de equipos y mapa de colección |
| `task` | `RGScript.Data.TaskDatas` (`0x02005516`) y `TaskSystem.TaskData` (`0x020021bd`). `NewTaskData`, `tasks`, `ActivityTaskData` y campos de ID, estado y progreso | Listas de tareas y contadores de registros |
| `bp_data` | `RGScript.Data.BattlePassSaveData` (`0x020053c9`). `seasonData`, `bpShopOthersPurchaseCounts`, `bpShopOthersRefreshMonthKey` | Lista de registros de pase por temporada, con clave entera y valor objeto |
| `misc_data` | `RGScript.Data.MiscData` (`0x020054da`). `unlockedKillEffectIds`, `equippedKillEffectIdByScene` | IDs numéricos de efectos y pares por escena |
| `pvp_data` | `RGScript.Data.PvpData` (`0x020054e9`). `pvpLobbyOpenCount`, `pvpTaskData`, `pvpSkinSelectionByHero`, `isPvpFirstMatch` | Contador del lobby, mapas y marcador booleano |

Los nombres se refieren a familias y miembros, con exposición de campos según el adaptador de 8.6.0. Un contador de entradas indica registros presentes, incluso si su valor es cero. La moneda de temporada, las gemas de la cuenta y los contadores de compras son conceptos distintos. [Campos admitidos de Fase 3](../../phase3/SUPPORTED_FIELDS.md)

## Diferencias observadas y sus límites

- En el `ItemData` del APK se encontraron `forgeWeaponMaterialPayments` y `trainingJourney`. Ambos estaban ausentes en el JSON de inventario de la muestra. `forgeWeapons` y `activeShopReceiptMarkers` ya estaban presentes en esa muestra. La ausencia puede depender del estado de la cuenta, de valores omitidos por el serializador o de la versión.
- Se confirmaron otros miembros del APK en el JSON 8.6.0, entre ellos `artifacts2TrophyLevel` y `aram2TrophyLevel` en temporada, `zongzi2026ActivityData` en estadísticas y `pvpCharacterSelectionByGameName` en PvP. Su aparición en los metadatos del APK por sí sola habría sido insuficiente para marcar esos campos como nuevos.
- El APK contiene guardados adicionales, con símbolos como `EscapeSeasonData`, `EscapeRunSaveData`, `BackupGameData` y `MallReloadData`. Ninguno tiene su propio archivo en las nueve muestras disponibles. Su primera versión de aparición y su representación en disco quedan abiertas.
- El valor comprobado de `item_data.AppVersion` es `80300`, pese a la atribución de las muestras a 8.6.0. En `monsrise_data`, `version` vale `1`. `last_play_version`, `serialzedVersion` del documento remoto y los números de compilación del APK deben registrarse por separado. El número de versión de cada archivo 8.8.0 sigue sin determinarse.

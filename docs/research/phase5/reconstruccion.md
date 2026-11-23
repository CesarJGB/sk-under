# Reconstrucción de CloudSaveGameData

## Estructura y correspondencia local

`CloudSaveGameData` (`0x02000bcb`) declara los siguientes miembros. Los nombres identifican campos administrados del APK. Los tipos de los modelos no certifican su representación JSON bajo todos los serializadores. Las correspondencias de 8.6.0 se apoyan en el análisis de las nueve familias locales y en las llamadas de captura y restauración de 8.8.0. [Análisis de archivos locales](../phase4/guardados-locales.md)

| Campo del agregado | Modelo o cometido | Comparación local disponible |
| --- | --- | --- |
| `serialzedVersion` | Entero de versión del agregado, con esa grafía. La construcción base escribe `1` en el primer campo a VA `0x099577e8`, dentro de `.ctor` (`0x060072d8`). | Separado de `gameData.gameVersion`, `PlayerSaveData.last_play_version`, `itemData.AppVersion`, `monsterRiseData.version` y las versiones del APK y del bundle. |
| `cloudSaveId`, `platformId` | Campos de texto de identidad de guardado y plataforma. | El agente usa identificadores de cuenta local y plataforma. El sufijo de los nombres locales no es prueba de una equivalencia con estos campos. |
| `gameData` | `AboGameData`, progreso general y preferencias de cuenta como gemas, héroes, habilidades y nivel de habitación. | `PlayerSaveData`, preferencias y ruta general de `RGSaveManager`. Sin muestra de este conjunto en las nueve disponibles. |
| `itemData` | `ItemData`, inventario y desbloqueos. | `item_data`. Coinciden miembros como `materials`, `seeds`, `blueprints` e `itemUnlock`. |
| `statisticData` | `StatisticData`, registros de logros, estadísticas y armas. | `statistic`. Coinciden `StatisticsData`, `achieve_record` y `handbookWeaponCollectionTrackedLevels`. |
| `settingData` | `SettingData`, configuración, layout e identidad local. | Sin muestra propia en el conjunto. |
| `taskData` | `RGScript.Data.TaskDatas`, tareas generales y de actividad. | `task`. Coinciden las familias de tareas y sus registros. |
| `maps`, `sandboxConfig` | Campos del modo sandbox. Las llamadas de creación y aplicación alcanzan `SandboxMaps`. | Sin muestra propia. La representación JSON de ambos campos queda abierta. |
| `seasonData` | `SeasonData`, economía y progreso de temporadas. | `season_data`. Coinciden campos como `coin`, `gainedCoinInSeason` y `chips`. |
| `mallReloadData` | `MallReloadData`, estado adicional de tienda. | Sin muestra propia en el conjunto. |
| `monsterRiseData` | `MonsterRiseData`, equipos, colección y progreso del modo. | `monsrise_data`. Coinciden `version`, `maxClearLevel`, `monsterTeams` y `CollectedMonsters`. |
| `weaponEvolutionData` | `WeaponEvolutionData`, evolución, aspectos y favoritos. | `weapon_evolution_data`. Coinciden `weapons` y `favorWeapons`. |
| `miscData` | `MiscData`, efectos y configuración por escena. | `misc_data`. Coinciden los efectos desbloqueados y seleccionados. |
| `pvpData` | `PvpData`, tareas y selección PvP. | `pvp_data`. Coinciden `pvpTaskData` y `pvpSkinSelectionByHero`. |
| `battlePassSaveData` | `BattlePassSaveData`, temporadas del pase y estado de su tienda. | `bp_data`. Coinciden `seasonData` y los contadores de compras de la tienda del pase. |
| `escapeSeasonData` | `EscapeSeasonData`, datos del modo Escape. | Sin muestra propia. El cliente trata un run activo mediante un componente separado. |

Las muestras locales contienen JSON en archivos por subsistema con la envoltura DES-CBC y Base64 verificada en las fases anteriores. El agregado combina esos modelos con preferencias, identidad y subsistemas adicionales. La relación por miembros permite comparar estructuras. Una conversión exacta en ambos sentidos exige el respaldo y los archivos locales generados por la misma compilación y cuenta. [Formato local](../../phase3/FORMAT_ANALYSIS.md) · [Hallazgos de sincronización](../phase4/sincronizacion.md)

## Captura, aplicación y migración

- `CreateFromPlayerPref` (`0x060072d9`, VA `0x09957820`) llama a `AboGameData.CreateFromPlayerPref`, a los getters de los subsistemas y a `StatisticData.RecordSaveId`. Consulta `GetLocalSaveId`, `GetCurrentAccountSaveId` y `get_pf_id`. Esto vincula la captura con las preferencias y la cuenta vigente.
- `ParseJsonToCloudSaveGameData` en el agente (`0x06021c00`) y el runner (`0x0602235d`) llama a `FixData` (`0x06021bf5`). El cuerpo observado comprueba texto vacío y tiene ramas de error. Los reemplazos de formatos históricos, el tratamiento exacto de campos ausentes y el contrato de cada serializador quedan abiertos.
- `LoadGame` (`0x06021c0b`) construye una comparación con `CloudSaveExtraData`, `GetProgressScope` y `GetPassTimes`. El callback de éxito de descarga también puede invocar `CloudSaveRunner.AutoDnload` (`0x06022350`) bajo condiciones del cliente.
- `CoverPlayerPref` (`0x060072db`, VA `0x09957c84`) llama a `AboGameData.CoverPlayerPref`, guarda inventario y ejecuta `MergePaymentHistoryCacheForSameAccount`. Guarda estadísticas, preferencias y tareas, recarga estas últimas y actualiza el identificador local. También contiene una llamada a `EscapeRunSaveController.ClearRunSave`. Para temporada, tienda, Monster Rise, evolución, efectos, PvP, pase y Escape aparecen ramas `Save` y `NewData`. Es evidencia de inicialización alternativa para esos subsistemas, con sus condiciones exactas pendientes.
- El tipo declara métodos de recuperación de pase (`0x060072df`–`0x060072e5`). `AutoDnloadAsync` (`0x0602236d`) vuelve a consultar sesión y UID y llama a `TryBuildConsumePlan`. `RefreshActiveShopAfterCloudSaveCoverAsync` (`0x06022357`) evidencia actualización de tienda tras aplicar datos.
- Hay migraciones de legado por canal con `MoveCloudSaveManager` y `MigrationClient`. En el almacenamiento local, `RGSaveManager.UpdateVersion` (`0x0600929c`) y `MonsterRiseData.ApplyVersionMigration` (`0x0600741a`) modifican estado por versión. La aplicación del agregado y cada migración local requieren pruebas independientes. [Migraciones y guardados locales](../phase4/guardados-locales.md)

## Contrato provisional del prototipo

`reconstruct_cloud_save(bytes)` devuelve un `ReconstructedCloudSave` con tamaño y SHA-256 de los bytes recibidos, codificación y `CloudSaveGameData` en memoria. Acepta un objeto JSON UTF-8 directo o un único miembro gzip que contiene ese objeto. Requiere `serialzedVersion` entero no negativo, identificadores de texto no vacío y un objeto `gameData`. Los demás miembros se conservan con distinción entre presencia, ausencia y nulo. Las secciones con modelo de objeto se validan como objeto o nulo y se conserva el JSON de `maps` y `sandboxConfig` como dato de forma abierta. También se conservan los miembros desconocidos y los enteros de precisión arbitraria que acepta el lector. Los bytes originales los conserva el llamador para verificación.

`summary()` entrega codificación, versión declarada y estado de cada sección. Omite identificadores, hash y valores de progreso. El lector limita a 8 MiB la entrada, 16 MiB el JSON descomprimido y 64 niveles de anidación. Rechaza claves duplicadas, números no finitos, gzip truncado o con datos sobrantes y tipos incompatibles. Las reglas de campos obligatorios son criterios del prototipo. El formato de transporte, las reglas de autenticidad y la compatibilidad de versiones quedan sujetos a un contrato y a una muestra autorizada. [Módulo](../../../backend/app/cloud_save.py) · [Fixture sintético](../../../backend/tests/fixtures/cloud-save-sintetico.json) · [Pruebas](../../../backend/tests/test_cloud_save.py)

# Campos reconocidos y permisos

Todos los campos reales son de solo lectura. Los contadores se muestran como enteros, o como texto decimal cuando exceden la precisión exacta de JavaScript. Para listas y mapas, la vista muestra cuántas entradas están presentes. Una entrada registrada por el juego puede representar un valor cero o un estado incompleto.

| Tipo | Campos visibles | Estructura adicional verificada |
| --- | --- | --- |
| `bp_data` | Número de entradas en `seasonData` | Registros con `Key` entero y `Value` objeto |
| `item_data` | `AppVersion`, `cumulativeFishCount` y número de entradas de `materials`, `seeds`, `blueprints` e `itemUnlock` | Materiales y semillas con valores enteros. Planos con valores de texto. Desbloqueos como lista de textos |
| `misc_data` | Número de entradas de `unlockedKillEffectIds` | Enteros para los IDs de efectos y pares de enteros para efectos equipados por escena |
| `monsrise_data` | `version`, `maxClearLevel`, `pveGameTimes` y número de entradas de `CollectedMonsters` | `monsterTeams` como lista |
| `pvp_data` | `pvpLobbyOpenCount` | Objetos para `pvpTaskData` y selección de aspectos. Indicador booleano `isPvpFirstMatch` |
| `season_data` | `coin`, `gainedCoinToday`, `cumulativeCoinCount` y número de entradas de `chips` | Mapa de enteros `gainedCoinInSeason`. Registros de chip con `chipName`, `level` y `refineLevel` |
| `statistic` | Número de entradas de `StatisticsData`, `handbookWeaponCollectionTrackedLevels` y `achieve_record` | Grupos de estadísticas como objetos. Niveles de seguimiento de armas como enteros. Logros como pares clave/objeto |
| `task` | Número de entradas de `NewTaskData` y `tasks` | Registros con ID, estado, progreso actual y objetivo |
| `weapon_evolution_data` | Número de entradas de `weapons` y `favorWeapons` | Registros con nombre, nivel, índice de aspecto y lista de aspectos |

El contrato devuelve únicamente la proyección de esta tabla y metadatos de inspección. Los campos desconocidos y las estructuras auxiliares permanecen dentro de la copia intacta. `.skdemo` conserva los campos editables de la Fase 2.

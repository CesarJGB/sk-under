# Mapa de archivos y rutas

El análisis utiliza los archivos originales de laboratorio. Las filas con colecciones vacías comprueban el contenedor. La [comparación histórica de esquemas](../research/phase5-6/schema-compatibility.md) conserva el inventario completo.

| Concepto | Archivo local | Ruta de nube | Evidencia propia |
| --- | --- | --- | --- |
| Saldo y contadores de gemas | `files/game.data` y [PlayerPrefs](playerprefs-research.md) | `gameData.{gems,lastGems,varGems,cumulativeGems,cumulativeConsumeGems}` | Los cinco campos se observan en 8.8.0. Las preferencias se escriben antes del archivo en el tutorial y transacciones del hotfix. |
| Progreso de personajes, mascotas, skins y habilidades | `files/game.data` y PlayerPrefs | `gameData.{heroUnlock,heroLevel,petUnlock,skinLock,currentSkinDatas,heroSkill,heroSkillUnlock}` | `heroUnlock` y `petUnlock` son diccionarios de bool por código. `heroLevel` y `currentSkinDatas` son diccionarios de enteros. Se observaron 42 héroes y 58 mascotas en 8.8.0. |
| Estadísticas | `statistic.data` y `statistic_<perfil>_.data` | `statisticData.{object2ObtainTime,object2PassTime,object2PassLevel,event2Count}` | Los cuatro mapas son hermanos de `StatisticsData`. La grafía camelCase difiere de Discord. La muestra de 8.6.0 tiene mapas poblados y el agregado 8.8.0 conserva la grafía. |
| Inventario | `item_data.data` y `item_data_<perfil>_.data` | `itemData.{materials,seeds,tokenTickets,blueprints,itemUnlock,cumulativeFishCount}` | Los cuatro primeros son mapas. `itemUnlock` es lista en ambas versiones y `cumulativeFishCount` es entero. En 8.6.0 se observaron planos con valores de texto. |
| Evolución y skins de armas | `weapon_evolution_data*.data` | `weaponEvolutionData.{weapons,favorWeapons,blindBoxOpenCount0,lastOpenMachineHistoryStr0}` | En 8.6.0, 167 filas con los elementos indicados en el registro. 8.8.0 local tiene `weapons` y `favorWeapons` vacíos y `lastOpenMachineHistoryStr0` nulo. El último campo se omitió en los agregados inspeccionados. |
| Moneda de temporada | `season_data*.data` | `seasonData.{coin,gainedCoinToday,cumulativeCoinCount}` | Los tres son enteros en los archivos locales de 8.6.0 y 8.8.0, y en el agregado 8.8.0. |
| Pase de batalla | `bp_data_<perfil>_.data` | `battlePassSaveData.seasonData` | Local 8.6.0 contiene una lista `[{Key,Value}]`. Local 8.8.0 tiene un objeto vacío, mientras nube 8.8.0 tiene una lista vacía. El contenido de `Value` está tipado en el registro con la evidencia de 8.6.0. |

## Cruces con catálogos

Los cuatro mapas de inventario poblados de 8.6.0 contienen 139 claves de material, 47 de semillas, 213 de cupones y 275 de planos. El CSV 8.8.0 reconoce 133/139 materiales, 47/47 semillas, 13/213 cupones y 228/275 planos por igualdad de ID. Las dos claves de materiales del agregado 8.8.0 también coinciden. Los 167 códigos de evolución de la copia 8.6.0 están en `weapon_full.json` 8.8.0 y sus 177 IDs de skins están en el catálogo traducido. Estos cruces justifican nombres para inspección siempre que se conserve el ID crudo, incluso cuando falte una traducción. [SKDFE fijado](https://github.com/aznoobnam/skdfe/tree/57b9b86335c080caca55e178c8409cb67658ccf6)

La grafía de los `itemUnlock` disponibles, incluyendo `Motorcycle`, y los sufijos, ceros a la izquierda y mayúsculas de los demás IDs son significativos para la comparación. Un `null`, un mapa vacío, una lista vacía o un campo ausente permanecen diferenciados. La presencia de un archivo sin sufijo y uno por perfil precisa comprobar qué perfil usa la sesión antes de interpretar valores.

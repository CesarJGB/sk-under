# Inventario y otros recursos

## Representaciones observadas

| Grupo | Ruta principal | Forma | Observación |
| --- | --- | --- | --- |
| Materiales | `itemData.materials` | objeto ID → entero | Cantidades. En 8.6.0 hay 139 claves; en la nube 8.8.0 solo dos. |
| Semillas | `itemData.seeds` | objeto ID → entero | 47 claves en 8.6.0; vacío en la nube 8.8.0. |
| Cupones | `itemData.tokenTickets` | objeto ID → entero | 213 claves en 8.6.0; vacío en 8.8.0. |
| Planos | `itemData.blueprints` | objeto ID → texto | 275 claves con `Researched` en 8.6.0; vacío en 8.8.0. |
| Desbloqueos de objeto | `itemData.itemUnlock` | lista de cadenas | Lista, no mapa. Conserva mayúsculas y sufijos. |
| Plantas | `itemData.plants` | lista de objetos o `null` | Objetos `{fertilized, plantName, state, watered}`. |
| Fertilizante | `itemData.materials.material_fertilize` | entero | Es un material; no es una ficha. |
| Fragmentos | `itemData.materials.material_*_fragment*` | entero | Familia de materiales; el ID concreto se conserva. |
| Pescado | `itemData.materials.material_fish` | entero | Material de pesca. No es el saldo de fichas. |
| Peces acumulados | `itemData.cumulativeFishCount` | entero | Contador histórico de capturas. |
| Forja | `itemData.forgeWeapons` | lista de nombres o `null` | Lista de armas forjadas; no es un mapa de cantidades. |
| Pagos de forja | `itemData.forgeWeaponMaterialPayments` | lista | Campo nuevo de 8.8.0; semántica parcial. |
| Mercancía | `itemData.commodities` | lista de objetos | `{count, name, showBetterTable}`. |
| Decoración | `itemData.roomDecorateDic` | objeto → lista de enteros | Niveles o estados por objeto; `ItemEggMachine` observado. |
| Skin de decoración | `itemData.roomDecorateCurSkinDic` | objeto | Selección de apariencia de objetos. |
| Máquina de huevos | `itemData.eggMachineTimes`, `eggMachineUseTimes` | entero | Contadores de uso; no son moneda. |
| Entrenamiento | `itemData.trainingJourney` | objeto `{period, revision}` | Campo nuevo de 8.8.0. |
| Joyería | `itemData.jewelryData`, `jewelryBlueprints` | objeto / lista | Datos y planos de joyas. |
| Tickets especiales | `itemData.specialTickets` | objeto | Vacío en la muestra de nube. |
| Mascotas | `gameData.petUnlock` | objeto código → bool | 58 códigos en 8.8.0. |
| Mascotas temporales | `itemData.easterEggTempPets` | lista | No equivale a desbloqueo permanente. |
| Moneda de temporada | `seasonData.coin` | entero | Saldo de temporada. |
| Ganancia de temporada | `seasonData.gainedCoinToday`, `gainedCoinThisWeek` | entero | Contadores de ganancia. |
| Acumulado de temporada | `seasonData.cumulativeCoinCount` | entero | Total acumulado. |
| Chips de temporada | `seasonData.chips` | lista de objetos | `{chipName, level, refineLevel}`; no son fichas de pesca. |
| Esquemas de chips | `seasonData.chipSchemes` | objeto con `schemes` | Configuración de temporada. |
| Tienda de temporada | `itemData.seasonStore*` | cadenas, objetos y contadores | Historiales y configuración; no son saldos. |
| Armas evolucionadas | `weaponEvolutionData.weapons` | objeto ID → objeto | `CurrentSkinIndex`, `Level`, `Name`, `UnlockedSkins`. |
| Favoritas | `weaponEvolutionData.favorWeapons` | lista | Vacía en las muestras 8.8.0. |
| Cajas ciegas | `weaponEvolutionData.blindBoxOpenCount0` | entero | Contador de aperturas. |
| Estadísticas de objetos | `statisticData.object2ObtainTime`, `object2PassTime`, `object2PassLevel` | objeto ID → entero | Obtención, superación y nivel. |
| Estadísticas de eventos | `statisticData.event2Count` | objeto ID → entero | Contadores de eventos. |
| Logros | `statisticData.achieve_record` | lista de `{Key, Value}` | `Value` contiene `got_award`, `has_show`, `id`, `unlock`. |
| Correos y actividades | `statisticData.alreadyGetEmails`, `recordedEvents` | listas | Estado de recompensas y eventos. |
| Escape | `escapeSeasonData` | objeto | Moneda `money`, slots, héroes y planos propios del modo. |
| Monster Rise | `monsterRiseData` | objeto | Emblemas, monstruos, equipos y niveles del modo. |
| PvP | `pvpData` | objeto | Tareas, selección y modo. |
| Tareas | `taskData` | objeto | Tareas activas, progreso y recompensas. |

## Cruce con catálogos

La muestra 8.6.0 permite comprobar la forma de los mapas poblados. El catálogo
8.8.0 reconoce 133/139 materiales, 47/47 semillas, 13/213 cupones y 228/275
planos por igualdad de ID. Los 167 códigos de evolución de 8.6.0 están en
`weapon_full.json` y sus 177 IDs de skins aparecen en el catálogo traducido.
Estos cruces son de nombres e IDs, no de propiedad.

El catálogo de personajes añade 42 códigos, 105 habilidades y 802 skins. El
catálogo externo `item.json` contiene 331 materiales, 265 planos, 47 plantas y
19 tokens; `needed_data.json` contiene 130 nombres de material. Las diferencias
de conteo indican que ninguna lista es exhaustiva para todas las versiones.

## Reglas de conservación

1. Un ID desconocido se conserva literal. No se inventa una traducción.
2. Un campo ausente, `null`, una lista vacía, `false` y `0` son estados
   distintos. El comparador los mantiene separados.
3. Los mapas de cantidades no se reconstruyen a partir de catálogos. El catálogo
   dice qué podría existir; el guardado dice qué existe.
4. Los planos con valores de texto no se convierten a enteros sin una prueba.
   En 8.6.0 el valor observado es `Researched`; la hipótesis de estados
   numéricos de la referencia comunitaria no se aplica a esa muestra.
5. Los historiales de tienda, recibos, entitlements y paquetes premium se
   mantienen de solo lectura.
6. Las listas de objetos (`plants`, `commodities`, `forgeWeapons`) pueden
   contener `null`; no se eliminan esos huecos al normalizar.
7. `object2ObtainTime` no es exclusivo de armas: en la copia de nube incluye
   enemigos y jefes. La misma clave puede tener un espacio de IDs compartido.

## Incógnitas

- Qué significa exactamente cada valor de `blueprints` en 8.8.0 cuando está
  poblado; las muestras modernas están vacías.
- Cómo se relacionan `plants[].state`, `watered` y `fertilized` con el inventario
  de semillas y fertilizante.
- Si `itemUnlock` y `roomDecorateDic` son fuentes independientes o
  proyecciones de una misma compra.
- Si los historiales de tienda (`*PurchaseHistoryIndexed`) son contadores,
  índices de catálogo o marcas de sincronización.
- Si las estadísticas de obtención se escriben en la misma transacción que el
  inventario o en un guardado posterior.
- Si `escapeSeasonData.money` y `seasonData.coin` son monedas independientes.
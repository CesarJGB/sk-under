# Fichas de pesca

## Conclusión

`gameData.fishChip` es el único campo observado que se comporta como un saldo
de fichas de pesca: es un entero, está en el estado de juego y tiene una
proyección local en preferencias (`<perfil>_furniture_fish_chips`). No se
observó ningún valor positivo ni una adquisición o un gasto legítimo, por lo
que su significado es **E2 con hipótesis H** y su autoridad local/remota sigue
siendo desconocida. No se debe habilitar edición ni asumir que el servidor lo
aceptará.

Los demás nombres relacionados no son el saldo:

- `itemData.materials.material_fish` es un material de pesca.
- `itemData.cumulativeFishCount` es el contador acumulado de la tienda de fichas (Fase 6.20); no es el saldo actual.
- `seasonData.chips` son chips de habilidad de temporada.
- `gameData.petUnlock.FishChipKing` es una mascota, no una moneda.
- `mallReloadData.buyFishCount*` cuenta compras de peces, no fichas.
- `fishChipConfigId` identifica una configuración de tienda.

## Campos observados

| Ruta | Archivo | Tipo observado | Evidencia | Interpretación |
| --- | --- | --- | --- | --- |
| `fishChip` | `gameData` / `files/game.data` | entero | E2; 0 en todas las muestras propias | Saldo candidato. H: moneda de la tienda de peces. |
| `<perfil>_furniture_fish_chips` | `shared_prefs/...playerprefs.xml` | entero XML | E2; aparece tras una recuperación, valor 0 | H: proyección local del saldo candidato. La igualdad observada no demuestra la relación. |
| `fishChipConfigId` | `itemData` | cadena | E2; cambia entre 8.6.0 y 8.8.0 | Identificador de configuración de tienda. |
| `fishChipStorePurchaseHistory` | `itemData` | objeto | E2; vacío en 8.8.0 | H: historial de compras de la tienda. |
| `fishChipStorePurchaseHistoryIndexed` | `itemData` | objeto ID → entero | E2; en 8.6.0 dos claves de bundle con 0 | H: contador por producto o índice. |
| `fishChipStoreAllPurchaseHistoryIndexed` | `itemData` | objeto | E2; vacío | H: historial acumulado por producto. |
| `lastFishChipStoreAllPurchaseHistoryIndexed` | `itemData` | objeto | E2; vacío | H: marca de la última sincronización. |
| `buyFishCount5/10/20/45/68/128` | `mallReloadData` | entero | E2; todos 0 | Contadores de paquetes de peces; no se vinculan al saldo. |
| `extraRewardChipTimesToday` | `seasonData` | entero | E2; 0 | Contador de recompensa de temporada. |
| `extraRewardChestNoChipTimes` | `seasonData` | entero | E2; 0 | Contador de cofre sin chip de temporada. |
| `extraRewardChestTimes` | `seasonData` | entero | E2; 0 | Contador de cofres de temporada. |
| `StatisticsData.HallGameStatisticData._buyItemUseFishChipTimes` | `statisticData` | objeto escena → entero | E2; `{"Any": 999}` en 8.6.0 | Contador histórico de compras con fichas. No es el saldo. |
| `cumulativeFishCount` | `itemData` | entero | E2; 7.218 en 8.6.0 y 0 en 8.8.0 | Progreso acumulado de la tienda de fichas (corregido en 6.20); no es el saldo. |
| `magicWellFishedTimes` | `itemData` | entero | E2; 0 | Contador de pesca en el pozo mágico. |
| `chips` / `chipSchemes` | `seasonData` | lista / objeto | E2; 20 chips con nombre y nivel en 8.6.0 | Habilidad de temporada; no es una moneda. |

El valor `_buyItemUseFishChipTimes={"Any":999}` de la muestra 8.6.0 demuestra
que el cliente registra usos de fichas en estadísticas, pero no dice de dónde
salen ni cuál es el saldo. Es una pista fuerte para localizar la acción
legítima en 6.13, no una prueba de persistencia.

## Estructura de la tienda

`FishChipStoreConfig.json` aparece en el cliente oficial bajo
`files/VersionConfigs/BaseConfig/GP/GP_Branch/`. El archivo observado tiene un
envoltorio `{"configs": [ ... ]}` con cadenas cifradas; es configuración, no
una partida. `fishChipConfigId` cambia con la versión de configuración y no
debe tratarse como un saldo.

Los historiales observados no permiten asignar una semántica estable a sus
claves. En 8.6.0 hay dos claves con valor 0; en 8.8.0 todos los mapas están
vacíos. Se conservan como opacos: no se normalizan, no se borran y no se
rellenan con valores inventados.

## Lo que el cliente estático sugiere

La metadata 8.8.0 identifica `AboGameData.fishChip` como un `int` y
`ItemData` con métodos `get_fishCount`, `GetFishCount`, `AddFishCount`,
`ConsumeFishCount` y `OldFishChipConvert`. Son indicios E1 de una economía
propia con lectura, suma, consumo y conversión de un formato anterior. No
prueban:

- que el saldo mostrado sea `fishChip`;
- que el servidor sea la autoridad;
- que una recuperación lo proyecte igual que las gemas;
- que una escritura de un solo campo sea aceptada.

La ruta de gemas no se reutiliza para fichas. `RGSaveManager` tiene métodos de
gemas, pero no se localizó un método equivalente de fichas en esa clase. Por
eso no se copia la conciliación `gems = lastGems + varGems`.

## Comportamiento de recuperación

En las capturas Android de 6.11, `fishChip` permaneció en 0 antes y después de
la recuperación. La preferencia `<perfil>_furniture_fish_chips` no estaba en
las capturas previas y apareció con 0 después de la recuperación. Es un indicio
de que la recuperación o la inicialización del perfil crea la proyección local,
pero el saldo era cero y no hubo una transacción que permitiera distinguir
proyección, valor por defecto o creación perezosa.

No se observó que la recuperación de gemas modificara los historiales de la
tienda de fichas. Tampoco se observó una descarga de nube con un saldo positivo.
No se puede afirmar qué sobrevive a un reinicio con fichas reales.

## Cómo demostrarlo en 6.13

1. Usar una cuenta de prueba autorizada y el cliente oficial, sin comprar
   moneda premium ni simular recibos.
2. Localizar una obtención legítima de fichas (recompensa, conversión o
   actividad) y una compra que las consuma.
3. Capturar antes, después de obtener, después de gastar, tras guardar, tras
   reiniciar el proceso y tras recuperar la copia oficial.
4. Comparar `gameData.fishChip`, la preferencia, los historiales y el contador
   estadístico. Registrar también el HUD y el precio mostrado.
5. Repetir con una copia en reposo para separar cambios de inicialización.
6. Solo elevar a E3/E4 si el delta es único, se repite y sobrevive a la
   recuperación. Si no se consigue una acción legítima, dejar el campo como E2.

## Política

- Lectura: permitida y documentada.
- Edición: **no implementada**.
- Compras, recibos y estados de entitlement: solo lectura.
- Valores privados: nunca en documentos, pruebas ni registros del repositorio.
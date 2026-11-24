# Fase 6.11 — Consistencia del saldo de gemas

La ruta local de consumo del APK Android Global 8.8.0 explica por qué un saldo que aparece tras recuperar de la nube puede revertirse al comprar. La recuperación puede aplicar `gameData.gems` al saldo mostrado y conservar los otros valores de la copia. Al gastar, el cliente compara el saldo de sus preferencias con el saldo anterior más la variación y restablece el saldo si difiere. El ensayo en el dispositivo del reporte y la validación con el hotfix activo siguen pendientes.

## Evidencia del cliente 8.8.0

Se reutilizó el mapa de métodos IL2CPP de la [fase 4](../phase4/guardados-locales.md) sobre el mismo APK ARM64. En el cuerpo local de `RGSaveManager.ConsumeGem` (token `0x0600927f`, VA `0x0627de58`), los accesos a `PlayerSaveData.get_gems`, `get_last_gems` y `get_var_gems` preceden a la suma y comparación (desplazamientos `+0x12c` a `+0x170`). Si difieren, la rama de `+0x174` a `+0x1e8` vuelve a leer los dos componentes, asigna su suma con `set_gems` y vuelve a leer el saldo antes de calcular el cargo. En la rama de consumo comprobada se resta el coste, se registra la variación negativa y el saldo previo, y se suma el coste al acumulado de consumo (`+0x1f0` a `+0x280`).

Las llamadas directas del APK enlazan esta función con `ItemSellPlaceGem.ItemTrigger` (`+0x1e0`), `RGSaveManager.HeroLevelUp` (`+0x128`) y `MallItem.PayWithOtherCurrency` (`+0x374`). La ruta de recogida `ItemGem.GetItem` llama a `AddGem` (`+0xbc`). Esa llamada por sí sola no permite atribuir la misma comprobación a todas las recompensas. `ConsumeGem` también tiene una ruta alternativa de código que el mapa estático no resuelve. El APK muestra un mecanismo local suficiente para explicar la reversión observada, con la rama efectiva del dispositivo y la autoridad remota todavía sin comprobar.

## Capas y función de los campos

Los cinco campos son enteros de 32 bits en el modelo Android 8.8.0. En el agregado sus rutas empiezan por `gameData.`, en `files/game.data` están en la raíz del JSON decodificado y en `shared_prefs/com.ChillyRoom.DungeonShooter.v2.playerprefs.xml` aparecen como entradas XML `int` de la cuenta. Se omitió el prefijo de cuenta en esta tabla.

| Campo en JSON | Clave de preferencias | Función y evidencia |
| --- | --- | --- |
| `gems` | `gems` | Saldo mostrado y saldo que usa la rama local de consumo después de conciliarlo. Se observó el valor 1.001 en HUD, archivo y preferencias tras la recuperación de 6.1. |
| `lastGems` | `last_gems` | Base previa usada en el cálculo local. La rama de consumo escribe el saldo inmediatamente anterior al cargo. En las capturas de tutorial y recuperación valía 0. |
| `varGems` | `var_gems` | Variación aplicada a esa base. El tutorial dejó 1.000 en preferencias y la rama local de consumo registra el coste con signo negativo. |
| `cumulativeGems` | `cumulative_gems` | Contador asociado a la ganancia. Acompañó la recompensa de tutorial en preferencias y permaneció en 1.000 al recuperar el saldo editado de 1.001. La actualización por cada clase de recompensa queda pendiente. |
| `cumulativeConsumeGems` | `cumulative_consume_gems` | En la rama de consumo comprobada se incrementa por el coste. La recuperación legítima incorporó la clave de preferencias con valor 0. |

`mallReloadData` de los agregados de 6.1 contiene contadores `buyGemCount*` y `hasConvertGemPackages`. Ninguno cambió en el ciclo observado de 1.000 a 1.001. No se vincularon al saldo local. `files/backup.data` se describe en referencias externas y en el inventario de literales del APK. Estaba ausente en las capturas de recuperación comparadas. Queda por comprobar cuándo se escribe y si interviene en otros casos.

## Comparaciones sobre capturas reales

Cada tupla contiene `(gems, lastGems, varGems, cumulativeGems, cumulativeConsumeGems)`. Un guion indica ausencia. Se volvieron a leer los archivos originales de laboratorio sin modificarlos.

| Estado | `game.data` | Preferencias | Agregado |
| --- | --- | --- | --- |
| 5.8 tras el tutorial y antes de recuperar | (0, 0, 0, 0, 0) | (1000, 0, 1000, 1000, —) | — |
| 5.8 tras recuperación oficial | (1000, 0, 1000, 1000, 0) | (1000, 0, 1000, 1000, 0) | (1000, 0, 1000, 1000, 0), muestra en memoria tras recuperar |
| 5.9 tras reabrir el cliente | (1000, 0, 1000, 1000, 0) | (1000, 0, 1000, 1000, 0) | — |
| 6.1 antes de recuperar 1.001 | (1000, 0, 1000, 1000, 0) | (1000, 0, 1000, 1000, 0) | (1001, 0, 1000, 1000, 0), descarga posterior a la subida |
| 6.1 tras recuperar 1.001 | (1001, 0, 1000, 1000, 0) | (1001, 0, 1000, 1000, 0) | Mismo agregado que en la fila anterior |

Durante el tutorial el HUD marcó 1.000 y coincidió con las preferencias, mientras `game.data` seguía en cero. Tras la recuperación legítima de 5.8, `game.data` incorporó el saldo, la variación y el acumulado. La recuperación de 6.1 actualizó solo `gems` entre los cinco campos, en el JSON local y en las preferencias. El diferencial recursivo de `game.data` de ese par devuelve una sola ruta modificada. Los demás cambios en el tar abarcan archivos auxiliares, cachés o marcas y no se atribuyeron a operaciones con gemas. La muestra anterior a la compra contiene exactamente la discrepancia que concilia la rama local del APK. El saldo incoherente alcanzó las preferencias, por lo que un fallo limitado a la serialización o al HUD no explica esa captura.

Se decodificaron también los nueve `.data` privados atribuidos a Android 8.6.0. En esos árboles no aparecieron las cinco claves, incluyendo sus variantes de mayúsculas y guiones bajos. El inventario de esas muestras carece de `game.data` y de preferencias. Los resultados no permiten trasladar la regla a 8.6.0. `serialzedVersion: 1` indica la versión del agregado y se conserva como comprobación de formato independiente de la versión del juego.

El inventario conserva como referencias `itemData.cumulativeFishCount`, `seasonData.coin` y sus contadores, `battlePassSaveData.seasonData`, `gameData.heroUnlock` y `gameData.currentSkinDatas`. La evidencia se limita a ubicación y estructura para esos recursos. [Modelos locales](../phase4/guardados-locales.md) · [Comparación de esquemas 8.6.0–8.8.0](../phase5-6/schema-compatibility.md)

Las capturas anteriores se detallan en [tutorial y copia local](../phase5-8/local-files.md), [recuperación oficial](../phase5-8/cloud-roundtrip.md), [reinicio y recuperación de 5.9](../phase5-9/roundtrip.md) y [validación de 6.1](../phase6-1/client-validation.md).

## Referencias históricas contrastadas

- El hilo de 4PDA documenta la reversión al comprar el 11 de noviembre de 2021. La respuesta siguiente vincula `gems` y `lastgems`. La coincidencia es histórica y el hilo no establece la relación de tres campos del APK actual. Se consultó la versión indexada porque la apertura directa devolvió HTTP 403. [Mensajes #2599–2600 de 4PDA](https://4pda.to/forum/index.php?showtopic=798561&st=2580)
- El artículo de iOS de 2025 ubica `gems` y `last_gems` en preferencias de aplicación mediante un plist con prefijos de cuenta. En los archivos Android 8.8.0 se comprobaron esas grafías en XML y las variantes camelCase en el JSON. La semántica se obtuvo del APK y las capturas de Android. [Charoneo](https://sdythmh.github.io/2025/02/24/%E5%85%83%E6%B0%94%E9%AA%91%E5%A3%ABios%E7%89%88%E4%BF%AE%E6%94%B9%E5%AD%98%E6%A1%A3%E6%95%99%E7%A8%8B/)
- El inventario Suto-Commune y el análisis de MlgmXyysd enumeran archivos locales separados de las preferencias. 8.8.0 confirma esa división, con nombres concretos que pueden variar, como `statistics.data` en el inventario externo y la familia `statistic` en las capturas de SK-Under. [Suto-Commune](https://github.com/Suto-Commune/soul_knight) · [MlgmXyysd](https://www.neko.ink/2023/10/10/soul-knight-data-edit/)

## Protección del flujo de escritura

`resource_consistency.py` reúne las rutas, el rango conservador de saldo, la versión del agregado observada y la comprobación de discrepancias. La ruta común de edición del backend la ejecuta al preparar y al confirmar, antes de crear un respaldo para un cambio incompatible y antes de cualquier intento de escritura. La confirmación vuelve a evaluar borradores antiguos. Las operaciones sin cambios conservan bytes exactos y no son publicables. La lectura, verificación y restauración de un original respaldado conservan sus comprobaciones anteriores. Una versión desconocida, un tipo incompatible, un cálculo ambiguo y un saldo incongruente se rechazan.

Con la edición actual de un único campo, cualquier cambio de saldo sobre un original coherente rompe la relación. Por eso este cambio **bloquea las nuevas escrituras de gemas**. La sincronización y comparación de bytes siguen siendo pruebas de la copia remota. El código no recalcula las preferencias ni los contadores. Las pruebas del flujo normal usan la política nueva. Las pruebas de compatibilidad de los mecanismos de escritura heredados usan un proveedor falso y sustituyen la política solo en la prueba.

Pasaron 466 pruebas de backend, con las capturas privadas 8.6.0 y 8.8.0 y una respuesta archivada de nube. También pasaron la compilación del frontend y 29 pruebas en Chromium con servicios simulados.

## Captura pendiente en Android

El [protocolo de captura](capture.md) aísla una recompensa, una compra y una mejora. Incluye los pasos de guardado, reinicio y recuperación, y permite procesar las muestras con el comparador local sin cargar datos en servicios externos.

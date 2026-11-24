# Dependencias entre capas y archivos

| Operación o categoría | Relación observada | Verificación pendiente |
| --- | --- | --- |
| Gemas | En la rama de consumo 8.8.0, `gems = lastGems + varGems`. Las transacciones legítimas del hotfix registran base, variación con signo y ganancia o consumo acumulado. La recuperación proyecta los cinco enteros en `game.data` y PlayerPrefs. | Extender la comprobación a perfiles con otros esquemas y a otras plataformas. |
| Héroes y habilidades | El nivel de `Knight` se proyecta entre XML y JSON. La recuperación de un invitado materializó 105 preferencias de habilidades. | Contrastar un desbloqueo normal de habilidad con `heroSkillUnlock`, planos y materiales. Clasificar fuentes de acceso por separado. |
| Estadísticas y armas | El contador y la evolución comparten un espacio de códigos de armas. Los planos de evolución y las recetas enlazan códigos de objetos y materiales en SKDFE. | Comparar una obtención y una evolución legítimas con `object2ObtainTime`, los planos y el mapa de evolución por separado. Los umbrales y estados de marcos quedan E1. |
| Jardín y lobby | `itemUnlock` es una lista. Los eventos de `statistic` y las preferencias de mobiliario ofrecen otras proyecciones. Una compra de cofre añade `furniture_chest` y modifica el saldo. | Identificar con una sola mejora qué parte se guarda en `event2Count`, `itemUnlock` o `gameData.unlockRoomDecorate`. |
| Pesca, temporada y pase | Se confirmaron contadores y rutas en archivos separados. | Aislar una captura de pez y una transacción de temporada. Verificar el ID de temporada y la relación con contadores, tienda y recompensas usando el cliente oficial. |

El saldo que aplica la rama conocida puede reponerse desde `lastGems + varGems` cuando el guardado ya contiene una discrepancia. En un guardado conciliado, mantener `lastGems` fija implica que `varGems = saldo solicitado − lastGems`. Esta es una consecuencia algebraica de conservar la comprobación observada. `cumulativeGems` y `cumulativeConsumeGems` conservan sus valores. Un ajuste manual del saldo no representa una obtención o un gasto jugado. [Comparaciones de transacciones legítimas](../research/phase6-11/README.md)

Para cubrir una dependencia nueva, captura el XML, los `.data` y el agregado antes y después de una única acción normal, guarda un control en reposo y repite después de guardar y reiniciar. El [protocolo de captura](../research/phase6-11/capture.md) identifica cada capa y conserva la posibilidad de repetir el análisis.

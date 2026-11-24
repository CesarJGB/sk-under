# Fase 6.11: investigación de persistencia (en curso)

## Hallazgos y límites

No se ha confirmado la causa de la reversión. El informe de uso real describe una divergencia posterior a transacciones; no hay aquí una pareja de capturas controladas de esa operación. No se ha demostrado si intervienen estado en memoria, persistencia local, servidor, ni otra representación. No se debe afirmar que cambiar múltiples campos resolvería el problema.

La [fase 6.1](../phase6-1/client-validation.md) demostró que una copia modificada se recuperó en el cliente 8.8.0, apareció en el HUD y se escribió en `game.data`; no probó una compra ni un reinicio después de ella. La [fase 5.8](../phase5-8/cloud-roundtrip.md) comparó antes y después de una recuperación legítima: `game.data.gems`, `varGems` y `cumulativeGems` cambiaron junto a otros campos; la operación involucró múltiples diferencias y no demuestra causalidad ni igualdad entre ellos. También hubo correspondencia de `gems` entre agregado en memoria y archivo local restaurado. La [fase 5.7](../phase5-7/modification-acceptance.md) observó una discrepancia durante el tutorial, con estado en memoria y disco en momentos distintos; no identifica la causa del caso actual.

## Inventario y mapa provisional

| Ubicación | Evidencia y clasificación | Confianza |
| --- | --- | --- |
| `gameData.gems` / `game.data.gems` | Campo entero observado en agregado y archivo local; mostrado tras recuperación 6.1. Autoridad al comprar desconocida. | Estructura y observación confirmadas; función transaccional desconocida |
| `gameData.lastGems`, `varGems` | Enteros en metadata 8.8.0. `varGems` cambió en recuperación 5.8. Sus nombres sugieren estado previo/variación, no establecen semántica. | Existencia confirmada; función desconocida |
| `gameData.cumulativeGems`, `cumulativeConsumeGems` | Enteros en metadata. Los nombres sugieren acumulados; `cumulativeGems` cambió en 5.8. | Existencia confirmada; reglas desconocidas |
| `itemData.cumulativeFishCount` | Campo documentado en esquema; nombre sugiere acumulado. | Función exacta desconocida |
| `seasonData.coin`, `gainedCoinToday`, `cumulativeCoinCount` | Campos observados en investigación local 8.6.0. No se ha demostrado relación matemática. | Existencia documentada; función exacta desconocida |
| `battlePassSaveData`, `gameData.heroUnlock`, `currentSkinDatas` | Secciones o campos presentes en investigaciones anteriores. | No se han establecido dependencias de edición |

La metadata no demuestra qué campos persiste cada versión ni que todos aparezcan en cada copia. La [comparación 8.6.0/8.8.0](../phase5-5/schema-diff-860-880.md) identifica nombres comunes y diferencias por sección, sin demostrar compatibilidad de tipos o comportamiento. El número `serialzedVersion` es versión del agregado, no versión del juego. No hay evidencia suficiente para reglas multiplataforma.

## Herramientas y estado de implementación

`app.cloud.resource_consistency` contiene un registro preliminar, inspección de presencia/tipo, comparación recursiva con rutas y cambios de tipo, y un planificador estricto que rechaza operaciones cuando las dependencias son desconocidas. `aggregate_tree` reutiliza la validación del agregado. La comparación de listas es por índice: inserciones pueden producir diferencias posteriores aparentes. La salida puede contener datos privados: ejecutar solo localmente y no publicar informes sin revisar y anonimizar.

**No está integrado en el editor de producción.** El editor anterior sigue cambiando únicamente `gameData.gems`; su comprobación transaccional y de serialización protege el agregado, pero no garantiza consistencia en el juego. El nuevo planificador no implementa todavía planes compatibles ni detección de discrepancias confirmadas, pues no hay relaciones confirmadas que comparar. La fase y sus criterios de aceptación permanecen incompletos. Los respaldos existentes no se alteraron.

## Protocolo de validación pendiente

Con una cuenta de laboratorio autorizada y copias privadas verificadas, registrar versión, plataforma, hora y saldo; capturar agregado y archivos locales en reposo. Obtener una recompensa pequeña, guardar normalmente y capturar de nuevo; repetir separadamente con compra y mejora, y después de guardar en nube y reiniciar. En un ensayo independiente, recuperar la copia editada, registrar HUD antes y después de una única transacción y capturar de nuevo cada estado. Conservar testigos sin modificación y evitar sobrescribir partidas ajenas. Comparar árboles localmente con `structural_diff`, revisar todas las rutas cambiadas y distinguir cambios incidentales; registrar valores de saldo y diferencias solo en un lugar privado. Repetir con más de una operación y saldo antes de formular una regla. No modificar contadores históricos por coincidencia numérica.

Niveles de prueba: archivo y relectura del agregado son verificables localmente; la sincronización se ha observado previamente en 6.1; transacciones normales tras editar y reinicio posterior siguen pendientes para este problema. No se ejecutó una prueba nueva en Android en esta fase.

## Siguiente trabajo para fase 7

Obtener pares controlados, clasificar cada ruta según evidencia y versión, determinar si existen representaciones independientes o dependencia externa, implementar validadores y planes transaccionales solo para relaciones demostradas, conectar el motor al editor y cubrir rechazos y recuperación de respaldo. Investigar monedas de batalla, personajes y skins sin añadir opciones de edición hasta entender sus reglas.

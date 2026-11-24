# Propuesta para la fase 6.13

La fase 6.13 debe cerrar las incógnitas con evidencia experimental antes de
añadir cualquier edición. La prioridad no es escribir más campos: es demostrar
qué campo controla cada recurso y qué capa tiene autoridad.

## Objetivo 1 — Fichas de pesca

### Experimento mínimo

1. Cuenta de prueba autorizada, cliente oficial Android 8.8.0.11, sin compras
   premium y sin manipular recibos.
2. Captura inicial de `files/`, `shared_prefs/`, HUD y, si el flujo lo permite,
   descarga de nube.
3. Obtener fichas por una vía legítima (recompensa, conversión o actividad).
   Registrar el texto y el importe mostrados.
4. Gastar una cantidad pequeña en la tienda de peces con una sola acción.
5. Guardar desde el menú y capturar de nuevo.
6. Reiniciar el proceso y comprobar el saldo.
7. Recuperar la copia oficial anterior y comprobar qué vuelve.
8. Repetir con una segunda obtención y un segundo gasto.

### Cambios que hay que vigilar

- `gameData.fishChip`.
- `<perfil>_furniture_fish_chips`.
- Los cuatro historiales `fishChipStore*`.
- `buyFishCount*` y `mallPurchase*`.
- `_buyItemUseFishChipTimes` y los contadores de eventos.
- Cualquier cambio simultáneo en `itemData`, `seasonData` o tareas.

### Criterio de aceptación

- El delta de `fishChip` coincide con el importe mostrado en la obtención y en
  el gasto.
- La preferencia y el saldo mantienen una relación estable, o se documenta que
  no la tienen.
- El saldo sobrevive a guardar y reiniciar.
- La recuperación se explica por una copia concreta.
- Si no se encuentra una vía legítima, el campo permanece E2 y no se implementa
  edición.

## Objetivo 2 — Personajes, skins y habilidades

### Experimentos

1. Subir un segundo nivel a un personaje ya mejorado y comparar `heroLevel`.
2. Desbloquear una habilidad con el flujo normal y comparar
   `heroSkillUnlock`, planos y materiales.
3. Cambiar la skin seleccionada sin comprar nada y comparar
   `currentSkinDatas`.
4. Desbloquear una skin por una vía legítima y determinar si `skinLock` cambia
   a un valor de posesión.
5. Desbloquear un personaje y distinguir `heroUnlock` de nivel, tutorial y
   entitlement.

### Criterio de aceptación

- Una sola acción produce un delta identificable.
- Se distingue “poseído”, “seleccionado”, “precio” y “requisito”.
- La recuperación no revierte el estado de forma inexplicable.
- No se edita una skin o habilidad mientras su valor no tenga semántica
  comprobada.

## Objetivo 3 — Herramientas y registro

### Backend

- Mantener `backend/app/save_analysis.py` como capa de solo lectura.
- Añadir pruebas sintéticas para:
  - listas con índices y tipos mezclados;
  - campos ausentes frente a `null`, `false` y `0`;
  - secciones de nube y archivos locales;
  - fichas separadas de materiales y chips de temporada;
  - catálogo de personajes con IDs desconocidos.
- No añadir rutas de escritura para recursos nuevos.

### CLI

- Conservar `inventory`, `fields`, `compare`, `fish` y `characters`.
- Añadir, si hace falta, un comando `report` que genere un resumen saneado sin
  valores.
- Mantener `--values` como opción local y advertir que la salida es privada.

### Registro de campos

- Ampliar `docs/save-research/field-registry.json` con los campos de esta fase.
- Separar `validation_level` de la confianza en la semántica.
- Añadir para cada campo: capa, tipo, dependencia conocida, dependencia
  pendiente, política de edición y evidencia.
- Marcar como solo lectura las fichas, skins, habilidades, compras y
  entitlements.
- No convertir una hipótesis en E3 sin la captura correspondiente.

## Objetivo 4 — Documentación y catálogos

- Mantener el catálogo `characters-880.json` con su commit de origen.
- Documentar los conteos y las diferencias entre 8.6.0 y 8.8.0.
- Añadir una tabla de correspondencia sección de nube ↔ archivo local.
- Registrar las variantes de nombre sin publicar perfiles.
- Conservar las hipótesis descartadas para no repetirlas.

## Fuera de alcance

- Edición de fichas, materiales, skins, habilidades o personajes.
- Compras, conversiones o recibos simulados.
- Sincronización automática entre XML y JSON.
- Reescritura de historiales de tienda.
- Cambios en la interfaz de edición de gemas ya validada.
- Publicación de capturas, IDs de cuenta o valores privados.

## Entregables de 6.13

1. Evidencia antes/después de al menos una obtención y un gasto de fichas, o
   un informe explícito de que no se pudo obtener.
2. Evidencia de un desbloqueo de habilidad o skin, o su ausencia justificada.
3. Registro actualizado con niveles de evidencia revisados.
4. Pruebas de regresión del analizador y suite completa.
5. Un informe de riesgos y una decisión sobre si alguna edición nueva es
   segura. La decisión por defecto es **no escribir**.
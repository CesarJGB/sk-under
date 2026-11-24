# Fase 6.20 — Tarjeta de renacimiento y progreso acumulado de fichas

## Resumen

Esta fase investigó dos funciones pendientes desde la Fase 6.19:

1. la **tarjeta de renacimiento permanente**;
2. el **progreso acumulado de recompensas por compra de fichas de pesca**.

Resultado:

- Se identificó y documentó el contador de recompensas: `itemData.cumulativeFishCount`.
- Se implementó un editor experimental aislado para ese contador.
- **No** se implementó un editor de la tarjeta de renacimiento: el cliente lee el
  estado real desde un entero de `PlayerPrefs`, con una ruta alternativa de
  objeto desbloqueado y una posible respuesta de servidor. No hay prueba de que
  editar el booleano de nube baste para activar la tarjeta.

Nivel de evidencia:

- Progreso acumulado: **E2 fuerte** (estructura y uso verificados en el código
  del cliente 8.8.0, sin prueba manual en Android).
- Tarjeta de renacimiento: **E2**, sin campo de nube editable con semántica
  confirmada. Se mantiene en solo lectura.

## Referencias consultadas

- `docs/research/phase6-19/README.md`
- `docs/research/phase6-12/fichas-de-pesca.md`
- `docs/save-research/README.md`
- `docs/save-research/field-registry.json`
- `AGENTS.md`
- `SK-Under_Investigacion_Discord_2026-11-23.txt`
- Metadatos y `libil2cpp.so` del cliente Android Global 8.8.0.
- Guardado local 8.6.0 de la cuenta de laboratorio.
- Agregados de nube 8.8.0 de la misma cuenta de laboratorio.
- Guardados auténticos 8.8.0 conservados en el almacenamiento privado.
- Repositorios y análisis externos ya citados en fases anteriores
  (`Suto-Commune/soul_knight`, `aznoobnam`, `SHOULXING`, `SKDEditor`).

No se publicaron identificadores de cuenta, credenciales ni capturas privadas.

## 1. Progreso acumulado de fichas de pesca

### Campo exacto

| Dato | Valor |
| --- | --- |
| Ruta en la nube | `itemData.cumulativeFishCount` |
| Archivo local | `item_data*.data:cumulativeFishCount` |
| Tipo | `Int32` / entero JSON |
| Rango aceptado | `0..2147483647` |
| Nivel | E2 |

No es el saldo actual. El saldo sigue en `gameData.fishChip`, con el material
espejo `itemData.materials.material_fish`.

### Evidencia de código (8.8.0)

El desensamblado del cliente mostró:

- `FishChipPurchaseController.get_cumulativeFishCount` devuelve directamente
  `ItemData.cumulativeFishCount` (campo en el offset `0x28`).
- `FishChipPurchaseController.set_cumulativeFishCount` escribe el mismo campo.
- `FishChipPurchaseController.get_fishCount` es una ruta distinta: representa el
  saldo actual.
- `MallFishChipRewardManager.GetCumulativeFishCount` llama al getter anterior.
- `FishChipStore.PlutusWindowPanel.RefreshRewardProgress` usa ese valor para
  refrescar la barra de recompensas.
- `FishChipReward.DriedFishAmount` define los umbrales de la tabla
  `TbFishChipReward`.

Por tanto, la barra de recompensas de la tienda se alimenta de
`cumulativeFishCount`, no de `buyFishCount*`, de los historiales de compra ni
del saldo actual.

### Muestras

- 8.6.0 local: `cumulativeFishCount = 7218`.
- 8.8.0 de laboratorio: `0`.
- No se encontró una muestra de nube con un valor positivo distinto de cero.

La muestra 8.6.0 respalda que es un contador histórico acumulado, no un
contador de peces capturados. La afirmación anterior de la Fase 6.12/6.19 queda
corregida.

### Implementación

Backend:

- `backend/app/cloud/fish_progress_editor.py`: lectura, validación, preparación
  determinista, comparación inversa y compatibilidad de borradores.
- `backend/app/cloud/lab_service.py`: preparación, respaldo, confirmación,
  restauración y verificación del nuevo campo.
- `backend/app/cloud/backup_store.py`: nuevo tipo de respaldo
  `fish_progress`.
- `backend/app/api/native.py`: `POST /api/v1/cloud/native/prepare-fish-progress`.
- `backend/app/models.py`: contratos de entrada/salida.
- `backend/app/native/service.py`: lectura del valor actual y operación de
  preparación por sesión.

Frontend:

- `frontend/src/api.ts`: tipos y llamada `prepareFishProgress`.
- `frontend/src/pages/NativeAuthPage.tsx`: control independiente **“Progreso
  acumulado de fichas de pesca”** dentro de la sección de fichas, con valor
  actual, valor nuevo, vista previa y confirmación explícita.
- `frontend/src/styles.css`: separación visual del control.

Garantías:

- Solo se modifica `itemData.cumulativeFishCount`.
- No se cambia el saldo, `material_fish`, los historiales ni las recompensas
  reclamadas.
- El campo debe existir; no se crea si falta.
- Se rechazan booleanos, texto, flotantes, negativos y valores fuera de rango.
- La confirmación exige el mismo flujo de respaldo, `SUBIR` y verificación por
  descarga que las funciones confirmadas.
- La restauración devuelve exactamente el original.

La interfaz indica que la función es experimental E2.

## 2. Tarjeta de renacimiento permanente

### Campos y rutas observados

| Ruta | Tipo | Observación |
| --- | --- | --- |
| `gameData.rebornCard` | bool | Bandera incluida en el agregado de nube |
| `<perfil>_reborn_card` | int en `PlayerPrefs` | Estado leído por el cliente |
| `itemData.RebornCard` | string | Nombre de catálogo de objeto |

### Evidencia de código (8.8.0)

- `AboGameData.rebornCard` es un booleano (offset `0xA8`).
- `DataUtil.GetRebornCardUnlock` consulta primero
  `PlayerSaveData.get_reborn_card`, que lee el entero de `PlayerPrefs`.
- Si el entero no es cero, la tarjeta se considera desbloqueada.
- Si es cero, se consulta además `CPPlayerItemData.GetItemUnlock` para un objeto
  relacionado.
- `CloudSaveExtraData.rebornCard`, `ExtraDescribeOptions.rebornCard` y
  `FetchGameDataResp.RebornCardUnlock` existen para resúmenes, diferencias y
  respuestas de paquete V1.

### Conclusión

No se demostró que `gameData.rebornCard = true` active la tarjeta al restaurar
la nube. La ruta de juego prioritaria es el entero de `PlayerPrefs`, y el
derecho podría depender de una compra validada por el servidor o de un objeto
de catálogo. Editar solo el booleano de nube podría producir un estado
inconsistente o no surtir efecto.

Por seguridad y por las reglas de la fase:

- no se añadió editor de esta tarjeta;
- no se modificaron recibos, transacciones ni verificaciones de compra;
- no se declaró que la tarjeta esté disponible;
- el campo permanece **protegido, solo lectura** en el registro.

Para convertirla en editable haría falta una prueba controlada que confirme la
conversión `gameData.rebornCard` → `PlayerPrefs` al restaurar, y que el cliente
muestre la tarjeta sin una compra verificada externamente.

## 3. Cambios descartados

- `mallReloadData.buyFishCount*`: contadores de paquetes de peces; no alimentan
  la barra de recompensas. Siguen en solo lectura.
- Historiales `fishChipStore*`: no se usan para calcular recompensas y no se
  tocaron.
- `CloudSaveSundry.CumulativePurchaseFishChip`: aparece en el resumen de nube,
  pero no en el agregado serializado ni en la ruta que lee la UI.
- `CumulativePurchaseFishChip` como campo del save: no existe en `ItemData` ni
  en `AboGameData`.

## 4. Pruebas

Backend:

- Pruebas nuevas de lectura, edición aislada, rechazo de tipos, campo ausente,
  respaldo, confirmación, restauración y conservación del saldo.
- Pruebas de API para el flujo completo y para valores inválidos.

Frontend:

- Build de TypeScript y Vite.
- Playwright: el progreso se prepara, se revisa, se confirma y actualiza el
  valor mostrado sin cambiar el saldo de fichas.

Resultados concretos de la ejecución en esta fase:

- `backend/.venv/bin/python -m pytest backend/tests -q`: **593 passed, 16 skipped**.
- `npm run build`: correcto.
- `npm run test:browser`: **48 passed**.
- Imagen `soul-knight-editor:phase6-20`: verificada; `/api/v1/health` respondió
  `status: ok` dentro del contenedor.

## 5. Validación manual en Android

Para el propietario:

1. Descargar la partida y anotar el saldo de fichas y el progreso actual.
2. Preparar un cambio pequeño del **progreso acumulado**.
3. Confirmar la subida y esperar la verificación por descarga.
4. Abrir la tienda de fichas de pesca en Soul Knight.
5. Comprobar si la barra de recompensas refleja el nuevo progreso.
6. Comprobar que el saldo de fichas no cambió y que los historiales siguen
   intactos.
7. Si el resultado no es el esperado, restaurar el respaldo original.

No se deben realizar compras reales para esta prueba.

## 6. Limitaciones

- El progreso acumulado es E2: el código confirma la fuente del dato, pero falta
  la comprobación visual en Android.
- No se localizó una tabla de umbrales publicable; no es necesaria para editar
  el contador.
- La tarjeta de renacimiento sigue pendiente por depender de `PlayerPrefs` y de
  una posible validación externa.
- El editor no concede compras, no marca recompensas como reclamadas y no
  sustituye el protocolo de nube.

## 7. Fragmentos de referencia

Del TXT de Discord (E1, hipótesis inicial):

> `reborn_card` se asocia con tarjeta de reanimación gratuita y un valor entero
> de ejemplo 1. No está establecido si es cantidad, indicador o derecho.
> `cumulativeFishCount` se asocia con una recompensa relacionada con el ticket
> Mode Hopper. Distinguir contador de pesca, derecho de acceso y estado de
> recompensa.

La Fase 6.20 corrige la parte de `cumulativeFishCount`: es el contador acumulado
de la tienda de fichas, no un contador de peces capturados. La relación exacta
con el ticket Mode Hopper no se confirmó.
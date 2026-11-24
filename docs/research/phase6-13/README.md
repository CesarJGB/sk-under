# Fase 6.13 — Informe de guardado y visualización de recursos

Esta fase convierte parte de la investigación de la Fase 6.12 en una función
verificable del editor: un informe saneado de la partida descargada que muestra
el saldo candidato de fichas de pesca, los personajes con su progreso observado
y los recursos de inventario identificados. No se añadió ninguna escritura
nueva. La edición de gemas, la autenticación, la descarga, los respaldos y la
subida conservan su comportamiento anterior.

## Resultado en una página

- El informe viaja dentro de la misma descarga autenticada de la partida. No
  provoca una segunda petición a la nube ni expone el agregado completo.
- **Fichas de pesca:** se muestra `gameData.fishChip` como saldo candidato,
  junto con su ruta, los campos relacionados y la prueba que falta. El nivel de
  evidencia sigue siendo E2 y la escritura permanece deshabilitada.
- **Personajes:** se listan los 42 códigos del catálogo con nombre, estado de
  desbloqueo observado, nivel actual, habilidad seleccionada, habilidades
  disponibles y skin equipada. El informe no inventa un nivel máximo ni deduce
  la posesión de skins desde `skinLock`.
- **Recursos:** se agrupan materiales, semillas, tickets, planos, objetos
  desbloqueados, plantas, mercancía, forja y el contador acumulado de peces.
  Los planos muestran tipo y longitud, nunca el texto interno.
- **Interfaz:** la vista **Editor** de `/partida` organiza la información en
  Recursos y Personajes, mantiene la tarjeta editable de gemas y deja los
  respaldos en la vista **Partida**. Las cuentas vinculadas y el laboratorio
  administrativo reutilizan el mismo componente de solo consulta.
- Se añadieron pruebas unitarias del informe y una prueba de navegador para la
  visualización en escritorio y móvil.
- El [registro de campos](../../save-research/field-registry.json) pasó a 66
  entradas al documentar `specialTickets`, que el informe muestra sin habilitar
  su edición. También se añadieron comprobaciones automáticas de su estructura,
  unicidad y política de solo lectura.

## Representación y límites de cada bloque

| Bloque | Origen | Estado | Límite explícito |
| --- | --- | --- | --- |
| Fichas de pesca | `gameData.fishChip` y campos `*fishChip*` | Solo lectura, E2 | Nunca se observó un saldo positivo ni una transacción legítima. |
| Personajes | `heroUnlock`, `heroLevel`, `heroSkill`, `heroSkillUnlock`, `currentSkinDatas` | Solo lectura | Solo Knight tiene evidencia E3/E4 de nivel 0→1; la escala y los máximos no están validados. |
| Habilidades | Catálogo de 105 habilidades y `heroSkillUnlock` | Solo lectura | El catálogo resuelve nombres; no demuestra que una habilidad se haya obtenido por una acción concreta. |
| Skins | Catálogo de 802 skins, `currentSkinDatas` y `skinLock` | Solo lectura | `skinLock` no se interpreta como posesión, precio ni requisito. Se muestra la skin equipada cuando existe. |
| Materiales y semillas | `itemData.materials`, `itemData.seeds` | Solo lectura | Los IDs se muestran sin catálogo de nombres; no se infiere su uso ni se editan cantidades. |
| Plantas | `itemData.plants` | Solo lectura | Se muestran posición, nombre, estado, riego y fertilización observados; no se probó ninguna acción agrícola. |
| Planos | `itemData.blueprints` | Solo lectura | Se muestra el identificador y el tipo; el texto del plano no se envía al navegador. |
| Otros recursos | Tickets, desbloqueos, mercancía y forja | Solo lectura | La forma observada no demuestra la semántica de cada transición. |

## Implementación

### Backend

`backend/app/save_report.py` construye el informe a partir del agregado ya
decodificado. Reutiliza `fish_chip_report` y `character_report` de
`save_analysis.py`, carga el catálogo saneado de personajes con una caché y
limita listas y textos para que la respuesta siga siendo pequeña. Los campos
desconocidos no se eliminan del guardado: el informe solo los omite.

`CloudLabService.load()` calcula el informe en la misma descarga y lo incluye
en `LoadedSave.summary()`. Así lo reciben la API nativa, las cuentas vinculadas
y el laboratorio sin una petición adicional. `CloudLabSave.report` es opcional
para conservar la compatibilidad con clientes anteriores.

El informe no contiene `cloudSaveId`, `platformId`, correo, tokens,
credenciales, el agregado completo ni el contenido de los planos. Una captura
privada de 8.8.0 produjo un informe de aproximadamente 32 KB con 42 personajes
y diez grupos de recursos; las cifras se comprobaron localmente y no se
publican valores de la cuenta.

### Frontend

`frontend/src/pages/SaveReportSections.tsx` muestra las secciones **Recursos**
y **Personajes**. Las etiquetas “Solo consulta” distinguen los datos no
editables de la tarjeta de gemas. En móvil, las listas tienen desplazamiento
interno y las columnas se apilan.

La vista **Editor** usa el componente después de la tarjeta de gemas. La vista
**Partida** conserva los respaldos y la restauración. Las cuentas vinculadas y
el laboratorio administrativo muestran el mismo informe cuando la respuesta
incluye `report`.

## Evidencia y pruebas

- El saldo de fichas se revisó en capturas antes y después de recompensas,
  compras, mejoras, reinicio y recuperación. `gameData.fishChip` permaneció en
  cero; no se localizó una transacción legítima de fichas ni un saldo positivo.
- La mejora legítima de Knight cambió `heroLevel.Knight` de 0 a 1 y persistió
  tras reiniciar. El informe muestra ese nivel, pero no lo generaliza a otros
  personajes.
- La prueba de regresión del backend terminó con **473 pruebas aprobadas y 16
  omitidas**. Las **34 pruebas de navegador** terminaron aprobadas, incluida la
  nueva comprobación de fichas, recursos y personajes en solo lectura.
- `npm run build` completó `tsc --noEmit` y la compilación de Vite.

## Incertidumbres

1. Falta una transacción legítima que produzca un saldo positivo de fichas y
   su comprobación tras reiniciar y recuperar desde la nube.
2. Se desconoce si la autoridad del saldo de fichas es local, remota o
   compartida.
3. No se validaron los niveles máximos, los costos ni las habilidades de los
   42 personajes.
4. No se demostró la semántica de los valores de `skinLock` ni de los
   historiales `fishChipStore*`.
5. No se probaron transiciones de materiales, semillas, plantas, planos,
   tickets ni mercancía.
6. No se verificaron variantes regionales ni iOS.

La propuesta para continuar se encuentra en
[propuesta-6.14.md](propuesta-6.14.md).
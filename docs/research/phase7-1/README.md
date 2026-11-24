# Fase 7.1 — Materiales, economía de temporada, beneficios permanentes y pase de batalla

Esta fase convierte parte del conocimiento estructurado de la fase 7.0 en editores
reales dentro de la página de producción. Parte del commit
`7eca51355cb5cbb02abdcdfbf24b7296a69ba32f`.

## Funcionalidades entregadas

- Editor de **materiales** con cantidades actuales, búsqueda por nombre o ID,
  filtro por categoría, selección múltiple, cantidad masiva y edición individual.
- Editor de **semillas** con el mismo flujo, usando el catálogo de plantas.
- Inserción de materiales y semillas del catálogo que todavía no existen en el
  guardado. Los identificadores desconocidos ya presentes se conservan y se
  muestran como solo lectura.
- Control de **monedas de temporada** (`seasonData.coin`) con cantidades rápidas,
  validación de entero y vista previa.
- Control experimental de **tarjeta de renacimiento permanente** sobre
  `gameData.rebornCard`, con la limitación de la proyección local documentada en
  la propia interfaz.
- Editor del **pase de batalla**: detección de temporadas existentes, selección
  inicial de la temporada con `seasonID` más alto, edición de nivel, experiencia
  y estado premium local, y visualización de recompensas gratuitas y premium
  reclamadas.
- Control rápido de **recompensas acumuladas de pesca** que reutiliza el editor
  existente de `itemData.cumulativeFishCount`; fija `max(actual, 21)` y nunca
  reduce un progreso superior.
- Preparación, diferencia binaria, respaldo, confirmación, restauración y
  verificación dentro del flujo ya existente. Todas las ediciones de esta fase
  se agrupan en un único candidato atómico.

Los controles nuevos están organizados en las secciones **Materiales**,
**Semillas**, **Monedas y recursos**, **Beneficios permanentes** y **Pase de
batalla**. En móvil se apilan y cada sección puede plegarse.

## Campos exactos y representación

| Campo | Representación local | Representación remota | Política |
| --- | --- | --- | --- |
| Cantidad de material | `item_data*.data:materials.<id>` | `itemData.materials.<id>` | Experimental E2; solo IDs del catálogo; `material_fish` excluido |
| Cantidad de semilla | `item_data*.data:seeds.<id>` | `itemData.seeds.<id>` | Experimental E2; solo IDs del catálogo |
| Moneda de temporada | `season_data*.data:coin` | `seasonData.coin` | Experimental E2 aislada |
| Tarjeta de renacimiento | `shared_prefs/com.ChillyRoom.DungeonShooter.v2.playerprefs.xml:<perfil>_reborn_card` (int) | `gameData.rebornCard` (bool) | Experimental E2; solo activación, proyección local no remota |
| Progreso acumulado de pesca | `item_data*.data:cumulativeFishCount` | `itemData.cumulativeFishCount` | Experimental E2; editor de la fase 6.20 |
| Pase de batalla | `bp_data_<perfil>_.data:seasonData[]` | `battlePassSaveData.seasonData[]` | Experimental E2; solo registros existentes |
| Nivel del pase | `...Value.curLevel` | `battlePassSaveData.seasonData[].Value.curLevel` | Experimental E2 |
| Experiencia del pase | `...Value.curExp` | `battlePassSaveData.seasonData[].Value.curExp` | Experimental E2 |
| Estado premium local | `...Value.hasBuy` | `battlePassSaveData.seasonData[].Value.hasBuy` | Experimental E2; no representa una compra |
| Recompensas reclamadas | `...Value.freeClaimedLevel`, `...Value.paidClaimedLevel` | mismas rutas | Solo lectura, se conservan siempre |

### Reglas de integridad aplicadas

- Solo se modifican las rutas autorizadas. El resto del agregado se conserva
  byte a byte tras revertir el plan.
- Los mapas `materials` y `seeds` deben existir y ser diccionarios. Se permite
  insertar IDs del catálogo, pero no se sobrescriben valores no enteros.
- `material_fish` no se edita desde el editor genérico porque es el espejo de
  `gameData.fishChip`. Las fichas se siguen editando desde su control específico.
- `seasonData.coin` debe existir y ser entero. El máximo aceptado es el límite
  estructural de entero de 32 bits (`2 147 483 647`), no un límite de juego
  confirmado.
- `gameData.rebornCard` debe existir y ser booleano. Solo se permite activarlo;
  no se inventan propiedades, recibos ni comprobantes.
- El pase de batalla debe existir y contener una única coincidencia de
  `Value.seasonID`. Nunca se crean temporadas.
- `curLevel` no puede quedar por debajo de `max(freeClaimedLevel,
  paidClaimedLevel)`. `hasBuy` no puede desactivarse si hay recompensas premium
  reclamadas.
- `freeClaimedLevel` y `paidClaimedLevel` nunca se modifican. Tampoco se
  modifican `Key`, `seasonID` ni los demás registros de temporada.
- No se repiten recompensas ya reclamadas ni se simula una compra.

## Dependencias descubiertas o confirmadas

- `materials-seeds-catalog-insertion` (E1): los catálogos respaldan la inserción
  estructural de IDs conocidos; no demuestra comportamiento en el cliente.
- `season-coin-battlepass-independent` (E2, negativa): las monedas de temporada
  no son experiencia ni nivel del pase.
- `battle-pass-level-claimed-consistency` (E2): el nivel no debe contradecir el
  progreso reclamado.
- `battle-pass-hasbuy-local-state` (E2, negativa): `hasBuy` es estado local y no
  una compra ni un derecho verificado por el servidor.
- `reborn-card-cloud-local-gap` (E2, hipótesis): `shared_pref:reborn_card` es
  local; `CoverPlayerPref` proyecta datos al agregado de nube. No está probado
  que editar `gameData.rebornCard` baste para el derecho permanente en todos los
  casos.
- `cumulative-fish-reward-threshold` (E2, hipótesis): superar 20 desbloquea las
  recompensas acumuladas, pero reclamarlas ocurre en el cliente.

## Knowledge Engine

- Nueva fuente aceptada: `knowledge/sources/owner-guide-phase7-1.md`, registrada
  como `owner_reference` de evidencia E1. Separa la referencia funcional del
  propietario de la confirmación empírica en dispositivo.
- Nuevas políticas de escritura experimentales E2 en
  `knowledge/fields/overrides.json` para materiales, semillas, moneda de
  temporada, tarjeta de renacimiento, contenedor del pase y sus campos editables.
- Se mantuvieron como solo lectura `seasonID`, `freeClaimedLevel`,
  `paidClaimedLevel`, compras y recibos.
- Se documentaron seis dependencias nuevas; el total pasa a 32.
- El catálogo de backend `backend/app/catalogs/items-880.json` se genera desde
  `knowledge/catalogs/materials.json` y `seeds.json` con
  `knowledge/tools/build_backend_items.py`. No hay copias manuales completas en
  frontend ni backend.
- Se regeneraron `knowledge/fields/fields.json`, el informe de cobertura y
  `knowledge/manifest.json`. Se conservaron los niveles E1/E2; ninguna función
  se elevó a E3 o E4.

## Limitaciones pendientes

- Ninguna de estas funciones ha sido confirmada todavía en un dispositivo
  Android físico. Permanecen en E2.
- La tarjeta de renacimiento se escribe únicamente en el booleano de nube cuando
  existe. La preferencia local `reborn_card=1` no se modifica remotamente y la
  proyección `CoverPlayerPref` no está decompilada.
- El nivel máximo del pase solo se ofrece si el propio registro incluye un campo
  entero de máximo respaldado. En los datos actuales no se inventa un límite.
- El máximo de monedas de temporada y de cantidades es el límite estructural de
  entero de 32 bits, no un tope de juego confirmado.
- Insertar un material o semilla conocido es estructuralmente compatible con el
  mapa, pero el comportamiento del cliente al recogerlo o mostrarlo debe
  validarse en dispositivo.
- Los identificadores desconocidos se conservan, pero no se editan porque no hay
  nombre, tipo ni compatibilidad demostrados.
- `cumulativeFishCount` solo cambia el progreso. No marca recompensas como
  reclamadas ni entrega fichas, materiales o el Mode Hopper Ticket.

## Pruebas

- Backend: suite completa con **636 pruebas aprobadas y 16 omitidas**;
  `backend/tests/test_advanced_editor.py` aporta 22 pruebas. Cubre edición
  individual y masiva, semillas, conservación de IDs desconocidos, exclusión de
  `material_fish`, monedas, renacimiento, umbral de pesca, selección de la
  temporada más reciente, estado premium, nivel, conservación de temporadas y
  reclamaciones, valores inválidos, combinación de ediciones y ausencia de
  cambios colaterales.
- Frontend: `npm run build` y **51 pruebas Playwright aprobadas**, incluidas las
  nuevas del flujo completo, el control rápido de pesca y el caso de progreso ya
  superior a 20.
- Catálogos: `python3 knowledge/tools/build_backend_items.py --check` y
  `python -m app.catalogs.verify`; 343 materiales, 47 semillas, 42 personajes,
  105 habilidades y 802 skins válidos.
- Knowledge Engine: validación, manifiesto, cobertura y comprobación de que la
  proyección legacy de campos permanece idéntica (616 campos, 32 dependencias,
  16 fuentes, 24 catálogos y 8.526 traducciones).

## Publicación

- Commit de implementación: `470c574bc566ed8dfb4e865acd8e5ec6e0feb588`.
- Push directo a `main`; `HEAD` local y `origin/main` coinciden.
- GitHub Actions: ejecución [45475821521](https://github.com/CesarJGB/sk-under/actions/runs/45475821521)
  completada con éxito. Pasaron Backend, Frontend, Higiene/secretos y
  Playwright/Chromium. Cloudflare Pages también informó `success`.
- El despliegue y la CI no demuestran el comportamiento dentro del cliente del
  juego. La validación funcional queda pendiente de las pruebas Android.

## Pruebas en Android físico

Usar una cuenta de prueba y un guardado del que exista respaldo. Antes de cada
prueba, descargar el guardado en la web y anotar los valores actuales.

1. **Materiales y semillas**
   - Abrir **Materiales**, buscar un material poseído y cambiar su cantidad.
   - Preparar, revisar la diferencia, confirmar y descargar de nuevo.
   - Abrir el juego, entrar en la mochila o inventario y comprobar la cantidad.
   - Repetir con una semilla en la granja.
   - Probar una inserción de un material conocido no poseído. Si el juego no lo
     muestra o falla, restaurar el respaldo y registrar el resultado.

2. **Monedas de temporada**
   - En **Monedas y recursos**, cambiar `seasonData.coin` a 100000.
   - Confirmar, abrir la temporada en el juego y comprobar el saldo.
   - Verificar que gemas, fichas de pesca y experiencia del pase no cambiaron.

3. **Tarjeta de renacimiento**
   - Anotar el estado actual. Activar la casilla y confirmar.
   - Cerrar y abrir el juego; comprobar si el beneficio aparece.
   - Si no aparece, restaurar y comprobar el archivo local de preferencias. No
     asumir que el valor de nube equivale al derecho local.

4. **Recompensas acumuladas de pesca**
   - Con un progreso menor o igual a 20, usar **Desbloquear todas las
     recompensas acumuladas**.
   - Confirmar y abrir la pantalla de recompensas de pesca.
   - Comprobar que las recompensas están disponibles para reclamar; reclamarlas
     manualmente en el cliente. La web no las marca como reclamadas.
   - Repetir con un progreso mayor que 20 y comprobar que no se reduce.

5. **Pase de batalla**
   - Abrir **Pase de batalla** y comprobar que se selecciona la temporada con el
     `seasonID` más alto.
   - Cambiar el nivel a un valor igual o superior al progreso reclamado y
     confirmar. Abrir el pase en el juego y comprobar el nivel.
   - Alternar el estado premium local y verificar que no se crea ninguna compra.
   - Comprobar que las temporadas anteriores y las recompensas reclamadas siguen
     intactas.
   - Si aparece un botón de nivel máximo, comprobar que el valor coincide con el
     límite real del juego. Si no aparece, el registro no ofrece un máximo
     respaldado.

6. **Restauración**
   - Tras cualquier resultado inesperado, usar **Restaurar** en el historial y
     verificar que el guardado vuelve al estado anterior.
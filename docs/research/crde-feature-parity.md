# Matriz persistente de paridad funcional CRDE ↔ SK-Under

Actualizada: 2026-11-26 (fase 9.4)

## Método y límites

La auditoría se hizo con la sesión autorizada del propietario en
<https://crde.pages.dev/login>, mediante la interfaz normal y en modo de solo
lectura. Se abrió la cuenta de juego vinculada y se inventariaron las acciones
SK visibles. No se pulsó la ejecución de ninguna modificación, no se compraron
créditos ni planes, no se consumieron créditos, no se migraron datos, no se
eliminaron respaldos ni cuentas y no se accedió a datos de otros usuarios.

CRDE presenta acciones masivas por casilla. SK-Under conserva su arquitectura
independiente: catálogos versionados, selección individual, un único borrador,
revisión explícita, respaldo automático, verificación y restauración exacta. La
paridad se evalúa por resultado funcional, no por copiar la implementación.

Estados:

- **IPV**: implementado y verificado físicamente por el propietario.
- **IPP**: implementado, pendiente de validación física.
- **Parcial**: cubre parte del resultado, pero no toda la función CRDE.
- **Ausente**: no implementado.
- **Investigación**: faltan estructuras, identificadores o semántica suficiente.

La evidencia de CRDE es de interfaz (E1). Que la interfaz muestre una acción no
demuestra que el servidor la acepte ni que el juego la reconozca. La evidencia
de SK-Under se toma de `knowledge/fields/fields.json`, los documentos de fase y
las pruebas físicas registradas.

## Matriz de acciones SK

| # | Función CRDE | Estado en SK-Under | Clasificación | Evidencia SK-Under | Dependencias | Complejidad | Prioridad |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Buy plant pots | Sin escritor de compra o desbloqueo de macetas | Ausente | `plantPotData` solo aparece en el lector legacy | Semántica de compra, estados de parcela y derechos de servidor | Media | P2 |
| 2 | Buy reborn card | Tarjeta de renacimiento | IPV | Campo E3 confirmado por el propietario | `gameData` y límites de compra | Baja | P1 |
| 3 | Complete battle pass | Nivel y compra de pase | IPP | Escritor E2, sin prueba física registrada | Temporada, registros de pase y recompensas | Media | P1 |
| 4 | Gold frame all enemies | Sin campo canónico identificado | Investigación | No hay ruta confirmada en las muestras | Colección de enemigos, marcos y posible estado de servidor | Alta | P3 |
| 5 | Research all blueprints | Obtención e investigación individual/masiva | IPP | Codificación textual/entera E2; conserva desconocidos | `itemData.blueprints`, materiales y alias | Media | P1 |
| 6 | Set fish | Fichas de pesca | IPV | Campo E3 confirmado por el propietario | `gameData.fishChip` y mínimo de cuenta | Baja | P1 |
| 7 | Set gems | Gemas | IPV | Editor de gemas validado en fases anteriores | `gameData.gems` y límites de cuenta | Baja | P1 |
| 8 | Set materials maximum count | Materiales y mínimos | IPV | Campos E3 de materiales/semillas | `itemData.materials`, `itemData.seeds`, inventario | Baja | P1 |
| 9 | Set plants maximum count | Parcelas en solo lectura | Ausente | Semántica de `state` no confirmada | `plantPotData`, cultivos y ciclo de crecimiento | Alta | P2 |
| 10 | Set season coins | Monedas de temporada | IPV | Campo E3 confirmado por el propietario | `seasonData.coin` y temporada activa | Baja | P1 |
| 11 | Set starting coins | Sin campo canónico identificado | Investigación | No se ha demostrado una ruta de monedas iniciales | `gameData`, configuración de nueva partida | Media | P3 |
| 12 | Unlock all weapons in forge table | Descubrimiento y elegibilidad de forja | Parcial | E2: `statisticData.object2ObtainTime`, 995 armas, 494 forjables | Contador de obtención, catálogo, cola de forja, evolución y mitológicas | Alta | P1 |
| 13 | Unlock battle pass | Nivel y compra de pase | IPP | Escritor E2 | Temporada y registros de pase | Media | P1 |
| 14 | Unlock everything in hall | Objetos y niveles del vestíbulo | IPP | Escritores E2; causa de banderas probable | `roomDecorateDic`, `roomObjectLevel`, banderas `room_unlock_*`, planos | Alta | P1 |
| 15 | Unlock heroes and skills | Personajes y habilidades | IPV | Políticas `confirmed_by_owner` | `heroUnlock`, `heroSkillUnlock`, catálogo | Media | P1 |
| 16 | Unlock kill effects | Efectos de eliminación | IPV | E3 validado en Android físico el 2026-11-26 | `miscData.unlockedKillEffectIds`; escenas de solo lectura | Baja | P1 |
| 17 | Unlock lobby skins | Apariencias del vestíbulo vía planos | Parcial | Planos E2 y selección activa de solo lectura | Planos de apariencia, `currentRoomDecorate` no resuelto | Media | P2 |
| 18 | Unlock mounts | Sin editor de monturas | Ausente | No hay ruta validada en el editor actual | Identificadores, propiedad y selección de montura | Alta | P3 |
| 19 | Unlock pets | Mascotas | IPP | Escritor E2 | `gameData.petUnlock`, afinidad y variantes | Media | P1 |
| 20 | Unlock plant pots | Sin desbloqueo de macetas | Ausente | Solo lectura legacy | `plantPotData` y estados de desbloqueo | Media | P2 |
| 21 | Unlock reborn card | Tarjeta de renacimiento | IPV | Campo E3 confirmado por el propietario | `gameData` y límites | Baja | P1 |
| 22 | Unlock skins | Skins de personaje | IPV | Política `confirmed_by_owner` | `skinLock`, catálogo y compatibilidad | Media | P1 |
| 23 | Unlock trophies | Sin editor de trofeos | Ausente | No hay catálogo/ruta de escritura validada | Identificadores, propiedad y condiciones | Alta | P3 |
| 24 | Unlock weapon skins | Skins cosméticas de arma | IPV | E3 validado en Android físico el 2026-11-26 | `weaponEvolutionData.weapons.*.UnlockedSkins`; no concede arma base | Baja | P1 |

## Funciones CRDE fuera de las 24 acciones

| Función CRDE | Estado en SK-Under | Clasificación | Notas |
| --- | --- | --- | --- |
| Editor RAW de la partida | Informes y secciones tipadas; no edición arbitraria | Parcial | SK-Under prioriza campos validados y diff granular frente a edición libre. |
| Migrar datos entre cuentas | No implementado | Ausente intencional | Alto riesgo de identidad, derechos y corrupción; no es objetivo de paridad. |
| Eliminar cuenta | No implementado | Ausente intencional | Fuera del alcance del editor; se recomienda usar el canal oficial. |
| Cambiar contraseña | No implementado | Ausente intencional | Gestión de credenciales ajena al editor de partidas. |
| API key y planes | No aplica | No aplica | SK-Under no revende créditos ni acciones. |
| Historial de pagos | No aplica | No aplica | Sin modelo de compras. |
| Modo demo | No aplica | No aplica | SK-Under opera con sesión nativa propia. |

## Ventajas de SK-Under que CRDE no muestra

- Selección individual por identificador, búsqueda y filtros.
- Valores actuales y propuestos antes de preparar.
- Un solo candidato para varias categorías y una sola subida.
- Respaldo automático previo, revisión explícita y rollback exacto.
- Catálogos versionados 8.8.0 con validación de esquema y recuento.
- Conservación de identificadores desconocidos y rechazo de valores no
  evidenciados.
- Pruebas unitarias, de integración y Playwright en móvil, tableta y escritorio.
- Conectividad nativa Linux hacia la nube del juego, sin depender de CRDE.

## Dependencias de la paridad de armas

`statisticData.object2ObtainTime` se interpreta como contador de adquisición,
no como cantidad ni fecha Unix. La fase 9.4 solo eleva contadores ausentes o en
cero a `1`. La cola `itemData.forgeWeapons` es transitoria y no se escribe como
desbloqueo. La posesión base, la evolución, las mitológicas y los planos son
sistemas independientes que requieren evidencia coordinada.

## Prioridad recomendada

1. **P1:** cerrar validación física de forja/descubrimiento, planos, pase,
   mascotas y vestíbulo; conservar E3 de skins y efectos.
2. **P2:** macetas/cultivos, apariencias de vestíbulo y funciones de cuenta que
   no comprometan derechos de servidor.
3. **P3:** marcos de enemigos, monedas iniciales, monturas y trofeos, solo tras
   localizar estructuras canónicas y valores legítimos.
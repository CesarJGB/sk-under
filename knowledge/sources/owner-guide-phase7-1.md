# Guía funcional del propietario — fase 7.1

Referencia aportada por el propietario para la fase 7.1. Se acepta como especificación
funcional de destino, no como prueba de que el cliente oficial aplique los cambios.

## Campos y valores indicados

| Archivo local | Campo | Referencia |
| --- | --- | --- |
| `season_data` | `coin` | Monedas de temporada; ejemplo `100000`. |
| `shared_pref` | `reborn_card` | `1` activa la tarjeta de renacimiento gratuita permanente. |
| `item_data` | `cumulativeFishCount` | Un valor estrictamente mayor que 20 permite desbloquear todas las recompensas acumuladas, incluida la tarjeta de acceso diario gratuito a modos. |
| `bp_data` | `seasonData[].Value` | `seasonID`, `curLevel`, `curExp`, `hasBuy`, `freeClaimedLevel`, `paidClaimedLevel`; seleccionar el `seasonID` más alto. |

## Límites de evidencia

- La guía describe el resultado esperado en el archivo local; no demuestra por sí sola
  cómo se serializa o proyecta cada valor en el agregado de nube.
- `season_data.coin` se corresponde con el campo superior `seasonData.coin` observado.
- `shared_pref:reborn_card` es una preferencia local entera. El agregado contiene
  `gameData.rebornCard` booleano, pero la proyección `CoverPlayerPref` no está decompilada
  ni confirmada en dispositivo. La edición remota del booleano es experimental y no
  modifica el PlayerPrefs local.
- El umbral de recompensas acumuladas se implementa sobre `itemData.cumulativeFishCount`.
  Cambiar el progreso no marca recompensas como reclamadas ni acredita el Mode Hopper
  Ticket; la reclamación se realiza en el cliente.
- Los pases históricos no se crean ni se modifican. Solo se edita un registro existente.
  `freeClaimedLevel` y `paidClaimedLevel` se conservan.
- Ningún cambio de `hasBuy` constituye una compra, recibo o derecho de servidor.

## Pruebas pendientes del propietario

1. Editar una cantidad individual y varias cantidades en bloque; recargar y comprobar el
   inventario.
2. Editar semillas y comprobar el jardín.
3. Editar monedas de temporada y abrir la temporada.
4. Activar `gameData.rebornCard` y comprobar si la tarjeta está disponible tras reiniciar.
5. Ajustar el progreso acumulado a 21 y comprobar la barra de recompensas y el ticket.
6. Editar nivel y estado premium local de la temporada más reciente; comprobar que las
   temporadas anteriores y las recompensas reclamadas no cambian.

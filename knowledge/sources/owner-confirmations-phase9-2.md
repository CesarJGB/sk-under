# Confirmaciones del propietario — fase 9.2

Pruebas manuales en un dispositivo Android físico con una cuenta autorizada.

## Confirmado

- La modificación del nivel de determinadas máquinas y objetos del vestíbulo se
  conserva en el juego.
- El desbloqueo efectivo de algunos de esos objetos no funcionó: el objeto podía
  tener un nivel asignado y seguir sin estar disponible.

## Interpretación

La confirmación separa dos operaciones que la fase 9.1 trataba como una sola:

- `gameData.roomObjectLevel` controla el nivel de una instalación ya disponible;
- la disponibilidad depende de las banderas `statisticData.event2Count.room_unlock_*`
  y, en los decorados investigables, de los planos `room_decorate_*`.

Crear `itemData.roomDecorateDic.<objeto> = [0]` no bastó para el desbloqueo
funcional. La fase 9.2 corrige el escritor para crear también las banderas y los
planos conocidos.

## No confirmado

No se ha validado físicamente el nuevo mecanismo completo. En particular:

- la creación de banderas `room_unlock_*` en una cuenta que no las tenía;
- la combinación de bandera y plano en el mismo candidato;
- el efecto de `room_decorate_fishbowl_level`;
- los objetos sin bandera conocida (expendedora y estatua), que dependen solo de
  su plano;
- la persistencia tras reiniciar el juego y volver a descargar la partida.

Hasta esa validación, el desbloqueo del vestíbulo conserva la etiqueta
experimental y no se declara funcional dentro del juego.

## Límites de la evidencia

La confirmación cubre el comportamiento observado en Android. No se extiende a
iOS, a otras versiones del juego ni a objetos distintos de los probados. El
propietario realizará las pruebas manuales del nuevo candidato.
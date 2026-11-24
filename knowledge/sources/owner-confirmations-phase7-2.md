# Confirmaciones del propietario — fase 7.2

El propietario probó la página desplegada junto con Soul Knight en un dispositivo
Android físico. Este documento distingue las confirmaciones explícitas de la
validación general y se incorpora como fuente del Save Knowledge Engine.

## Confirmaciones explícitas

1. **Edición de materiales:** funciona, incluidas las ediciones masivas.
2. **Recompensas acumuladas de pesca:** se pueden canjear correctamente. El campo
   `itemData.cumulativeFishCount` permite habilitar el canje.
3. **Tarjeta de renacimiento permanente:** aparece como comprada dentro del juego.
   `gameData.rebornCard = true` fue suficiente en la prueba real; no fue necesario
   editar directamente el PlayerPrefs local.

## Validación general

La validación general del propietario también comprende:

- semillas (`itemData.seeds`);
- monedas de temporada (`seasonData.coin`).

## Función no probada

El pase de batalla no pudo probarse porque no había un pase disponible para
comprar y validar. Esto no constituye un fallo del editor de pase de batalla y
la función permanece experimental E2.

## Límites de esta evidencia

- Se eleva a E3 el alcance efectivamente probado; no se eleva a E4 porque no hay
  una comprobación de persistencia posterior adicional.
- La validación en dispositivo no demuestra el comportamiento de funciones no
  probadas, en particular el pase de batalla y el editor de mascotas.
- Las mascotas, sus variantes de skin y el alimento se incorporan en la fase 7.2
  como funciones experimentales E2 pendientes de prueba en Android físico.
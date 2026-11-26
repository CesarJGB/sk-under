# Observaciones propias — fase 9.1

Muestras de guardado descargadas en modo de solo lectura desde dos cuentas
autorizadas por el propietario, comparadas con muestras descifradas de fases
anteriores. No se conservan credenciales, tokens, identificadores privados ni
guardados completos en el repositorio.

## Metodología

- Descarga remota de solo lectura mediante los mecanismos existentes de
  SK-Under, sin ninguna subida ni modificación remota.
- Descifrado y validación de integridad de las muestras locales.
- Comparación estructural y semántica entre una cuenta con progreso avanzado
  (A) y una cuenta nueva (B), contrastada con catálogos y con muestras propias
  anteriores.
- Los identificadores publicados son únicamente claves de configuración del
  juego observadas en los guardados; no se publican valores privados de las
  cuentas.

## Observaciones usadas en catálogos

- Planos decorativos observados en los guardados y ausentes de la proyección
  8.8 del catálogo externo: `garden_skin_3`, `garden_skin_4`,
  `hall_skin_2`…`hall_skin_5`, `magic_area_skin_2`…`magic_area_skin_4`,
  `multi_room_skin_11`…`multi_room_skin_21`, `work_shop_skin_3`,
  `work_shop_skin_4`, `mboar2`, `mcristal`, `mspider`, `mvaken`,
  `weapon_388`, `weapon_389`, `weapon_400`, `weapon_401`,
  `skin_werewolf_23`.
- Objetos del vestíbulo observados en `itemData.roomDecorateDic`:
  `ItemEggMachine`, `ItemTrashCan`, `ObjectBooks`, `ObjectDrinkSeller`,
  `ObjectFishBowl`, `ObjectMagicWell`, `ObjectMysteriouStatue`,
  `ObjectPlant`, `ObjectSafe`, `PetFood`.

## Límites

- La presencia de un identificador en una cuenta no demuestra por sí sola una
  relación causal ni la eficacia de un escritor.
- Los nombres en español de los elementos observados son etiquetas de la
  interfaz, no traducciones oficiales.
- Las funciones que crean claves o modifican estados conservan la etiqueta
  experimental hasta su validación en Android físico.
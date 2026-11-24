# Limitaciones de la fase 7.0

La base de conocimiento es amplia, pero no es una especificación oficial del
juego ni una garantía de que todos los campos sean editables.

## Fuentes

- **SKDFE no declara licencia** en el commit consultado. Por eso SK-Under no
  redistribuye CSV, HTML de la wiki, sprites, volcados completos ni textos largos.
  Solo conserva identificadores, nombres normalizados, recuentos y relaciones
  factuales con procedencia.
- **No hay acceso a todas las versiones del juego**. La comparación histórica se
  limita a las muestras 8.6.0 y 8.8.0 y a los catálogos SKDFE 8.6.0, 8.7.0 y
  8.8.0. No se declara compatibilidad con 8.5.0 ni con versiones futuras.
- **`data.json` y `weapon_skins.json` de SKDFE** tienen forma de guardado, pero
  no se ha demostrado que sean guardados auténticos. Se usan como referencias E1,
  nunca como observaciones propias ni como prueba de posesión.
- **La metadata IL2CPP** confirma nombres y tipos declarados, no el uso real de
  cada campo en una partida. Muchos campos nuevos quedan en E1.
- **El TXT de Discord** es una referencia comunitaria E1. Sus patrones de
  PlayerPrefs no se elevaron a E2 sin una observación propia.

## Cobertura

- 616 campos registrados: 194 en E1, 406 en E2, 10 en E3 y 6 en E4. La fase 7.2
  elevó cinco funciones a E3 por confirmación del propietario; no se añadió ningún E4.
- Muchos elementos de catálogo no tienen nombre localizado. Se conserva `null`
  en lugar de inventar un nombre.
- Los planos, tokens, trofeos, vales y joyería tienen cobertura de identificadores
  desigual. La presencia en el catálogo no implica posesión.
- No se catalogaron todos los textos de misión, correos, diálogos ni objetos
  internos sin relación demostrada con el guardado.

## Comportamiento

- Ningún campo nuevo se habilitó para edición. Todas las entradas nuevas tienen
  política de solo lectura.
- Las relaciones `observed` describen coaparición; no demuestran causalidad.
- Las relaciones `hypothesis` y `negative` están marcadas para evitar que futuras
  fases confundan campos con nombres parecidos.
- La tarjeta de resurrección, los derechos de compra y los historiales de compra
  no se editan ni se consideran derechos locales.

## Reproducibilidad

- Los catálogos se pueden regenerar desde una copia local de SKDFE en el commit
  fijado. Sin esa copia, las herramientas de validación siguen funcionando sobre
  los artefactos versionados, pero `build_catalog --check` no puede comparar.
- Las pruebas con una fixture sintética verifican el pipeline sin depender de
  SKDFE ni de red.
- Las diferencias de versión se generaron con `git show` sobre los commits
  fijados; no se descargaron binarios del juego.
## Fase 7.2 — mascotas y consolidación

- El propietario confirmó en Android físico la edición de materiales (incluida la
  masiva), el canje de recompensas acumuladas con `itemData.cumulativeFishCount`,
  `gameData.rebornCard = true` para la tarjeta permanente y, dentro de la
  validación general, semillas y moneda de temporada. Esas funciones se elevaron
  a E3 con política `confirmed_by_owner`.
- El pase de batalla no se pudo probar porque no había un pase disponible. Sigue
  experimental E2; esto no se interpreta como un fallo del editor.
- No se elevó ninguna función a E4: falta una comprobación de persistencia
  posterior independiente.
- Las 58 mascotas se identifican en `gameData.petUnlock`. El código 57 es
  `FishChipKing`, confirmado por guardados y nube reales, aunque no aparezca en
  `pet_code_name.json` de SKDFE.
- No se encontró un mapa de bloqueo de skins de mascota separado. Las 12
  variantes `Cat1..Cat7`, `Dog1..Dog3`, `Pig1` y `Rabbit1` se catalogan como
  hipótesis E2 y comparten `gameData.petUnlock.<variante>`. El editor incluye la
  mascota base al seleccionar una variante, pero la relación no está confirmada
  en dispositivo.
- La progresión se observa en `statisticData.event2Count` mediante
  `pet_<ID>_intimacy`, `pet_<ID>_full_intimacy`, `pet_<ID>_action_unlock` y el
  global `pet_full_intimacy`. Los máximos observados varían (180, 240 y 300) y la
  configuración por mascota no está recuperada; la progresión es de solo lectura
  y no se simulan máximos con 999, 9999 ni Int32.MaxValue.
- `material_grain` (Pet Treats) y `material_battery` (Battery) son los alimentos
  identificados. Ambos pertenecen a `itemData.materials`; el editor reutiliza ese
  escritor y rechaza cantidades contradictorias en el mismo lote.
- Ninguna función de mascotas se declara validada en Soul Knight: las pruebas
  automatizadas solo verifican estructura, atomicidad y persistencia en la nube.

# Copia local y modificación

## Procedimiento nuevo

Con `adb root`, se hizo un `tar` privado de `files/` y `shared_prefs/` antes de limpiar los datos del cliente; se verificó que el tar se puede listar (9.294.848 bytes). A partir de `files/game.data` de esa copia, se ejecutaron `decode_game_data`, cambio de `gems` a `424242`, `encode_game_data` y relectura de la copia escrita, sin modificar el respaldo. La relectura devuelve las 41 claves y el valor modificado; los demás campos conservan sus valores. Original y copia editada están fuera del repositorio.

## Interpretación

Esto confirma el roundtrip local de esta muestra, **no** que el cliente use el valor, lo muestre en el HUD ni lo conserve al reiniciar. La copia modificada no se ha sincronizado con la nube. No se ha establecido una correspondencia de campos entre el agregado legacy vacío y el estado local. Las observaciones de HUD de 5.7 no son un experimento nuevo de esta fase.

**Hipótesis confirmada:** el codificador y decodificador locales preservan esta modificación en disco. **Pendiente:** aceptación por el cliente y persistencia después de reiniciar. **Siguiente experimento:** con tutorial completado y copia de seguridad, cargar el archivo modificado en modo local, observar HUD, forzar guardado normal y releer tras reinicio, sin sincronizar la modificación a la nube.

## Copia posterior al tutorial

Se extrajo y listó un segundo tar privado con `files/` y `shared_prefs/` (9.800.704 bytes) desde el hall, después de que la interfaz mostrara la finalización del tutorial, el desbloqueo y 1.000 gemas. Ese tar contiene 20 archivos `.data`; frente al respaldo anterior a `pm clear`, ocho archivos comunes tienen bytes distintos. Esta comparación atraviesa el borrado y la sesión nueva, por lo que no atribuye cada diferencia al tutorial. `game.data` se descifró con 41 claves y contenía `gems=0` y `lastGems=0`; respecto al respaldo anterior solo cambió `generalSeed`. La recompensa observada en pantalla no demuestra que esos bytes ya estuvieran actualizados. La copia modificada de esta fase no se instaló ni se subió.

La recuperación oficial posterior sí cambió `game.data.gems` de 0 a 1.000. La prueba de edición artificial descrita arriba se ejecutó solo sobre una copia fuera del dispositivo; no se demostró que el juego muestre o conserve una edición artificial tras reiniciar y no se subió a la nube. La [comparación y límites](cloud-roundtrip.md) distingue la recuperación legítima de esa edición experimental.

# Archivos y reconstrucción

En Android 15 se inspeccionaron las rutas de la instalación limpia después del primer arranque. Los comandos usaron ADB con los permisos normales del dispositivo de prueba.

| Prueba | Resultado y alcance |
| --- | --- |
| `run-as com.ChillyRoom.DungeonShooter id` | Android rechazó el paquete porque es de producción y no depurable. Se usó `id` como comprobación de permisos. |
| `ls -d /data/user/0/com.ChillyRoom.DungeonShooter/files` | `Permission denied`. El resultado mide el límite de ADB en una instalación del APK distribuido. |
| `/sdcard/Android/data/com.ChillyRoom.DungeonShooter/files` | Ruta visible vía ADB. En ese punto inicial había 21 archivos accesibles, cero con extensión `.data` y cero con extensión `.rij`. Solo se enumeraron para obtener conteos de la instalación de prueba. |
| `/sdcard/Android/media/com.ChillyRoom.DungeonShooter` | Ruta ausente en el primer arranque. |

La visibilidad del directorio externo para el usuario `shell` de ADB es específica de ese entorno. Una aplicación auxiliar está sujeta a las reglas de almacenamiento de Android 11 o posterior. Si el juego ofrece una exportación mediante el selector oficial, esa salida se puede inspeccionar por separado. [Almacenamiento de Android 11](https://developer.android.com/about/versions/11/privacy/storage)

En la imagen de Android 11, el mismo sondeo devolvió `run-as=paquete no depurable` y acceso denegado tanto para la ruta interna como para la externa de `Android/data`. La ruta de `Android/media` estaba ausente. Estos resultados de ADB dependen de la imagen del sistema y del estado del dispositivo.

Tras restaurar con éxito en Android 11, se repitió el sondeo con `uid=2000(shell)` y se intentó copiar `game.data` tanto de la ruta interna como de la externa mediante `adb pull`. Ambas lecturas devolvieron **permiso denegado**. En `/sdcard/Download` tampoco se encontraron archivos candidatos. El gestor de paquetes registró el APK sin `ALLOW_BACKUP` y el gestor de copias de Android estaba deshabilitado en el AVD. Se probó `adb backup` limitado al paquete, con archivo temporal en memoria. Aunque el comando devolvió código 0, produjo cero bytes. El único resultado de progreso accesible fue la representación visible del cliente.

## Comparación verificable

- Las nueve referencias de 8.6.0 son archivos individuales que el adaptador local del editor reconoce y devuelve byte a byte. Las pruebas de regresión volvieron a ejecutarse con ese conjunto. Son la referencia para contrastar un futuro materializado local de 8.8.0. [Guardados locales de Fase 4](../phase4/guardados-locales.md)
- `CloudSaveGameData` reúne identificadores, progreso general y subsistemas. La Fase 5 relacionó miembros de ese modelo con las nueve familias locales. El reconstructor acepta el objeto JSON UTF-8 o su versión gzip. [Reconstrucción de Fase 5](../phase5/reconstruccion.md)
- El juego reconstruyó la partida en el dispositivo. La enumeración y los intentos de copia carecen de bytes del guardado para el backend. Una comparación de formatos requiere una copia que Android o el proveedor permita exportar, su tamaño y SHA-256 y una identificación de formato. Si se obtiene material local por subsistema, se compara con 8.6.0. Si se obtiene el agregado, se prueba el reconstructor experimental. El resumen resultante debe concordar con los valores observados tras restaurar.

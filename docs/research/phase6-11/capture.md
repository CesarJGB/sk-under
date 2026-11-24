# Protocolo de captura de gemas

Usar una cuenta y un perfil de laboratorio con saldo suficiente para el ensayo. Confirmar el respaldo original y su lectura antes de usar la función de recuperación que sobrescribe el estado local. Identificar APK, build, versión que aparece en pantalla (incluido el hotfix), zona horaria y hora de cada paso. Anotar el saldo visible y el precio o premio exacto. Tomar una captura con el HUD en cada punto. Conservar los archivos en un directorio privado.

1. **Control.** Desde el vestíbulo en reposo, tomar `00-base.tar` y `01-control.tar` tras esperar unos segundos sin actuar. Sirven para reconocer cambios que ocurren por el paso del tiempo.
2. **Recompensa.** Reclamar una sola recompensa de gemas, sin comprar ni cerrar el juego. Tomar `02-recompensa.tar` de inmediato y `03-recompensa-guardada.tar` después de volver al menú y de que termine el guardado normal. Distingue escritura inmediata de las preferencias, guardado del archivo y acumulados de ganancia.
3. **Compra.** Desde el último estado guardado, gastar gemas una sola vez en un objeto con precio conocido. Capturar `04-compra.tar` de inmediato y `05-compra-guardada.tar` tras guardado normal. Si el dispositivo ya presenta el saldo discrepante, tomar un par equivalente antes y después de la primera compra que lo reproduzca. Registrar si el cobro coincide con el HUD inicial menos el precio o con otro saldo menos el precio. No crear una discrepancia nueva editando la partida para esta prueba.
4. **Mejora.** Con saldo y nivel conocidos, mejorar un único personaje un nivel. Capturar `06-mejora.tar` y `07-mejora-guardada.tar`. Comprueba qué update comparte la mejora con la compra y qué cambia solo en el personaje.
5. **Reinicio.** Cerrar normalmente después del guardado, abrir de nuevo y tomar `08-reinicio.tar` al volver al vestíbulo. Comprueba si el estado efectivo persiste sin volver a recuperar.
6. **Nube.** En el perfil de laboratorio, tomar `09-pre-subida.tar`, guardar mediante la interfaz oficial y, cuando confirme, tomar `10-post-subida.tar` y el agregado `10-nube.json`. Capturar `11-pre-recuperar.tar` y verificar que la copia remota corresponde a ese perfil antes de recuperar con la interfaz oficial. Tomar `12-post-recuperar.tar` y volver a descargar como `12-nube.json`. Comprueba qué valores se serializan y cuáles se restauran o permanecen locales. La ausencia de acceso al archivo local en un dispositivo de producción se registra como dato faltante.

En un AVD o dispositivo de laboratorio con acceso de lectura al directorio de la aplicación, la captura usada en las fases previas es:

```bash
umask 077
adb -s SERIAL exec-out tar -C /data/user/0/com.ChillyRoom.DungeonShooter \
  -cf - files shared_prefs > 00-base.tar
tar -tf 00-base.tar > /dev/null
adb -s SERIAL exec-out screencap -p > 00-base.png
```

Repetir con el nombre de cada punto. Si solo se dispone de permiso para exportar el agregado, usar la descarga autorizada [documentada en 5.9](../phase5-9/download.md) y capturar el HUD. No enviar sesiones ni preferencias completas a GitHub. Para interpretar casos con varios perfiles, confirmar localmente cuál es el perfil observado antes de atribuir cambios.

Desde `backend/`:

```bash
PYTHONPATH=. uv run --locked python ../docs/research/phase6-11/tools/compare_saves.py \
  /ruta/privada/03-recompensa-guardada.tar /ruta/privada/04-compra.tar
```

El comparador acepta tar de ADB, `game.data` o un agregado JSON/gzip válido. Muestra los cinco campos por capa, variaciones, número de diferencias estructurales y archivos que cambiaron entre dos tar. Puede incorporar `backup.data` si existe y es decodificable. La opción `--details` muestra rutas de propiedades y valores anteriores y posteriores. Revisar y anonimizar la salida antes de compartirla, pues nombres de archivos, rutas y otros valores pueden identificar cuentas. Los índices de listas se comparan por posición. Una captura con un archivo modificado fuera de `game.data` o de las claves conocidas de preferencias señala dónde investigar, sin atribuirle todavía una función.

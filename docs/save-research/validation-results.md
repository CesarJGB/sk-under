# Validación de la fase 6.11.1

## Regresión reproducida

`4855656` seguía preparando un candidato con un cambio en `gameData.gems`. En `ef5c01f`, `CloudLabService.prepare` exigió `validate_gems_transition` y la confirmación pasó a verificar la misma política. Sobre un original coherente con `gems=1000`, `lastGems=1500` y `varGems=-500`, la regla exigía que el objetivo siguiera siendo 1000. Se reprodujeron candidatos 0, 999 y 1001 rechazados con `inconsistent_gems_balance`. La única preparación admisible era 1000, que producía una operación sin cambios. En el navegador, los códigos nuevos quedaban fuera de la tabla de mensajes de la vista nativa y se mostraba el aviso genérico. El mismo diagnóstico se confirmó en la cuenta de laboratorio, cuyo guardado previo conservaba una discrepancia de fases anteriores.

`resource_consistency.py` planifica el cambio con la evidencia observada. Un original coherente cambia `gems` y `varGems`. Un original discrepante se puede conciliar usando el saldo que ya indican sus dos contadores. La preparación valida el esquema, el rango del saldo y de la variación y la serialización canónica. Reabre el candidato y vuelve a obtener los bytes originales al restaurar las rutas del plan. Los totales históricos son opcionales. Un original con las dependencias mínimas ausentes conserva la lectura y la opción de verificar respaldos, con un error específico al intentar editar.

La confirmación reproduce el plan a partir del original y comprueba los bytes del candidato guardado, su huella, la vigencia de la copia remota y la autorización existente. Un borrador que cambia solo el saldo sobre un original coherente sigue siendo verificable como respaldo histórico. Para subir una edición en ese caso hay que generarla de nuevo. Los respaldos actuales y antiguos conservan su formato. La respuesta de preparación añade `changed_fields`. La vista nativa muestra cuándo también cambia la variación y distingue errores de esquema, dependencias, sesión, integridad y conexión.

## Pruebas automatizadas

| Alcance | Comprobación | Resultado local |
| --- | --- | --- |
| Backend, unitarias e integración HTTP con proveedores falsos | Rangos, valores positivos y negativos de variación, dependencias ausentes, tipos, versiones, confirmaciones simultáneas, huella y cambios de partida entre operaciones, restauración antigua y actual, aislamiento de cuentas y cifrado. | **472 aprobadas** en toda la suite con muestras privadas. |
| Archivos y respuesta auténticos archivados | Exportación y reapertura 8.6.0 / 8.8.0, copia de nube y archivo restaurado, respuesta de red archivada y decodificación. | Incluidas en las 472. La respuesta archivada se reproduce localmente. |
| Frontend | `npm run build` y Playwright en Chromium con API simulada. Confirmación de la vista previa y mensajes diferenciados. | Compilación aprobada, **33 aprobadas**. |

```bash
cd backend
SK_PHASE4_CIPHER_ENV_FILE="$CIPHER_ENV" \
SK_PHASE4_SAMPLES_DIR="$SAMPLES_860" \
SK_PHASE56_880_DIR="$FILES_880" \
SK_PHASE58_CLOUD_JSON="$CLOUD_880" \
SK_PHASE58_RESTORED_GAME="$RESTORED_GAME" \
SK_PHASE59_WIRE_RESPONSE="$CAPTURED_RESPONSE" \
uv run --locked pytest -q
uv run --locked python -m compileall -q app
cd ../frontend
npm ci
npx playwright install chromium
npm run build
npm run test:browser
```

`CIPHER_ENV` apunta al archivo privado del códec. Las otras variables son rutas a archivos de laboratorio. `CAPTURED_RESPONSE` apunta a una respuesta exitosa de 5.9 con 1.000 gemas. En el laboratorio se utilizó `linux-response-2.bin`. Sin esas variables, pytest excluye deliberadamente los casos privados.

## ChillyRoom y cliente oficial

El backend local de esta rama autenticó una cuenta propia de laboratorio por la ruta nativa de producción, verificó su identidad, descargó una copia real y la cotejó con la identidad de la prueba 6.1. La escritura se habilitó solo en esa instancia y para el perfil de laboratorio. Se reutilizó la sesión entre ejecuciones del backend y se comprobó que los archivos de respaldo estaban sellados. La API de ChillyRoom aceptó las dos confirmaciones y devolvió exactamente los bytes esperados al volver a descargar y verificar. Los valores son los de esa cuenta de laboratorio.

| Operación | Gemas antes → después | Rutas modificadas |
| --- | --- | --- |
| Conciliación | 99.999 → 1.000 | `gameData.gems` |
| Edición de saldo coherente | 1.000 → 1.001 | `gameData.gems`, `gameData.varGems` |

El cliente oficial Android Global 8.8.0, hotfix 8.8.0.11, se ejecutó en un AVD API 30. Tras autenticarse, abrió el panel de nube y recuperó la partida mediante **Retrieve Progress**. La fila remota mostró 1.001. La fila local pasó de 0 a 1.001. `files/game.data` y PlayerPrefs adquirieron la tupla `(1001, 0, 1001, 1000, 0)` en el orden del [registro de gemas](../research/phase6-11/README.md). La captura previa preserva el estado local original del AVD. El diferencial de la edición se calculó entre agregados. Las diferencias de recuperar una partida completa en Android corresponden a una comparación distinta.

| Acción en el cliente oficial | HUD | PlayerPrefs | `game.data` |
| --- | ---: | --- | --- |
| Recuperación de la copia editada | 1001 | `(1001, 0, 1001, 1000, 0)` | `(1001, 0, 1001, 1000, 0)` |
| Recompensa guiada de 500 | 1501 | `(1501, 1001, 500, 1500, 0)` | Conservó la tupla de recuperación hasta el guardado. |
| Mejora del Caballero por 500 | 1001 | `(1001, 1501, -500, 1500, 500)` | Conservó la tupla de recuperación hasta el guardado. |
| Vuelta al título, guardado y reinicio del proceso | 1001 antes de cerrar | `(1001, 1501, -500, 1500, 500)` | `(1001, 1501, -500, 1500, 500)` antes y después del reinicio. |

El panel y las preferencias confirmaron que la recompensa se sumó a 1.001 y que luego la mejora cobró 500 sobre 1.501. El cliente guio la recompensa como primera transacción tras la recuperación. Queda por repetir con un perfil que haga un gasto como primera transacción. Después del ensayo se restauraron ambos respaldos en orden inverso con la ruta nativa `restore`. Dos descargas sucesivas verificaron primero el estado conciliado y luego los bytes exactos del original anterior a la prueba.

Las capturas y archivos se conservan en el laboratorio privado de 6.11.1. Los pares de archivos `08-before-retrieve.tar` / `10-after-retrieve.tar`, `16-reward.tar` / `17-upgrade.tar` y `22-saved.tar` / `23-restarted.tar` reproducen recuperación, cargo y reinicio respectivamente.

## Repetición en Android físico

La verificación adicional en un teléfono propio usa el mismo ciclo de la [guía de captura](../research/phase6-11/capture.md). Abre `/partida` en una instancia de prueba, inicia sesión en Android Global, descarga, prepara el saldo elegido, confirma y verifica la descarga. En el teléfono inicia sesión en el mismo perfil, conserva una copia propia, recupera mediante el panel oficial y haz un gasto normal de precio conocido. Guarda, cierra y vuelve a arrancar antes de comprobar el HUD. Si el dispositivo de laboratorio permite leer el directorio de la app, ejecuta los comandos en cada punto de captura:

```bash
adb devices -l
umask 077
adb -s "$ANDROID_SERIAL" shell dumpsys package com.ChillyRoom.DungeonShooter | rg 'versionName|versionCode'
adb -s "$ANDROID_SERIAL" exec-out screencap -p > "$POINT.png"
adb -s "$ANDROID_SERIAL" exec-out tar -C /data/user/0/com.ChillyRoom.DungeonShooter \
  -cf - files shared_prefs > "$POINT.tar"
tar -tf "$POINT.tar" > /dev/null
cd backend
PYTHONPATH=. uv run --locked python ../docs/research/phase6-11/tools/compare_saves.py \
  "$BEFORE_TAR" "$AFTER_TAR"
```

Compara el HUD, la reducción por el precio, la base previa, la variación negativa y el aumento del total consumido. Si no hay permiso para leer los archivos privados, contrasta el HUD y las descargas de la interfaz oficial. Registra el APK y el hotfix. Para una instalación existente se aplican las [instrucciones de Coolify y frontend](../research/phase6-9/deployment.md). La fase no requiere migrar el formato de respaldo ni añadir variables de entorno de producción.

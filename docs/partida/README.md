# Partida y persistencia de respaldos

## Hallazgo en producción

El 25 de noviembre de 2026 se inspeccionó en solo lectura el backend de Coolify que ejecutaba `46ab731`. Docker mostraba dos volúmenes de lectura y escritura, montados en `/var/lib/sk-under/accounts` y `/var/lib/sk-under/backups`. Las rutas efectivas del flujo nativo eran `/var/lib/sk-under/native` y `/var/lib/sk-under/native-backups`. Ambas eran accesibles con UID/GID `10001:10001` y modo `0700` en la capa escribible del contenedor.

Coolify registró recreaciones por webhook en `3b7262d`, `c4b46c5` y `46ab731`. En la inspección solo quedaba el contenedor actual, creado a las 20:51 UTC. Su almacén de respaldos nativos tenía cero directorios de cuenta, mientras que los volúmenes legacy conservaban tres registros de laboratorio y uno de cuentas vinculadas. Guardar respaldos nativos fuera de los volúmenes explica que el historial quede vacío al reemplazar el contenedor. La inspección confirma el defecto de persistencia y el vacío actual. La recuperación de ediciones concretas requeriría encontrar una copia privada anterior. [Cómo conserva datos Coolify](https://coolify.io/docs/core/persistent-storage/storage-mounts/overview).

La clave de sesiones estaba configurada y la de respaldos se derivaba de ella. El estado actual de las claves se comprobó sin imprimirlas. Quedan por comprobar su continuidad histórica, la identidad usada por las ediciones concretas y si existe una copia anterior fuera del contenedor. Los registros legacy pertenecen a almacenes separados. Asociarlos a un titular exige evidencia independiente de identidad.

La causa inmediata del mensaje «El servidor aún no ofrece el estado del historial» era distinta del vacío: el dominio servía `46ab731`, anterior a la ruta `/api/v1/cloud/native/backups`, y el frontend traducía cualquier respuesta sin `total` a ese texto. La comprobación de versión y las capacidades evitan confundir un backend antiguo con un historial vacío. Los dos defectos se corrigieron juntos: contrato compatible y montajes persistentes.

## Creación y lectura

El editor envía el plan junto con la huella de su descarga a `prepare-unified`. El backend descarga la misma cuenta, comprueba la huella, genera el candidato con el editor existente y publica juntos el original exacto, el candidato y sus metadatos cifrados. El guardado sincroniza los archivos y directorios antes de devolver el identificador. Confirmar vuelve a leer el respaldo completo, verifica sus hashes, reproduce el candidato y compara la partida remota con el original. Un fallo de almacenamiento o de integridad detiene la subida. Restaurar conserva la confirmación explícita y la comprobación de que la nube coincide con el original o el candidato de ese respaldo.

Preparar, confirmar, listar y restaurar usan el mismo directorio por cuenta. El identificador se deriva de la identidad autenticada con la clave del almacén de sesiones. La descarga comprueba además su asociación con la partida del titular. Cambiar `SK_NATIVE_STORE_KEY` altera el identificador derivado y, si aplica, también la clave de respaldos. Cambiar solo `SK_NATIVE_BACKUP_KEY` conserva el identificador pero impide leer los respaldos cifrados con la clave anterior.

El historial devuelve el total de registros encontrados para la cuenta, una página de hasta 25 y un cursor opaco para pedir la siguiente. La paginación es por clave estable `(fecha, identificador)`: insertar un respaldo nuevo mientras se consulta no duplica ni salta registros ya mostrados. El botón «Cargar más respaldos» solicita solo la página siguiente; nunca se descargan ni descifran todas las partidas al abrir. El índice lee únicamente los metadatos autenticados de cada registro v2 para pintar tipo, fecha, categorías y resumen, y verifica la partida completa al restaurar o verificar.

Cada registro distingue su origen: automático antes de una edición, manual, preventivo antes de una restauración o histórico compatible. Los respaldos manuales y preventivos son copias completas de la partida y no escriben en ChillyRoom. La integridad del archivo se muestra por separado del estado de la subida remota. Los estados visibles incluyen edición preparada, subida verificada, subida no verificada, operación interrumpida, respaldo disponible, restauración verificada o no verificada y respaldo ilegible. Un fallo de almacenamiento no se presenta como historial vacío.

El respaldo automático se verifica leyendo de nuevo el original y su candidato antes de permitir cualquier escritura. Crear un respaldo manual descarga la partida, la cifra en el almacén persistente y confirma su lectura; no modifica la nube. Restaurar una versión histórica exige confirmación explícita con fecha y resumen, comprueba la huella de la partida actual, crea y verifica un respaldo preventivo, vuelve a comprobar que la nube no cambió y solo entonces escribe los bytes originales. Después descarga y verifica el resultado. El preventivo aparece como un punto independiente; restaurarlo deshace la restauración. El protocolo de subida de ChillyRoom no ofrece una transacción entre descarga y escritura, por lo que la comprobación previa reduce pero no elimina la ventana de concurrencia.

El endpoint público `GET /api/v1/version` expone la versión del contrato, las capacidades de respaldos y el commit desplegado. El frontend lo consulta para distinguir un backend incompatible de un historial vacío o de un error temporal. Solo las rutas de datos exigen sesión.

## Compatibilidad

Los lectores de gemas, fichas de pesca, progreso de pesca, personajes, habilidades, skins y planes unificados conservan la verificación de los formatos conocidos. Para los planes avanzados de la fase 7.1, la comparación estricta con el plan actual rechazaba registros válidos porque la fase 7.2 añadió dos campos opcionales. El lector reconoce la forma exacta anterior y añade sus valores neutros en memoria. A continuación reproduce el candidato y compara sus bytes y huellas como antes. Los archivos históricos permanecen intactos.

Los archivos de la fase 6.8 guardados en claro bajo una instalación anterior se identifican como ilegibles cuando se configura cifrado. Si se encuentran, primero conserva una copia intacta y comprueba su procedencia. La migración administrativa existente puede probarse sobre una copia separada, con una clave de destino conservada y comprobación de bytes antes y después. Para claves antiguas o formatos aún incompatibles, conserva el material original y prueba la recuperación en un entorno aislado.

Los registros anteriores al formato 2 siguen siendo legibles: se interpretan como automáticos de edición y conservan sus hashes y planes. Los registros nuevos añaden tipo, categorías, conteo de cambios y un resumen saneado sin duplicar la partida. Un registro incompatible o ilegible no se restaura ni se reescribe.

## Crecimiento y mantenimiento

Cada edición guarda el original y el candidato; cada respaldo manual o preventivo guarda una copia completa. Los archivos se cifran individualmente y no se comprimen. El historial no borra ni rota respaldos automáticamente: hacerlo impediría deshacer restauraciones antiguas y ocultaría evidencia. El propietario debe revisar el espacio del volumen y conservar copias externas. Un respaldo en el volumen de Docker sobrevive a reinicios y recreaciones del contenedor, pero no protege de perder el VPS, el disco o la configuración de Coolify: no sustituye una copia independiente y cifrada fuera del servidor.

El índice se reconstruye leyendo los directorios de cada cuenta, sin un archivo central que pueda quedar desincronizado. La paginación usa la fecha y el identificador del último registro visible. Si en el futuro se añade una base de índice, deberá autenticarse con la misma clave y verificarse contra los archivos antes de restaurar.

## Configuración de Coolify

1. Conserva las variables de runtime y el contenedor actual hasta tener una copia privada y consistente del almacén SQLite nativo y de cualquier directorio nativo de respaldos disponible. Si se usa una copia de archivos de SQLite, hazla con el servicio en pausa y conserva los archivos auxiliares asociados. Conserva en paralelo las claves de runtime en el gestor del propietario.
2. En **Configuration → Persistent Storage**, conserva los montajes legacy y configura dos volúmenes persistentes, uno con destino `/var/lib/sk-under/native` y otro con destino `/var/lib/sk-under/native-backups`. Un volumen existente que ya cubra ambas rutas también es válido. La raíz de cada directorio nativo debe permitir lectura, escritura y acceso al UID/GID `10001:10001`, con modo `0700`. Conserva los mismos volúmenes en los siguientes despliegues. [Volúmenes de Coolify](https://coolify.io/docs/core/persistent-storage/storage-mounts/volume-mounts).
3. Mantén `SK_NATIVE_STORE_DIR` y `SK_NATIVE_BACKUP_DIR` en esos destinos, o monta las rutas efectivas si hay una configuración explícita distinta. Conserva `SK_NATIVE_STORE_KEY`. Si originalmente existía `SK_NATIVE_BACKUP_KEY`, conserva su valor. Si se derivaba de la clave de sesiones, mantén la variable opcional vacía. La imagen nueva activa `SK_NATIVE_BACKUP_REQUIRE_MOUNT` y rechaza el historial y las escrituras nativas cuando la ruta de respaldo queda en la capa efímera o en un montaje temporal.
4. Tras colocar la copia privada en los volúmenes y desplegar, ejecuta los diagnósticos y comprueba que el titular siga viendo su historial al recargar y volver a iniciar sesión. Verifica que la recreación siguiente conserve los mismos montajes, claves y registros sin realizar escrituras en ChillyRoom.

### Migración realizada el 25 de noviembre de 2026

La copia privada se guardó antes de detener el contenedor en `/home/cesar/sk-under-private/phase-native-persistence-20261125T2135` con modo `0600`. Incluye un respaldo consistente de SQLite (`integrity_check=ok`), el directorio nativo en vivo, los volúmenes legacy y el inspect del contenedor. No se encontraron respaldos nativos históricos recuperables: las capas escribibles de contenedores anteriores ya no existen y los volúmenes anónimos restantes pertenecen a otros servicios.

### Diagnóstico de solo lectura

En el host, sustituye el nombre por el que muestra Coolify. El primer comando imprime el UID/GID configurado y los destinos de los montajes. El segundo usa las rutas y las claves efectivas sin imprimir valores de claves, rutas de cuentas o identificadores.

```bash
container='<contenedor-backend-de-Coolify>'
docker inspect --format '{{.Config.User}} {{range .Mounts}}{{.Type}} {{.Destination}} rw={{.RW}}{{println}}{{end}}' "$container"
docker exec -i "$container" python -B - <<'PY'
import os
import re
import stat
from collections import Counter
from app.cloud.backup_store import LabBackupStore
from app.cloud_save import CloudSaveError
from app.settings import Settings

settings = Settings(_env_file=None)
print("UID/GID", os.geteuid(), os.getegid())
print("Clave de sesiones configurada", settings.native_store_key is not None)
print("Clave de respaldos", "explícita" if settings.native_backup_key
      else "derivada" if settings.native_store_key else "ausente")
for path in (settings.native_store_path, settings.native_backup_path):
    try:
        info = path.stat()
        print(path, oct(stat.S_IMODE(info.st_mode)), (info.st_uid, info.st_gid),
              "acceso rwx", os.access(path, os.R_OK | os.W_OK | os.X_OK))
    except OSError as exc:
        print("Directorio inaccesible", type(exc).__name__)

counts = Counter()
try:
    subjects = list(settings.native_backup_path.iterdir())
except OSError as exc:
    print("Almacén no disponible", type(exc).__name__)
    raise SystemExit(1) from None
for subject in subjects:
    if subject.is_symlink() or not re.fullmatch(r"[0-9a-f]{64}", subject.name):
        continue
    store = LabBackupStore(subject, cipher_key=settings.native_backup_key_bytes())
    counts["directorios de cuenta"] += 1
    try:
        entries = list(subject.iterdir())
    except OSError:
        counts["directorios inaccesibles"] += 1
        continue
    for entry in entries:
        if not re.fullmatch(r"[0-9a-f]{32}", entry.name):
            continue
        try:
            store.load(entry.name)
            counts["respaldos legibles"] += 1
        except (CloudSaveError, OSError) as exc:
            counts[type(exc).__name__] += 1
print(dict(counts))
PY
```

## Validación

- Backend local con dependencias bloqueadas. 675 pruebas aprobadas, 16 omitidas. Compilación y verificación del catálogo correctas.
- TypeScript y compilación de Vite correctos. Playwright Chromium con 63 pruebas aprobadas y 23 omitidas. Los tamaños 320, 360, 375, 390 y 430 px mantuvieron el historial sin desplazamiento horizontal, también con el botón de paginación. Tableta y escritorio pasaron la comprobación de ancho.
- Docker aislado sin red. La imagen rechazó la ruta efímera sin volumen. En contenedores sucesivos con el mismo montaje se conservaron el perfil nativo y los bytes exactos de los respaldos cifrados. Las pruebas de almacén cubren respaldo manual, preventivo, restauración histórica, deshacer, paginación con inserción intermedia, interrupción y ausencia de montaje.
- Producción. Actualizada al commit de esta fase con los volúmenes `native` y `native-backups`; la comprobación posterior figura en el informe de entrega. El commit se publica sin `[skip cd]` para que Coolify recree el contenedor.

## Capturas

Datos sintéticos y API simulada en Chromium.

- [320 px](capturas/partida-320.png) · [360 px](capturas/partida-360.png) · [375 px](capturas/partida-375.png) · [390 px](capturas/partida-390.png) · [430 px](capturas/partida-430.png)
- [Tableta](capturas/partida-768.png) · [Escritorio](capturas/partida-1280.png)

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

## Estadísticas de Partida

La tarjeta «Partida en la nube» consume una sola copia de `NativeSaveSummary`: la última partida descargada, o la que devuelve la sesión autenticada al iniciar. El carrusel no realiza solicitudes propias, no descarga partidas al cambiar de página y solo se vuelve a calcular cuando cambia esa copia. Las páginas se generan en bloques de cuatro métricas ordenadas por prioridad; la primera conserva Gemas, Fichas de pesca, Monedas de temporada y Personajes desbloqueados.

El carrusel usa desplazamiento horizontal con `scroll-snap`, páginas de 2 × 2 en móvil y cuatro columnas desde 640 px. Oculta las barras de desplazamiento, contiene el gesto horizontal para no interferir con el desplazamiento vertical, no se reproduce automáticamente y ofrece puntos de paginación, flechas en escritorio y navegación con flechas, Inicio y Fin cuando el visor tiene el foco. La altura de las cuatro páginas es común y el contenido no es editable.

### Registro central

`frontend/src/partidaStats.ts` es la única fuente de verdad de las métricas. Cada entrada declara:

- `id` estable y `label` visible.
- `icon` de la iconografía existente y `category` (`Recursos`, `Colección`, `Inventario`, `Progreso`).
- `priority`, usada para ordenar y paginar sin tocar el componente visual.
- `evidence` con nivel (`E2`, `E3`, `E4`), nota y marca de experimentalidad.
- `extract(save)`, que devuelve un `StatValue` tipado.

Los formatos soportados son cantidad, proporción desbloqueados/total, nivel con máximo opcional, porcentaje, booleano, estado, inventario resumido y los estados explícitos `unavailable` y `error`. `readStat()` captura fallos de extracción y los convierte en `error`; `formatStat()` decide el texto y `statPages()` corta el registro en páginas de cuatro. El componente `StatsCarousel` no conoce métricas concretas.

### Métricas implementadas

| Métrica | Categoría | Formato | Evidencia |
| --- | --- | --- | --- |
| Gemas | Recursos | Cantidad | E4, confirmada |
| Fichas de pesca | Recursos | Cantidad | E4, confirmada |
| Monedas de temporada | Recursos | Cantidad | E3, confirmada |
| Personajes desbloqueados | Colección | Desbloqueados / catálogo | E3, confirmada |
| Habilidades desbloqueadas | Colección | Desbloqueados / catálogo | E3, confirmada |
| Skins desbloqueadas | Colección | Desbloqueados / catálogo | E3, confirmada |
| Mascotas desbloqueadas | Colección | Desbloqueadas / filas observadas | E3, confirmada |
| Materiales | Inventario | Unidades y tipos con cantidad legible | E3, confirmada |
| Alimentos de mascota | Inventario | Unidades y tipos con cantidad legible | E3, confirmada |
| Baterías | Inventario | Cantidad de `material_battery` | E3, confirmada |
| Progreso de pesca | Progreso | Contador acumulado | E3, confirmada |
| Nivel del pase | Progreso | Nivel y máximo solo si existe | E2, experimental |
| Estado del pase | Progreso | Temporada activa o inactiva | E2, experimental |
| Tarjeta de renacimiento | Progreso | Booleano obtenida/no obtenida | E3, confirmada |
| Semillas | Inventario | Unidades y tipos con cantidad legible | E3, confirmada |
| Objetos desbloqueados | Colección | Longitud real de la lista observada | E2, confirmada |

Los inventarios no crean una tarjeta por objeto. Muestran el total de unidades legibles y el número de tipos; si alguna cantidad no se puede interpretar, no se suma y se advierte en la tarjeta. Las proporciones de mascotas usan solo filas con un booleano observado y muestran cuántas filas tienen dato, en lugar de inventar un total de catálogo.

### Cómo añadir una métrica

Añade una entrada a `statMetrics` y devuelve uno de los formatos existentes. No hace falta modificar `StatsCarousel` ni el CSS de paginación:

```ts
{
  id: 'claimed_rewards', label: 'Recompensas reclamadas', icon: Trophy,
  category: 'Progreso', priority: 170,
  evidence: confirmed('E3', 'Lectura validada con una partida real.'),
  extract: (save) => {
    const value = save.report?.some_confirmed_field
    return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
      ? { kind: 'count', value }
      : { kind: 'unavailable', reason: 'La partida no expone este contador' }
  },
}
```

La extracción debe distinguir un cero real de un dato ausente. Nunca debe devolver cero por defecto, sumar cantidades ilegibles, inventar máximos o totales de catálogo ni presentar un campo experimental como confirmado. Para una métrica nueva conviene añadir un fixture de partida y una aserción de estado en `frontend/tests/phase8-editor.spec.ts`.

### Parámetros que todavía no se leen de forma fiable

- **Recompensas de pesca reclamadas.** El informe conserva contadores internos de cofres y fichas extra, pero no una semántica validada de recompensas obtenidas. Mostrarlos como total sería interpretar un detalle de implementación.
- **Máximo y recompensas del pase de batalla.** `max_level` suele faltar y los niveles reclamados son experimentales. Solo se muestra el máximo cuando aparece de forma numérica en la partida; el pase sigue marcado E2.
- **Progreso e intimidad de mascotas.** `pet_progression.available` es falso en las partidas observadas. El catálogo de 58 mascotas no se usa como denominador si faltan observaciones.
- **Totales de colecciones sin catálogo fiable.** Los objetos desbloqueados se muestran como longitud de la lista observada, no como «X de Y». No se inventan totales para categorías sin catálogo validado.
- **Inventario genérico de recursos.** Solo se muestran materiales, alimentos, baterías y semillas con cantidades conocidas. Un recorrido genérico de claves numéricas produciría falsos positivos.
- **Monedas o recursos no confirmados.** No se añaden divisas nuevas sin una validación de lectura y evidencia por plataforma.
- **Estado de personajes bloqueados.** Si la partida no distingue un personaje bloqueado de un dato ausente, la proporción se muestra como no disponible, no como cero.

### Cuenta y respaldos

El correo autenticado se guarda solo dentro del sobre cifrado de la sesión existente y se expone únicamente en la sesión autenticada. No se añadió una tabla ni un almacén de credenciales. Las sesiones anteriores sin correo muestran el alias enmascarado disponible. La tarjeta usa una fila compacta con correo, plataforma, región y versión; el cierre de sesión es un icono de 44 px con nombre accesible y conserva la confirmación.

El historial contraído muestra nombre, fecha y hora, un indicador de estado compacto y el control de expansión. El título es «Respaldos» y debajo solo aparece el total. «Crear respaldo» comparte fila cuando cabe y baja a una fila propia en 320–360 px sin comprimir el título. El detalle expandido conserva integridad, resumen, explicaciones, verificación, restauración y mensajes de error. La confirmación de creación es un aviso temporal de cuatro segundos; los errores y advertencias siguen visibles.

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
- TypeScript y compilación de Vite correctos (`tsc --noEmit && vite build`, 2226 módulos). Playwright Chromium con 66 pruebas aprobadas y 23 omitidas. Los tamaños 320, 360, 375, 390, 430, 768 y 1280 px mantuvieron el historial, la cuenta y el carrusel sin desbordamiento horizontal; el carrusel conserva 2 columnas en móvil y 4 desde tableta, y el botón «Crear respaldo» baja a una fila propia cuando no cabe.
- Docker aislado sin red. La imagen rechazó la ruta efímera sin volumen. En contenedores sucesivos con el mismo montaje se conservaron el perfil nativo y los bytes exactos de los respaldos cifrados. Las pruebas de almacén cubren respaldo manual, preventivo, restauración histórica, deshacer, paginación con inserción intermedia, interrupción y ausencia de montaje.
- Producción. Publicado `eb9cacf8747409e1e045e6a296e4eebd386ef4d0` sin `[skip cd]`. Coolify desplegó un contenedor saludable con los cuatro montajes (`accounts`, `backups`, `native`, `native-backups`); `/api/v1/version` devuelve ese commit y las seis capacidades; `/backups` sin sesión responde 401. Una recreación real con `docker compose … up -d --force-recreate` conservó la integridad del SQLite y los conteos (2 cuentas, 2 perfiles, 1 sesión, 3 eventos), y el sondeo de escritura/borrado en `native-backups` confirmó permisos `10001:10001` y `0700`. Cloudflare Pages sirve la compilación con el historial nuevo. El estado nativo anterior (un SQLite, cero respaldos nativos) se preservó y migró; no se encontraron respaldos nativos históricos recuperables.

## Archivos de esta fase

- Backend: `backend/app/native/store.py`, `backend/app/native/service.py`, `backend/tests/test_native_api.py`.
- Registro y carrusel: `frontend/src/partidaStats.ts`, `frontend/src/StatsCarousel.tsx`.
- Interfaz: `frontend/src/pages/NativeAuthPage.tsx`, `frontend/src/pages/PartidaPanels.tsx`, `frontend/src/styles.css`, `frontend/src/api.ts`.
- Pruebas: `frontend/tests/phase8-editor.spec.ts`, `frontend/tests/native-auth.spec.ts`.
- Documentación y capturas: `docs/partida/README.md`, `docs/partida/capturas/partida-*.png`.

## Capturas

Datos sintéticos y API simulada en Chromium. El carrusel se captura en su primera página; las páginas restantes usan el mismo alto y se navegan con puntos, flechas o teclado.

- [320 px](capturas/partida-320.png) · [360 px](capturas/partida-360.png) · [375 px](capturas/partida-375.png) · [390 px](capturas/partida-390.png) · [430 px](capturas/partida-430.png)
- [Tableta](capturas/partida-768.png) · [Escritorio](capturas/partida-1280.png)

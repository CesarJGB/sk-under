# Fase 6.4 · Cuentas vinculadas y operación en producción

## Auditoría y cambios

La auditoría partió de `dbea084`. Antes del ajuste, `GET /api/v1/health` devolvía `200` y `access_mode=token`. `GET /api/v1/cloud/accounts` devolvía `200`, `configured=false` y «Configura el origen seguro para las cuentas». El valor de `SK_CLOUD_ACCOUNTS_ORIGIN` en Coolify terminaba en `/`. El origen que envía el navegador y la entrada de CORS carecían de esa barra. Cloudflare Pages servía `/partida` con `200` y el preflight de cuentas respondía para el origen autorizado.

Los tres GET administrativos `/cloud/lab/status`, `/cloud/lab/save` y `/cloud/lab/backups` devolvían `401 access_denied` sin el token de acceso. El backend estaba saludable. En el contenedor faltaban la sesión, los identificadores de instalación y el token administrativo. Esto explica los mensajes de laboratorio sin configurar, modo deshabilitado, lectura sin configurar y autorización administrativa ausente. Aunque el interruptor global de escritura ya estaba activo, faltaban los requisitos para escribir desde el laboratorio. Tampoco había volúmenes persistentes.

Se corrigió el origen en Coolify y se añadieron dos volúmenes privados. Tras el despliegue, `GET /cloud/accounts` devolvió `configured=true`. Se configuró el laboratorio con una sesión autorizada de prueba previamente verificada y un token administrativo independiente. Después del segundo despliegue, su estado autenticado devolvió `mode=live` y la descarga real devolvió 1,002 gemas. Los contextos guardados de la CLI devolvieron `401`. Los cambios se aplicaron desde la administración local de Coolify para el recurso de SK Under y el ajuste global de su API quedó como estaba.

### Arquitectura de cuentas

`/partida` usa la cookie de SK Under con `HttpOnly`, `Secure`, `SameSite=Strict` y prefijo `__Host-` en producción. Las solicitudes de escritura exigen el origen exacto y JSON. La API acepta una barra final en el **valor de configuración** del origen de cuentas y la quita antes de compararlo con CORS.

La vinculación por ticket sigue validando una sesión emitida mediante una descarga auténtica. SQLite conserva las sesiones de ChillyRoom cifradas con AES-SIV y los identificadores de sesión del navegador como hashes. Cada lectura de guardado compara su identidad con la que se validó al vincular y verifica la pertenencia de la cuenta a la sesión del navegador. La escritura requiere el interruptor global y el permiso privado de esa cuenta.

`POST /api/v1/cloud/accounts/logout` invalida la sesión de navegador en SQLite, borra las credenciales de nube registradas para sus cuentas, invalida sus tickets pendientes y expira la cookie. Los respaldos se conservan bajo la identidad de la cuenta. Para recuperarlos se requiere una nueva vinculación autorizada. El cierre aplica a SK Under. La sesión en el cliente oficial se administra en ChillyRoom.

El editor conserva la descarga, validación de gemas, preparación y respaldo, confirmación, comprobación de cambios remotos y verificación posterior por SHA-256. Si la subida queda incierta, se conserva el intento y se puede consultar el resultado antes de otra escritura. ChillyRoom no ha expuesto una precondición de escritura verificada por el cliente Linux. Una escritura concurrente desde otro cliente aún puede ocurrir entre la última lectura y la subida.

### Estados operativos

| Comprobación | Qué demuestra |
| --- | --- |
| `GET /api/v1/health` con `200` | FastAPI atiende solicitudes. El healthcheck de Docker usa este endpoint local. |
| `GET /api/v1/cloud/accounts` | Configuración y lectura del almacén, disponibilidad del formulario, interruptor global y cuentas visibles para la cookie. `storage_status` y `problem_code` distinguen origen, clave y almacenamiento en el arranque. Un fallo de SQLite durante la operación devuelve `503 cloud_accounts_storage`. |
| `POST /api/v1/cloud/accounts/login` | Devuelve `503 cloud_login_unavailable` para una solicitud del origen válido. El formulario permanece bloqueado mientras el intercambio directo esté pendiente. |
| `GET /api/v1/cloud/accounts/{id}/save` | Comprueba la sesión de navegador, titularidad, autorización remota y validez de la partida en esa operación. Un `502 cloud_provider_unavailable` distingue un fallo remoto de un problema de SQLite. |
| `write_enabled` y `accounts[].write_ready` | Interruptor de escritura del servidor y permiso vigente por cuenta, respectivamente. |
| `GET /api/v1/cloud/lab/status` | Configuración administrativa. El estado de ChillyRoom solo se comprueba con una operación real y el frontend indica el resultado de la última descarga. |

Las llamadas de BlobSave conservan el timeout de socket de 30 segundos por operación HTTPS. La confirmación incluye varias llamadas. La API permanece activa y se comunica con ChillyRoom bajo demanda.

## Configuración de producción

| Variable | Uso y valor |
| --- | --- |
| `SK_ENV` | General. `production`. |
| `SK_ALLOWED_ORIGINS` | General. Lista JSON con `https://sk.underdive.space`. Se pueden autorizar otros orígenes exactos para los flujos generales. |
| `SK_CLOUD_ACCOUNTS_ORIGIN` | Cuentas. `https://sk.underdive.space`, con el mismo valor en CORS. Frontend y API usan subdominios del mismo sitio HTTPS para la cookie. |
| `SK_CLOUD_ACCOUNTS_KEY` | Cuentas. Secreto externo de 32 bytes aleatorios en 64 dígitos hexadecimales. Conservar la misma clave y un respaldo privado de ella. |
| `SK_CLOUD_ACCOUNTS_DIR` | Cuentas. `/var/lib/sk-under/accounts`. Contiene SQLite y los respaldos de los usuarios. |
| `SK_CLOUD_BACKUP_DIR` | Laboratorio. `/var/lib/sk-under/backups`. Contiene los respaldos administrativos. |
| `SK_CLOUD_WRITE_ENABLED` | Cuentas y laboratorio. `true` autoriza la escritura solo cuando se cumplen también los permisos específicos del flujo. |
| `SK_ACCESS_TOKEN` | Editor de archivos y laboratorio. Secreto de acceso de la API de al menos 32 caracteres ASCII visibles. Las cuentas usan su cookie. |
| `SK_CLOUD_ADMIN_TOKEN` | Laboratorio. Secreto de al menos 32 caracteres ASCII visibles para confirmar y restaurar. |
| `SK_CLOUD_SESSION_TOKEN`, `SK_CLOUD_UNIQUE_ID`, `SK_CLOUD_DISTRO_ID` | Laboratorio. Sesión previamente emitida, identificador y distribución de la instalación autorizada. El backend de cuentas opera con su propio almacén. La sesión del laboratorio debe renovarse por el titular cuando caduque. |
| `VITE_API_BASE_URL` | Pages. Variable pública de build con `https://api-sk.underdive.space`, sin `/api/v1`. |

### Coolify

Edita la aplicación existente de `CesarJGB/sk-under` en `main`. Usa el build pack Dockerfile, directorio base `/backend`, Dockerfile `/Dockerfile`, puerto interno `8000` y dominio `https://api-sk.underdive.space`. Configura las variables `SK_*` necesarias como variables de runtime. Mantén el healthcheck de la imagen. El contenedor usa UID/GID `10001:10001`.

En **Persistent Storage**, monta dos volúmenes Docker independientes en `/var/lib/sk-under/accounts` y `/var/lib/sk-under/backups`. Para un montaje de directorios del host, asigna `10001:10001` y modo `0700` antes de desplegar. Verifica que SQLite use `0600`. Conserva un respaldo privado de los dos volúmenes y, por un canal separado, de la clave de cuentas. [Almacenamiento de Coolify](https://coolify.io/docs/applications/configuration/persistent-storage) · [Healthchecks de Coolify](https://coolify.io/docs/applications/configuration/health-checks)

Después de desplegar, verifica que la revisión coincida con `main`, que el contenedor esté saludable, que su política sea `unless-stopped` y que Docker esté habilitado al arrancar el VPS. Comprueba los dos endpoints públicos y la descarga con una cuenta autorizada. Tras recrear el contenedor, repite la lectura con la misma cookie y comprueba el historial de respaldos. Para emitir enlaces privados y reconectar una cuenta, usa el procedimiento de la [Fase 6.3](../phase6-3/README.md#vinculación-privada).

### Cloudflare Pages

Configura la rama de producción `main`, directorio raíz `frontend`, comando `npm run build`, salida `dist` y `VITE_API_BASE_URL` como se indica arriba. Comprueba el dominio personalizado `sk.underdive.space` y el estado del build del commit en GitHub. En el navegador, confirma que `/partida` consulta la API HTTPS y recibe el origen CORS exacto con credenciales admitidas. El dominio alternativo de Pages queda fuera del flujo de cuentas con cookie, que se sirve en el dominio principal. [Monorepos en Pages](https://developers.cloudflare.com/pages/configuration/monorepos/) · [Integración Git](https://developers.cloudflare.com/pages/configuration/git-integration/)

## Evidencia y alcance

- Producción, sesión ya emitida. Chromium con perfil Pixel 7 abrió el sitio real de Pages, reclamó el ticket y descargó 1,002 gemas con la cookie del backend de Coolify. Preparó 1,003 y verificó que el botón seguía deshabilitado hasta confirmar. La subida devolvió `persisted=true`, una descarga independiente devolvió 1,003 con el SHA-256 del candidato y la restauración devolvió 1,002 con el SHA-256 original. La partida medía 114,778 bytes.
- Emulador Android 11, cliente 8.8.0. Un intento con contraseña incorrecta para la cuenta de laboratorio devolvió `BadRequest` y el cliente mostró un error de cuenta o contraseña. Un intento con la contraseña correcta devolvió `OK`, produjo una sesión distinta de la anterior y volvió a la pantalla de título autenticada. Linux consumió esa sesión recién emitida, descargó 114,778 bytes y validó 1,002 gemas de la misma cuenta. Los secretos se mantuvieron fuera de Git.
- Persistencia. Tras reiniciar el contenedor de producción, la cookie siguió funcionando en WebKit con perfil iPhone 13. La misma cuenta descargó 1,002 gemas y conservó su respaldo. Un navegador separado obtuvo `401` al usar la misma ruta de descarga sin cookie. Se comprobaron los modos `0700` de los directorios y `0600` de SQLite, todos con propietario `10001:10001`.
- Recreación y revocación. Coolify recreó el contenedor al desplegar `dff419a`. Tras el despliegue, la misma cookie volvió a descargar 1,002 gemas y encontró el respaldo anterior. El cierre de sesión desde Pages revocó esa cookie. La API devolvió `401` al reutilizarla.
- Pruebas automatizadas. 340 aprobadas y 16 omitidas de backend por requerir muestras privadas. 14 de Chromium y cuatro del editor de cuentas en WebKit. Las pruebas con dos titulares y los fallos de proveedor usan fixtures. La integración real de producción usó una cuenta autorizada.
- El estado del intercambio directo y la evidencia de la solicitud se detallan en el [contrato investigado](authentication.md). Siguen pendientes una autenticación de extremo a extremo iniciada desde el backend, la renovación automática verificada y las pruebas con dos cuentas reales. No se reinició el VPS completo ni se usó un iPhone físico.
- La sesión invitada del mismo laboratorio se probó en una lectura independiente. BlobSave devolvió un error de disponibilidad y carecimos de una segunda partida validable para la prueba multiusuario real.

Los resultados de las operaciones reales constan en [evidence.json](evidence.json).

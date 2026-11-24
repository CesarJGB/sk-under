# Fase 6.8 · Despliegue persistente en Coolify

**Estado: runbook preparado; no ejecutado.** Esta guía describe cómo desplegar la rama `feature/phase6-8-web-native-auth` sin hacer merge a `main` ni activar escrituras. No se creó ningún recurso, volumen ni variable en producción desde esta sesión. La rama está publicada en `origin` (commit de implementación `f87d63f`) antes de usar esta guía; el despliegue y el aprovisionamiento requieren acción manual del propietario. Quedan preparados el contrato de variables, la topología, el procedimiento de respaldo y las comprobaciones de solo lectura; requieren acción manual la publicación de la rama, la creación del recurso y del volumen, la carga de secretos y el aprovisionamiento de `distro_id`/`unique_id`.

## 1. Topología

```text
Navegador
  │ HTTPS; SPA estática y fetch con credenciales
  ▼
Cloudflare Pages · https://sk.underdive.space
  │ JSON, Origin exacto, cookie __Host-sk_native
  ▼
Proxy/CDN de Cloudflare · TLS Full (strict)
  ▼
Coolify (Traefik) · https://api-sk.underdive.space
  ▼
Contenedor FastAPI · 0.0.0.0:8000 · UID/GID 10001
  │ HTTPS saliente con validación TLS normal
  ▼
api-gateway.soulknight.chillyroom.com
```

| Elemento | Valor obligatorio |
| --- | --- |
| Origen del editor | `https://sk.underdive.space` |
| Origen de la API | `https://api-sk.underdive.space`, sin `/api/v1` |
| `SK_ALLOWED_ORIGINS` | `["https://sk.underdive.space"]` |
| `SK_NATIVE_ORIGIN` | `https://sk.underdive.space`; si está vacío se usa `SK_CLOUD_ACCOUNTS_ORIGIN` |
| Cookie | `__Host-sk_native` (`sk_native_dev` solo en desarrollo), `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, sin `Domain` |
| CORS | Origen exacto, `Access-Control-Allow-Credentials: true`, `Vary: Origin`; nunca `*` |

El frontend y la API comparten el dominio registrable `underdive.space`, así que la petición es cross-origin pero same-site. Eso permite que la cookie `SameSite=Strict` se envíe a `api-sk.underdive.space` con `credentials: "include"`. Un despliegue de vistas previas en `*.pages.dev` es cross-site: la cookie no se enviará y el login fallará. No se debe rebajar `SameSite` a `None` para compensarlo; se usa el dominio principal o una vista previa bajo el mismo sitio. El backend habla con ChillyRoom; el navegador nunca recibe el token del proveedor ni la contraseña. La sesión del proveedor dura aproximadamente siete días y no hay renovación verificada. TLS se valida en todos los tramos: no se usa el modo Flexible de Cloudflare, no se desactiva la verificación y no se interpone un proxy de inspección.

## 2. Recurso en Coolify

| Campo | Valor |
| --- | --- |
| Fuente | GitHub `CesarJGB/sk-under` |
| Rama | `feature/phase6-8-web-native-auth` |
| Build pack | `Dockerfile` |
| Directorio base | `/backend` |
| Dockerfile | `/Dockerfile`, relativo al directorio base |
| Puerto interno (`Ports Exposes`) | `8000` |
| Dominio | `https://api-sk.underdive.space` |
| Health check | El de la imagen, `GET /api/v1/health` |
| Política de reinicio | `unless-stopped` |
| Réplicas | `1` |
| Volumen persistente | `/var/lib/sk-under` |
| Usuario del proceso | `10001:10001` |
| Auto deploy | Desactivado hasta que el propietario lo apruebe |

- El contexto de build es `backend/`. El `.dockerignore` solo incluye `app/`, `pyproject.toml`, `uv.lock` y el Dockerfile; no cambies el directorio base a la raíz del repositorio. [Dockerfile en Coolify](https://coolify.io/docs/applications/builds/dockerfile)
- El `CMD` de la imagen ejecuta Uvicorn sin `--workers`. No añadas workers ni réplicas: SQLite y el estado del rate limit no están preparados para escritura concurrente entre procesos o hosts.
- El healthcheck de la imagen ya consulta `/api/v1/health` con `python` y `urllib`. Deja desactivado el healthcheck del panel de Coolify: un chequeo HTTP del panel requiere `curl` o `wget` dentro de la imagen y `python:3.12-slim` no los incluye. Si se activa, usa un chequeo `CMD` con el mismo comando de Python. [Healthchecks de Coolify](https://coolify.io/docs/applications/configuration/health-checks)
- No está confirmado que todas las versiones de Coolify expongan un selector de política de reinicio. La versión actual aplica `unless-stopped` a los contenedores gestionados. Verifica el resultado con `docker inspect` (sección 4); si tu versión tiene el campo, selecciona `unless-stopped`. [Ajustes avanzados de Coolify](https://coolify.io/docs/applications/configuration/advanced)
- Un solo volumen en `/var/lib/sk-under` cubre `accounts`, `backups`, `native` y `native-backups`. Es preferible a cuatro montajes separados porque conserva una sola raíz de permisos. No montes el volumen padre y además un subdirectorio del mismo árbol.
- Para un volumen Docker nuevo, Docker hereda los directorios de la imagen si están presentes. Para un montaje de directorio del host, crea la raíz con `10001:10001` y modo `0700` antes de arrancar. Si el volumen ya existía con otro propietario, corrige los permisos antes del primer arranque.

## 3. Variables de entorno

Todas las variables `SK_*` son de runtime. En Coolify, marca cada una como **no disponible durante build** salvo que una compilación las necesite; ninguna de las de esta tabla debe llegar al build. `VITE_*` solo existe en Cloudflare Pages y es público.

| Variable | ¿Obligatoria? | Valor de producción | Notas |
| --- | --- | --- | --- |
| `SK_ENV` | Sí | `production` | Sin modo desarrollo en producción. |
| `SK_ACCESS_TOKEN` | Sí, si se usan archivos o laboratorio | `<32+ caracteres ASCII visibles>` | Secreto independiente; no es la clave nativa. |
| `SK_ALLOWED_ORIGINS` | Sí | `["https://sk.underdive.space"]` | JSON exacto, sin barra final ni comodines. |
| `SK_MAX_FILE_BYTES` | No | `1048576` | Rango 1–8388608. |
| `SK_NATIVE_AUTH_ENABLED` | Sí | `false` al desplegar | Solo `true` después de verificar clave, volumen y origen. |
| `SK_NATIVE_WRITE_ENABLED` | Sí | `false` | No se activa en esta fase. |
| `SK_NATIVE_STORE_KEY` | Sí para native | `<64 dígitos hexadecimales>` | 32 bytes; runtime, bloqueada y respaldada aparte. |
| `SK_NATIVE_STORE_DIR`, `SK_NATIVE_BACKUP_DIR` | No | `/var/lib/sk-under/native`, `/var/lib/sk-under/native-backups` | Valores por defecto de la imagen; deben quedar dentro del volumen. |
| `SK_NATIVE_ORIGIN` | Recomendada | `https://sk.underdive.space` | Si está vacía, se usa `SK_CLOUD_ACCOUNTS_ORIGIN`; el origen debe estar incluido exactamente en `SK_ALLOWED_ORIGINS`. Sin barra final. |
| `SK_NATIVE_DISTRO_ID`, `SK_NATIVE_UNIQUE_ID` | Opcional | Privados; ver sección 6 | UUID validado por ChillyRoom e identificador de instalación para BlobSave; no son `android-global`. |
| `SK_NATIVE_PROFILE_LABEL` | No | `Instalación Android Global` | Etiqueta del perfil inicial; no es un identificador. |
| `SK_NATIVE_PROFILE_ALLOW_WRITE` | No | `false` | Permiso del perfil; no sustituye al interruptor global. |
| `SK_NATIVE_IDLE_SECONDS`, `SK_NATIVE_LOGIN_ATTEMPTS`, `SK_NATIVE_LOGIN_WINDOW_SECONDS` | No | `1800`, `5`, `900` | Inactividad 60–86400 s; intentos 1–50; ventana 60–86400 s. |
| `SK_CLOUD_ACCOUNTS_KEY` | Sí, si se usan cuentas vinculadas | `<64 dígitos hexadecimales>` | Clave distinta de la nativa; conserva la misma. |
| `SK_CLOUD_ACCOUNTS_ORIGIN` | Sí, si se usan cuentas | `https://sk.underdive.space` | Fallback de `SK_NATIVE_ORIGIN`. |
| `SK_CLOUD_ACCOUNTS_DIR`, `SK_CLOUD_BACKUP_DIR` | No | `/var/lib/sk-under/accounts`, `/var/lib/sk-under/backups` | Cuentas y respaldos del laboratorio administrativo. |
| `SK_CLOUD_SESSION_TOKEN`, `SK_CLOUD_UNIQUE_ID`, `SK_CLOUD_DISTRO_ID` | Opcional | Privados | Solo para el laboratorio de 6.2; no son la sesión nativa. |
| `SK_CLOUD_ADMIN_TOKEN` | Opcional | `<32+ caracteres ASCII visibles>` | Solo confirmar/restaurar del laboratorio. |
| `SK_CLOUD_WRITE_ENABLED` | No | `false` | Se mantiene apagado. |
| `VITE_API_BASE_URL` | Build de Pages | `https://api-sk.underdive.space` | Público, sin `/api/v1`; nunca en Coolify. |

### Clave del almacén nativo

Genera 32 bytes aleatorios con `openssl rand -hex 32` y guárdalos como 64 dígitos hexadecimales. No ejecutes el comando en un log compartido ni pegues la salida en un issue. Guarda la clave en el gestor privado del propietario y en Coolify como variable bloqueada de runtime. Verifica la forma sin imprimir el valor:

```bash
case "$SK_NATIVE_STORE_KEY" in
  ''|*[!0-9a-fA-F]*) echo "clave inválida"; exit 1 ;;
esac
[ "${#SK_NATIVE_STORE_KEY}" -eq 64 ] || { echo "longitud inválida"; exit 1; }
echo "forma válida"
```

El almacén nativo crea `native.sqlite3` con modo `0600`, exige que el directorio sea `0700` y rechaza cualquier permiso de grupo u otros. También guarda un verificador HMAC de la clave: si la clave no corresponde al almacén existente, el arranque falla cerrado y `native_auth_ready` no puede ser verdadero.

### Rotación de la clave

La rotación es destructiva para los perfiles y sesiones nativas: los identificadores y tokens están cifrados con AES-SIV y no hay re-cifrado ni keyring documentado en esta fase. Una clave nueva no puede descifrar el volumen anterior y el verificador impedirá abrir la base existente.

1. Mantén `SK_NATIVE_WRITE_ENABLED=false` y `SK_NATIVE_PROFILE_ALLOW_WRITE=false`.
2. Copia el volumen completo y la clave anterior fuera del servidor; conserva ambos hasta terminar la verificación.
3. Detén la aplicación. Archiva el directorio `native/` actual (no lo borres) y crea un `native/` vacío con `10001:10001` y `0700`.
4. Genera la clave nueva, reemplaza `SK_NATIVE_STORE_KEY` y arranca. El almacén anterior queda inutilizable con la clave nueva.
5. Vuelve a aprovisionar los perfiles y a iniciar sesión; las sesiones anteriores no se recuperan. `native_auth_ready` debe volver a `true`.
6. Guarda la clave nueva en el gestor privado. Si necesitas volver atrás, restaura el volumen archivado junto con la clave anterior; no mezcles volumen viejo con clave nueva.

La rotación de `SK_CLOUD_ACCOUNTS_KEY` es independiente y también invalida el almacén de cuentas vinculadas. No rotes ambas claves en la misma ventana sin respaldos separados.

### Build frente a runtime

`VITE_API_BASE_URL` se incorpora al JavaScript durante el build de Pages y es público. No pongas `SK_*` en Pages ni `VITE_*` en Coolify como secreto. Los argumentos de build de Docker pueden quedar visibles en metadatos de la imagen; no pases claves por `ARG`. [Variables de Coolify](https://coolify.io/docs/applications/configuration/environment-variables)

## 4. Health checks y arranque

Sustituye el dominio si cambia. Estos comandos son de solo lectura.

```bash
export API_BASE='https://api-sk.underdive.space'

curl -fsS "$API_BASE/api/v1/health" | jq .
curl -fsS "$API_BASE/api/v1/health" | jq -e '.status == "ok"'

curl -fsS "$API_BASE/api/v1/cloud/native/config" | jq .
curl -fsS "$API_BASE/api/v1/cloud/native/config" \
  | jq -e 'if has("native_auth_ready") then .native_auth_ready
           else (.enabled == true and .available == true and .configured == true and .login_available == true) end'
```

El contrato de la fase usa `native_auth_ready`; si la rama publicada todavía no lo incluye, el estado equivalente es `enabled && available && configured && login_available`. No cambies las variables por esa diferencia: el servicio debe cumplir uno de los dos contratos antes de habilitar el login. Interpretación:

- Con `SK_NATIVE_AUTH_ENABLED=false`, `native_auth_ready=false` es correcto; el endpoint debe seguir respondiendo `200` sin habilitar el login.
- Con la función habilitada pero sin clave, volumen, permisos u origen válidos, `native_auth_ready` debe ser `false` y el login debe fallar cerrado con `503` (`native_auth_disabled`, `native_auth_misconfigured`, `native_store_misconfigured` o `native_store_unavailable`).
- Solo con `native_auth_ready=true` se permite el login nativo. Esto no implica que la escritura esté habilitada.
- El JSON de configuración no debe incluir la clave, el token de acceso, el token de ChillyRoom, ni los valores de `distro_id`/`unique_id`.

Comprueba el preflight del origen exacto:

```bash
curl -sS -D - -o /dev/null -X OPTIONS "$API_BASE/api/v1/cloud/native/login" \
  -H 'Origin: https://sk.underdive.space' -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type' | grep -i '^access-control-'
```

Debe aparecer `access-control-allow-origin: https://sk.underdive.space` y `access-control-allow-credentials: true`, sin `*`. Revisa también que `Access-Control-Allow-Headers` incluya `content-type`; si falta, el navegador bloquea el login aunque el origen sea correcto. Un origen no autorizado no debe recibir `Access-Control-Allow-Origin`:

```bash
curl -sS -D - -o /dev/null -X OPTIONS "$API_BASE/api/v1/cloud/native/login" \
  -H 'Origin: https://ejemplo.invalid' -H 'Access-Control-Request-Method: POST' \
  | grep -i '^access-control-allow-origin' || echo "sin ACAO para origen no autorizado"
```

Dentro del contenedor, desde la terminal de Coolify:

```bash
id
stat -c '%u:%g %a %n' /var/lib/sk-under /var/lib/sk-under/accounts /var/lib/sk-under/backups \
  /var/lib/sk-under/native /var/lib/sk-under/native-backups
find /var/lib/sk-under -maxdepth 2 -type f -printf '%u:%g %m %p\n'
python -c "from urllib.request import urlopen; print(urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2).read().decode())"
```

Esperado: UID/GID `10001:10001`, los cuatro subdirectorios `700` (la raíz del volumen puede ser `755`), `native.sqlite3` y demás archivos privados `600`. Desde el host de Coolify, verifica el estado de Docker y la política de reinicio:

```bash
docker inspect --format '{{.State.Health.Status}}' <CONTENEDOR>
docker inspect --format '{{.HostConfig.RestartPolicy.Name}}' <CONTENEDOR>
```

No incluyas `env`, `printenv` ni el valor de la clave en capturas o tickets. Si `native_auth_ready=false`, revisa los códigos sanitizados de los logs; no vuelques el entorno.

## 5. Persistencia y respaldo

Contenido del volumen `/var/lib/sk-under`:

| Ruta | Contenido | Si falta |
| --- | --- | --- |
| `accounts/` | SQLite y secretos cifrados de cuentas vinculadas (6.3/6.4) | Se pierden las vinculaciones; el login nativo puede seguir, pero las cuentas anteriores no. |
| `backups/` | Respaldos privados del laboratorio administrativo (6.2) | Se pierden los respaldos administrativos. |
| `native/` | `native.sqlite3`, perfiles, sesiones, intentos y eventos de 6.8 | Se pierden perfiles y sesiones nativas. |
| `native-backups/` | Respaldos del flujo nativo | Se pierden los respaldos nativos. |

Al recrear el contenedor se conserva el volumen; se pierde todo lo escrito fuera de él. Un redeploy de la misma rama, un reinicio o una nueva imagen no borran el volumen si el destino del montaje no cambia. Cambiar el destino, crear un volumen nuevo o desplegar sin montaje sí pierde los datos.

Procedimiento de respaldo con la aplicación detenida:

```bash
# En el host de Coolify. Ajusta VOL a la ruta real del volumen o del directorio montado.
VOL='<RUTA_DEL_VOLUMEN>'
sudo install -d -m 0700 /srv/backups/sk-under
sudo tar --numeric-owner -C "$VOL" -czf "/srv/backups/sk-under/sk-under-$(date -u +%Y%m%dT%H%M%SZ).tgz" .
sudo sha256sum /srv/backups/sk-under/*.tgz
```

Detén el recurso en Coolify antes de copiar; una copia de SQLite con escrituras en curso puede ser inconsistente. Si necesitas copia en caliente, usa la [API de respaldo de SQLite](https://www.sqlite.org/backup.html) para cada base y copia después los archivos no volátiles. El archivado debe incluir propietario y modos (`--numeric-owner`); una restauración sin ellos vuelve a fallar por permisos. Conserva una copia cifrada fuera del servidor y la clave en un canal separado. [Almacenamiento persistente](https://coolify.io/docs/applications/configuration/persistent-storage) · [Respaldos de montajes](https://coolify.io/docs/core/persistent-storage/storage-mounts/backups). La copia programada de montajes de Coolify, si tu versión la ofrece, es una capa adicional; no sustituye una copia fuera del servidor ni una prueba de restauración, y su disponibilidad no está confirmada para esta instalación.

Para comprobar que la sesión sobrevive a un redeploy:

1. Inicia sesión en el navegador del propietario y abre una lectura de solo lectura de la partida.
2. Anota la cuenta y el estado visible; no copies la cookie.
3. Redeploy o reinicio en Coolify, sin cambiar variables ni volumen.
4. Espera `health` saludable y `native_auth_ready=true`; recarga la página.
5. La misma sesión debe seguir activa y leer la misma cuenta. Si pide login, revisa el montaje, el propietario, los modos y que la clave no cambió.

Recuperación tras una caída:

- Contenedor caído o host reiniciado: la política `unless-stopped` lo reinicia; si no, revisa logs, `docker inspect` y que Docker/Coolify arranquen al inicio con el volumen montado.
- Volumen o clave perdidos: restaura el último archivo validado con propietario y modos antes de arrancar, o recupera la clave del gestor privado; sin ambos no se descifra el almacén y hay que re-provisionar. No generes una clave nueva sobre el volumen viejo.
- Sesión del proveedor caducada: vuelve a iniciar sesión; no hay refresh token. La sesión local por inactividad expira a los 1800 segundos y la absoluta no supera los siete días.

## 6. Aprovisionamiento inicial del propietario

`SK_NATIVE_DISTRO_ID` es el UUID de distribución que ChillyRoom valida en `x-distro-id`; no es el identificador interno `android-global`. `SK_NATIVE_UNIQUE_ID` es el identificador de instalación que BlobSave exige. Ambos son privados: no se publican en documentación, Git, capturas ni logs. La distribución interna validada en esta fase es `android-global`; las demás están deshabilitadas.

Para que el perfil quede operativo, configura ambos identificadores. El backend crea el perfil inicial con `SK_NATIVE_PROFILE_LABEL` cuando `SK_NATIVE_DISTRO_ID` está configurado; sin `SK_NATIVE_UNIQUE_ID` el perfil puede existir pero la descarga queda pendiente (`native_installation_required`). Como alternativa, el propietario puede aprovisionar por CLI en un proceso privado, sin persistir los identificadores en Coolify; confirma las opciones en una terminal privada con `docker exec -it <CONTENEDOR> python -m app.native.provision --help`, porque los nombres exactos deben coincidir con la rama publicada. Ejemplo con placeholders:

```bash
# La CLI pide los dos identificadores sin eco; no quedan en el historial del shell.
docker exec -it <CONTENEDOR> python -m app.native.provision \
  --label 'Instalación Android Global' --distribution android-global
```

También acepta `--distro-stdin` y `--unique-stdin` para una entrada controlada por tubería, y `--no-unique` para dejar la instalación pendiente. Evita pasar los identificadores como argumentos visibles o por `VITE_*`; no los devuelvas al navegador. Si usas una tubería, limpia el historial y cualquier archivo temporal.

Alternativa por variables: configura `SK_NATIVE_DISTRO_ID` y `SK_NATIVE_UNIQUE_ID` como variables de runtime, arranca y deja que el backend cree el perfil si no existe. No actualiza un perfil existente con valores nuevos; para cambiarlo, usa la CLI o el formulario de instalación pendiente. Puedes retirar las variables después de verificar. No actives `SK_NATIVE_PROFILE_ALLOW_WRITE` ni `SK_NATIVE_WRITE_ENABLED`.

Después del aprovisionamiento:

1. Mantén `SK_NATIVE_AUTH_ENABLED=true` solo cuando la clave, el volumen y el origen estén verificados; deja `SK_NATIVE_WRITE_ENABLED=false`.
2. Reinicia o redeploya y comprueba `native_auth_ready=true` y que el login nativo esté disponible.
3. El propietario inicia sesión manualmente con su correo y contraseña. La contraseña solo vive en memoria; el navegador recibe una cookie `HttpOnly`, no el token del proveedor.
4. Verifica una lectura de la partida y el estado de la cuenta; no ejecutes confirmación, subida ni restauración.

No se declara soporte para terceros: la autorización del proveedor y el aprovisionamiento de `distro_id`/`unique_id` siguen siendo una condición pendiente de la Fase 6.7.

## 7. Cloudflare Pages

| Opción | Valor |
| --- | --- |
| Rama de producción | `main`; la rama 6.8 se prueba como preview hasta el merge |
| Directorio raíz | `frontend` |
| Comando de build | `npm ci && npm run build` |
| Directorio de salida | `dist` |
| `NODE_VERSION` | `24` |
| `VITE_API_BASE_URL` | `https://api-sk.underdive.space`, variable de build |
| Dominio | `https://sk.underdive.space` con HTTPS |

`VITE_API_BASE_URL` debe volver a compilarse si cambia la URL. El dominio de Pages y el de la API deben tener certificado HTTPS válido. Configura SSL/TLS en **Full (strict)** y **Always Use HTTPS**; no uses Flexible. [Dominios personalizados](https://developers.cloudflare.com/pages/configuration/custom-domains/) · [Modos SSL](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/)

El archivo `frontend/public/_headers` se copia a `dist/_headers` y solo aplica a respuestas estáticas de Pages; no añade CORS a la API. Un bloque recomendado, que debe validarse contra el build real antes de publicarlo:

```text
/*
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: no-referrer
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Content-Security-Policy: default-src 'self'; connect-src 'self' https://api-sk.underdive.space; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
```

Si el frontend necesita otro recurso, añade solo ese origen exacto; no uses `connect-src *`. El CORS real lo emite FastAPI. El preflight de `POST` con `Content-Type: application/json` debe recibir el origen exacto y credenciales; no debe depender de Pages. La protección CSRF se apoya en el origen exacto, `SameSite=Strict`, `HttpOnly` y JSON obligatorio; no se usa un token CSRF adicional. [Cabeceras de Pages](https://developers.cloudflare.com/pages/configuration/headers/) · [Variables de build](https://developers.cloudflare.com/pages/configuration/build-configuration/)

La cookie `__Host-sk_native` exige `Secure`, `Path=/` y ningún atributo `Domain`; el navegador la rechaza si falta alguno o si la respuesta no es HTTPS. Se emite en `api-sk.underdive.space` y se envía solo a ese host. El frontend debe usar `fetch(..., { credentials: "include" })`; el backend debe devolver `Access-Control-Allow-Credentials: true` con el origen exacto. [Prefijos de cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie#cookie_prefixes)

Las vistas previas `*.pages.dev` son cross-site para la API y no reciben la cookie `SameSite=Strict`. Úsalas solo para revisar la interfaz, protégelas con Cloudflare Access o asígnalas a un subdominio del mismo sitio; no cambies la política de cookie para que funcionen. [Vistas previas](https://developers.cloudflare.com/pages/configuration/preview-deployments/)

## 8. Lista de verificación

Antes de producción:

- [ ] La rama `feature/phase6-8-web-native-auth` está publicada y el build de la imagen termina desde `backend/`.
- [ ] El recurso usa Dockerfile, directorio base `/backend`, puerto `8000`, dominio HTTPS y healthcheck de la imagen.
- [ ] El volumen `/var/lib/sk-under` existe, es persistente y pertenece a `10001:10001`; sus subdirectorios `0700` incluyen `native/` y `native-backups/`, y `native.sqlite3` se crea con `0600`.
- [ ] `SK_NATIVE_STORE_KEY` tiene 64 hex, está bloqueada en Coolify y respaldada fuera del servidor.
- [ ] `SK_ALLOWED_ORIGINS` y `SK_NATIVE_ORIGIN` usan el origen exacto, sin barra final ni comodines; `SK_NATIVE_AUTH_ENABLED=false` y los interruptores de escritura (`SK_NATIVE_WRITE_ENABLED`, `SK_NATIVE_PROFILE_ALLOW_WRITE`, `SK_CLOUD_WRITE_ENABLED`) empiezan en `false`.
- [ ] No hay secretos `SK_*` en el build de Pages ni valores `VITE_*` tratados como secretos.
- [ ] DNS, certificados y SSL Full (strict) están activos; la política es `unless-stopped`, hay una sola réplica y Docker arranca con el host.
- [ ] El preflight permite `Content-Type`, y el guard de origen acepta el `Sec-Fetch-Site: same-site` del flujo entre `sk` y `api-sk`.
- [ ] Existe una copia del volumen y se probó una restauración en un destino desechable.
- [ ] El propietario tiene una cuenta autorizada y sus identificadores privados; no se publicaron.

Después de desplegar:

- [ ] `GET /api/v1/health` devuelve `200`, `status=ok`, y `GET /api/v1/cloud/native/config` devuelve `200`, readiness coherente y ningún secreto.
- [ ] El preflight del origen exacto devuelve ACAO/ACAC; un origen no autorizado no recibe ACAO.
- [ ] El propietario inicia sesión manualmente y la respuesta no contiene el token del proveedor.
- [ ] La cookie es `__Host-sk_native`, `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, sin `Domain`; la lectura y la identidad son correctas y de solo lectura.
- [ ] Logout invalida la sesión local; la cookie anterior recibe `401`.
- [ ] La sesión sobrevive a un redeploy con el mismo volumen y la misma clave.
- [ ] La inactividad de 1800 segundos expira la sesión; a los siete días del proveedor se requiere login de nuevo.
- [ ] Una segunda cuenta autorizada no puede leer la primera; el aislamiento real queda pendiente si no hay segunda cuenta.
- [ ] Los logs no muestran correo, contraseña, token, UID, `distro_id` ni `unique_id`; la escritura sigue deshabilitada y no se ejecutaron confirmación, subida ni restauración.

No se deben ejecutar operaciones reales de escritura, pruebas de carga contra ChillyRoom ni reintentos ante `429` o `10003`.

## 9. Limitaciones y riesgos

| Riesgo | Impacto | Mitigación |
| --- | --- | --- |
| Un solo worker y SQLite | Sin escalado horizontal; escrituras concurrentes bloqueadas o frágiles | Una réplica, sin `--workers`, sin [rolling update](https://coolify.io/docs/applications/deployments/rolling-updates) con dos contenedores sobre el mismo volumen |
| SQLite en volumen local | Sin alta disponibilidad; disco lleno o volumen perdido detiene el servicio | Supervisar espacio, copias fuera del host y restauración probada |
| Rate limit y una réplica | El límite se persiste en SQLite, pero la IP puede ser la del proxy y el contador no se comparte entre réplicas | Mantener una réplica; validar la IP de proxy si se configura; no sustituye un límite distribuido |
| IP detrás de proxy | Con `--no-proxy-headers`, la IP puede ser la del proxy; si se confía en cabeceras sin validar, se puede falsear | Limitar `--forwarded-allow-ips` a la red de Traefik/Cloudflare; no usar `*`; combinar cuenta y sesión, no solo IP |
| Guard de `Sec-Fetch-Site` | Una llamada de `sk.underdive.space` a `api-sk.underdive.space` es same-site. La Fase 6.8 acepta `same-origin`, `same-site` y `none`, siempre con `Origin` exacto | Verificar en el despliegue que el login cross-origin no recibe 403 y que un origen ajeno sí lo recibe |
| Clave nativa perdida o rotada | Perfiles y sesiones cifradas ilegibles; el arranque falla si la clave no coincide | Copia separada de la clave; rotación planificada con volumen archivado y re-provisión |
| Sesión del proveedor de ~7 días | Sin refresh verificado; el usuario debe volver a autenticarse | Avisar en la interfaz; no prometer sesión indefinida; logout local no revoca la sesión de ChillyRoom |
| Cloudflare/Pages cross-site | La cookie `SameSite=Strict` no se envía desde `*.pages.dev` | Dominio principal para el flujo real; previews solo para interfaz |
| Dependencia del proveedor | `502`, `429`, `10003` o cambios de contrato pueden impedir login | Sin reintentos automáticos; errores tipados; cuenta y canal autorizados |
| Secretos en entorno | Un administrador de Coolify o un log mal configurado puede verlos | Variables bloqueadas, runtime only, redacción de logs y gestor privado |
| Despliegue no automatizado | La rama no se publica ni se despliega desde esta sesión; no hay credenciales de Coolify | Acción manual del propietario; verificar el commit y el estado del recurso |

La autorización de ChillyRoom para un uso de terceros y un mecanismo oficial de aprovisionamiento de `distro_id`/`unique_id` siguen pendientes. Hasta entonces, el flujo es privado, para la cuenta del propietario y sin escritura.

## 10. Alcance de la fase

La Fase 6.8 no despliega automáticamente, no hace merge a `main`, no modifica el recurso de producción y no activa operaciones de escritura. Esta guía deja preparados la configuración, los comandos de verificación y las comprobaciones de persistencia; la publicación de la rama, la creación del volumen, la carga de secretos, el aprovisionamiento y las pruebas reales requieren al propietario. No se incluyen secretos reales ni se declara un despliegue que no se ejecutó.

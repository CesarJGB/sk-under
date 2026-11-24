# Fase 6.8 · Prueba manual de autenticación nativa y multicuentas

**Estado: guía preparada; no ejecutada.** Este documento describe la validación manual de la Fase 6.8 en la rama `feature/phase6-8-web-native-auth`. No se ejecutaron pruebas reales contra ChillyRoom desde esta sesión: no hay credenciales ni despliegue disponibles aquí. La validación multicuentas real queda pendiente y debe hacerla el propietario con cuentas propias o expresamente autorizadas.

**Corte:** 23 de noviembre de 2026. **Alcance:** `/partida` (autenticación nativa web), backend `/api/v1/cloud/native/*`, distribución `android-global`, entorno de laboratorio o despliegue privado. `/partida/vinculadas` conserva el flujo anterior de la Fase 6.3 y no forma parte de esta validación.

## 1. Objetivo, alcance y advertencias

El objetivo es comprobar, con evidencia saneada, que una cuenta autorizada puede iniciar sesión desde la web, verificar su identidad, descargar su partida y preparar una edición sin exponer secretos; que la escritura solo funciona cuando se autoriza de forma explícita; y que dos cuentas con perfiles distintos permanecen aisladas en sesiones, respaldos y partidas.

Advertencias obligatorias:

- Usa únicamente cuentas propias o cuentas sobre las que tengas autorización escrita del titular. No pruebes con cuentas de terceros ni con credenciales compartidas.
- No eludas controles del proveedor: nada de captchas, desafíos, dobles factores, límites de intentos, bloqueos regionales ni validaciones TLS. Si aparece un desafío o un `429`, detente y documenta.
- No hagas fuerza bruta, pruebas de carga, reintentos automáticos ni peticiones repetidas contra ChillyRoom.
- La escritura remota solo se prueba en la Prueba 2, con autorización explícita del propietario y sobre su cuenta de laboratorio. En la Prueba 1 y en la Prueba 3 la escritura permanece desactivada.
- No publiques correo, contraseña, cookie, token, UID, `player.id`, `distro_id`, `unique_id`, `backup_id` ni capturas sin sanear. Los resultados se registran con códigos, estados HTTP, etiquetas y recuentos.
- Esta guía no constituye autorización de ChillyRoom para un uso de terceros. La autorización del proveedor y el aprovisionamiento oficial de identificadores siguen pendientes.

Resultados automatizados de referencia en esta rama: backend 380 pruebas aprobadas y 16 omitidas; Playwright 22 aprobadas. Si el recuento cambia en el commit probado, anota “más de 370” en lugar de una cifra exacta. Estas pruebas usan proveedores simulados y no sustituyen la validación real.

## 2. Preparación

### 2.1 Rama, commit y artefacto

```bash
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
```

Debe aparecer la rama `feature/phase6-8-web-native-auth` y un commit que contenga los archivos de la fase: `backend/app/native/`, `backend/app/api/native.py`, `frontend/src/pages/NativeAuthPage.tsx` y las pruebas nativas. No basta con el nombre de la rama: si el despliegue se hizo desde un commit anterior, detén la prueba y anota el bloqueo. Registra el commit exacto en la tabla de resultados.

### 2.2 Variables, volumen y permisos

| Variable | Valor para la prueba | Nota |
| --- | --- | --- |
| `SK_ENV` | `production` en despliegue; `development` solo en laboratorio local | No mezcles modos en la misma evidencia. |
| `SK_NATIVE_AUTH_ENABLED` | `true` | Sin esto, el login responde `native_auth_disabled`. |
| `SK_NATIVE_WRITE_ENABLED` | `false` en las pruebas 1 y 3; `true` solo en la Prueba 2 autorizada | Interruptor global. |
| `SK_NATIVE_STORE_KEY` | `<64_DÍGITOS_HEXADECIMALES>` | Secreto de runtime; nunca se imprime ni se pega. |
| `SK_NATIVE_ORIGIN` | `https://sk.underdive.space` | Origen exacto, sin barra final. |
| `SK_ALLOWED_ORIGINS` | `["https://sk.underdive.space"]` | Debe incluir el mismo origen exacto. |
| `SK_NATIVE_STORE_DIR` | `/var/lib/sk-under/native` | Perfiles, sesiones y eventos. |
| `SK_NATIVE_BACKUP_DIR` | `/var/lib/sk-under/native-backups` | Respaldos del flujo nativo, aislados por sujeto. |
| `SK_NATIVE_IDLE_SECONDS` | `1800`; `60` solo en laboratorio desechable para la prueba de caducidad | No cambies el reloj del servidor. |
| `SK_NATIVE_PROFILE_ALLOW_WRITE` | `false` salvo perfil de la Prueba 2 | Solo aplica al crear el perfil inicial por variables; no sustituye al interruptor global. |
| `SK_ACCESS_TOKEN` | `<TOKEN_DE_ACCESO_DEL_LABORATORIO>` | Solo para diagnóstico en terminal privada; no es la contraseña ni la cookie nativa. |

Verifica la forma de la clave sin imprimir su valor:

```bash
python - <<'PY'
import os
value = os.environ.get("SK_NATIVE_STORE_KEY", "")
assert len(value) == 64 and all(c in "0123456789abcdefABCDEF" for c in value)
print("forma de SK_NATIVE_STORE_KEY válida")
PY
```

Comprueba el volumen y los permisos, sin listar contenidos sensibles:

```bash
sudo stat -c '%u:%g %a %n' /var/lib/sk-under \
  /var/lib/sk-under/native /var/lib/sk-under/native-backups
sudo find /var/lib/sk-under/native -maxdepth 1 -name native.sqlite3 \
  -printf '%u:%g %m %p\n'
```

Esperado: UID/GID `10001:10001`; `native/` y `native-backups/` en `700`; `native.sqlite3` en `600`. La raíz del volumen puede ser `755`, pero los directorios que contienen secretos no. No uses `cat`, `env` ni `printenv` para revisar variables.

### 2.3 HTTPS, origen y cookie

- El editor y la API deben servirse por HTTPS con certificado válido. No uses `curl -k`, no desactives la verificación TLS y no interpongas un proxy de inspección.
- El origen del editor debe ser exactamente `https://sk.underdive.space`. Un despliegue de vistas previas en `*.pages.dev` es cross-site para la API y no recibirá la cookie `SameSite=Strict`; no rebajes la cookie a `SameSite=None` para compensarlo.
- En HTTPS la cookie es `__Host-sk_native`: `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, sin `Domain`. En desarrollo local sobre HTTP se usa `sk_native_dev`; esa variante no sirve como evidencia de producción.
- La API debe devolver `Access-Control-Allow-Origin` con el origen exacto y `Access-Control-Allow-Credentials: true`, nunca `*`.

### 2.4 Salud, configuración y preflight

```bash
export API_BASE='https://api-sk.underdive.space'
export EDITOR_ORIGIN='https://sk.underdive.space'

curl -fsS "$API_BASE/api/v1/health" | jq -e '.status == "ok"'
curl -fsS "$API_BASE/api/v1/cloud/native/config" | jq '{
  available, configured, login_available, write_enabled, secure, problem_code,
  profiles: [.profiles[] | {label, distribution, installation_ready, bound, write_allowed}],
  session,
  distributions: [.distributions[] | {id, enabled, validated}]
}'
```

Comprueba readiness con el contrato de esta rama y el alternativo:

```bash
curl -fsS "$API_BASE/api/v1/cloud/native/config" | jq -e '
  if has("native_auth_ready") then .native_auth_ready
  else (.available == true and .configured == true and .login_available == true)
  end'
```

No exijas la clave `enabled` si la respuesta de esta rama no la incluye; el estado equivalente es `available && configured && login_available`. Comprueba que la configuración no expone secretos:

```bash
curl -fsS "$API_BASE/api/v1/cloud/native/config" | jq -e '
  ([.. | objects | keys[] |
    select(test("^(store_key|token|password|email|distro_id|unique_id)$"))] | length) == 0'
```

Preflight del origen exacto:

```bash
curl -sS -D - -o /dev/null -X OPTIONS "$API_BASE/api/v1/cloud/native/login" \
  -H "Origin: $EDITOR_ORIGIN" \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type' | grep -i '^access-control-'
```

Debe aparecer `access-control-allow-origin: https://sk.underdive.space` y `access-control-allow-credentials: true`. Un origen ajeno no debe recibir `Access-Control-Allow-Origin`. Si `config` falla, la interfaz muestra “Servicio temporalmente no disponible” y ofrece “Reintentar”; no introduzcas credenciales en ese estado.

### 2.5 Aprovisionamiento y perfiles

Lista los perfiles sin mostrar secretos:

```bash
cd backend
uv run --locked python -m app.native.provision --list
```

Si no hay perfiles, `config` devuelve `login_available=false` y la interfaz muestra “Configuración de instalación pendiente”. No inventes identificadores ni copies los de otra instalación. Aprovisiona en una terminal privada, con la misma `SK_NATIVE_STORE_KEY` y el mismo volumen que la API. También puedes crear el perfil inicial con `SK_NATIVE_DISTRO_ID` y `SK_NATIVE_UNIQUE_ID`; la CLI evita dejar esos valores en el entorno:

```bash
cd backend
uv run --locked python -m app.native.provision --label '<ETIQUETA_PERFIL>'
```

La CLI pide el identificador de distribución y el de instalación sin eco. Alternativa por entrada estándar, útil en automatización privada:

```bash
cd backend
printf '%s\n%s\n' '<DISTRO_ID_PRIVADO>' '<UNIQUE_ID_PRIVADO>' \
  | uv run --locked python -m app.native.provision \
      --label '<ETIQUETA_PERFIL>' --distro-stdin --unique-stdin
```

No escribas los identificadores como argumentos: quedarían en el historial o en la lista de procesos. Si usas `printf`, hazlo en una sesión sin historial o desde el gestor de secretos. En un contenedor, ejecuta la misma orden con `docker exec -it <CONTENEDOR> python -m app.native.provision ...` y confirma antes las opciones con `--help`.

Opciones: `--no-unique` crea el perfil con la instalación pendiente y luego se completa desde la web con el identificador propio; `--allow-write` autoriza escritura para ese perfil, pero el interruptor global sigue mandando. El permiso de escritura se fija al crear el perfil: si el perfil ya existe sin `--allow-write`, no lo cambies por SQL; crea un perfil nuevo autorizado en un volumen de laboratorio.

El perfil queda sin vincular hasta el primer login. En ese momento se vincula a la identidad (correo, `uid` y `player.id`) y no puede reutilizarse con otra cuenta: el intento devuelve `native_profile_identity_mismatch`. Si falta la instalación, la web muestra “Configuración de instalación pendiente”, pide “Identificador de instalación” y ofrece “Completar instalación”. Si hay más de un perfil, la interfaz exige seleccionar uno en “Perfil de instalación”; sin selección, el backend responde `native_profile_required`.

## 3. Prueba 1: cuenta de laboratorio en solo lectura

Condiciones: `SK_NATIVE_WRITE_ENABLED=false`, perfil creado sin `--allow-write`, una sola cuenta autorizada. No se envía ninguna escritura a la nube.

| Paso | Acción | Resultado esperado |
| --- | --- | --- |
| 1 | Abre `/partida` y revisa la cabecera y el selector “Distribución”. | Seis distribuciones listadas; solo `Android Global (GP)` habilitada; las otras cinco deshabilitadas. |
| 2 | Escribe el correo en “Correo electrónico de ChillyRoom” y la contraseña en “Contraseña”; usa “Mostrar contraseña” una vez y vuelve a ocultarla. Envía el formulario. | Estado “Iniciando sesión…”, luego “Identidad verificada” y “Sesión activa”; no se muestra correo, token ni contraseña. |
| 3 | Revisa la cookie en DevTools. | `__Host-sk_native` con `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, sin `Domain`; o `sk_native_dev` solo en local. |
| 4 | Busca en JS, `localStorage`, `sessionStorage` y respuestas de red. | No aparece el token del proveedor ni la contraseña; la cookie no es accesible desde JavaScript. |
| 5 | Anota caducidad de sesión e inactividad mostradas. | Fechas coherentes con el entorno; no copies la cookie ni las fechas si identifican al titular. |
| 6 | Pulsa “Descargar partida”. | El botón muestra “Descargando…”; luego aparecen gemas actuales, tamaño, SHA-256 y origen, y el aviso indica que la escritura está deshabilitada. |
| 7 | Cambia la cantidad de gemas en +1 y pulsa “Preparar edición”. | Se muestra original, nueva cantidad, cambio y respaldo; el respaldo aparece como “Copia preparada”. |
| 8 | Comprueba el editor con escritura desactivada. | No existe el botón “Subir y verificar”; el aviso dice que se puede descargar y preparar, pero no subir. |
| 9 | Abre “Respaldos” y pulsa “Verificar nube” sobre el respaldo preparado. | La comparación no escribe en la nube y solo muestra el estado de la copia. |
| 10 | Cierra sesión y acepta la confirmación. | Vuelve “Iniciar sesión en ChillyRoom”; la partida y los respaldos dejan de mostrarse en la vista. |
| 11 | En otra pestaña abierta antes del logout, pulsa “Descargar partida”. | La petición responde `401 native_session_required`; la vista vuelve al acceso y, al recargar, no queda partida. |
| 12 | Prueba de caducidad en laboratorio: baja `SK_NATIVE_IDLE_SECONDS=60`, reinicia, inicia sesión y espera más de 60 s sin actividad. | La siguiente descarga responde `401 native_session_expired`; la interfaz muestra “La sesión caducó”. Restaura `1800` al terminar. |

La caducidad por inactividad se demuestra esperando o con la ventana corta de laboratorio. No manipules el reloj del servidor en producción. La caducidad absoluta de siete días y la caducidad del token del proveedor no se acortan desde la aplicación: si no se esperan, se marcan como “no ejecutadas”, no como aprobadas. El logout borra la sesión del navegador y la cookie, pero no se afirma que revoque el token en ChillyRoom; la revocación remota no está verificada. El error de credenciales no se provoca aquí para no consumir intentos ni activar bloqueos; se cubre con la prueba automatizada y con la tabla de diagnóstico.

## 4. Prueba 2: escritura autorizada (opcional)

Esta prueba solo se ejecuta si el propietario autoriza explícitamente una escritura sobre su cuenta. Si no hay autorización, se marca “N/A por falta de autorización” y no se habilita nada. Antes de empezar, guarda una copia del volumen o del respaldo nativo.

1. Confirma el estado inicial: `write_enabled=false` en `config` y `write_allowed=false` en el perfil. Detente si algún interruptor ya está activo sin autorización.
2. Activa `SK_NATIVE_WRITE_ENABLED=true` y asegura que el perfil de prueba tenga `--allow-write`. Si el perfil existente no lo tiene, no edites SQLite: crea un perfil nuevo autorizado en el laboratorio. Reinicia o redeploya.
3. Verifica en `config` que `write_enabled=true` y que el perfil aparece con `write_allowed=true`; al iniciar sesión, `write_ready` debe ser `true` solo si además la instalación está lista.
4. Inicia sesión y descarga la partida. Comprueba que ya no aparece el aviso de solo lectura.
5. Cambia las gemas en +1 y pulsa “Preparar edición”. Marca la casilla “Confirmo que quiero sobrescribir la partida de …”. Antes de marcarla, “Subir y verificar” debe estar deshabilitado; después, habilitado.
6. Pulsa “Subir y verificar” una sola vez. Espera la respuesta. Si hay `429`, `502` o un desafío, no reintentes: registra el código y detente.
7. Verifica la persistencia: descarga de nuevo la partida y comprueba que las gemas coinciden con el candidato; usa “Verificar nube” sobre el respaldo confirmado y revisa que el mensaje indique coincidencia.
8. Restaura el respaldo original desde la interfaz y confirma. Descarga otra vez y comprueba que vuelven las gemas originales. No encadenes una segunda subida para “probar suerte”.
9. Apaga `SK_NATIVE_WRITE_ENABLED=false`, reinicia y recarga. El editor debe volver a solo lectura y el botón de subida debe desaparecer. Un intento controlado de confirmación debe responder `503 native_write_disabled` sin subir nada; si la interfaz ya oculta el botón, no fuerces la petición.
10. Deja el entorno como estaba: `SK_NATIVE_WRITE_ENABLED=false` y una nota con el estado final. El permiso del perfil puede seguir en `true`, pero sin el interruptor global no se escribe. No edites SQLite para retirarlo; si el volumen es desechable, destruye el volumen de laboratorio al terminar. Si no puedes garantizar el apagado global, no ejecutes esta prueba.

Si el interruptor global está activo pero el perfil no tiene permiso, la respuesta esperada es `403 native_write_denied`; si falta la instalación, `409 native_installation_required`. La escritura requiere los tres elementos: global, permiso del perfil e instalación completa.

## 5. Prueba 3: aislamiento multicuentas

Es la prueba más importante y la única que puede respaldar una afirmación de aislamiento real. Requiere dos cuentas propias o autorizadas y dos perfiles distintos, cada uno vinculado a una sola cuenta. Usa los identificadores de instalación que el propietario haya aprovisionado para cada perfil; no inventes ni copies los de otra instalación y no reutilices un perfil entre cuentas.

1. Aprovisiona dos perfiles con etiquetas distintas, por ejemplo `<ETIQUETA_A>` y `<ETIQUETA_B>`, ambos `android-global` y sin escritura. Verifica con `--list` que son dos perfiles separados.
2. Usa dos navegadores o dos perfiles de navegador completamente separados (A y B). No uses dos pestañas del mismo perfil: comparten cookies y contaminan la prueba. Inicia sesión con A en el navegador A y con B en el navegador B, seleccionando el perfil correcto en cada caso.
3. Comprueba que ambas sesiones son activas y que cada una muestra la etiqueta y la distribución correctas. No publiques correo, UID ni `player.id`; la evidencia saneada es la etiqueta y el estado.
4. Descarga la partida en ambos navegadores. Anota gemas y SHA-256 solo si hace falta; si las dos partidas tienen las mismas gemas, no concluyas que son la misma cuenta por ese dato. El aislamiento se demuestra con sesiones, respaldos y comportamiento, no solo con el valor de gemas.
5. En A, prepara una edición. En B, abre “Respaldos”: la lista de B no debe incluir el respaldo de A. Desde B, haz una petición `POST /verify` con el `backup_id` de A, obtenido de la respuesta de `prepare` en A y nunca publicado; debe responder `404 backup_not_found`. No copies cookies entre navegadores.
6. Acceso simultáneo: con ambas sesiones activas, descarga en A y B al mismo tiempo. Cada navegador debe recibir su propia partida y no debe aparecer la etiqueta, el respaldo ni el estado de la otra cuenta.
7. Caducidad independiente: en laboratorio, baja la inactividad a 60 s y reinicia. Mantén B activo con una descarga antes de que se cumpla la ventana y deja A sin actividad. Pasados más de 60 s, A debe responder `native_session_expired` y B debe seguir activo. Si no mantienes B activo, ambas pueden caducar; eso no demuestra independencia.
8. Vuelve a iniciar sesión en A. Cierra sesión en A y comprueba que B sigue funcionando: en A una descarga posterior debe dar `401 native_session_required`; en B la sesión y la descarga deben seguir. B no cambia de etiqueta ni de partida.
9. Revisa contaminación antes de cambiar de cuenta: en A no debe haber etiquetas, respaldos ni datos de B en la vista, `localStorage` ni `sessionStorage`; en B no debe aparecer nada de A. Comprueba que cerrar un navegador no afecta al otro.
10. Cambio de cuenta en el navegador A: tras cerrar A, intenta iniciar sesión con las credenciales de B usando el perfil de A. Debe fallar con `409 native_profile_identity_mismatch` y no crear sesión. Después usa el perfil de B y comprueba que A ve la cuenta B y que no conserva respaldos de A.
11. Al terminar, cierra sesión en ambos. En laboratorio desechable puedes destruir el volumen; en producción no borres `native.sqlite3` a mano ni reutilices perfiles vinculados. Anota el estado final.

| Comprobación | Cuenta A | Cuenta B |
| --- | --- | --- |
| Cookie propia y sesión activa | | |
| Etiqueta y distribución correctas | | |
| Descarga propia (no cruzada) | | |
| Respaldo de A invisible desde B | | |
| Logout de A no afecta a B | | |
| Cambio de cuenta rechazado con el perfil ajeno | | |
| Caducidad independiente | | |
| Sin contaminación tras recarga | | |

No se puede concluir aislamiento si solo se probó una cuenta. Si no hay segunda cuenta autorizada, la Prueba 3 se marca “no ejecutada” y el aislamiento real queda pendiente.

## 6. Registro de resultados

El propietario debe rellenar esta tabla y marcar cada resultado. No borres las filas fallidas ni las bloqueadas. La evidencia saneada no debe incluir correo, cookie, token, UID, `player.id`, `distro_id`, `unique_id`, `backup_id` ni capturas sin redactar.

| Prueba | Fecha (UTC) | Commit | Cuenta/etiqueta | Distribución | Resultado | Evidencia saneada | Observaciones |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 · preparación | | | | `android-global` | | | |
| 1 · login e identidad | | | | `android-global` | | | |
| 1 · cookie y secretos | | | | `android-global` | | | |
| 1 · descarga y gemas | | | | `android-global` | | | |
| 1 · preparar y respaldo | | | | `android-global` | | | |
| 1 · logout y sesión inválida | | | | `android-global` | | | |
| 1 · caducidad | | | | `android-global` | | | |
| 2 · escritura autorizada | | | | `android-global` | | | |
| 2 · apagado de escritura | | | | `android-global` | | | |
| 3 · sesiones y partidas | | | | `android-global` | | | |
| 3 · respaldos aislados | | | | `android-global` | | | |
| 3 · logout y cambio de cuenta | | | | `android-global` | | | |
| 3 · caducidad y concurrencia | | | | `android-global` | | | |

Valores de resultado: `PASA`, `FALLA`, `BLOQUEADA`, `NO EJECUTADA`. Una prueba “BLOQUEADA” no es un aprobado. Adjunta solo la evidencia mínima y conserva el resto en el gestor privado del propietario.

## 7. Diagnóstico

| Síntoma | Código / HTTP | Causa probable | Acción |
| --- | --- | --- | --- |
| El login falla antes de enviar credenciales | `native_origin_denied` / 403 | `Origin` ausente o distinto; `Sec-Fetch-Site` cross-site; vista previa `*.pages.dev` | Usa el origen exacto y el dominio principal; revisa `SK_ALLOWED_ORIGINS`; no debilites `SameSite`. |
| La escritura se rechaza con sesión válida | `native_write_denied` / 403 | El perfil no tiene `--allow-write` | Mantén solo lectura o crea un perfil autorizado; no edites SQLite. |
| Credenciales rechazadas | `native_credentials_rejected` / 401 | Correo o contraseña incorrectos; cuenta o canal no válido | Revisa la cuenta; no reintentes en bucle. |
| La sesión no existe | `native_session_required` / 401 | Cookie ausente, borrada o no enviada; logout previo | Inicia sesión; comprueba HTTPS, `credentials: include` y que no se copió la cookie. |
| La sesión caducó | `native_session_expired` / 401 | Inactividad, tope absoluto o rechazo del proveedor | Inicia sesión de nuevo; no hay refresh token verificado. |
| Hay varios perfiles y no se elige | `native_profile_required` / 409 | Más de un perfil disponible | Selecciona el perfil de la cuenta. |
| El perfil pertenece a otra cuenta | `native_profile_identity_mismatch` / 409 | Perfil ya vinculado a otra identidad | Usa un perfil distinto para cada cuenta; no reutilices el vinculado. |
| La identidad no corresponde | `native_identity_mismatch` / 409 | El correo, `uid` o `distro_id` devuelto no coincide con lo solicitado | No se creó sesión; revisa cuenta y perfil, y detente si se repite. |
| Falta la instalación | `native_installation_required` / 409 | Perfil creado con `--no-unique` o sin `unique_id` | Completa el identificador propio desde la web o reprovisiona. |
| Distribución no habilitada | `native_distribution_disabled` / 409 | Se eligió iOS, Vietnam, China o TapTap | Usa `android-global`, la única validada. |
| Demasiados intentos | `native_login_throttled` / 429 | Límite local de intentos | Espera `Retry-After`; no reintentes. |
| El proveedor limita | `native_auth_throttled` / 429 | Límite o desafío de ChillyRoom | Detente; espera; no eludas el control. |
| El proveedor no responde | `native_auth_unavailable` / 502 | Red, timeout o error del gateway | Comprueba salud y conectividad; reintenta solo de forma manual y tras esperar. |
| El proveedor rechaza la distribución | `native_distribution_rejected` / 502 | `distro_id` no válido para esa cuenta o instalación | Revisa el perfil; no inventes ni copies identificadores. |
| Respuesta inesperada del proveedor | `native_auth_protocol` / 502 | Contrato cambiado o respuesta no verificable | No continúes; conserva el código saneado y revisa la rama. |
| Servicio deshabilitado | `native_auth_disabled` / 503 | `SK_NATIVE_AUTH_ENABLED=false` | Habilítalo solo tras verificar clave, volumen y origen. |
| Configuración incompleta | `native_auth_misconfigured` o `native_store_misconfigured` / 503 | Clave, origen, volumen o permisos inválidos | Revisa las variables y los permisos; no imprimas secretos. |
| Almacén no disponible | `native_store_unavailable` / 503 | SQLite bloqueado, disco lleno o permisos | Revisa volumen, propietario, modos y espacio. |
| No hay perfil | `native_profile_missing` / 503 | Falta aprovisionar Android Global | Aprovisiona un perfil y recarga. |
| Escritura apagada | `native_write_disabled` / 503 | Interruptor global en `false` | Es el estado esperado en solo lectura; no lo actives sin autorización. |
| La partida no corresponde | `native_save_identity_mismatch` / 422 | Descarga de otra cuenta o copia manipulada | Detente; no subas; revisa el perfil y el sujeto. |
| Respaldo inexistente | `backup_not_found` / 404 | Respaldo de otra cuenta o ya eliminado | Confirma el aislamiento; no cruces respaldos. |

Diagnóstico saneado con una sesión activa o con `Authorization: Bearer SK_ACCESS_TOKEN`. El token de acceso es el del laboratorio, no la contraseña ni la cookie nativa. Léelo sin eco y no lo pegues en la guía, el historial ni un ticket:

```bash
read -rsp 'SK_ACCESS_TOKEN: ' SK_ACCESS_TOKEN; echo
export SK_ACCESS_TOKEN
curl -fsS "$API_BASE/api/v1/cloud/native/diagnostics" \
  -H "Authorization: Bearer $SK_ACCESS_TOKEN" | jq '{
    enabled, configured, write_enabled, cookie_secure, origin_scheme, store_ready,
    profiles_total, profiles_bound, sessions_total, sessions_active,
    idle_seconds, login_attempts, login_window_seconds,
    distributions: [.distributions[] | {id, enabled, validated}],
    events: [.events[] | {at, event, outcome, code}]
  }'
unset SK_ACCESS_TOKEN
```

La ruta también acepta la cookie de una sesión activa desde el navegador. No copies la cookie a `curl` ni a un archivo compartido. El JSON completo de eventos incluye un prefijo del sujeto; no publiques la salida cruda, solo los campos seleccionados. Sin sesión ni Bearer válido, `diagnostics` responde `401 native_session_required`.

## 8. Criterios de aceptación

- [ ] El commit probado contiene la implementación de la Fase 6.8 y quedó registrado en la tabla; el entorno es HTTPS y el origen es el exacto.
- [ ] `health` responde `200` y `status=ok`; `config` está listo, solo `android-global` habilitada y las otras cinco deshabilitadas.
- [ ] La configuración y los diagnósticos no muestran clave, token, correo, contraseña, `distro_id` ni `unique_id`.
- [ ] La cookie tiene los atributos esperados (`__Host-sk_native`, `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, sin `Domain`) o se documenta la variante local.
- [ ] La Prueba 1 pasa completa: login, identidad, descarga, gemas, preparación, respaldo, no escritura y logout. La caducidad se aprueba solo si se observó; si no, queda “no ejecutada”.
- [ ] La Prueba 2 se ejecutó solo con autorización y el entorno quedó con escritura apagada; si no hubo autorización, consta como “N/A” y no se declara soporte de escritura.
- [ ] La Prueba 3 pasa con dos cuentas y dos perfiles: sesiones independientes, respaldos aislados, partidas propias, logout de A sin efecto en B, cambio de cuenta rechazado con el perfil ajeno y sin contaminación.
- [ ] La tabla de resultados está completa, con evidencia saneada y sin secretos.
- [ ] La lista de seguridad de la sección 9 está revisada.
- [ ] El estado final de producción es solo lectura salvo decisión explícita y documentada del propietario.

Hasta que el propietario complete la Prueba 3, no se puede afirmar que el aislamiento multicuentas esté validado en producción. Hasta que complete la Prueba 2, no se puede afirmar que la escritura funcione con datos reales. Tampoco se puede afirmar que ChillyRoom autorice el uso a terceros, que el token se revoque en el proveedor al cerrar sesión, que la sesión se renueve, que las otras distribuciones funcionen, que el flujo resista carga concurrente real ni que el despliegue se haya hecho desde esta sesión. Las pruebas automatizadas y esta guía no sustituyen esas comprobaciones.

## 9. Comprobaciones de seguridad durante la prueba

- [ ] HTTPS válido en editor y API; sin `curl -k`, sin desactivar TLS y sin proxy de inspección.
- [ ] Cookie `HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/`, sin `Domain`; el valor no se copia ni se comparte.
- [ ] El token del proveedor no aparece en JavaScript, `localStorage`, `sessionStorage` ni en respuestas al navegador. La cookie puede verse como `Set-Cookie`, pero no es legible desde JS.
- [ ] La contraseña no aparece en pantalla, red, logs, capturas ni historial; el campo se limpia después del intento. Los logs tampoco muestran correo, token ni identificadores privados.
- [ ] No se muestran correo, UID, `player.id`, `distro_id`, `unique_id` ni `backup_id` en la evidencia.
- [ ] Logout borra la sesión local y la interfaz vuelve al acceso; no se afirma revocación remota.
- [ ] No se comparten enlaces con cookie, tokens, capturas sin redactar ni archivos del volumen.
- [ ] No se usan datos, perfiles, respaldos ni partidas de otra cuenta; cada navegador usa su propio perfil.
- [ ] Ante `429`, desafío, captcha o bloqueo: detenerse, no reintentar y no eludir.
- [ ] La escritura permanece apagada salvo la Prueba 2 autorizada; al terminar se verifica que volvió a `false`.
- [ ] Los identificadores privados no se pasan como argumentos, no se imprimen y no se guardan en Git.

## 10. Referencias

- [Despliegue persistente en Coolify](deployment.md): variables, volumen, HTTPS, aprovisionamiento y verificación.
- [Identificadores observados](identifiers.md): límites de `distro_id`, `unique_id`, token y aislamiento.
- [Pruebas de la API nativa](../../../backend/tests/test_native_api.py): sesiones, respaldos, escritura, origen y diagnósticos.
- [Pruebas de interfaz nativa](../../../frontend/tests/native-auth.spec.ts): estados, etiquetas y flujo de solo lectura.
- [Fase 6.3 · Cuentas vinculadas](../phase6-3/README.md): flujo anterior que se conserva en `/partida/vinculadas`.

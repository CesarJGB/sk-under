# sk-under

**Soul Knight Editor · Fase 6.9**

Editor web privado para inspeccionar copias locales y, con autorización expresa, autenticar una cuenta propia de ChillyRoom y editar sus gemas desde el navegador. La muestra sintética `.skdemo` permite edición y exportación. El adaptador opcional de la Fase 3 lee nueve estructuras `.data` observadas en muestras de Soul Knight 8.6.0 y permite descargar copias intactas. [Configuración y cobertura de la Fase 3](docs/phase3/IMPLEMENTATION.md)

La Fase 4 documenta el análisis estático del APK 8.8.0 y las pruebas con las muestras de 8.6.0. [Informe de la Fase 4](docs/research/phase4/README.md)

La Fase 5.1 registra las pruebas de ejecución de Soul Knight 8.8.0 y de acceso al guardado en un laboratorio Android. [Validación experimental](docs/research/phase5-experimental/README.md)

La Fase 5.3 verificó una ruta condicional de precarga en el panel y reconstruyó las nueve referencias locales 8.6.0 en Linux. El importador acepta agregados suministrados en JSON o gzip. [Informe de Fase 5.3](docs/research/phase5-3/README.md) · [Uso del importador](docs/research/phase5-3/importer.md)

La Fase 5.4 separó el transporte RPC, documentó la máquina de estados de recuperación y añadió un cliente Linux con transporte remoto deshabilitado. La sesión autenticada y la muestra real de 8.8.0 siguen bloqueadas. [Informe de Fase 5.4](docs/research/phase5-4/README.md) · [Prototipo Linux](docs/research/phase5-4/linux-client-prototype.md)

La Fase 5.5 descifró la metadata real de 8.8.0, inventarió `CloudSaveGameData` y sus secciones, comparó los nombres con las nueve muestras 8.6.0 y añadió un laboratorio local de edición y un decodificador RPC gzip experimental. [Informe de Fase 5.5](docs/research/phase5-5/README.md)

La Fase 5.6 obtuvo un perfil local auténtico de Soul Knight 8.8.0 desde el APK oficial en un emulador propio, decodificó sus 18 archivos de datos (incluido `game.data`), confirmó gzip en el cuerpo de `ZipHelper.Decompress` y añadió un puente local Linux con roundtrip binario exacto. El agregado de nube y la aceptación por el cliente siguen pendientes. [Informe de Fase 5.6](docs/research/phase5-6/README.md)

La Fase 5.7 estabilizó el cliente 8.8.0 en un AVD Android 11 x86_64 con ABI arm64, inició sesión ChillyRoom por email y ejecutó una lectura auténtica de `/Backup/FetchGameData` desde Linux con el token del cliente. La cuenta de laboratorio devolvió un agregado legacy vacío; no se obtuvo `CloudSaveGameData` ni se demostró la aceptación visible de una modificación. [Informe de Fase 5.7](docs/research/phase5-7/README.md) · [Estabilización](docs/research/phase5-7/emulator-stabilization.md) · [Lectura de nube](docs/research/phase5-7/authentic-cloud-read.md)

La Fase 5.8 realizó un guardado y una recuperación oficiales con progreso visible, extrajo del proceso un agregado auténtico no vacío y verificó su relación parcial con archivos locales. [Resultados experimentales](docs/research/phase5-8/README.md).

La Fase 5.9 reprodujo la descarga moderna desde Linux con Android detenido: cuatro lecturas autenticadas devolvieron el mismo agregado de 114.778 bytes, con `gameData.gems=1000`. También preparó un candidato de subida, pero no lo transmitió. [Informe de Fase 5.9](docs/research/phase5-9/README.md).

La Fase 6.0 completó el análisis estático de `UploadAsync`, `JsonPayload.Data`, la compresión y los callbacks de token, y reprodujo el sobre JSON con Json.NET. La escritura remota seguía sin ejecutarse. [Resumen de Fase 6.0](docs/research/phase6-0/summary.md).

La Fase 6.1 ejecutó la primera subida real desde Linux a `/BlobSave/Upload`. El servidor devolvió `200` con `true`; una descarga posterior confirmó la persistencia byte a byte. Después se cambió `gameData.gems` de `1000` a `1001`, se subió, se volvió a descargar con el mismo SHA-256 y el cliente oficial 8.8.0 recuperó la copia, escribió `1001` en `game.data` y abrió el hall con ese valor. [Informe de Fase 6.1](docs/research/phase6-1/README.md) · [Protocolo](docs/research/phase6-1/protocol.md) · [Implementación](docs/research/phase6-1/implementation.md)

La Fase 6.2 convirtió ese protocolo en un editor web de gemas. La página **Partida** descarga la copia auténtica de laboratorio, muestra `gameData.gems`, prepara una copia determinista que solo cambia ese campo, crea un respaldo privado, valida el resultado y permite confirmar la subida con una autorización administrativa del servidor. La persistencia se comprueba con una descarga posterior y el original se puede restaurar desde el respaldo. La escritura sigue deshabilitada por defecto y no se puede activar desde el navegador. [Informe de Fase 6.2](docs/research/phase6-2/README.md)

La [Fase 6.3](docs/research/phase6-3/README.md) documenta la vinculación privada, el editor por cuenta y la prueba real de persistencia en Android Global. El inicio directo con correo y contraseña se integró en la Fase 6.8, pendiente de la prueba real del propietario.

La [Fase 6.7](docs/research/phase6-7/README.md) obtuvo una sesión nueva desde Linux con la cuenta de laboratorio, verificó su identidad y descargó la partida real sin emulador activo. La diferencia decisiva fue la cabecera `x-distro-id`; el cuerpo correcto es JSON plano. El cliente experimental y la propuesta de integración quedan en la rama de investigación, no en producción. [Evidencia saneada](docs/research/phase6-7/evidence.json)

La [Fase 6.8](docs/research/phase6-8/README.md) (rama `feature/phase6-8-web-native-auth`, commit `f87d63f`) integra ese cliente en el backend y añade acceso web con sesiones aisladas por cuenta: formulario con distribución, correo y contraseña; verificación de identidad; perfiles de instalación cifrados; descarga, edición, respaldo y verificación de gemas. Solo Android Global está habilitada; las demás distribuciones aparecen deshabilitadas. La escritura sigue apagada por defecto.

La [Fase 6.9](docs/research/phase6-9/README.md) elimina el aprovisionamiento manual del flujo normal. El backend consulta el portal oficial de cuentas, recupera el distro del jugador de Soul Knight, genera un código de instalación nuevo, lo cifra y lo conserva, y descarga la partida con una sesión aislada. La prueba real con la cuenta de laboratorio completó portal → login → descarga de 114.779 bytes con 99.999 gemas → edición y respaldo cifrado → reinicio del proceso → descarga y re-login. Las tres cuentas facilitadas no autenticaron con la contraseña indicada (rechazo del gateway y del portal); la validación multicuenta queda pendiente de esas credenciales. También se añadieron cifrado de respaldos en reposo, CSP, límite de intentos atómico, IP real tras proxies confiables y sesiones persistentes. [Identificadores](docs/research/phase6-9/identifiers.md) · [Experimentos](docs/research/phase6-9/experiments.md) · [Seguridad](docs/research/phase6-9/security.md) · [Despliegue](docs/research/phase6-9/deployment.md)

## Arquitectura

```text
soul-knight-editor/
├── .env.example
├── .gitignore
├── README.md
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── public/
│   │   ├── _headers
│   │   └── ejemplo.skdemo
│   └── src/
│       ├── App.tsx
│       ├── api.ts
│       ├── main.tsx
│       ├── session.ts
│       ├── styles.css
│       ├── ui.tsx
│       ├── useOperation.ts
│       └── pages/
│           ├── HomePage.tsx
│           ├── ImportPage.tsx
│           ├── LabEditorPage.tsx
│           ├── NativeAuthPage.tsx
│           ├── CloudAccountsPage.tsx
│           ├── EditorPage.tsx
│           └── ExportPage.tsx
└── backend/
    ├── .dockerignore
    ├── Dockerfile
    ├── pyproject.toml
    ├── uv.lock
    ├── app/
    │   ├── __init__.py
    │   ├── api/
    │   │   ├── __init__.py
    │   │   ├── cloud_accounts.py
    │   │   ├── cloud_lab.py
    │   │   ├── native.py
    │   │   ├── routes.py
    │   │   └── uploads.py
    │   ├── native/
    │   │   ├── client.py
    │   │   ├── distributions.py
    │   │   ├── provision.py
    │   │   ├── service.py
    │   │   └── store.py
    │   ├── cloud/
    │   │   ├── backup_store.py
    │   │   ├── gems_editor.py
    │   │   ├── lab_service.py
    │   │   └── ... (protocolo y transporte de fases anteriores)
    │   ├── formats/
    │   │   ├── __init__.py
    │   │   ├── adapter.py
    │   │   ├── demo.py
    │   │   ├── game_data.py
    │   │   ├── real_save.py
    │   │   └── registry.py
    │   ├── parsers/
    │   │   ├── __init__.py
    │   │   ├── demo.py
    │   │   └── json_document.py
    │   ├── serializers/
    │   │   ├── __init__.py
    │   │   └── demo.py
    │   ├── bridge.py
    │   ├── engine.py
    │   ├── errors.py
    │   ├── local_save.py
    │   ├── file_validation.py
    │   ├── main.py
    │   ├── models.py
    │   └── settings.py
    └── tests/
        ├── conftest.py
        ├── fixtures/sintetico.skdemo
        ├── test_api.py
        └── test_engine.py
```

- **Frontend.** React, TypeScript, Vite, Tailwind CSS y React Router. La SPA recibe las capacidades del backend y genera los campos de edición a partir del contrato. La copia cargada, los cambios pendientes y el token permanecen en memoria durante la sesión de la pestaña.
- **Backend.** FastAPI, Pydantic y Uvicorn. Las rutas comprueban el acceso y limitan la carga antes de inspeccionar el archivo. Cada petición envía de nuevo la copia original. El servicio procesa bytes en memoria, sin base de datos, archivos temporales ni volúmenes de partidas.
- **Motor.** El registro contiene adaptadores de formato y versión. Cada adaptador reconoce una firma, lee y valida el documento, declara campos editables, aplica cambios a una copia y serializa. El motor comprueba la lista de campos autorizados, vuelve a detectar el formato y compara el documento completo reanalizado con el resultado esperado. Una exportación sin cambios efectivos conserva los bytes de entrada.

## Requisitos e instalación local

- Node.js 22.12+ dentro de la serie 22, o Node.js 24+, y npm.
- Python 3.12+ y [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Docker con BuildKit para construir y probar la imagen.

Desde la raíz, crea la configuración local.

```bash
cp .env.example .env
```

Terminal de API.

```bash
cd backend
uv sync --locked
uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8017 --reload --no-proxy-headers --no-access-log
```

Terminal de frontend.

```bash
cd frontend
npm ci
npm run dev
```

Abre `http://127.0.0.1:5173`. En **Importar**, pulsa **Usar muestra** o selecciona `frontend/public/ejemplo.skdemo`. Modifica un campo, revisa los cambios, valida la copia y descárgala como `copia-editada.skdemo`. Puedes importar esa copia para comprobar el resultado. Si el puerto 8017 está ocupado, usa otro en Uvicorn y actualiza `VITE_API_BASE_URL` en `.env` antes de arrancar Vite.

Swagger UI está en `http://127.0.0.1:8017/docs` y el esquema generado está en `/openapi.json`.

## Variables de entorno

| Variable | Servicio | Valores |
| --- | --- | --- |
| `SK_ENV` | Backend | `production` por defecto. `development` habilita pruebas sin token solo con cliente y host de loopback. |
| `SK_ACCESS_TOKEN` | Backend | Vacío por defecto. Cuando se configura, se exige en las tres rutas de archivos en cualquier modo. Usa un secreto aleatorio de al menos 32 caracteres ASCII visibles. |
| `SK_ALLOWED_ORIGINS` | Backend | Arreglo JSON de orígenes exactos, vacío por defecto. Incluye esquema y puerto cuando corresponda. El ejemplo local incluye `http://127.0.0.1:5173` y `http://localhost:5173`. |
| `SK_MAX_FILE_BYTES` | Backend | `1048576` por defecto. Rango de 1 a 8388608 bytes. Limita el archivo decodificado y la copia de salida. |
| `SK_CLOUD_SESSION_TOKEN` | Backend | Vacío por defecto. Sesión ya emitida por el cliente oficial para la cuenta de laboratorio. Nunca se envía al navegador. |
| `SK_CLOUD_UNIQUE_ID` | Backend | Vacío por defecto. Identificador de la instalación de laboratorio. |
| `SK_CLOUD_DISTRO_ID` | Backend | Vacío por defecto. Distribución observada de la instalación de laboratorio. |
| `SK_CLOUD_ADMIN_TOKEN` | Backend | Vacío por defecto. Secreto de al menos 32 caracteres ASCII visibles. Se exige en la cabecera `X-SK-Cloud-Admin` para confirmar o restaurar. |
| `SK_CLOUD_WRITE_ENABLED` | Backend | `false` por defecto. Solo `true` habilita la escritura remota; el frontend no puede cambiarlo. |
| `SK_CLOUD_BACKUP_DIR` | Backend | Ruta absoluta privada, fuera del repositorio. Por defecto `~/.local/share/sk-under/backups`. Los archivos se crean con modo `0600` y el directorio con `0700`. |
| `SK_NATIVE_AUTH_ENABLED` | Backend | `false` por defecto. Habilita `/api/v1/cloud/native/*` y el formulario de acceso. |
| `SK_NATIVE_WRITE_ENABLED` | Backend | `false` por defecto. Interruptor global de escritura nativa; el navegador no puede activarlo. |
| `SK_NATIVE_STORE_KEY` | Backend | Clave de 32 bytes en 64 hex para AES-SIV. Obligatoria si la autenticación nativa está habilitada. Genérala con `openssl rand -hex 32`. |
| `SK_NATIVE_BACKUP_KEY` | Backend | Opcional. Clave de 32 bytes en 64 hex para cifrar los respaldos. Si falta, se deriva de `SK_NATIVE_STORE_KEY` con HMAC-SHA-256 y un dominio distinto. |
| `SK_NATIVE_AUTO_IDENTITY` | Backend | `true` por defecto. Genera y conserva un par de instalación por cuenta. El usuario solo aporta correo, contraseña y distribución. |
| `SK_NATIVE_AUTO_ALLOW_WRITE` | Backend | `false` por defecto. No autoriza escritura automáticamente; la edición remota sigue siendo opt-in. |
| `SK_NATIVE_PORTAL_ENABLED` | Backend | `true` por defecto. Consulta el portal oficial de cuentas para recuperar el distro del jugador existente. Sin esta consulta, una cuenta con progreso anterior puede quedar en un jugador vacío. |
| `SK_NATIVE_STORE_DIR` | Backend | Almacén SQLite de perfiles y sesiones. Por defecto `~/.local/share/sk-under/native`; en la imagen `/var/lib/sk-under/native`. |
| `SK_NATIVE_BACKUP_DIR` | Backend | Respaldos por subject. Por defecto `~/.local/share/sk-under/native-backups`; en la imagen `/var/lib/sk-under/native-backups`. |
| `SK_NATIVE_ORIGIN` | Backend | Origen HTTPS exacto del editor, incluido en `SK_ALLOWED_ORIGINS`. Si está vacío se usa `SK_CLOUD_ACCOUNTS_ORIGIN`. |
| `SK_NATIVE_DISTRO_ID` | Backend | Opcional y solo administrativo/migración. `x-distro-id` privado de una instalación propia para crear un perfil inicial. El flujo normal no lo necesita. Nunca se publica ni se registra en claro. |
| `SK_NATIVE_UNIQUE_ID` | Backend | Opcional y solo administrativo/migración. Identificador de instalación de esa misma instalación. El flujo normal lo genera y lo cifra. |
| `SK_NATIVE_PROFILE_LABEL` | Backend | Etiqueta del perfil inicial. Por defecto `Instalación Android Global`. |
| `SK_NATIVE_PROFILE_ALLOW_WRITE` | Backend | `false` por defecto. Permiso de escritura solo para el perfil aprovisionado. |
| `SK_NATIVE_IDLE_SECONDS` | Backend | `1800` por defecto. Caducidad por inactividad, entre 60 y 86400. |
| `SK_NATIVE_LOGIN_ATTEMPTS` | Backend | `5` por defecto. Fallos permitidos por IP/correo en la ventana. |
| `SK_NATIVE_LOGIN_WINDOW_SECONDS` | Backend | `900` por defecto. Ventana del límite de intentos. |
| `SK_NATIVE_TRUSTED_PROXIES` | Backend | Vacío por defecto. IPs o CIDR de proxies confiables, separados por comas o JSON. Solo entonces se interpreta `X-Forwarded-For`; si está vacío se usa la IP del socket. |
| `VITE_API_BASE_URL` | Frontend | URL pública de la API, sin `/api/v1`. En desarrollo cae por defecto en `http://127.0.0.1:8017`. Configúrala explícitamente al compilar para otro entorno. |

Para desarrollo, el backend y Vite leen el `.env` de la raíz. El backend también puede leer `backend/.env`. Las variables del proceso tienen prioridad. Los valores `VITE_*` son públicos y se incorporan al JavaScript durante el build. El propietario introduce el token en el formulario de importación. En producción sin token, las rutas de archivos devuelven `503` y `health` informa `access_mode: "disabled"`. La API rechaza el token ausente o incorrecto con `401` cuando está configurado.

## Acceso nativo web (Fase 6.9)

La página `/partida` permite iniciar sesión con una cuenta propia de ChillyRoom usando solo distribución, correo y contraseña. El flujo es: consulta del portal oficial → selección del jugador → generación y cifrado del par de instalación → login → verificación de identidad → descarga autorizada → edición → respaldo cifrado → confirmación explícita → subida → verificación. El flujo anterior por enlace de la Fase 6.3 sigue disponible en `/partida/vinculadas`.

La autenticación nativa permanece deshabilitada hasta que el propietario configure el origen y `SK_NATIVE_STORE_KEY`. No se exige aprovisionar `distro_id` ni `unique_id`: el backend los resuelve y los conserva cifrados con AES-SIV. El portal se consulta una sola vez por cuenta; después el perfil se reutiliza y no se vuelve a llamar al portal. La CLI `python -m app.native.provision` queda como herramienta administrativa o de migración para una instalación concreta.

Si el proveedor limita la vinculación de un dispositivo nuevo (`error 100509`), el backend conserva el par generado, guarda la espera indicada y no reintenta automáticamente. El frontend muestra el plazo y permite reintentar la descarga después. Si la cuenta no tiene partida en la nube (`100504`), se informa sin crear ni sobrescribir nada. Los respaldos nativos se cifran en reposo (AES-SIV); los antiguos se pueden migrar con `python -m app.native.maintenance migrate-backups`.

| Método y ruta | Autenticación | Respuesta |
| --- | --- | --- |
| `GET /api/v1/cloud/native/config` | pública, sin secretos | distribuciones, perfiles, disponibilidad y estado de sesión. |
| `POST /api/v1/cloud/native/login` | origen exacto + JSON | sesión verificada, caducidades y resumen de la partida; nunca token, correo ni identificadores. |
| `GET /api/v1/cloud/native/session` | cookie | estado de la sesión del navegador. |
| `POST /api/v1/cloud/native/logout` | cookie + origen | revoca la sesión local y borra la cookie. |
| `POST /api/v1/cloud/native/installation` | cookie + origen | vía administrativa para completar un `unique_id` en un perfil migrado; el flujo normal no la usa. |
| `GET /api/v1/cloud/native/save` | cookie | gemas, tamaño y SHA-256 de la partida. |
| `POST /api/v1/cloud/native/{prepare,confirm,restore,verify}` | cookie + origen | mismas validaciones que el laboratorio, por cuenta. |
| `GET /api/v1/cloud/native/backups` | cookie | respaldos del subject autenticado. |
| `GET /api/v1/cloud/native/diagnostics` | cookie o Bearer existente | conteos y eventos saneados. |

La cookie es `__Host-sk_native` en HTTPS (`Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`); en desarrollo local se usa `sk_native_dev`. Las sesiones caducan por inactividad y por el plazo absoluto; el cierre de sesión no afirma revocar el token en ChillyRoom. Los errores tienen códigos estables (`native_credentials_rejected`, `native_portal_rejected`, `native_portal_challenge_required`, `native_device_binding_throttled`, `native_no_cloud_save`, `native_login_throttled`, `native_session_expired`, `native_session_rejected`, `native_write_disabled`, etc.) y no incluyen cuerpos remotos ni secretos.

La guía de despliegue está en [deployment.md](docs/research/phase6-9/deployment.md) y la validación con cuentas reales en [manual-testing.md](docs/research/phase6-9/manual-testing.md).

## Editor web de partida (Fase 6.2)

El laboratorio administrativo en `/partida/laboratorio` usa las rutas `/api/v1/cloud/lab/*`. La lectura descarga la copia auténtica, la preparación crea un respaldo privado y valida que solo cambió `gameData.gems`, y la confirmación exige simultáneamente `SK_CLOUD_WRITE_ENABLED=true`, `SK_CLOUD_ADMIN_TOKEN` configurado y la cabecera `X-SK-Cloud-Admin` correcta. La escritura se comprueba siempre con una descarga posterior; un `200` aislado no se presenta como persistencia.

La edición es determinista y conserva los bytes ajenos al campo: exige la serialización canónica observada en 8.8.0 (claves ordenadas, separadores `", "` y `": "`, sin indentación) y rechaza cualquier copia que no la reproduzca. El valor aceptado es un entero entre `0` y `2147483647`. Un valor igual al actual genera una operación sin cambios y la confirmación remota se rechaza. La restauración reenvía el original solo si la nube contiene exactamente el candidato confirmado de ese respaldo.

La API no devuelve el contenido de la partida ni las credenciales: solo gemas, tamaños, SHA-256, metadatos del respaldo y estado de la operación. Los respaldos se guardan fuera del repositorio.

### Escritura experimental por CLI (Fase 6.1)

La subida real también está disponible por CLI en `backend/app/cloud/blob_upload.py` y el ciclo con verificación en `backend/app/cloud/blob_roundtrip.py`. La escritura permanece desactivada por defecto y exige una sesión de laboratorio ya emitida por el cliente oficial.

```bash
export SK_CLOUD_SESSION_TOKEN='<sesión de laboratorio>'
export SK_CLOUD_UNIQUE_ID='<identificador de la instalación>'
export SK_CLOUD_DISTRO_ID='<distribución>'
export SK_CLOUD_WRITE_EXPERIMENTAL=1

cd backend
.venv/bin/python -m app.cloud.blob_roundtrip /ruta/privada/agregado.json \
  --confirm-experimental-write
```

El comando sube, vuelve a descargar y solo devuelve éxito si el SHA-256 remoto coincide con el enviado. No imprime credenciales ni contenido de la partida. Un `200` aislado no se considera confirmación de persistencia. Los detalles, límites y evidencia están en el [informe de Fase 6.1](docs/research/phase6-1/README.md).

## Contratos de API

Todas las rutas de archivos reciben JSON UTF-8 con el archivo original en Base64 estándar y sin compresión. El JSON se limita durante la lectura a `4 × ceil(SK_MAX_FILE_BYTES / 3) + 16384` bytes. Los endpoints de validación y exportación reciben además un objeto `changes`, con hasta 32 entradas. Cada clave debe corresponder a un campo marcado como editable por el adaptador. Por ejemplo, `{"label":"Revisión","sample_count":5}`. Para conservar los valores envía `{}`.

| Método y ruta | Entrada | Respuesta exitosa |
| --- | --- | --- |
| `GET /api/v1/health` | — | Estado, modo de acceso y límite de archivo. |
| `GET /api/v1/formats` | — | Formatos registrados, versiones, extensiones y nivel de compatibilidad. |
| `POST /api/v1/files/inspect` | `content_base64` | Formato, tamaño, SHA-256 del original y campos con tipo, valor y restricciones. |
| `POST /api/v1/files/validate` | `content_base64`, `changes` | Resultado validado, cambios efectivos, tamaño y SHA-256 de la copia. |
| `POST /api/v1/files/export` | `content_base64`, `changes` | Bytes de la copia verificada con `Content-Type: application/octet-stream` y nombre en `Content-Disposition`. |
| `GET /api/v1/cloud/lab/status` | — | Modo del laboratorio, disponibilidad de lectura/escritura, respaldos y rango de gemas. |
| `GET /api/v1/cloud/lab/save` | — | Gemas actuales, origen, tamaño y SHA-256 de la copia auténtica. No devuelve el contenido. |
| `POST /api/v1/cloud/lab/prepare` | `new_gems` | Copia candidata verificada, vista previa del cambio y respaldo privado creado. |
| `POST /api/v1/cloud/lab/confirm` | `backup_id`, `expected_sha256`, `confirmation: "SUBIR"` | Subida autenticada, descarga posterior y resultado `persisted`. Exige `X-SK-Cloud-Admin`. |
| `POST /api/v1/cloud/lab/verify` | `backup_id` | Comparación de la nube con el original y el candidato del respaldo. |
| `POST /api/v1/cloud/lab/restore` | `backup_id`, `confirmation: "RESTAURAR"` | Reenvío verificado del original. Exige `X-SK-Cloud-Admin`. |
| `GET /api/v1/cloud/lab/backups` | — | Resúmenes de respaldos privados, sin contenido de la partida. |

Los errores de las rutas usan `{"error":{"code":"…","message":"…","issues":[]}}`. Los problemas de un campo pueden incluir `field_id`. Una inspección fallida devuelve el error y omite los campos. Los estados incluyen `400` para un cuerpo malformado, `401` y `403` para acceso, `404` para un respaldo inexistente, `409` para una operación sin cambios, una nube que cambió o un respaldo ya confirmado, `413` para límites, `415` para formato o contenido no admitido, `422` para datos o cambios inválidos, `502` para fallos del servicio de nube y `503` cuando falta configurar la protección o la escritura. Un fallo de verificación local devuelve `500` sin entregar un archivo.

En modo protegido, incluye `Authorization: Bearer <token>` en las tres operaciones de archivo. CORS controla el acceso desde navegadores y el token autentica las peticiones. El backend no recibe nombres ni rutas de archivos desde el cliente. El nombre de descarga lo elige el adaptador, y las respuestas de archivos indican `Cache-Control: no-store`. La configuración de Uvicorn que se entrega desactiva los registros de acceso. Al configurar un proxy, mantén fuera de sus registros el cuerpo y la cabecera de autorización.

## Pruebas y compilación

```bash
# Desde backend/
uv sync --locked
uv run --locked pytest -q

# Desde frontend/
npm ci
npm run build
npx playwright install chromium
npm run test:browser

# Desde la raíz del monorepo
docker build -t soul-knight-editor:local backend
docker run --rm -p 127.0.0.1:8018:8000 soul-knight-editor:local
```

La última orden permite consultar `http://127.0.0.1:8018/api/v1/health` con el servicio en modo seguro por defecto. Los endpoints de archivos permanecen deshabilitados hasta configurar el token. Las pruebas cubren el fixture válido, entrada malformada, firmas desconocidas, límites de entrada y salida, cambios inválidos, relectura, conservación del original, CORS, control de acceso y contratos OpenAPI.

Para probar localmente el frontend ya compilado, añade `http://127.0.0.1:4173` a `SK_ALLOWED_ORIGINS` y reinicia el backend. Compila con `VITE_API_BASE_URL=http://127.0.0.1:8017 npm run build` y ejecuta `npm run preview -- --host 127.0.0.1` desde `frontend/`. Cambia la URL si levantaste la API en otro puerto.

## Preparación para publicación

### Cloudflare Pages

Conecta `CesarJGB/sk-under` en **Workers & Pages → Create application → Pages → Import an existing Git repository**.

| Opción | Valor |
| --- | --- |
| Framework | Vite (React) |
| Rama de producción | `main` |
| Directorio raíz | `frontend` |
| Comando de compilación | `npm ci && npm run build` |
| Directorio de salida | `dist`, relativo a `frontend` |
| `NODE_VERSION` | `24` |
| `VITE_API_BASE_URL` | URL HTTPS final del backend, por ejemplo `https://api-editor.example.com`, sin el sufijo `/api/v1` |

Configura `VITE_API_BASE_URL` como variable de build de producción y vuelve a compilar si cambia la URL. Su valor es público. Cloudflare Pages aplica su fallback nativo de SPA al recargar rutas como `/editor` y `/exportar` si `dist/` carece de un `404.html` en la raíz. [Cloudflare Pages para monorepos](https://developers.cloudflare.com/pages/configuration/monorepos/) · [Rutas SPA](https://developers.cloudflare.com/pages/configuration/serving-pages/) · [Imagen de build](https://developers.cloudflare.com/pages/configuration/build-image/)

Para usar un subdominio como `editor.example.com`, abre **Custom domains → Set up a custom domain** en el proyecto Pages, añade el subdominio y sigue las indicaciones del panel para verificar el DNS y activar HTTPS. Si el DNS se administra fuera de Cloudflare, crea el CNAME que indique Pages hacia el host `*.pages.dev` del proyecto después de asociar el dominio en el panel. Añade el origen exacto `https://editor.example.com` a `SK_ALLOWED_ORIGINS` en Coolify. Si también usarás el host `*.pages.dev`, autoriza su origen por separado. Para limitar quién puede abrir la interfaz estática, protege los dominios y vistas previas que mantengas accesibles mediante Cloudflare Access. [Dominios personalizados](https://developers.cloudflare.com/pages/configuration/custom-domains/) · [Vistas previas](https://developers.cloudflare.com/pages/configuration/preview-deployments/)

### Coolify

| Opción | Valor |
| --- | --- |
| Fuente | GitHub, `CesarJGB/sk-under` |
| Rama | `main` |
| Build Pack | `Dockerfile` |
| Directorio base | `/backend` |
| Dockerfile Location | `/Dockerfile`, relativo al directorio base |
| Puerto interno (Ports Exposes) | `8000` |
| Dominio de la API | URL HTTPS, por ejemplo `https://api-editor.example.com` |
| Healthcheck | El de la imagen en `/api/v1/health` |

Las cuentas vinculadas, los volúmenes de producción y el diagnóstico del login están en la [guía de la Fase 6.4](docs/research/phase6-4/README.md).
La [Fase 6.5](docs/research/phase6-5/README.md) verifica el acceso al portal de ChillyRoom y documenta qué falta para que ese acceso abra la partida en `/partida`.

El puerto `8017` corresponde al desarrollo local. Dentro del contenedor, Uvicorn escucha en `0.0.0.0:8000` como usuario sin privilegios. El Dockerfile se construye usando únicamente el contexto `backend/`. En Coolify, deja desactivado el ajuste de healthcheck del panel para que se utilice el de la imagen. La inspección y exportación local no requieren volúmenes. El laboratorio de nube usa `/var/lib/sk-under/backups` dentro del contenedor; si vas a habilitar la escritura real, monta ahí un volumen persistente y privado. [Dockerfile en Coolify](https://coolify.io/docs/applications/builds/dockerfile) · [Healthchecks en Coolify](https://coolify.io/docs/applications/configuration/health-checks)

Configura estas variables de runtime antes de habilitar la edición:

| Variable | Valor de producción |
| --- | --- |
| `SK_ENV` | `production` |
| `SK_ACCESS_TOKEN` | Secreto aleatorio de al menos 32 caracteres ASCII visibles, guardado en Coolify como variable de runtime |
| `SK_ALLOWED_ORIGINS` | Arreglo JSON con los orígenes HTTPS exactos del frontend, por ejemplo `["https://editor.example.com"]` |
| `SK_MAX_FILE_BYTES` | `1048576` por defecto. Ajústalo solo si cambia el tamaño máximo aceptado. |
| `SK_CLOUD_SESSION_TOKEN`, `SK_CLOUD_UNIQUE_ID`, `SK_CLOUD_DISTRO_ID` | Solo si se habilitará el laboratorio real. La sesión se obtiene fuera de banda desde el cliente oficial y nunca se publica. |
| `SK_CLOUD_ADMIN_TOKEN` | Secreto independiente de al menos 32 caracteres ASCII visibles. Se exige en la cabecera `X-SK-Cloud-Admin` para confirmar o restaurar. |
| `SK_CLOUD_WRITE_ENABLED` | `false` por defecto. Cámbialo a `true` solo durante una operación de laboratorio autorizada. |
| `SK_CLOUD_BACKUP_DIR` | Ruta absoluta privada y persistente, fuera del repositorio, con permisos restrictivos. |

Comprueba que el dominio HTTPS funcione antes de introducir un token. Puedes generar el secreto con `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`. Guárdalo en Coolify y en el gestor privado del propietario.

### Acceso privado provisional

El operador introduce el token Bearer manualmente en **Importar**. El sitio lo conserva en la memoria de la pestaña y lo envía en la cabecera `Authorization` al inspeccionar, validar o exportar. El bundle de Pages contiene la URL pública de la API y el formulario de acceso. Reserva las variables `VITE_*` para valores públicos. El backend autentica las tres operaciones de archivos y deja disponibles los metadatos de salud y formatos. Las rutas de archivos devuelven `503` mientras falte la protección y `401` cuando el token esté configurado pero la petición carezca de un token válido.

El token concede el mismo acceso a quienes lo comparten. Esta solución está prevista para el propietario o un grupo reducido. No ofrece permisos ni revocación individuales. Para rotarlo, reemplaza `SK_ACCESS_TOKEN` en Coolify, reinicia el servicio y vuelve a introducir el token en la pestaña. La protección de la interfaz mediante Cloudflare Access es independiente de la autenticación de la API.

## Compatibilidad y próximos pasos

| Formato o plataforma | Estado |
| --- | --- |
| `.data` con la configuración de la Fase 3 | Nueve estructuras de 8.6.0 y tres secciones nuevas de 8.8.0. Inspección y descarga intacta; 18 archivos locales 8.8.0 reconstruidos sin pérdida binaria. [Fase 5.6](docs/research/phase5-6/real-save-roundtrip.md) · [Restricciones](docs/phase3/LIMITATIONS.md) |
| `game.data` 8.8.0 | `AboGameData` con 41 claves y capa XOR local. Solo lectura en la API; edición de laboratorio por CLI. [Adquisición](docs/research/phase5-6/real-save-acquisition.md) |
| `.skdemo` v1 | Verificado con dos muestras sintéticas. Firma `SK-EDITOR-DEMO/1` seguida de salto de línea y JSON UTF-8. Incluye una etiqueta, un ID de solo lectura y dos enteros de prueba con la regla cantidad ≤ límite. |
| XML de preferencias y datos históricos de Android documentados en la investigación | Pendientes de verificación con muestras representativas. Se rechazan en esta fase. |
| Otras variantes de Android e iOS | Compatibilidad pendiente por canal y versión. |
| Acceso a guardados de ChillyRoom | Fase 5.9: descarga moderna autenticada desde Linux, sin Android, con un agregado de 114.778 bytes. Fase 6.1: subida real a `/BlobSave/Upload`, persistencia verificada por descarga y recuperación por el cliente oficial. Fase 6.2: lectura y preparación desde la web; la escritura sigue limitada al laboratorio y deshabilitada por defecto. [Fase 6.2](docs/research/phase6-2/README.md) · [Fase 6.1](docs/research/phase6-1/README.md) |
| Agregado `CloudSaveGameData` 8.8.0 | Modelo identificado en metadata (18 secciones, 46 649 typeDefs) y copia moderna real de 114.778 bytes con 17 secciones. Fase 6.1 demostró que el servidor conserva un cambio de un byte y que el cliente 8.8.0 lo recupera y aplica. Fase 6.2 aisló la edición de `gameData.gems` con serialización canónica, respaldo y restauración verificable. Falta generalizar a otras cuentas, versiones y campos. [Fase 6.2](docs/research/phase6-2/README.md) · [Fase 6.1](docs/research/phase6-1/protocol.md) |
| Edición web de `gameData.gems` | Descarga auténtica, lectura, preparación determinista, respaldo privado, vista previa, confirmación administrativa, verificación por descarga y restauración. La escritura está deshabilitada por defecto. [Fase 6.2](docs/research/phase6-2/README.md) |
| Edición local de un agregado | Laboratorio sobre JSON/gzip sintético y sobre archivos locales 8.8.0 (DES y XOR), con conservación de campos desconocidos y diff semántico/binario. No se declara aceptación por el juego. [Laboratorio 5.5](docs/research/phase5-5/save-editing-lab.md) · [Roundtrip 5.6](docs/research/phase5-6/real-save-roundtrip.md) |

La investigación local `SHOULXING_RESEARCH`, en particular los informes 03, 06 y 07, describe XML de preferencias y archivos históricos con JSON, Base64 y DES-CBC, así como las limitaciones de ABI y del análisis estático. Se verificó la licencia Apache-2.0 del clon de SHOULXING en el commit de referencia. La implementación del adaptador sintético es propia y el motor funciona de forma independiente de esos componentes. [Referencia histórica de SHOULXING](https://github.com/STE4LPH/SHOULXING/tree/685691e09798aa6d39ae2f44f29e31ad6423b98d)

Para incorporar un formato real:

1. Define la plataforma, el canal y la versión exacta del juego. Obtén, por una vía autorizada, varias copias propias representativas, incluidas muestras sin cambios y con cambios observables de un solo campo.
2. Identifica firmas y variantes de estructura. Documenta tipos, rangos y relaciones, las secciones que deben conservarse y cualquier regla de integridad o codificación a partir de evidencia reproducible.
3. Implementa un adaptador por versión en `backend/app/formats/`, con parser y serializador comprobados. Regístralo en el motor y añade fixtures sintéticos derivados de las estructuras verificadas, con casos de rechazo, relectura y preservación de datos ajenos a los cambios.
4. Distingue la verificación del motor de la aceptación por el juego. Prueba la importación por un mecanismo autorizado en el cliente objetivo, con recuperaciones ensayadas, antes de anunciar compatibilidad para esa versión.

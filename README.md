# sk-under

**Soul Knight Editor · Fase 5.7**

Editor web privado para inspeccionar copias locales. La muestra sintética `.skdemo` permite edición y exportación. El adaptador opcional de la Fase 3 lee nueve estructuras `.data` observadas en muestras de Soul Knight 8.6.0 y permite descargar copias intactas. [Configuración y cobertura de la Fase 3](docs/phase3/IMPLEMENTATION.md)

La Fase 4 documenta el análisis estático del APK 8.8.0 y las pruebas con las muestras de 8.6.0. [Informe de la Fase 4](docs/research/phase4/README.md)

La Fase 5.1 registra las pruebas de ejecución de Soul Knight 8.8.0 y de acceso al guardado en un laboratorio Android. [Validación experimental](docs/research/phase5-experimental/README.md)

La Fase 5.3 verificó una ruta condicional de precarga en el panel y reconstruyó las nueve referencias locales 8.6.0 en Linux. El importador acepta agregados suministrados en JSON o gzip. [Informe de Fase 5.3](docs/research/phase5-3/README.md) · [Uso del importador](docs/research/phase5-3/importer.md)

La Fase 5.4 separó el transporte RPC, documentó la máquina de estados de recuperación y añadió un cliente Linux con transporte remoto deshabilitado. La sesión autenticada y la muestra real de 8.8.0 siguen bloqueadas. [Informe de Fase 5.4](docs/research/phase5-4/README.md) · [Prototipo Linux](docs/research/phase5-4/linux-client-prototype.md)

La Fase 5.5 descifró la metadata real de 8.8.0, inventarió `CloudSaveGameData` y sus secciones, comparó los nombres con las nueve muestras 8.6.0 y añadió un laboratorio local de edición y un decodificador RPC gzip experimental. [Informe de Fase 5.5](docs/research/phase5-5/README.md)

La Fase 5.6 obtuvo un perfil local auténtico de Soul Knight 8.8.0 desde el APK oficial en un emulador propio, decodificó sus 18 archivos de datos (incluido `game.data`), confirmó gzip en el cuerpo de `ZipHelper.Decompress` y añadió un puente local Linux con roundtrip binario exacto. El agregado de nube y la aceptación por el cliente siguen pendientes. [Informe de Fase 5.6](docs/research/phase5-6/README.md)

La Fase 5.7 estabilizó el cliente 8.8.0 en un AVD Android 11 x86_64 con ABI arm64, inició sesión ChillyRoom por email y ejecutó una lectura auténtica de `/Backup/FetchGameData` desde Linux con el token del cliente. La cuenta de laboratorio devolvió un agregado legacy vacío; no se obtuvo `CloudSaveGameData` ni se demostró la aceptación visible de una modificación. [Informe de Fase 5.7](docs/research/phase5-7/README.md) · [Estabilización](docs/research/phase5-7/emulator-stabilization.md) · [Lectura de nube](docs/research/phase5-7/authentic-cloud-read.md)

La Fase 5.8 realizó un guardado y una recuperación oficiales con progreso visible, extrajo del proceso un agregado auténtico no vacío y verificó su relación parcial con archivos locales. La descarga directa del agregado moderno desde Linux sigue pendiente. [Resultados experimentales](docs/research/phase5-8/README.md).

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
    │   │   ├── routes.py
    │   │   └── uploads.py
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
| `VITE_API_BASE_URL` | Frontend | URL pública de la API, sin `/api/v1`. En desarrollo cae por defecto en `http://127.0.0.1:8017`. Configúrala explícitamente al compilar para otro entorno. |

Para desarrollo, el backend y Vite leen el `.env` de la raíz. El backend también puede leer `backend/.env`. Las variables del proceso tienen prioridad. Los valores `VITE_*` son públicos y se incorporan al JavaScript durante el build. El propietario introduce el token en el formulario de importación. En producción sin token, las rutas de archivos devuelven `503` y `health` informa `access_mode: "disabled"`. La API rechaza el token ausente o incorrecto con `401` cuando está configurado.

## Contratos de API

Todas las rutas de archivos reciben JSON UTF-8 con el archivo original en Base64 estándar y sin compresión. El JSON se limita durante la lectura a `4 × ceil(SK_MAX_FILE_BYTES / 3) + 16384` bytes. Los endpoints de validación y exportación reciben además un objeto `changes`, con hasta 32 entradas. Cada clave debe corresponder a un campo marcado como editable por el adaptador. Por ejemplo, `{"label":"Revisión","sample_count":5}`. Para conservar los valores envía `{}`.

| Método y ruta | Entrada | Respuesta exitosa |
| --- | --- | --- |
| `GET /api/v1/health` | — | Estado, modo de acceso y límite de archivo. |
| `GET /api/v1/formats` | — | Formatos registrados, versiones, extensiones y nivel de compatibilidad. |
| `POST /api/v1/files/inspect` | `content_base64` | Formato, tamaño, SHA-256 del original y campos con tipo, valor y restricciones. |
| `POST /api/v1/files/validate` | `content_base64`, `changes` | Resultado validado, cambios efectivos, tamaño y SHA-256 de la copia. |
| `POST /api/v1/files/export` | `content_base64`, `changes` | Bytes de la copia verificada con `Content-Type: application/octet-stream` y nombre en `Content-Disposition`. |

Los errores de las rutas de archivos usan `{"error":{"code":"…","message":"…","issues":[]}}`. Los problemas de un campo pueden incluir `field_id`. Una inspección fallida devuelve el error y omite los campos. Los estados incluyen `400` para un cuerpo malformado, `401` y `403` para acceso, `413` para límites, `415` para formato o contenido no admitido, `422` para datos o cambios inválidos, y `503` cuando falta configurar la protección. Un fallo de verificación devuelve `500` sin entregar un archivo.

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

El puerto `8017` corresponde al desarrollo local. Dentro del contenedor, Uvicorn escucha en `0.0.0.0:8000` como usuario sin privilegios. El Dockerfile se construye usando únicamente el contexto `backend/`. En Coolify, deja desactivado el ajuste de healthcheck del panel para que se utilice el de la imagen. No se requieren volúmenes de datos. [Dockerfile en Coolify](https://coolify.io/docs/applications/builds/dockerfile) · [Healthchecks en Coolify](https://coolify.io/docs/applications/configuration/health-checks)

Configura estas variables de runtime antes de habilitar la edición:

| Variable | Valor de producción |
| --- | --- |
| `SK_ENV` | `production` |
| `SK_ACCESS_TOKEN` | Secreto aleatorio de al menos 32 caracteres ASCII visibles, guardado en Coolify como variable de runtime |
| `SK_ALLOWED_ORIGINS` | Arreglo JSON con los orígenes HTTPS exactos del frontend, por ejemplo `["https://editor.example.com"]` |
| `SK_MAX_FILE_BYTES` | `1048576` por defecto. Ajústalo solo si cambia el tamaño máximo aceptado. |

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
| Acceso a guardados de ChillyRoom | La Fase 5.1 verificó la restauración oficial en Android con una cuenta propia. La Fase 5.7 inició sesión ChillyRoom en un AVD arm64 y ejecutó `FetchGameData` desde Linux con el token del cliente (`200`, agregado legacy vacío); no obtuvo `CloudSaveGameData` ni una copia no vacía. La copia para el editor y la automatización siguen pendientes. [Fase 5.7](docs/research/phase5-7/cloud-save-acquisition.md) · [Fase 5.1](docs/research/phase5-experimental/README.md) |
| Agregado `CloudSaveGameData` 8.8.0 | Modelo identificado en metadata (18 secciones, 46 649 typeDefs) y perfil local real de 8.8.0. Falta la copia de nube (`serialzedVersion`, `cloudSaveId`, `platformId`) y la aceptación por el cliente. La Fase 5.7 confirmó rutas y firmas, obtuvo `FetchGameData` (agregado legacy vacío) y no obtuvo el wrapper nuevo: `GetBlobSave` devuelve 500. [Fase 5.7](docs/research/phase5-7/rpc-netpack-capture.md) · [Lectura](docs/research/phase5-7/authentic-cloud-read.md) |
| Edición local de un agregado | Laboratorio sobre JSON/gzip sintético y sobre archivos locales 8.8.0 (DES y XOR), con conservación de campos desconocidos y diff semántico/binario. No se declara aceptación por el juego. [Laboratorio 5.5](docs/research/phase5-5/save-editing-lab.md) · [Roundtrip 5.6](docs/research/phase5-6/real-save-roundtrip.md) |

La investigación local `SHOULXING_RESEARCH`, en particular los informes 03, 06 y 07, describe XML de preferencias y archivos históricos con JSON, Base64 y DES-CBC, así como las limitaciones de ABI y del análisis estático. Se verificó la licencia Apache-2.0 del clon de SHOULXING en el commit de referencia. La implementación del adaptador sintético es propia y el motor funciona de forma independiente de esos componentes. [Referencia histórica de SHOULXING](https://github.com/STE4LPH/SHOULXING/tree/685691e09798aa6d39ae2f44f29e31ad6423b98d)

Para incorporar un formato real:

1. Define la plataforma, el canal y la versión exacta del juego. Obtén, por una vía autorizada, varias copias propias representativas, incluidas muestras sin cambios y con cambios observables de un solo campo.
2. Identifica firmas y variantes de estructura. Documenta tipos, rangos y relaciones, las secciones que deben conservarse y cualquier regla de integridad o codificación a partir de evidencia reproducible.
3. Implementa un adaptador por versión en `backend/app/formats/`, con parser y serializador comprobados. Regístralo en el motor y añade fixtures sintéticos derivados de las estructuras verificadas, con casos de rechazo, relectura y preservación de datos ajenos a los cambios.
4. Distingue la verificación del motor de la aceptación por el juego. Prueba la importación por un mecanismo autorizado en el cliente objetivo, con recuperaciones ensayadas, antes de anunciar compatibilidad para esa versión.

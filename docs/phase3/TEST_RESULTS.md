# Pruebas y resultados

| Verificación de la revisión final | Resultado |
| --- | --- |
| `cd backend && uv sync --locked && uv run --locked pytest -q` | 90 pruebas aprobadas |
| `cd frontend && npm ci && npm run build` | Node.js 24.21.0 y npm 11.19.0. TypeScript y Vite completaron la compilación y generaron `frontend/dist` |
| `cd backend && docker build --no-cache -t sk-under-phase3-local .` | Instalación de PyCryptodome 4.6.0 y arranque de Uvicorn. Salud, CORS permitido y rechazado, autenticación y `Cache-Control: no-store` verificados. Sin token, la API de archivos devuelve `503` |
| `cd frontend && npm run test:browser` | 4 pruebas de Chromium cubren el rechazo de un hash, tamaño o descarga alterados y la disposición del nombre y estado a 320 píxeles |
| Chromium en loopback | A 1440 y 320 píxeles se autenticó, inspeccionó, validó, descargó y reimportó un `.data` sintético de solo lectura con el mismo SHA-256. En ambos tamaños se editó, validó, descargó y reimportó una muestra `.skdemo` |
| API autenticada con los nueve archivos reales | 9/9 identificados, validados, descargados y reimportados. Los bytes y SHA-256 de cada descarga coinciden con su original. Los nueve rechazan cambios |
| SHA-256 de los originales | Los nueve SHA-256 coinciden con el inventario privado antes y después de las pruebas. Las muestras solo se leyeron y las descargas de la API se compararon en memoria |
| Auditoría de dependencias | `npm audit` y `pip-audit` sobre las dependencias de runtime del lock de Python no reportaron vulnerabilidades conocidas |

Las pruebas automatizadas generan fixtures a partir de los tipos observados y usan claves de prueba. Cubren detección por contenido, variante estadística, base64 truncado o no canónico, bytes alterados, padding y JSON inválidos, estructuras ambiguas, marcadores incompatibles, rechazo de cambios, límites de la API, reimportación, preservación de valores desconocidos e igualdad exacta. Una prueba altera la salida del serializador y verifica que el motor bloquee la exportación incluso cuando la estructura sigue siendo admisible.

La reimportación y la igualdad de bytes acreditan el comportamiento del editor. La aceptación en Soul Knight permanece sin verificar.

## Verificación de despliegues

El commit inicial del PR registró dos fallos independientes, `Cloudflare Pages` y `Workers Builds: sk-under`. GitHub solo mostró enlaces a los logs. El panel y la API de Cloudflare requieren una sesión o un token autorizado para recuperar el primer error de cada build. La compilación local de Pages completó `npm ci` y `npm run build` desde `frontend/` con Node 24, un `VITE_API_BASE_URL` de prueba y salida `dist`. Los logs de cada entorno permiten comprobar la raíz, versión de Node, instalación, comando y salida efectivos. En el entorno de vista previa, configura `VITE_API_BASE_URL` con una API HTTPS autorizada para el origen de la vista previa. Workers Builds es una integración aparte. Si solo se usa Pages, comprueba si el Worker tiene su propio disparador Git y desconéctalo si está duplicado. [Cloudflare Pages](https://developers.cloudflare.com/pages/configuration/build-configuration/) · [Workers Builds](https://developers.cloudflare.com/workers/ci-cd/builds/configuration/)

En el despliegue existente de la Fase 2, se verificaron la salud pública de Coolify y el flujo autenticado `.skdemo` de edición, validación, descarga y reimportación en Chromium contra la aplicación de producción. Se comprobó que `/api/v1/formats` todavía anuncia el formato sintético. La prueba de los nueve archivos reales se ejecutó contra Docker local.

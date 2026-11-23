# Pruebas y resultados

| Verificación en el VPS | Resultado |
| --- | --- |
| `cd backend && uv sync --locked && uv run --locked pytest -q` | 76 pruebas aprobadas, incluidas las 41 de la Fase 2 |
| `cd frontend && npm ci && npm run build` | TypeScript y Vite completaron la compilación de producción |
| `cd backend && docker build -t sk-under-phase3-local .` | Imagen local construida. Arranque y carga de DES verificados en un contenedor sin red. Acceso de archivos deshabilitado en producción sin token |
| Chromium en loopback | Se importó un `.data` sintético, se verificaron sus campos de solo lectura y se descargó una copia idéntica. En el mismo navegador se editó, validó y descargó una muestra `.skdemo` |
| API autenticada con las nueve copias reales | 9/9 reconocidas, validadas y descargadas en memoria con los mismos bytes y SHA-256. 9/9 reimportadas con la misma inspección. Se rechazaron los nueve intentos de edición |
| Preservación en disco | Inventario, nombres y hashes de originales comprobados contra las copias antes y después. Las pruebas trabajaron sobre las copias |

Las pruebas automatizadas generan fixtures a partir de los tipos observados y usan claves de prueba. Cubren detección por contenido, variante estadística, base64 truncado o no canónico, bytes alterados, padding y JSON inválidos, estructuras ambiguas, marcadores incompatibles, rechazo de cambios, límites de la API, reimportación, preservación de valores desconocidos e igualdad exacta. Una prueba altera la salida del serializador y verifica que el motor bloquee la exportación incluso cuando la estructura sigue siendo admisible.

La reimportación y la igualdad de bytes acreditan el comportamiento del editor. La aceptación en Soul Knight permanece sin verificar.

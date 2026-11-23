# Pruebas con la cuenta propia

## Resultado de acceso y descarga

La revisión del manual de Android, preguntas frecuentes, soporte y documentación de límites confirmó una vía de restauración dentro del cliente oficial. Al recuperar progreso desde el juego, la copia se aplica al almacenamiento local del cliente. No se encontró un contrato público de lectura delegada ni un mecanismo público para entregar al backend los bytes originales. La prueba con la cuenta de investigación se detuvo antes de enviar credenciales. El entorno de análisis era Linux x86-64 y no disponía de un dispositivo Android conectado ni de un emulador en funcionamiento. El APK contiene binarios ARM. [Manual de Android](https://soulknight.chillyroom.com/et/article/base/3) · [Preguntas frecuentes](https://soulknight.chillyroom.com/et/article/base/6) · [Soporte](https://www.chillyroom.com/en/support)

| Verificación prevista | Resultado |
| --- | --- |
| Autenticación de la cuenta secundaria | Cero intentos. Sin sesión de prueba ni desafío de verificación observado. |
| Consulta de metadatos y posesión de respaldo | Pendientes. El estado de la partida de la cuenta es desconocido. |
| Descarga intacta, conservación y SHA-256 | Pendientes. No se recibió un objeto remoto. |
| Formato, descompresión, reconstrucción y contraste con el APK | Probados con cuerpos sintéticos para el prototipo. Pendientes con un respaldo real. |
| Cambios en la nube | Cero operaciones de escritura. |

La dependencia para una prueba integral es acceso de solo lectura autorizado para el editor o una exportación del agregado que ChillyRoom entregue o autorice para la cuenta. Si soporte ofrece una copia del respaldo, se podrá conservar el original fuera de Git con acceso restringido, calcular su SHA-256 antes de procesarlo y contrastar cabecera, compresión, raíz y subsistemas con el APK. Si el titular dispone del cliente oficial, el panel de guardado puede comprobar existencia, identidad y metadatos visibles. Una restauración autorizada en un dispositivo de prueba documentaría el resultado local y puede consumir una vinculación según las condiciones publicadas. Esa prueba local requiere una exportación admitida para comprobar también los bytes remotos. [Límites de guardado](https://soulknight.chillyroom.com/et/article/base/4) · [Soporte de ChillyRoom](https://www.chillyroom.com/en/support)

## Verificación local

| Ejecución | Resultado |
| --- | --- |
| `uv run --locked pytest -q`, con la configuración privada de Fase 4 | 124 aprobadas. Incluye las 99 existentes, nueve de ellas con los archivos 8.6.0, y 25 casos del reconstructor. |
| `uv run --locked pytest -q`, sin configuración privada | 115 aprobadas y nueve omitidas. |
| `npm ci` y `npm run build` | Instalación con lockfile y compilación de TypeScript y Vite correctas. |
| `npm run test:browser` | 4 aprobadas en Chromium. |
| Construcción local del Dockerfile | Imagen construida. Se importó el módulo dentro del contenedor y se comprobó el contrato OpenAPI sin rutas de nube. |

Las pruebas privadas existentes verifican SHA-256, tamaño, copia byte a byte y reimportación de las nueve muestras locales. Las pruebas del módulo cubren JSON, gzip, límites, integridad de la envoltura, esquema y privacidad del resumen. El único fixture nuevo se construyó con datos sintéticos. [Pruebas de 8.6.0](../../../backend/tests/test_private_save_roundtrip.py) · [Pruebas de reconstrucción](../../../backend/tests/test_cloud_save.py)

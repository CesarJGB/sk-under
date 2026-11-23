# Fase 5.8 · Adquisición experimental de nube

**Resultado:** el cliente oficial 8.8.0 completó el tutorial con la cuenta de laboratorio, subió mediante su interfaz una copia con progreso visible y aplicó una recuperación. Después de reiniciar el proceso, el panel oficial volvió a mostrar en la fila de nube 1.000 gemas y un contador de tarjetas de prueba de 5. El archivo local `game.data` pasó de 0 a 1.000 gemas tras la recuperación. Se obtuvo también del espacio de memoria del cliente un objeto JSON auténtico compatible con `CloudSaveGameData` y con 1.000 gemas. **No se ha demostrado que ese objeto sea el cuerpo exacto de una respuesta de red**, ni se ha reproducido la descarga moderna desde Linux sin Android.

| Línea | Resultado nuevo | Informe |
| --- | --- | --- |
| Cliente, tutorial y guardado | Login por email, tutorial completo, subida por interfaz, recuperación y nuevo proceso con resumen de nube no vacío | [Android](android.md), [guardado](cloud-roundtrip.md) |
| Datos auténticos | JSON de 110.049 bytes extraído del proceso después de recuperar; parser existente lo acepta; 1.000 gemas | [Guardado y memoria](cloud-roundtrip.md) |
| Relación local | Antes/después de recuperación: `game.data.gems` 0 → 1.000; 29 de 38 campos comunes iguales al objeto en memoria | [Guardado](cloud-roundtrip.md), [archivos](local-files.md) |
| Linux con emulador apagado | `FetchGameData` 200 legacy vacío; `GetBlobSave` POST 500; `BlobSave/Download` GET 404 | [Linux](linux.md) |
| GetBlobSave | Sobrecargas sin solicitud explícita; GET completo respondió 404; contrato de éxito pendiente | [Protocolo](protocol.md) |
| Tramas y NetPack | Dos tramas TCP reales de ocho bytes más gzip, sin atribución a guardado ni a NetPack | [Protocolo](protocol.md) |
| Edición artificial | Roundtrip de copia local; sin aceptación visible ni persistencia en el cliente | [Archivos](local-files.md) |
| Implementación | Lector legacy separado, clasificación de errores, rechazo de un falso 200 y pruebas privadas optativas | [Linux](linux.md) |

La interfaz oficial distinguió el resumen remoto del local y ambos mostraron progreso tras la operación y el reinicio. El agregado legacy vacío no contradice esa observación: es un formato y una ruta diferentes. La obtención de los bytes exactos desde ChillyRoom directamente en Linux, sin emulador, sigue pendiente. La traza y el JSON en memoria no se publican como si fueran una respuesta de red.

## Pruebas de esta revisión

- Backend completo con muestra local 8.8.0 y agregado privado configurados: **244 pasan, 9 omitidas** (las omitidas requieren otras muestras privadas).
- Frontend: `npm run build` pasa y `npm run test:browser` **4 pasan**.
- El proveedor legacy tiene pruebas sintéticas separadas de las comprobaciones auténticas; la nueva prueba privada compara el JSON del proceso y el `game.data` restaurado sin subirlos a Git.
- Las credenciales, sesiones, imágenes, tráfico, volcados y copias permanecen bajo `~/.config/sk-under/phase5-8/` o en el laboratorio privado de la fase anterior. El contenedor del emulador quedó detenido después de la prueba Linux.

El siguiente experimento prioritario es correlacionar el método de descarga oficial con una respuesta concreta antes del cifrado o por análisis de su implementación, y reproducir esa lectura de solo lectura con la sesión autorizada desde Linux. La edición artificial visible y persistente también sigue pendiente; no se sincronizó ninguna copia modificada con la nube.

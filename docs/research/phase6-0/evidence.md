# Evidencia

- **Ejecutado:** dos descargas nuevas con Android detenido; datos, tamaños y hash en [download.md](download.md). Copias privadas: `~/.config/sk-under/phase6-0/download-1.json` y `download-2.json`.
- **Ejecutado localmente:** preparación y comparación del candidato, [upload-experiments.md](upload-experiments.md).
- **Estático:** inventario privado `~/.config/sk-under/phase6-0/metadata.json`, generado con `docs/research/phase5-5/tools/metadata_inventory.py` a partir del APK 8.8.0. Hallazgos y límites en [upload-protocol.md](upload-protocol.md).
- **Regresiones:** backend 255 pasan y 16 se omiten sin muestras privadas configuradas; prueba moderna con respuesta privada capturada: 16 pasan. Compilación Python, TypeScript/Vite y cuatro pruebas de navegador pasan. Las respuestas sintéticas no son descargas reales.
- **Fallido / pendiente:** no hay experimento de escritura real, resultado de servidor, persistencia posterior, recuperación oficial posterior ni modificación.

## Continuación experimental

- **Estático y memoria dirigida:** DTO, llamadas, estado puntual de callbacks y entradas IFix: [protocolo](upload-protocol.md). Desensamblado e inventarios de trabajo permanecen en `~/.config/sk-under/phase6-0/`.
- **Ejecutado localmente:** Json.NET 13.0.3 y Python coinciden byte a byte para el sobre de la muestra auténtica; un caso sintético detectó una diferencia de escape corregida y cubierta por prueba.
- **Ejecutado en cliente con salida bloqueada:** fallo previo en `FetchData`, sin aceptación de servidor; proceso detenido antes de devolver la red. Nueva descarga Linux igual al original: [experimento](upload-experiments.md).
- **No demostrado:** una escritura de nube restaurable exactamente a partir del agregado conservado, aceptación, persistencia y recuperación de una subida Linux.

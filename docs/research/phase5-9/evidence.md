# Evidencia y pruebas

## Procedencia

- **5.8:** copia de memoria con 17 claves, recuperación oficial y capturas anteriores; ver [fase 5.8](../phase5-8/README.md).
- **Primera ejecución 5.9:** análisis temporal de la captura anterior, sin nueva recuperación ni lectura moderna.
- **Continuación:** nuevo arranque y recuperación oficial, captura con SNI y atribución del socket al PID mediante inodos `/proc`, observación de archivos, análisis de literales del ELF, cuatro descargas modernas Linux y preparación local de candidato de subida.

La captura nueva incluye tráfico ajeno; la atribución usa los inodos observados por muestreo y no identifica contenidos TLS. Hubo 3.339 paquetes capturados y cero descartados por el kernel según tcpdump; 33 paquetes recibidos por el filtro no aparecen en la cuenta de capturados al cerrar. Capturas, perfil, sesión, respuestas y scripts privados permanecen bajo `~/.config/sk-under/phase5-9-cont/`.

| Artefacto privado | SHA-256 |
| --- | --- |
| `operations.pcap` | `99125921f586fcd70541905c915769ec5c789423fa8e9b87b3a5ae51cddf7731` |
| `operations.log` | `dff39205cc8c4d757271a736e09ce81cab00e8e35aafe04cc9cff8cc2859829c` |
| `provider-download.json` | `eeef81390418a60cf6f4da25932ab93c0ee22bc418eeb60bf595f28f13f6f97c` |
| Referencia de memoria 5.8 | `fefb3ee83c382a4cfcc55d27968902f116797fb3cfbec263fe38488220db518f` |

Pruebas locales: backend completo **258 pasan y 9 se omiten**, con respuesta privada moderna y muestras privadas configuradas; pruebas negativas de gzip corrupto/truncado, respuesta incompleta o inválida, límites y credenciales; TypeScript y Vite pasan; navegador **4 pasan**. La prueba privada de respuesta recibe una captura real ya guardada, mientras las pruebas negativas utilizan fixtures sintéticos. La descarga real se verificó aparte contra el servicio con Android detenido.

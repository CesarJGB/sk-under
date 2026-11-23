# Evidencia y verificación

Los artefactos permanecen fuera de Git, en `~/.config/sk-under/phase5-8/`. Referencias por SHA-256 para reproducibilidad local:

| Artefacto privado | SHA-256 |
| --- | --- |
| `network-operations.pcap` | `c85b33e40fd0801da4a29395ff7b18249ccc22651a5c1dbb5a01e39859a7e7bb` |
| `retrieve.log` | `313f93c8b0b97dc3b27316335486b4583fdf58d0579981a32ec4b9d3feffba34` |
| `memory-cloud-exact-utf8.json` | `fefb3ee83c382a4cfcc55d27968902f116797fb3cfbec263fe38488220db518f` |

Se recorrió la captura con Scapy 2.8.0, seleccionando paquetes TCP con carga y hora UTC entre 19:14:53 y 19:15:14, y clasificando por puerto de origen o destino 443. La cuenta de bytes es de carga por paquete, no de flujo TCP reensamblado; incluye posibles retransmisiones y tráfico no relacionado. El log registra horas sin zona; se asumió UTC para compararlo, pendiente de calibración.

Pruebas locales de esta revisión: backend completo **238 pasan, 15 omitidas**; subconjunto de proveedor, transporte y pruebas privadas de agregado y archivos restaurados **51 pasan**. TypeScript y compilación Vite pasan; navegador Chromium **4 pasan**. Las pruebas privadas utilizan el JSON de memoria y el perfil extraído del tar posterior a la recuperación, no tráfico descargado por Linux. Las pruebas negativas existentes abarcan respuestas inválidas, truncadas y corruptas; ninguna demuestra el contrato moderno. Los archivos privados se mantuvieron fuera del árbol Git.

# Fase 6.1: primera subida real desde Linux

**Resultado principal y avanzado conseguidos.** Desde Linux se envió una copia auténtica de la cuenta de laboratorio a `POST https://save.soulknight.chillyroom.com/BlobSave/Upload`, el servidor respondió `200` con cuerpo `true`, y una descarga posterior devolvió exactamente el mismo agregado y SHA-256. Después se cambió un solo dígito (`gameData.gems` de `1000` a `1001`), se subió y se volvió a descargar con el mismo resultado. El cliente oficial 8.8.0 mostró `1001` en la fila de nube del panel, recuperó la copia, escribió `1001` en `game.data` local y abrió el hall con `1001` visible.

| Evidencia | Estado | Alcance |
| --- | --- | --- |
| Descarga Linux de la copia original | Confirmado por ejecución | 114.778 bytes, 17 secciones, SHA-256 `eeef…97c` |
| Solicitud de subida idéntica | Confirmado por ejecución | `200`, cuerpo gzip `true`, 30 bytes en el cable |
| Persistencia de la copia idéntica | Confirmado por ejecución | Nueva descarga con el mismo hash |
| Modificación mínima `gems=1001` | Confirmado por ejecución | Un byte distinto en el agregado; cuerpo gzip de 17.386 bytes |
| Persistencia de la modificación | Confirmado por ejecución | Nueva descarga idéntica al archivo subido |
| Cliente oficial lee la nube | Confirmado con el cliente 8.8.0 | El panel mostró `1001` en la fila superior |
| Cliente oficial recupera y abre | Confirmado con el cliente 8.8.0 | `CoverPlayerPref()`, `game.data` local con `1001`, hall abierto con `1001` |
| Contrato universal o anti-cheat | No demostrado | Una cuenta, una versión, una región y una modificación de un entero |

La escritura quedó implementada como transporte opt-in y **no está expuesta por ninguna ruta HTTP**. Sin `enabled=True` lanza `CloudWriteDisabled`; la CLI exige `SK_CLOUD_WRITE_EXPERIMENTAL=1` y `--confirm-experimental-write`. La API existente sigue siendo de inspección y exportación local.

## Archivos

- [Protocolo observado](protocol.md): solicitud, respuestas, diferencia entre aceptación y persistencia.
- [Experimentos](experiment.md): bitácora de las dos subidas y de las descargas de verificación.
- [Cliente oficial](client-validation.md): panel, recuperación, `game.data` y hall.
- [Implementación](implementation.md): módulos, activación, CLI y pruebas.
- [Seguridad](security.md): alcance de la autorización, secretos y límites.
- [Evidencia](evidence.md): artefactos privados, hashes y comandos.

## Estado de la cuenta de laboratorio

La nube quedó con el agregado de `gems=1001` y el perfil local del emulador también. La copia original `1000` se conserva en `~/.config/sk-under/phase6-1/original.json` con modo `0400`; no se restauró porque el propietario autorizó sobrescribir la cuenta y porque mantener el estado modificado permite reproducir la comprobación del cliente. La restauración es una subida más del original, no un procedimiento nuevo.

## Límites de la conclusión

- El servidor no publicó una firma ni un hash independiente: la igualdad se calculó localmente al volver a descargar.
- La respuesta `true` es idéntica en las dos subidas; por sí sola no distingue una escritura de un no-op.
- La aceptación de `gems=1001` no demuestra que el servicio valide otros campos, cantidades grandes o invariantes de progreso.
- No se capturó el cuerpo TLS oficial; el contrato se reconstruyó con análisis estático previo y se validó por ejecución desde Linux.
- No se probaron reintentos, concurrencia, caducidad de sesión ni límites de frecuencia.

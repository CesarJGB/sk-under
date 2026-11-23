# Seguridad y alcance

## Autorización

La cuenta ChillyRoom usada es exclusivamente de laboratorio. El propietario autorizó descargar, subir, sobrescribir el guardado, modificar datos de prueba, reiniciar el progreso y comparar con el cliente oficial. Esta fase ejecutó dos subidas y una recuperación oficial sobre esa cuenta.

La autorización no se extiende a terceros, otras cuentas ni producción. La escritura implementada no está expuesta a usuarios normales.

## Credenciales

- La sesión y los identificadores se leyeron de artefactos privados ya existentes bajo `~/.config/sk-under/`.
- No se inició sesión desde el backend ni se automatizó el login.
- No se imprimieron tokens, correo, `cloudSaveId` ni contenido de la partida en la salida de las CLI.
- Los errores de transporte se convierten en errores tipados sin conservar el mensaje original.
- Los artefactos privados, capturas y perfiles permanecen fuera del repositorio y con permisos restrictivos.
- El repositorio no contiene claves, tokens ni archivos de partida.

## Controles de escritura

| Control | Efecto |
| --- | --- |
| `BlobSaveUploader(enabled=False)` por defecto | `upload()` falla con `CloudWriteDisabled` |
| `SK_CLOUD_WRITE_EXPERIMENTAL=1` | Primer requisito de la CLI |
| `--confirm-experimental-write` | Segundo requisito explícito |
| Sin ruta HTTP | La API no puede invocar la escritura |
| Validación del agregado | Un documento inválido no llega al socket |
| Límite de entrada | `MAX_INPUT_BYTES` (8 MiB) |
| Límite de respuesta | 64 KiB |
| TLS normal | No se desactiva la verificación ni se intercepta |
| Sin redirecciones | El POST no se redirige a otro host |

## Integridad

El SHA-256 se calcula localmente sobre el agregado y sobre el cuerpo. El servidor no publicó un hash ni una firma, por lo que la comprobación es una comparación local entre lo enviado y lo descargado, no una prueba criptográfica emitida por el servicio.

La respuesta `200` + `true` no se trata como confirmación definitiva. El único criterio de persistencia es `matches_uploaded=true` tras una descarga posterior.

## Riesgos residuales

- La cuenta remota quedó sobrescrita con `gems=1001`. No existe un procedimiento de rollback del servidor probado; la copia original se conserva y puede reenviarse.
- No se probaron concurrencia, reintentos, caducidad de sesión ni límites de frecuencia. Una automatización futura debe incluir espera y límites.
- La aceptación de una modificación pequeña no demuestra tolerancia a cambios grandes ni a campos con validación de servidor.
- La sesión es un secreto de alta sensibilidad; su exposición o reutilización fuera del laboratorio queda prohibida.
- El cliente oficial puede cambiar el contrato en otra versión. Cualquier generalización requiere nueva verificación.

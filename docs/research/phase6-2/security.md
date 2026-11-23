# Seguridad y alcance

## Autorización

El editor está pensado para la cuenta de laboratorio del propietario. La lectura y la preparación usan el token de acceso existente de la API. La confirmación y la restauración exigen además una cabecera administrativa independiente.

| Control | Efecto |
| --- | --- |
| `SK_CLOUD_WRITE_ENABLED=false` por defecto | El servicio no construye el uploader y la API responde `503`. |
| `SK_CLOUD_ADMIN_TOKEN` | Secreto de al menos 32 caracteres ASCII visibles; se compara en tiempo constante con `X-SK-Cloud-Admin`. |
| `SK_ACCESS_TOKEN` | Protege todas las rutas del laboratorio, incluidas lectura y respaldos. |
| Frase de confirmación | `SUBIR` para escribir y `RESTAURAR` para restaurar. |
| Verificación previa de la nube | La confirmación se detiene si la copia remota cambió desde la preparación. |
| Confirmación única | Un respaldo confirmado no se vuelve a enviar. |
| Sin ruta de activación | Ninguna petición del navegador puede cambiar `SK_CLOUD_WRITE_ENABLED` ni el token administrativo. |

La autorización no se extiende a terceros, otras cuentas ni producción.

## Credenciales

- La sesión de nube y los identificadores de instalación se leen solo de variables de entorno del backend.
- No se envían al navegador, no se incluyen en respuestas, errores, registros de eventos ni mensajes de commit.
- Los errores del proveedor se traducen a mensajes genéricos (`cloud_session_rejected`, `cloud_provider_unavailable`) sin conservar el mensaje original.
- El token administrativo se conserva en la memoria de la pestaña y se envía solo en confirmar/restaurar.
- El repositorio no contiene `.env`, tokens, partidas ni capturas privadas.

## Respaldos

- Se guardan fuera del repositorio, en `SK_CLOUD_BACKUP_DIR` (por defecto `~/.local/share/sk-under/backups`; en la imagen Docker, `/var/lib/sk-under/backups`).
- Para habilitar la escritura real en Coolify, monta un volumen persistente en esa ruta; sin volumen, los respaldos se pierden al recrear el contenedor.
- El directorio se crea con modo `0700`; los archivos con `0600`.
- Cada respaldo contiene `original.json`, `candidate.json`, `record.json` y `events.jsonl`.
- El registro no incluye `cloudSaveId`, correo, token ni contenido de la partida; solo hashes, tamaños, gemas y metadatos del origen.
- Al cargar un respaldo se verifican tamaño, SHA-256, estructura y reproducibilidad del candidato.
- La API no expone ni permite descargar `original.json` o `candidate.json` desde el navegador.

## Integridad

- Se exige la serialización canónica observada; no se reformatean copias ajenas.
- Se compara el árbol completo y se demuestra que, al restaurar el valor original, se recuperan los bytes de entrada.
- La persistencia solo se declara cuando una descarga posterior devuelve exactamente el SHA-256 enviado.
- El servidor no publica una firma ni un hash independiente; la comprobación es local entre lo enviado y lo descargado.

## Riesgos residuales

- La sesión de nube es de alta sensibilidad. Su exposición o reutilización fuera del laboratorio está prohibida.
- No se probaron concurrencia, reintentos, caducidad de sesión ni límites de frecuencia contra el servicio real.
- La restauración depende de que la nube conserve el candidato exacto; si se modificó por otra vía, se detiene y requiere una revisión manual.
- La aceptación de un entero pequeño no demuestra tolerancia a valores grandes ni a otros campos.
- El cliente oficial puede cambiar el contrato en otra versión.

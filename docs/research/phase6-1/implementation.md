# Implementación Linux

## Separación de capas

| Módulo | Responsabilidad |
| --- | --- |
| `backend/app/cloud/blob_wire.py` | URL, cabeceras comunes y decodificación gzip estricta |
| `backend/app/cloud/upload_dry_run.py` | Serialización del sobre `{"data": …}` y gzip local |
| `backend/app/cloud/blob_upload.py` | Transporte `POST /BlobSave/Upload`, clasificación de errores y resultado |
| `backend/app/cloud/blob_roundtrip.py` | Orquestación subida + descarga + comparación de SHA-256 |
| `backend/app/cloud/modern.py` | Lectura autenticada existente; ahora comparte las cabeceras de `blob_wire` |

`BlobSaveUploader` no inicia sesión ni obtiene tokens: recibe una sesión ya emitida por el cliente oficial, igual que el proveedor de descarga. La escritura no está conectada a `app/api/routes.py`.

## Activación explícita

La escritura está deshabilitada por defecto de tres formas independientes:

1. `BlobSaveUploader.enabled` es `False` por defecto y `upload()` lanza `CloudWriteDisabled`.
2. La CLI exige `SK_CLOUD_WRITE_EXPERIMENTAL=1`.
3. La CLI exige el flag `--confirm-experimental-write`.

No hay ruta HTTP, variable de `Settings` ni opción del frontend que active la escritura. La API pública sigue siendo de inspección y exportación local.

## Uso de laboratorio

Las credenciales se pasan solo por entorno y nunca por argumentos ni por el repositorio:

```bash
export SK_CLOUD_SESSION_TOKEN='<token de la sesión de laboratorio>'
export SK_CLOUD_UNIQUE_ID='<identificador de la instalación>'
export SK_CLOUD_DISTRO_ID='<distribución observada>'
export SK_CLOUD_WRITE_EXPERIMENTAL=1

cd backend
.venv/bin/python -m app.cloud.blob_roundtrip /ruta/privada/agregado.json \
  --confirm-experimental-write
```

La salida es un JSON con estado, tamaños, SHA-256, sí/no del token de solicitud y `matches_uploaded`. No incluye el token, el contenido de la partida ni cuerpos de error del transporte. El proceso devuelve `0` solo si la descarga posterior coincide.

Para enviar sin verificar (no recomendado) existe `python -m app.cloud.blob_upload`. El ciclo recomendado es siempre `blob_roundtrip`.

## Contrato del resultado

```json
{
  "upload": {
    "status": 200,
    "accepted": true,
    "aggregate_size": 114778,
    "aggregate_sha256": "…",
    "body_size": 17386,
    "body_sha256": "…",
    "response_size": 30,
    "response_sha256": "…",
    "request_token_sent": false
  },
  "verification": {
    "remote_size": 114778,
    "remote_sha256": "…",
    "remote_source": "modern-cloud",
    "matches_uploaded": true
  }
}
```

`accepted` solo refleja el `200` + `true` observado. `matches_uploaded` es la confirmación de persistencia.

## Pruebas

`backend/tests/test_cloud_blob_upload.py` cubre:

- escritura deshabilitada por defecto;
- URL, método, cabeceras, gzip y `data` textual;
- ausencia de `x-request-token` y envío cuando se inyecta un entero positivo;
- `false`, valores no booleanos, `401`, `403`, `500`, gzip corrupto y fallo de transporte;
- agregado inválido sin llegar al socket;
- validación de credenciales y URL;
- servidor HTTP local real en loopback que comprueba los bytes y cabeceras recibidos;
- roundtrip con proveedor de descarga simulado que distingue coincidencia y no coincidencia.

Las pruebas usan un agregado sintético y un servidor local. No contactan ChillyRoom. La ejecución real se documenta en [experimentos](experiment.md) y [evidencia](evidence.md).

## Compatibilidad con la descarga

`ModernCloudSaveProvider` conserva su contrato, su CLI y sus pruebas. El único cambio es que las cabeceras comunes se construyen en `blob_wire.build_blob_headers`; los valores enviados son los mismos que antes. La descarga real posterior a las subidas devolvió el agregado esperado.

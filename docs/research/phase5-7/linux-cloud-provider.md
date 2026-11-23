# Proveedor Linux de nube (solo lectura, experimental)

**Estado: PROTOTIPO, SIN DESCARGA REAL.** Existe la interfaz desacoplada, un
proveedor deshabilitado por defecto, un proveedor de fixture local y un
proveedor HTTP de solo lectura para el gateway oficial. La ruta de éxito del
proveedor HTTP **no se verificó** contra el servicio real porque no se obtuvo un
token de juego válido.

## 1. Archivos

| Archivo | Función |
| --- | --- |
| [`backend/app/cloud/provider.py`](../../../backend/app/cloud/provider.py) | Protocolo, metadatos, errores, proveedores |
| [`backend/app/bridge.py`](../../../backend/app/bridge.py) | `CloudBridge`: proveedor → importador → exportador |
| [`backend/tests/test_cloud_provider.py`](../../../backend/tests/test_cloud_provider.py) | 14 pruebas sintéticas |

## 2. Interfaz

```python
class CloudSaveAcquisitionProvider(Protocol):
    def metadata(self) -> CloudSaveMetadata: ...
    def download(self, limit: int = MAX_INPUT_BYTES) -> AcquiredCloudSave: ...
```

`AcquiredCloudSave` verifica que el tamaño y el SHA-256 declarados coincidan con
los bytes entregados. `CloudBridge` convierte la copia en un `ImportedCopy` con
el importador existente (JSON/gzip, secciones, campos desconocidos) y puede
exportarla con `write_private_file` (`0600`, sin sobrescritura por defecto).

## 3. Implementaciones

| Implementación | Red | Etiqueta | Estado |
| --- | --- | --- | --- |
| `DisabledCloudSaveProvider` | No | — | Por defecto; falla con `cloud_provider_disabled` |
| `LocalFixtureCloudSaveProvider` | No | `source="fixture"` | Funciona; no es una descarga |
| `GatewayCloudSaveProvider` | Sí, GET | `source="gateway"` | Prototipo; éxito no verificado |

### 3.1 `GatewayCloudSaveProvider`

- Recibe el token de juego **ya emitido**; no implementa login.
- Envía `Authorization: Bearer <token>` y `Accept: application/json`.
- Acepta HTTPS; permite HTTP solo para `127.0.0.1`/`localhost` en pruebas.
- Interpreta `{"data": "..."}`, `{"Data": "..."}`, un objeto `data` o un
  agregado directo con `serialzedVersion`.
- Mapea `10001`/`401`/`403` a `cloud_provider_unauthenticated` y otros errores a
  `cloud_provider_unavailable`/`cloud_provider_protocol`.
- No escribe, no sube, no refresca tokens y no desactiva TLS.
- El token no aparece en `repr`, resúmenes ni mensajes de error.

**Hipótesis no confirmada:** que `/Backup/GetBlobSave` entregue un `JsonPayload`
con `Data` o un agregado directo. La Fase 5.4 confirmó `JsonPayload.Data` de
forma estática; no se observó una respuesta de éxito. La ruta y la forma deben
verificarse antes de confiar en este proveedor.

## 4. Qué funciona

- La interfaz y el flujo de errores.
- La lectura de un fixture JSON o gzip con límite, `O_NOFOLLOW` y sin enlaces
  simbólicos.
- La conservación de campos desconocidos y el roundtrip.
- La exportación local `0600` sin sobrescribir.
- La redacción de tokens y la ausencia de secretos en los resúmenes.
- Las pruebas con un `fetch` inyectado; no se abre ningún socket.

## 5. Qué no funciona

- La descarga real desde la cuenta: no hay token de juego.
- La verificación del esquema de éxito de `/Backup/GetBlobSave`.
- La selección automática de la ruta (`/Backup/GetBlobSave` vs
  `/BlobSave/Download`).
- El login desde Linux: no se implementó ni se adivinó el cuerpo de
  `/UserAuth/Login`.
- La escritura remota: fuera de alcance por diseño.

## 6. Pruebas

```sh
cd backend
.venv/bin/pytest tests/test_cloud_provider.py -q
```

Resultado de la fase: **14 pasan**. La suite completa: **229 pasan, 14
omitidas**. Las pruebas no usan la cuenta real ni el gateway; el `fetch` es una
función inyectada que devuelve cuerpos sintéticos.

Casos cubiertos:

- proveedor deshabilitado;
- metadatos y descarga de fixture;
- límite de tamaño y enlace simbólico;
- extracción de `data`/`Data` y agregado directo;
- error `10001` y HTTP `401`;
- respuesta no JSON y respuesta sobredimensionada;
- metadatos inconsistentes;
- roundtrip con campos desconocidos y gzip;
- exportación `0600` y original intacto;
- token ausente de `repr`/resúmenes.

## 7. Cómo se usaría con un token autorizado

El titular obtendría el token por el mecanismo oficial y lo entregaría al
proceso por una variable de entorno o un archivo privado `0600`. El proveedor
no lo lee de Git ni lo escribe en logs. Antes de usarlo:

1. Confirmar la ruta y el esquema con una respuesta auténtica.
2. Comparar el tamaño y el SHA-256 con la respuesta.
3. Ejecutar el importador y verificar las secciones.
4. Etiquetar el resultado como lectura experimental hasta que haya una prueba
   de cliente.

## 8. Conclusión

El proveedor Linux es una **interfaz real y probada con datos sintéticos**, no
una adquisición remota demostrada. No se debe presentar como “lectura de nube
desde Linux” hasta que una ejecución autorizada devuelva una copia auténtica y
el cliente oficial la acepte.

# Implementación del editor de gemas

## Separación de responsabilidades

| Módulo | Responsabilidad |
| --- | --- |
| `backend/app/cloud/gems_editor.py` | Leer `gameData.gems`, validar tipo/rango, modificar solo esa ruta, serializar canónicamente y verificar el resultado. |
| `backend/app/cloud/backup_store.py` | Crear respaldos privados, verificar sus hashes al cargarlos, listarlos, registrar eventos y guardar la confirmación. |
| `backend/app/cloud/lab_service.py` | Orquestar descarga, preparación, confirmación, verificación y restauración con bloqueo de escritura. |
| `backend/app/api/cloud_lab.py` | Rutas HTTP, autenticación de acceso, autorización administrativa y traducción de errores. |
| `frontend/src/pages/LabEditorPage.tsx` | Sección **Partida**, vista previa, respaldo, confirmación explícita y restauración. |
| `frontend/src/api.ts` | Cliente tipado de las rutas de laboratorio. |

## Serialización canónica

La copia real de 8.8.0 se reproduce con:

```python
json.dumps(document, ensure_ascii=False, sort_keys=True, allow_nan=False,
           separators=(", ", ": "))
```

Antes de editar se comprueba que esta serialización del original sea **idéntica byte a byte** a la entrada. Si no lo es, el editor rechaza la copia con `unsupported_serialization`: no reformatea datos ajenos. Después de editar se vuelve a reconstruir el agregado, se reabre y se comprueba que al restaurar el valor original se recuperan exactamente los bytes de entrada.

La copia real de 114.778 bytes cumple la igualdad y el cambio `1001 → 1002` produce exactamente un byte distinto en el desplazamiento 2419.

## Contrato HTTP

| Método | Ruta | Autorización | Efecto |
| --- | --- | --- | --- |
| `GET` | `/api/v1/cloud/lab/status` | Token de acceso | Estado, límites y número de respaldos. |
| `GET` | `/api/v1/cloud/lab/save` | Token de acceso | Descarga y devuelve gemas y huella; no devuelve contenido. |
| `POST` | `/api/v1/cloud/lab/prepare` | Token de acceso | Descarga, edita en memoria y crea respaldo privado. |
| `POST` | `/api/v1/cloud/lab/confirm` | Token + `X-SK-Cloud-Admin` | Sube el candidato, descarga y compara hashes. Frase `SUBIR`. |
| `POST` | `/api/v1/cloud/lab/verify` | Token de acceso | Compara la nube con el respaldo. |
| `POST` | `/api/v1/cloud/lab/restore` | Token + `X-SK-Cloud-Admin` | Reenvía el original y verifica. Frase `RESTAURAR`. |
| `GET` | `/api/v1/cloud/lab/backups` | Token de acceso | Resúmenes de respaldos, sin contenido. |

Los cuerpos de las rutas POST se limitan a 16 KiB y deben ser JSON UTF-8 sin compresión. Las respuestas llevan `Cache-Control: no-store` y `X-Content-Type-Options: nosniff`.

## Controles antes de escribir

1. La preparación descarga la copia actual y crea un respaldo con el original y el candidato.
2. La confirmación exige `write_enabled`, un uploader construido en el servidor y la autorización administrativa.
3. Vuelve a descargar la nube y aborta si su SHA-256 ya no coincide con el original del respaldo.
4. Vuelve a validar el candidato desde el respaldo antes de enviarlo.
5. Sube y descarga de nuevo. Solo un SHA-256 idéntico produce `persisted=true`.
6. Si la persistencia falla, no guarda la confirmación y el respaldo queda disponible para reintentar o investigar.
7. Una confirmación ya guardada no se repite: devuelve `cloud_already_confirmed`.

## Estados y errores

| Situación | Código HTTP | Código de error |
| --- | --- | --- |
| Laboratorio sin credenciales | `503` | `cloud_lab_not_configured` |
| Escritura deshabilitada | `503` | `cloud_write_disabled` |
| Falta autorización administrativa | `503` | `cloud_admin_not_configured` |
| Cabecera administrativa incorrecta | `403` | `cloud_admin_denied` |
| Sin token de acceso | `401` | `access_denied` |
| Respaldo inexistente | `404` | `backup_not_found` |
| Operación sin cambios | `409` | `cloud_no_changes` |
| Nube modificada desde la preparación | `409` | `cloud_remote_changed` |
| Respaldo ya confirmado | `409` | `cloud_already_confirmed` |
| Valor de gemas inválido | `422` | `invalid_gems_value` |
| Serialización no canónica | `422` | `unsupported_serialization` |
| Sesión de nube rechazada | `502` | `cloud_session_rejected` |
| Fallo de red o protocolo de nube | `502` | `cloud_provider_*` / `cloud_upload_rejected` |

## Frontend

La navegación incluye **Partida**. La página:

- consulta el estado del laboratorio y los respaldos;
- pide el token de acceso si la API está en modo `token`;
- carga la copia y muestra el valor actual;
- valida localmente que el entero esté en rango antes de preparar;
- muestra la vista previa, el respaldo y la huella del candidato;
- exige token administrativo, frase `SUBIR` y confirmación de sobrescritura;
- deshabilita la confirmación si el laboratorio es de solo lectura o si la vista previa quedó obsoleta;
- muestra el resultado de la subida, la persistencia y la verificación;
- permite restaurar un respaldo con la frase `RESTAURAR`.

La estética oscura se limita a la sección de laboratorio y reutiliza la tipografía, los botones y el lenguaje visual del resto del sitio.

## Pruebas

- `backend/tests/test_gems_editor.py`: lectura, edición, determinismo, límites, serialización, rechazo de gzip/no canónico, respaldo, carga verificada, manipulación, confirmación, restauración y eventos.
- `backend/tests/test_cloud_lab_api.py`: autenticación, autorización administrativa, flujo completo con proveedor y uploader simulados, no-op, nube cambiada, errores de sesión/red, CORS y OpenAPI.
- `frontend/tests/lab-editor.spec.ts`: flujo completo con API simulada, solo lectura, gating de confirmación y ancho móvil.

Ninguna prueba contacta ChillyRoom.

# Evidencia y pruebas

## Artefactos privados

Directorio: `~/.config/sk-under/phase6-1/`. No se versiona.

| Archivo | Bytes | SHA-256 | Papel |
| --- | ---: | --- | --- |
| `original.json` | 114.778 | `eeef81390418a60cf6f4da25932ab93c0ee22bc418eeb60bf595f28f13f6f97c` | Copia original descargada; modo `0400` |
| `modified-gems-1001.json` | 114.778 | `3f4b7617b04da3f1bd3b1b01197c46cf99d6ebd2a048c733d1738657239f492a` | Un solo byte distinto |
| `download-20261123T203954Z.json` | 114.778 | `eeef…97c` | Descarga previa a la primera subida |
| `download-20261123T204012Z.json` | 114.778 | `eeef…97c` | Descarga posterior a la subida idéntica |
| `download-20261123T204031Z.json` | 114.778 | `3f4b…92a` | Descarga posterior a la modificación |
| `upload-attempt-20261123T204008Z.json` | — | `873d029ad49460ad4f191dc39693a3073c208ef19fa5fc198f0c70feadabe35c` | Respuesta cruda de la subida idéntica |
| `upload-attempt-20261123T204027Z.json` | — | `cbe03ade8f4bb584719cee607bae04af790bc0102738209b985c324664bcce5e` | Respuesta cruda de la subida modificada |
| `repository-cli-roundtrip.json` | — | `37527aac683facf462a2220af2cab0cc01d7dbadaec0cb64744dec4b18eb47e9` | Salida de la CLI del repositorio |
| `game-cloudpanel2.png` | 36.151 | `a2a299bbd9a7641c4ab6c501d75fd0289c05196ecd70c4e144ef07cd5c133a55` | Nube `1001`, local `1000` |
| `game-after-retrieve.png` | 29.782 | `b740cd75f2345d42d7a49b88b01a8343725b3d95665957163968c3ed28e3a97e` | Ambas filas `1001` |
| `game-select2.png` | 209.502 | `59bed87401696ffff2ce2b21f57dd81ce4eef3a0ccfa16b5e5f809ba0442cc0c` | Hall con `1001` |
| `retrieval-logcat.txt` | — | `cd7f96d3187a5569aed3c5e4456238b07ea529cd8b6382c703d1eb9fbf6f0934` | `CoverPlayerPref` y `AutoDnloadAsync` |
| `after-retrieve-game-gems.json` | — | `1010246dff9dbc514cf91823db7c8058b3e1c832d861da6c51117e8cd6c4e6c0` | `game.data` local con `gems=1001` |
| `after-retrieve-profile.tar` | 9.915.392 | — | Perfil local posterior a la recuperación |

## Comandos ejecutados

Descarga autenticada:

```bash
cd backend
.venv/bin/python ~/.config/sk-under/phase6-1/download.py
```

Subida idéntica y modificada (script de laboratorio, anterior a la integración):

```bash
.venv/bin/python ~/.config/sk-under/phase6-1/upload_attempt.py \
  ~/.config/sk-under/phase6-1/original.json
.venv/bin/python ~/.config/sk-under/phase6-1/upload_attempt.py \
  ~/.config/sk-under/phase6-1/modified-gems-1001.json
```

Subida y verificación con el código del repositorio:

```bash
.venv/bin/python -m app.cloud.blob_roundtrip \
  ~/.config/sk-under/phase6-1/modified-gems-1001.json \
  --confirm-experimental-write
```

El wrapper privado que carga las credenciales es `run_repository_cli.py`; no se versiona.

## Pruebas del backend

```bash
cd backend
.venv/bin/python -m compileall -q app
.venv/bin/python -m pytest -q
```

Resultado: **275 pasan, 16 se omiten**. Las omisiones son pruebas privadas que requieren muestras o respuestas capturadas no configuradas en esta ejecución. La suite nueva `tests/test_cloud_blob_upload.py` aporta **19 pruebas** con servidor HTTP local y proveedor simulado; no contacta el servicio real.

## Verificación del cliente

- Panel de nube: **1001** arriba, **1000** abajo.
- Tras recuperar: **1001** en ambas filas.
- `game.data` local: 41 claves, `gems=1001`.
- Hall abierto: **1001** visible.

## Publicación

El commit y el resultado de GitHub Actions se registran en el informe de entrega y en el mensaje de commit. El árbol no contiene secretos, partidas ni capturas.

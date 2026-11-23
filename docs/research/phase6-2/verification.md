# Verificación

## Pruebas locales

```bash
cd backend
.venv/bin/python -m compileall -q app
.venv/bin/python -m pytest -q
```

Resultado: **330 pasan, 16 se omiten**. Las omisiones son pruebas privadas que requieren muestras o respuestas capturadas no configuradas en esta ejecución. La suite nueva no contacta ChillyRoom.

```bash
cd frontend
npm run build
npm run test:browser
```

Resultado: TypeScript y Vite compilan; **10 pruebas de Playwright pasan** (4 existentes y 6 nuevas del editor de partida).

## Verificación real de lectura

La API real se arrancó desde Linux con la sesión de laboratorio de la Fase 6.1, `SK_CLOUD_WRITE_ENABLED=false` y un directorio de respaldos privado. Las credenciales se cargaron desde el archivo privado existente y no se imprimieron.

| Petición | Resultado |
| --- | --- |
| `GET /api/v1/health` | `200`, `access_mode=token`. |
| `GET /api/v1/cloud/lab/status` | `mode=read_only`, `read_ready=true`, `write_enabled=false`, `admin_configured=true`. |
| `GET /api/v1/cloud/lab/save` | `modern-cloud`, 114.778 bytes, `gems=1001`, `serialzed_version=1`, SHA-256 `3f4b7617b04da3f1bd3b1b01197c46cf99d6ebd2a048c733d1738657239f492a`. |
| `POST /prepare` con `1001` | `changed=false`; candidato idéntico al original; respaldo creado. |
| `POST /prepare` con `1002` | `changed=true`; 114.778 bytes; un byte distinto; candidato `d0e019c816921f0d…`; respaldo creado. |
| Respaldo `1002` | `original.json`, `candidate.json` y `record.json` con modo `0600`; directorio `0700`. |
| Reproducción independiente | `prepare_gems_edit(original, 1002)` devuelve exactamente el candidato respaldado. |
| Conservación semántica | Al reponer `gems=1001` en el candidato, el documento es idéntico al original; 17 secciones y 38 claves en `gameData`. |

La nube ya contenía `1001`, por lo que **no se ejecutó confirmación ni restauración remota**. No se hizo una escritura adicional sin una modificación pendiente que la justificara.

## Verificación real de la interfaz

Se levantó Vite contra la API real y se ejecutó un recorrido con Playwright:

- la página mostró `Laboratorio real · solo lectura`;
- tras introducir el token de acceso, cargó la copia y mostró `1,001` gemas;
- preparó `1002` y mostró `1001 → 1002` con «Solo cambia gameData.gems.»;
- el botón de subida permaneció deshabilitado por la escritura deshabilitada en el servidor;
- la preparación sin cambios mostró «El valor solicitado ya está en la partida; no hay cambios que subir.»;
- no hubo errores de consola.

La captura privada se conserva en `~/.config/sk-under/phase6-2/real-browser.png` y no se versiona.

## Cliente oficial

No se reejecutó la comprobación con Soul Knight 8.8.0: `adb devices` no encontró dispositivos y no había un AVD disponible. La aceptación de `gems=1001` por el cliente oficial, la escritura en `game.data` y el hall con `1001` siguen documentados en la [Fase 6.1](../phase6-1/client-validation.md). El editor web no depende del emulador.

## Publicación

- Commit final: pendiente de registrar tras el push.
- GitHub Actions: pendiente de verificar tras el push.

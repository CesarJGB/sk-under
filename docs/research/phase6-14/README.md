# Fase 6.14 — Edición experimental de fichas de pesca

Esta fase habilita una prueba manual autorizada del saldo candidato
`gameData.fishChip` desde el editor web. La escritura se limita a ese campo y
reutiliza el flujo autenticado, el respaldo cifrado, la confirmación y la
restauración que ya existían para las gemas. **El campo sigue siendo E2 y no se
presenta como una funcionalidad validada.**

## Resultado en una página

- La vista **Editor** de `/partida` muestra una tarjeta identificada como
  **Experimental · E2** para las fichas de pesca.
- Se visualiza el saldo de la copia descargada y se puede introducir un entero
  no negativo entre 0 y 2 147 483 647.
- Preparar la edición crea un respaldo cifrado y un candidato determinista que
  solo cambia `gameData.fishChip`.
- La subida usa el mismo endpoint autenticado de confirmación de gemas. La
  descarga posterior verifica que el agregado remoto coincide con el candidato.
- La vista **Partida** lista los respaldos con su campo (`gemas` o
  `fichas de pesca`) y permite verificarlos o restaurarlos.
- No se añadió ninguna marca de escritura nueva: se reutiliza la autorización
  de escritura del perfil y del servidor que ya usan las gemas. Por ello la
  versión desplegada permite iniciar la prueba manual sin configuración extra.

## Alcance y límites

| Elemento | Estado | Límite explícito |
| --- | --- | --- |
| `gameData.fishChip` | Escritura experimental autorizada, E2 | No hay evidencia de una transacción legítima ni de la autoridad del servidor. La persistencia dentro del juego no está validada. |
| `material_fish`, `cumulativeFishCount` | Solo lectura | No forman parte del plan de edición ni se recalculan. |
| `fishChipStore*`, `furniture_fish_chips` | Solo lectura | No se crean, modifican ni interpretan como saldo. |
| Gemas | Sin cambios | Conservan su conciliación `gems = lastGems + varGems`, sus respaldos y su restauración. |
| Personajes, habilidades, skins y demás recursos | Solo lectura | No se habilitó ninguna edición nueva. |

La tarjeta advierte expresamente que la escritura es una prueba y que faltan la
comprobación de gasto, la persistencia tras reiniciar y la descarga desde un
dispositivo Android real. La documentación del registro de campos mantiene
`validation_level: E2` y describe la política como escritura experimental, no
como una capacidad validada.

## Implementación

### Backend

- `backend/app/cloud/fish_chip_editor.py` valida la serialización canónica del
  agregado y prepara un candidato que solo cambia `gameData.fishChip`. Reutiliza
  `serialize_aggregate` del editor de gemas y repite la verificación inversa:
  restaurar el valor original debe reproducir los bytes de entrada.
- `backend/app/cloud/backup_store.py` añade el campo `field` al registro
  (`gems` o `fish_chip`). Los respaldos de la Fase 6.13 sin `field` se siguen
  leyendo como gemas. La carga verifica el candidato con el editor que
  corresponde al campo registrado.
- `backend/app/cloud/lab_service.py` incorpora `prepare_fish_chip()`, expone el
  saldo en la descarga y adapta la confirmación, verificación y restauración al
  campo del respaldo. Las respuestas añaden `field` y `remote_value` sin quitar
  `remote_gems`, por lo que los clientes anteriores siguen funcionando.
- `backend/app/api/native.py` añade `POST /api/v1/cloud/native/prepare-fish-chip`.
  La confirmación, la restauración y la lista de respaldos siguen usando las
  rutas existentes.
- `backend/app/save_report.py` conserva el informe como solo consulta, pero
  declara `write_policy: experimental_authorized` y `validation_level: E2`
  para las fichas.

### Frontend

- `frontend/src/pages/NativeAuthPage.tsx` incorpora la tarjeta experimental,
  el campo de saldo, la vista previa del cambio, la confirmación explícita y el
  botón de subida. Los estados de error distinguen fichas de gemas.
- La lista de respaldos muestra la etiqueta y el valor del campo correspondiente
  y mantiene disponibles la verificación y la restauración.
- `frontend/src/pages/SaveReportSections.tsx` mantiene el informe de recursos y
  personajes como solo consulta y explica que la escritura de fichas es
  experimental.

## Pruebas automatizadas

Backend:

```bash
cd backend
.venv/bin/python -m pytest
```

Frontend:

```bash
cd frontend
npm run build
npx playwright test
```

La fase añade pruebas que comprueban:

- el cambio de `gameData.fishChip` en el agregado;
- el rechazo de valores negativos, flotantes, booleanos, texto y fuera de rango;
- la conservación de gemas, `material_fish`, `cumulativeFishCount`,
  `fishChipStorePurchaseHistory` y del resto del agregado;
- la creación, verificación, confirmación y restauración de respaldos de fichas;
- que la edición de gemas sigue funcionando junto a los respaldos de fichas;
- que la interfaz prepara y sube el cambio mediante el flujo autenticado y
  rechaza valores inválidos antes de llamar a la API.

Resultado de la entrega: `503 passed, 16 skipped` en backend, `36 passed` en
Playwright y `npm run build` completado con `tsc --noEmit` y Vite. Las pruebas
omitidas requieren muestras privadas o credenciales y no forman parte de esta
fase.

## Validación manual posterior

El propietario realizará estas comprobaciones en un dispositivo Android real.
No bloquean la entrega de la fase:

1. Modificar el saldo desde el editor web.
2. Subir la partida a la nube.
3. Recuperar la partida desde un dispositivo Android real.
4. Comprobar el saldo dentro del juego.
5. Intentar gastar las fichas.
6. Reiniciar el juego y comprobar su persistencia.
7. Guardar nuevamente en la nube y descargar la partida para verificar los
   valores resultantes.

Hasta completar ese protocolo, los resultados deben registrarse como
observaciones experimentales y no como validación E3/E4.

## Fuera de alcance

- No se modifican archivos XML ni PlayerPrefs: el flujo opera sobre el agregado
  de guardado en la nube.
- No se alteran autenticación, descarga, subida ni las garantías de las gemas.
- No se habilitan personajes, habilidades, skins ni otros recursos.
- No se publican capturas privadas, credenciales, tokens ni el documento privado
  de investigación de Discord.
# Fase 10.2 — Validación real de escritura iOS

Fecha: 2026-11-27.

> **Corrección posterior (Fase 10.1, 2026-11-27):** la persistencia en el
> servidor descrita aquí fue real, pero **el cliente oficial de iOS rechazó el
> guardado** con «La versión de tu juego es demasiado antigua». La causa era
> enviar `8.8.0.13` (versión visible) en `x-app-version` y `x-game-version` en
> lugar de la versión de protocolo `8.8.0`. Por tanto el nivel D no estaba
> realmente alcanzado y el nivel E seguía pendiente. El análisis y la corrección
> están en
> [`../phase10-1/ios-version-metadata.md`](../phase10-1/ios-version-metadata.md).
> Este documento se conserva como registro de lo que se probó y de sus límites.

Esta fase deja de tratar la escritura iOS como una hipótesis. Con una cuenta iOS
de pruebas expresamente autorizada por el propietario se comprobó que el mismo
transporte `BlobSave` usado para Android acepta, conserva y devuelve un guardado
iOS modificado. La evidencia se obtuvo con respaldo íntegro, confirmación
explícita, descarga posterior y restauración del original.

## Resultado principal

| Prueba | Resultado | Evidencia |
| --- | --- | --- |
| Login nativo iOS | Correcto | Sesión `IOS_`, distro iOS, `platformId: IOS` |
| Descarga del guardado | Correcto | 115.175 bytes, `gameVersion` iOS, SHA-256 registrado en privado |
| Respaldo completo previo | Correcto | Copia privada 0600 y respaldo cifrado del laboratorio |
| Resubida sin cambios | HTTP 200 `true` | Descarga posterior byte a byte idéntica |
| Edición aislada | Correcto | Solo `gameData.gems` y su contrapeso `gameData.varGems` |
| Subida del candidato | HTTP 200 `true` | Descarga posterior con el mismo SHA-256 del candidato |
| Persistencia de gemas | Correcto | 1.000 → 1.100, y después 1.000 → 1.050 en la prueba de integración |
| Restauración | Correcto | Descarga posterior idéntica al original; gemas de vuelta a 1.000 |
| Integridad estructural | Correcto | `platformId`, `cloudSaveId`, secciones y campos desconocidos intactos |

Un HTTP 200 no se consideró prueba por sí solo. Cada subida se siguió de una
descarga independiente y de la comparación de tamaño, SHA-256 y contenido.

## Qué se probó exactamente

1. Inicio de sesión con la cuenta autorizada y la identidad de dispositivo ya
   vinculada, mediante portal + gateway + `x-distro-id` iOS.
2. Descarga del guardado nativo y respaldo completo antes de cualquier escritura.
3. Reenvío del original sin modificaciones y comprobación de persistencia exacta.
4. Edición aislada de gemas con el editor existente: únicamente cambiaron
   `gameData.gems` y `gameData.varGems`.
5. Subida del candidato, descarga posterior y comparación de SHA-256.
6. Restauración del original y nueva descarga de verificación.
7. Repetición del ciclo completo a través de `CloudLabService`, no solo del
   transporte: respaldo cifrado, preparación, confirmación con detección de
   cambios remotos, verificación y restauración.

La segunda prueba de integración usó 1.050 gemas y terminó restaurando 1.000. El
resultado confirmó `persisted: true`, `remote_gems: 1050` y después
`remote_gems: 1000`, con los hashes esperados.

Se probó un segundo campo aislado, las fichas de pesca: 0 → 1 → 0. La edición
cambió solo `gameData.fishChip` y su contraparte `itemData.materials.material_fish`.
La subida persistió en la nube, la descarga posterior devolvió 1 y la
restauración devolvió el archivo original exacto. Esto descarta que la escritura
funcione únicamente para el campo de gemas.

## Verificación en producción

Tras desplegar el commit `b40ae3c` se repitió el ciclo completo contra
`https://api-sk.underdive.space` con la cuenta autorizada, no solo en local:

- Login correcto con `write_state: write_experimental` y `write_ready: true`; el
  perfil de dispositivo existente se reutilizó sin nueva espera de vinculación.
- Respaldo manual creado y visible en el historial junto al respaldo previo.
- Candidato unificado de 1.050 gemas: `accepted: true`, `persisted: true`,
  descarga posterior con 1.050 y SHA-256 del candidato.
- Verificación `matches_candidate: true`.
- Restauración: `persisted: true`, 1.000 gemas y SHA-256 original exacto.
- Segundo campo de fichas de pesca 0 → 1 → 0 con la misma persistencia y
  restauración exacta.
- La interfaz de producción muestra el aviso experimental, el editor habilitado y
  el botón de guardado a 390 px, sin desbordamiento horizontal.

## Apple ID, Game Center y autorización

- La cuenta de prueba es una cuenta ChillyRoom vinculada por correo y contraseña.
  La escritura funcionó con la sesión emitida por `UserAuth/Login`; no se necesitó
  ningún token de Apple ID ni de Game Center.
- Esto no demuestra que una cuenta iOS que solo use Apple ID pueda operarse sin el
  flujo oficial de Apple. Para esas cuentas sigue siendo necesario un token de
  identidad emitido por el cliente oficial, que no está implementado.
- La documentación oficial describe la subida manual desde el juego y no publica
  un contrato HTTP. La falta de documentación no impidió validar el mecanismo con
  una sesión legítima.
- No se usaron tokens fabricados, suplantación de identidad ni evasión de los
  controles del servidor.

## Límites de vinculación de dispositivos

La documentación oficial de ChillyRoom limita la vinculación a **5 dispositivos
por cada 90 días**, con al menos **24 horas entre vinculaciones**. Iniciar sesión
en un dispositivo nuevo y subir o descargar progreso consume una oportunidad.

La prueba consumió una vinculación al usar una identidad de dispositivo nueva.
No se crearon identidades adicionales innecesarias. Cualquier prueba posterior
con otro dispositivo debe esperar el intervalo correspondiente.

## Modo experimental restringido

> **Actualización 2026-11-27:** a petición explícita del propietario se habilitó
> temporalmente la subida iOS para todas las cuentas mediante
> `IOS_WRITE_TEST_ENABLED = True`. El estado sigue siendo `write_experimental`,
> no `write_verified`, y el modo se puede revertir. Ver
> [Fase 10.1, sección 11](../phase10-1/ios-version-metadata.md#11-modo-de-prueba-de-escritura-2026-11-27).
> El texto siguiente describe el modo restringido original de la Fase 10.2.

La escritura iOS general sigue en `write_pending_validation`. Se añadió un modo
`write_experimental` que solo se activa para la cuenta de pruebas autorizada,
identificada mediante un digest SHA-256 con separación de dominio. El correo no
se guarda en el código ni se registra.

Consecuencias:

- La cuenta autorizada ve el editor normal, puede preparar, respaldar, subir y
  restaurar.
- Cualquier otra cuenta iOS sigue viendo preparación y respaldos, pero la subida
  permanece bloqueada con `native_write_pending_validation`.
- Android conserva su flujo verificado y sus pruebas.
- El modo se puede retirar cambiando el digest o el estado de la matriz.

No se habilita la escritura iOS para usuarios generales. La matriz sigue
declarando que la plataforma iOS no está verificada de forma general.

## Cambios técnicos

- `backend/app/cloud/capabilities.py`: estado `write_experimental`, digest de la
  cuenta autorizada y matriz específica de la cuenta.
- `backend/app/cloud/lab_service.py`: modo experimental explícito; las
  comprobaciones de escritura siguen exigiendo respaldo, confirmación y
  verificación.
- `backend/app/native/service.py`: autorización por cuenta, factorías de descarga
  y subida conscientes de la distribución y visibilidad correcta en sesión y
  cuentas.
- `backend/app/cloud/blob_wire.py`, `blob_upload.py`, `modern.py`: cabeceras
  `x-platform`, `x-app-version` y `x-game-version` derivadas de la distribución
  iOS. Android mantiene sus valores por defecto.
- `frontend/src/pages/EditorWorkspace.tsx` y `AccountPage.tsx`: aviso explícito de
  modo experimental, confirmación y flujo normal de subida solo para la cuenta
  autorizada.
- `backend/app/version.py`: `ios_remote_write_experimental`.

## Pruebas

- Backend: 769 pruebas, 16 omitidas. Incluye cuatro pruebas nuevas del modo
  experimental, cabeceras iOS, respaldo, persistencia y aislamiento de otra
  cuenta iOS.
- Frontend: 100 pruebas Playwright aprobadas, 22 omitidas; se añadió el flujo
  experimental iOS con confirmación y verificación.
- `npm run build` correcto.
- Capturas móviles/tableta/escritorio sin desbordamiento horizontal.

## Riesgos y límites

- La evidencia cubre una cuenta iOS autorizada y campos de progreso editables con
  los editores existentes. No demuestra que todos los campos iOS tengan la misma
  semántica ni que el cliente iOS acepte cualquier combinación.
- El cliente puede aplicar validaciones adicionales al cargar la partida. La
  comprobación en un iPhone físico sigue siendo la validación final.
- ChillyRoom puede aplicar sanciones por manipulación del progreso. El propietario
  aceptó el riesgo para esta cuenta de pruebas.
- La restauración remota está validada por bytes; la interfaz del juego puede
  tardar en reflejar cambios o requerir reinicio.
- No se usó la partida de referencia "César Javier Bebe" para evitar consumir otra
  vinculación y porque la copia de la cuenta de prueba ya permitió validar el
  contrato de escritura.

## Nivel alcanzado

- A: investigación y requisitos reales — alcanzado.
- B: preparación completa de candidatos iOS en la infraestructura web — alcanzado.
- C: mecanismo remoto autorizado identificado y validado — alcanzado.
- D: escritura remota integrada en SK-Under con respaldo y verificación de
  persistencia — **no alcanzado**: el cliente oficial rechazó el blob por
  metadatos de versión. Corregido en la Fase 10.1, pendiente de validación
  física.
- E: confirmación del propietario en un iPhone físico — pendiente.

## Pasos mínimos para el propietario

1. Abrir SK-Under, iniciar sesión con la cuenta iOS autorizada y descargar la
   partida.
2. Crear o aceptar el respaldo completo.
3. Hacer un cambio pequeño y autorizado, confirmar la subida y esperar la
   verificación de SK-Under.
4. Abrir Soul Knight en el iPhone, recuperar el progreso desde la nube si el
   cliente lo solicita y comprobar el valor.
5. Si el valor no aparece, restaurar el respaldo desde SK-Under y comunicar el
   resultado. No repetir subidas sin conservar el respaldo.
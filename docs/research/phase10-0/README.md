# Fase 10.0 — Compatibilidad iOS: investigación e integración inicial

Fecha: 2026-11-26

## Resumen ejecutivo

La fase alcanza los niveles **A, B, C y D** definidos en el encargo:

- **A — Investigación:** diferencias de plataforma documentadas y separadas de
  las diferencias de versión o progreso.
- **B — Compatibilidad local:** importación, decodificación, informe y lectura
  de un guardado iOS real, incluida la representación que exporta CRDE.
- **C — Comunicación directa:** autenticación y descarga de una partida iOS
  real desde el backend de SK-Under.
- **D — Integración:** cuenta iOS en el flujo multicuenta existente, partida,
  respaldos separados y editor en modo de solo lectura.

**No se declara el nivel E.** No se han generado ni probado candidatos de
escritura locales en un dispositivo iOS físico, y la escritura remota permanece
deshabilitada por diseño.

La investigación fue de solo lectura. No se subió ninguna partida, no se
compraron créditos ni se enviaron modificaciones a CRDE, y no se alteró ninguna
cuenta remota.

## 1. Hallazgos sobre CRDE

CRDE se usó únicamente como referencia de investigación con la sesión
autorizada de nuestra propia cuenta. No es una dependencia de SK-Under.

### Cómo distingue Android e iOS

- La plataforma se guarda como **canal de la cuenta vinculada** (`GP`, `IOS`,
  `IOS_VNM`, `IOS_CN`, `TapTap`, …). No se deduce del guardado en el navegador.
- El formulario de alta solo pide correo, contraseña, canal y juego. **No pide
  Apple ID ni Game Center**; la vinculación iOS la resuelve su backend.
- La respuesta RAW no incluye un campo de plataforma del juego. CRDE añade
  `_crde_misc.platformId = "IOS"` y mueve ahí `maps`.
- El cliente público no expone ningún endpoint que devuelva el distro, el
  identificador de jugador ni el token de la cuenta iOS.

### Qué ocurre en el navegador y qué en el backend

| Operación | Lado observado |
| --- | --- |
| Formulario, selección de canal/juego y estado de la UI | Navegador |
| Aplicación de reglas de plan y bloqueo de RAW | Navegador, y también backend |
| Envío de correo/contraseña a `/api/accounts` | Navegador |
| Autenticación real contra el servicio del juego | Backend de CRDE |
| Obtención y decodificación del guardado | Backend de CRDE |
| Aplicación de modificaciones masivas | Backend de CRDE |
| Persistencia RAW (`PUT .../raw`) | Backend de CRDE |
| Créditos, migración, cambio de contraseña | Backend de CRDE |

El mecanismo exacto con el que CRDE obtiene la partida iOS está encapsulado en
su servidor. Se registra como **desconocido**. No se intentó eludir ningún
control ni recuperar secretos internos.

### Formato de exportación

- `GET /api/accounts/{id}/raw` devuelve el guardado **ya decodificado** como
  JSON, sin sobre de transporte.
- CRDE elimina del nivel superior `cloudSaveId`, `platformId`, `maps` y
  `serialzedVersion`; conserva los tres primeros en `_crde_misc`.
- Convierte enteros grandes de tiempo a cadenas
  `__CRDE_LARGE_INT64__<valor>`. Es un artefacto de visualización: al comparar
  con la partida nativa, las únicas diferencias fueron esas cadenas y los
  metadatos retirados.
- No se encontró un botón independiente de descarga o respaldo. La
  visualización RAW fue el mecanismo disponible.
- Las operaciones de edición son las mismas para Android e iOS; la diferencia
  práctica es el canal usado al vincular la cuenta.

## 2. Diferencias entre Android e iOS

La comparación usó la partida iOS nativa descargada por SK-Under (17 secciones,
`gameVersion` 2155, `AppVersion` 1531), la exportación CRDE de esa misma cuenta
y dos partidas Android de versiones y progreso distintos.

| Aspecto | Android | iOS nativo | Lectura |
| --- | --- | --- | --- |
| Transporte | Gateway + `BlobSave` | El mismo contrato | Compartido |
| Selección de partida | `x-distro-id` de Android | `x-distro-id` de iOS | Específico por cuenta, no por cabecera `x-platform` |
| `platformId` | UUID de distribución | `IOS` | Diferencia de plataforma confirmada |
| `cloudSaveId` | `GP_…` / `GPV2_…` | `IOS_…` | Diferencia de plataforma confirmada |
| `serialzedVersion` | 1 | 1 | Compartido |
| `maps` | Presente | Presente | Compartido |
| Secciones de juego | 13 + `gameData` en 8.8.0 | Las mismas 13 + `gameData` | Compartido |
| `gameData.gameVersion` | 2145 / 2155 según muestra | 2155 | Diferencia de versión, no de plataforma |
| `itemData.AppVersion` | 80800 en 8.8.0 | 1531 | Marcador específico de plataforma/compilación |
| Planos | Entero 1/2 | Entero 1/2 | Compartido |
| Catálogos e identificadores | — | Mismos códigos | Compatibles |
| Progreso y desbloqueos | Varía por cuenta | Varía por cuenta | No atribuible a la plataforma |

No se encontró ningún campo de juego exclusivo de iOS. Las diferencias
observadas son de **identidad de plataforma, versión de compilación y progreso
de la cuenta**. La afirmación de ChillyRoom de que los sistemas de cuenta y las
estructuras de datos son distintos se confirma en la identidad y el canal; no
se observó una estructura de secciones divergente en 8.8.0.

La exportación CRDE no debe usarse para decidir el formato nativo: elimina
metadatos y transforma enteros. El formato nativo es el que devuelve
`BlobSave`, con el sobre completo.

## 3. Mecanismos de comunicación identificados

1. **Descubrimiento de jugadores:** el portal oficial de ChillyRoom permite
   iniciar sesión y enumerar los jugadores de Soul Knight con su `pid` y
   `registerDistroId`/`lastLoginDistroId`. La cuenta debe estar vinculada por
   correo/contraseña.
2. **Login de juego:** `POST /UserAuth/Login` en el gateway, con
   `loginType: 3`, correo y contraseña, y cabeceras de juego que incluyen
   `x-distro-id`, `x-platform`, `x-app-version`, `x-game-version`, `x-game-id`,
   `x-unique-id` y `x-game-lang`.
3. **Descarga:** `POST /BlobSave/Download` con el token de sesión, el
   identificador de dispositivo y el distro. La respuesta usa compresión gzip
   en tránsito y contiene un objeto `{ "data": "<json>" }`; `data` es el
   guardado completo ya en JSON. No hay un segundo sobre comprimido dentro.
4. **Sesión:** el token tiene expiración y se conserva solo en memoria; no se
   reutiliza entre plataformas ni se escribe en el repositorio.

La selección de la partida la determina el **distro**. Enviar `x-platform: ios`
con un distro Android devuelve la partida Android. Por eso SK-Under verifica el
marcador `platformId` de la partida descargada antes de aceptarla.

### Identificadores necesarios para interpretar frente a autenticar

- Para **interpretar** el guardado bastan `gameData`, las secciones y los
  catálogos. `platformId`, `cloudSaveId` y las versiones sirven para
  identificación y validación, no para leer el progreso.
- Para **autenticar** hacen falta la cuenta, el distro correcto, un
  identificador de dispositivo y el token de sesión. El correo o el `pid` por
  separado no autentican.

### Límite de autenticación

La ruta verificada funciona para cuentas iOS vinculadas a una cuenta ChillyRoom
con correo y contraseña. El cliente oficial también contiene rutas para
`InspectWithAppleId` y `BindingWithAppleId`; una cuenta que solo use Apple ID o
Game Center necesitará el token de identidad de Apple emitido por el flujo
oficial. No se dispone de ese token y no se ha implementado ese camino.

## 4. Estado real de la autenticación

- **Verificada** con una cuenta iOS propia, canal `IOS`, versión 8.8.0.13.
- El portal resolvió el jugador iOS correcto y el login del gateway devolvió un
  token válido para ese `pid`.
- El `pid` de iOS es distinto del `pid` Android de la misma persona, aunque
  compartan el identificador de cuenta ChillyRoom.
- No se usaron credenciales de Apple, Game Center, CRDE ni tokens de terceros.
- La sesión es independiente de la de Android y queda marcada como solo
  lectura.

## 5. Estado real de la descarga

- **Verificada.** `POST /BlobSave/Download` devolvió HTTP 200 y un guardado
  nativo iOS de 279.230 bytes.
- El documento contiene `cloudSaveId` con prefijo `IOS_`, `platformId: "IOS"`,
  `serialzedVersion: 1`, `gameVersion: 2155`, `itemData.AppVersion: 1531` y las
  17 claves de nivel superior esperadas.
- La lectura coincide con la exportación CRDE de la misma cuenta. Las
  diferencias son solo los metadatos retirados por CRDE y las cadenas de
  enteros grandes.
- La muestra original permanece fuera del repositorio.
- No se realizó ninguna subida.

## 6. Compatibilidad con el editor

La lectura se considera compatible cuando el informe puede construirse y los
valores se interpretan con los catálogos existentes. La escritura iOS **no está
expuesta**, ni local ni remota.

| Funcionalidad | Lectura iOS | Escritura iOS | Evidencia |
| --- | --- | --- | --- |
| Monedas y recursos | Compatible | No expuesta | E2 |
| Personajes y niveles | Compatible | No expuesta | E2 |
| Habilidades | Compatible | No expuesta | E2 |
| Skins de personaje | Compatible | No expuesta | E2 |
| Skins de armas | Compatible | No expuesta | E2 |
| Efectos de eliminación | Compatible | No expuesta | E2 |
| Mascotas y afinidad | Compatible | No expuesta | E2 |
| Planos | Compatible | No expuesta | E2 |
| Progreso y desbloqueos | Compatible | No expuesta | E2 |
| Decoraciones y vestíbulo | Pendiente de investigación | No expuesta | E2 |
| Objetos y máquinas del vestíbulo | Pendiente de investigación | No expuesta | E2 |
| Escritura local experimental | — | No implementada | H |
| Validación en iOS físico | Pendiente | Pendiente | — |

El informe iOS no hereda los niveles E3/E4 de Android. Las políticas de
escritura se presentan como `not_exposed`, la transacción como no validada y las
skins como `not_validated`. Que una función esté confirmada en Android no la
convierte en confirmada en iOS.

## 7. Cambios implementados

### Backend

- `backend/app/cloud/ios.py`: detección y decodificación de guardados iOS
  nativos y de la representación CRDE; conserva los bytes originales; rechaza
  documentos sin marcador iOS; calcula SHA-256; genera un informe de solo
  lectura con matriz de capacidades y niveles de evidencia propios de iOS.
- `backend/app/api/ios.py`: `GET /api/v1/cloud/ios/capabilities` y
  `POST /api/v1/cloud/ios/inspect` para importar y analizar una copia local sin
  autenticar ni escribir.
- `backend/app/native/distributions.py`: `ios-global` habilitada y validada
  para lectura, versión 8.8.0.13, con nota explícita de solo lectura.
- `backend/app/native/errors.py`: error de plataforma
  `native_platform_mismatch` cuando el distro devuelve una partida de otra
  plataforma.
- `backend/app/native/service.py`: validación del marcador de plataforma antes
  de aceptar la partida; sujeto de identidad con ámbito de plataforma; raíz de
  respaldos separada (`…/ios`); bloqueo de escritura y de laboratorio para iOS;
  `read_only` en la vista de cuenta y sesión.
- `backend/app/save_report.py`: el informe acepta plataforma y degrada las
  afirmaciones de escritura para iOS sin cambiar la salida Android.
- `backend/app/version.py`: capacidades `ios_local_import`,
  `ios_read_only_report` e `ios_native_read_only`.

### Frontend

- Selector de distribución con la opción iOS marcada «Solo lectura».
- Mensaje específico en Partida para iOS.
- Editor deshabilitado por completo cuando `write_ready` es falso, no solo el
  botón de subida.
- Tipos y mensajes para el nuevo error de plataforma.
- El dashboard ya mostraba la plataforma; ahora recibe cuentas iOS reales.

### Respaldos

- Los respaldos iOS se guardan bajo un sujeto con ámbito de plataforma, en una
  raíz `…/ios`, separada de Android.
- Se creó y listó un respaldo iOS en la verificación en vivo.
- La restauración remota queda bloqueada por `cloud_write_disabled`.

## 8. Pruebas realizadas

- **Backend:** 761 pruebas superadas, 16 omitidas.
- **Nuevas pruebas iOS:** 12, con documentos sintéticos, sin muestras privadas.
  Cubren decodificación nativa y CRDE, gzip, conservación de bytes y SHA,
  rechazo de documentos Android o sin marcador, tipos inválidos, capacidades,
  distribución habilitada, separación de sujetos, rechazo de plataforma
  incorrecta y contrato de la API.
- **Frontend:** `npm run build` supera TypeScript y Vite.
- **Playwright:** prueba específica de cuenta iOS y editor de solo lectura
  superada; se comprobó el `fieldset` deshabilitado, el botón Guardar
  deshabilitado y el mensaje de Partida. La suite completa se ejecuta antes del
  cierre.
- **Verificación en vivo:** login iOS, descarga, lectura de gemas y fichas,
  creación de respaldo y bloqueo de restauración, sobre una tienda temporal.
- **Integridad:** el SHA-256 del guardado original no cambió; no se escribió en
  la nube.

## 9. Nivel de avance alcanzado

| Nivel | Estado |
| --- | --- |
| A — Investigación | Alcanzado |
| B — Compatibilidad local | Alcanzado |
| C — Comunicación directa | Alcanzado |
| D — Integración | Alcanzado |
| E — Preparación para edición | No alcanzado |

## 10. Bloqueos técnicos pendientes

- **Escritura remota iOS:** no validada. No se enviará ningún candidato hasta
  disponer de una prueba controlada en dispositivo físico y de un mecanismo de
  restauración verificado.
- **Cuentas solo Apple/Game Center:** requieren un token de identidad de Apple.
  No se ha implementado ese flujo ni se ha solicitado credencial alguna.
- **CRDE:** su mecanismo interno de obtención iOS sigue siendo desconocido. No
  se usa como dependencia.
- **Semántica de campos iOS:** la estructura coincide, pero la persistencia y
  el efecto en el cliente iOS no están confirmados.
- **Partida local plist:** existe una vía offline documentada
  (`com.ChillyRoom.DungeonShooter.plist`), aún no implementada como importador.

## 11. Pasos para el propietario en un dispositivo iOS físico

1. Confirmar si la cuenta del juego usa **correo ChillyRoom**, **Apple ID** o
   **Game Center**. No compartir contraseñas ni códigos 2FA.
2. Verificar en el juego que la versión es 8.8.0.13 y que la nube está activada.
3. Conservar una copia local del plist
   `Library/Preferences/com.ChillyRoom.DungeonShooter.plist` obtenida de un
   respaldo del dispositivo, sin modificarla.
4. Comparar los valores visibles en el juego (gemas, fichas, un personaje y una
   mascota) con el informe de SK-Under para confirmar la lectura.
5. Para una futura prueba de escritura: usar una cuenta secundaria o un
   respaldo restaurable, aplicar un solo campo de bajo riesgo en una copia
   local, subir solo tras validar el respaldo y comprobar el resultado en el
   juego. No hacerlo todavía con la cuenta principal.
6. Si la cuenta es solo Apple, probar el inicio de sesión oficial en el
   dispositivo y registrar únicamente el resultado (éxito/error), nunca el
   token.

## 12. Propuesta para la Fase 10.1

1. **Importador plist iOS:** leer el plist local y normalizarlo al mismo
   documento que usa el editor, sin tocar el archivo original.
2. **Candidatos locales iOS:** implementar una escritura en seco (dry-run) para
   un conjunto mínimo y reversible, con diferencia byte a byte y sin subida.
3. **Validación física:** probar primero lectura y después un único candidato
   de bajo riesgo en un dispositivo iOS, con respaldo y restauración.
4. **Escritura remota experimental:** solo tras la validación física, detrás de
   dos banderas independientes, con respaldo obligatorio, confirmación
   autenticada y verificación posterior.
5. **Apple/Game Center:** investigar el flujo oficial de token de identidad sin
   extraer secretos del cliente ni de terceros.
6. **Ampliar semántica:** decoraciones, vestíbulo, planos y progreso, con
   niveles de evidencia específicos de iOS.

## Conclusión

SK-Under ya puede autenticarse contra la cuenta iOS propia, descargar su partida
nativa, interpretarla, mostrar un informe, crear respaldos separados y abrir el
editor en solo lectura. La escritura iOS sigue deliberadamente cerrada hasta
que exista evidencia física y un procedimiento de restauración probado.
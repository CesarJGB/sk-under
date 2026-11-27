# Fase 10.1 — Preparación de candidatos iOS y compuerta de escritura remota

Fecha: 2026-11-26

> **Actualización 2026-11-27:** la Fase 10.2 llegó a subir un guardado iOS real,
> pero el cliente oficial lo rechazó. La causa era el uso de la versión visible
> `8.8.0.13` como versión de protocolo. El análisis y la corrección están en
> [`ios-version-metadata.md`](ios-version-metadata.md). Este documento se
> conserva como registro del estado anterior a esa evidencia.

## Resumen ejecutivo

La fase alcanza el **nivel B** del encargo: la cuenta iOS ya puede descargar,
editar, preparar un candidato validado y crear un respaldo cifrado desde el
mismo editor web que Android. La **subida remota iOS sigue bloqueada** con el
estado `write_pending_validation`.

No se ha enviado ninguna escritura a la nube. No hay evidencia propia de que
`BlobSave/Upload` acepte y persista un candidato iOS, y la semejanza estructural
con Android no se considera prueba. El **nivel D no se declara alcanzado**.

La decisión se expone en una matriz única por plataforma y función con cuatro
estados: `read_only`, `write_pending_validation`, `write_experimental` y
`write_verified`. Android conserva `write_verified`; iOS queda en
`write_pending_validation` para subida y restauración.

## 1. Hallazgos de investigación

### Fuentes oficiales

- `https://soulknight.chillyroom.com/et/article/base/5` — manual de nube para
  iOS: dos formas de acceso, **cuenta Apple o cuenta ChillyRoom**; la nube se
  gestiona desde el cliente con **Retrieve Progress** y **Upload Progress**.
- `https://soulknight.chillyroom.com/et/article/base/3` — manual Android: el
  mismo sistema de cuenta, con Google o ChillyRoom, y el mismo flujo manual.
- `https://soulknight.chillyroom.com/et/article/base/4` — límites de
  vinculación de dispositivos y motivos de rechazo.
- `https://github.com/HTCheater/SKDEditor` — editor de terceros. Su README
  afirma soporte para cualquier plataforma, pero no se encontró código de
  subida ni una implementación iOS verificable en el clon local. Es evidencia
  de viabilidad de terceros, no una validación propia.
- `https://crde.pages.dev/` y la auditoría local de CRDE — CRDE edita cuentas
  iOS mediante su propio backend. El cliente público solo llama a
  `PUT /api/accounts/{id}/raw` de CRDE; eso demuestra el endpoint de CRDE, no un
  contrato público de escritura de ChillyRoom. La auditoría mantiene el
  mecanismo real como **NO DETERMINADO**.
- `https://www.youtube.com/watch?v=-453BBMwHko` — el video se conserva como
  referencia de experiencia de usuario. No se pudo obtener una transcripción
  textual y no se usa como evidencia técnica ni como dependencia.

### Contrato de escritura

No se encontró documentación pública de un endpoint HTTP de subida iOS. La
documentación oficial describe la subida **desde el cliente del juego**, no una
API para terceros. El transporte `BlobSave` y el sobre completo son compartidos,
pero compartir transporte no demuestra autorización, aceptación ni persistencia.

### Límite operativo de dispositivos

El artículo oficial de limitaciones establece:

- hasta **5 dispositivos vinculados por cuenta cada 90 días**;
- al menos **24 horas entre dos vinculaciones**;
- una oportunidad se consume al iniciar sesión en un dispositivo nuevo y
  **subir o descargar** progreso;
- restablecer el dispositivo o cambiar de cuenta también puede consumir una
  oportunidad;
- un dispositivo solo puede estar vinculado a una cuenta a la vez;
- si se agotan las 5 oportunidades, hay que esperar al ciclo de 90 días.

Una identidad de instalación generada por SK-Under puede comportarse como un
dispositivo nuevo. Por tanto, iniciar sesión y descargar repetidamente con
identidades distintas puede consumir oportunidades reales del propietario. La
interfaz reutiliza el perfil conocido cuando existe, pero esta restricción debe
tenerse en cuenta antes de cualquier prueba.

### Riesgo de cuenta

La documentación oficial indica que las cuentas que participan en trampas o
modificaciones pueden ser **bloqueadas permanentemente**. SK-Under no elude
controles ni automatiza compras, pero la edición de progreso sigue siendo una
operación sensible. Cualquier prueba debe hacerse con una cuenta autorizada,
preferiblemente secundaria y restaurable, y con confirmación explícita.

## 2. Evidencia sobre Apple ID

| Afirmación | Evidencia | Conclusión |
| --- | --- | --- |
| Apple ID es obligatorio para iOS | La documentación oficial ofrece **cuenta Apple o cuenta ChillyRoom** | Falso como regla general |
| Una cuenta ChillyRoom vinculada por correo necesita Apple ID | Login y descarga iOS propios verificados en la Fase 10.0 con correo/contraseña y sin tokens de Apple | No lo necesita para esta ruta |
| Game Center es necesario para la nube | Solo se exige en la ruta de acceso con Apple ID, junto con iCloud | No es un requisito universal |
| Restaurar compras autentica la nube | La documentación separa la vinculación de compras del guardado en la nube | Son mecanismos distintos |
| Una cuenta solo Apple/Game Center puede usarse igual | Requiere el token de identidad emitido por el flujo oficial de Apple; no está implementado | Bloqueo específico, no regla general |

La ruta verificada es la cuenta ChillyRoom con correo y contraseña. No se han
fabricado tokens de Apple ni se ha suplantado identidad. Una cuenta que solo
use Apple ID o Game Center queda fuera del flujo actual y necesita el mecanismo
oficial de identidad, que no se ha implementado.

## 3. Diferencias reales de escritura Android/iOS

| Aspecto | Android | iOS | Estado |
| --- | --- | --- | --- |
| Gateway y `BlobSave` | Compartidos | Compartidos | Observado |
| Selección de partida | Distro Android | Distro iOS | Verificado en lectura |
| Identidad de plataforma | UUID de distribución | `platformId: "IOS"` | Verificado |
| `cloudSaveId` | Prefijo `GP_`/`GPV2_` | Prefijo `IOS_` | Verificado |
| Estructura del documento | 13 secciones + `gameData` en 8.8.0 | Las mismas secciones | Verificado en la muestra |
| Serialización | `serialzedVersion: 1` | `serialzedVersion: 1` | Compartida |
| Autenticación | Correo/Google según cuenta | Correo/Apple según cuenta | Documentado |
| Subida remota | Validada por SK-Under | Sin evidencia propia | Pendiente |
| Restauración remota | Validada por SK-Under | Sin evidencia propia | Pendiente |

La diferencia práctica confirmada no es el esquema del guardado, sino la
**identidad de plataforma, el canal de acceso y el estado de validación de la
escritura**. No se encontró un campo de juego exclusivo de iOS en la muestra
8.8.0. Las diferencias de `gameVersion` y `AppVersion` corresponden a versión y
compilación, no a una estructura divergente.

CRDE demuestra que la edición iOS es posible en principio, pero su mecanismo
está encapsulado y no se ha reproducido. No se usa como dependencia.

## 4. Estado de autorización de escritura

| Comprobación | Resultado |
| --- | --- |
| Sesión iOS válida | Verificada en Fase 10.0 |
| Descarga iOS | Verificada; HTTP 200 no se usa como prueba de escritura |
| Permiso de escritura del perfil | El perfil puede autorizarlo, pero la plataforma lo bloquea |
| Formato candidato preparado | Validado localmente contra el editor y el documento original |
| Aceptación de `BlobSave/Upload` para iOS | **No probada** |
| Persistencia remota iOS | **No probada** |
| Restauración iOS | **No probada** |

No se realizó ninguna subida porque no había una sesión iOS autorizada
disponible en el entorno de desarrollo y porque no existe evidencia de
persistencia. Un HTTP 200 de subida tampoco se aceptaría como éxito: la
verificación exigiría descargar de nuevo, comparar tamaño y SHA-256 con el
candidato y comprobar el efecto en el cliente.

Antes de habilitar `write_experimental` o `write_verified` para iOS se exige:

1. cuenta autorizada, preferiblemente secundaria y restaurable;
2. respaldo completo previo y verificado;
3. confirmación explícita del propietario;
4. un único campo de bajo riesgo;
5. detección de cambios remotos antes de subir;
6. descarga posterior y comparación de bytes;
7. comprobación del valor en el cliente iOS;
8. restauración probada y registrada.

## 5. Compatibilidad y round-trip

La referencia sigue siendo la muestra nativa iOS de la Fase 10.0, no una
exportación transformada de CRDE. La exportación de CRDE elimina metadatos y
convierte enteros grandes en cadenas; no sirve para decidir el formato nativo.

Comprobaciones de esta fase:

- el documento iOS conserva `platformId`, `cloudSaveId`, `serialzedVersion`,
  `gameVersion`, `AppVersion`, secciones y campos desconocidos;
- una edición de gemas modifica `gameData.gems` y su contrapeso de consistencia
  `gameData.varGems`, y **ninguna otra ruta**;
- los campos desconocidos de prueba (`futureSection`, `gameData.futureField`) se
  conservan intactos;
- el respaldo guarda el SHA-256 original y el candidato tiene su propio SHA-256;
- el proveedor simulado conserva los bytes originales; no se envió nada.

La preparación valida el candidato, pero **no demuestra que iOS lo acepte ni que
el juego lo conserve**. Esa distinción se mantiene en la matriz y en la
interfaz.

## 6. Matriz de capacidades

Estados posibles: `read_only`, `write_pending_validation`,
`write_experimental`, `write_verified`.

| Función | Android | iOS |
| --- | --- | --- |
| Autenticación | `read_only` | `read_only` |
| Descarga | `read_only` | `read_only` |
| Respaldos | `read_only` | `read_only` |
| Preparación de cambios | `read_only` | `read_only` |
| Verificación | `read_only` | `read_only` |
| Subida | `write_verified` | `write_pending_validation` |
| Restauración remota | `write_verified` | `write_pending_validation` |

`read_only` significa que la operación no escribe en la nube; no significa que
la cuenta no pueda editar un candidato local. La matriz describe la capacidad
de la plataforma, no los permisos de una cuenta concreta: el servicio sigue
aplicando el interruptor global, la autorización del perfil y la preparación de
la instalación.

Una plataforma desconocida se degrada a `read_only`, sin preparación y sin
escritura. No hereda Android.

## 7. Cambios de backend

- `backend/app/cloud/capabilities.py`: matriz única, estados explícitos,
  funciones por plataforma, motivo, evidencia y requisitos de confirmación.
- `backend/app/cloud/lab_service.py`: el estado del laboratorio incluye
  `platform`, `prepare_ready`, `write_state` y `capabilities`; la subida y la
  restauración pasan por una compuerta que distingue “pendiente de validación”
  de “deshabilitado”. Las operaciones de preparación siguen siendo neutrales.
- `backend/app/native/errors.py`: `native_write_pending_validation` (HTTP 409),
  distinto de una denegación de permisos.
- `backend/app/native/service.py`: la vista de sesión y cuenta expone
  `prepare_ready`, `write_state` y la matriz; `_lab` solo construye uploader si
  la plataforma permite escribir; `_require_write` bloquea iOS antes de mirar
  los demás permisos. Preparar, descargar, respaldar y verificar siguen
  disponibles.
- `backend/app/api/cloud_lab.py` y `backend/app/models.py`: contrato HTTP 409 y
  campos nuevos del estado.
- `backend/app/version.py`: capacidades `ios_candidate_preparation`,
  `ios_remote_write_pending_validation` y `platform_capability_matrix`.
- No se añadieron campos de guardado, categorías ni entradas al registro de 66
  campos. No se implementó el importador plist.

## 8. Cambios de frontend y funciones disponibles

- `EditorWorkspace` separa **editar/preparar** de **subir**. En iOS permite
  editar y preparar, muestra “Revisar candidato”, el respaldo y el SHA del
  candidato, y deshabilita la confirmación y la subida. En Android conserva
  “Guardar en la nube” y su confirmación.
- Si una sesión Android tiene la escritura deshabilitada, sigue siendo de solo
  lectura: la habilitación de preparación no se extiende fuera del estado iOS
  pendiente.
- Partida y el selector de distribución explican que iOS permite descarga,
  respaldos y preparación, pero la subida está pendiente.
- Nuevos mensajes para `native_write_pending_validation` y
  `cloud_write_pending_validation`.
- Se mantiene el diseño, el editor rápido inicial, las categorías, el historial,
  los temas y la adaptación móvil. No hay pantalla de importación local ni un
  editor iOS separado.

Funciones visibles en la web para iOS:

- iniciar sesión con una cuenta ChillyRoom vinculada por correo;
- descargar e interpretar la partida;
- editar el borrador global y preparar un candidato;
- crear y consultar respaldos;
- revisar el candidato y su SHA;
- **no** subir, **no** restaurar remotamente y **no** confirmar una escritura.

## 9. Pruebas

- Backend: **765 pruebas superadas, 16 omitidas**.
- Nuevas pruebas de la fase: matriz de estados, degradación de plataforma
  desconocida, preparación iOS con respaldo, round-trip sin cambios secundarios,
  bloqueo de subida y restauración, sesión nativa iOS preparable, HTTP 409 y
  vista con capacidades.
- Frontend: `npm run build` correcto; bundle
  `dist/assets/index-Bfs3wYeN.js` y CSS `index-BS9YUA0E.css`.
- Playwright: **99 superadas, 22 omitidas**. Las omitidas son pruebas ya
  marcadas como `fixme`, no fallos nuevos.
- La prueba iOS prepara un candidato, comprueba que no se llama a `confirm` y
  que la subida aparece deshabilitada.
- Capturas revisadas a 320, 360, 375, 390, 430, 768 y 1280 px; sin
  desbordamiento horizontal ni oclusión de la barra inferior.
- No hay prueba de escritura iOS real: no había sesión autorizada ni evidencia
  de persistencia.

## 10. Despliegue

La Fase 10.0 dejó una inconsistencia: el backend de producción estaba en
`71f4afb`, pero Cloudflare Pages seguía sirviendo el bundle anterior
`index-DSBy5HYG.js`. El bundle local de esta fase es `index-Bfs3wYeN.js`.

Tras publicar el commit `065852c` se activó el hook de despliegue de Pages.
Producción pasó a servir `index-BqVkX8lW.js` con el CSS `index-BS9YUA0E.css`.
El hash difiere del build local porque Pages inyecta su propio entorno de
compilación, pero el bundle público contiene las cadenas nuevas
`Preparar candidato`, `Subida pendiente de validación` y
`write_pending_validation`; por tanto es la interfaz de esta fase, no el bundle
antiguo.

El backend de producción pasó a `065852c74e86c3bf9a80e22e84ec774036ff3ecb`,
`api_version` `2026.11.26`, con `ios_candidate_preparation`,
`ios_remote_write_pending_validation` y `platform_capability_matrix`. El
despliegue automático de Coolify funcionó. El hook de Pages sigue siendo el
mecanismo de recuperación si la integración Git vuelve a quedarse atrás.

## 11. Nivel alcanzado y bloqueos

| Nivel | Estado |
| --- | --- |
| A — Investigación | Alcanzado |
| B — Preparación iOS en la infraestructura web | Alcanzado |
| C — Mecanismo remoto autorizado identificado y validado | No alcanzado |
| D — Escritura remota integrada con respaldo y verificación | No alcanzado |
| E — Confirmación en iPhone físico | No alcanzado |

Bloqueos concretos:

1. **Sin sesión iOS autorizada en el entorno:** no hay credenciales ni sesión
   iOS viva disponibles. No se fabrican tokens ni se extraen secretos.
2. **Sin evidencia de aceptación/persistencia:** no se ha probado
   `BlobSave/Upload` con iOS; un 200 no bastaría.
3. **Límite de dispositivos:** cada identidad nueva y cada descarga/subida puede
   consumir una de las 5 oportunidades por 90 días.
4. **Cuentas solo Apple/Game Center:** necesitan el token de identidad del flujo
   oficial, no implementado.
5. **CRDE:** su mecanismo iOS no es público; no se usa como dependencia.
6. **Semántica iOS:** la estructura coincide, pero el efecto en el cliente no
   está confirmado.

## 12. Pasos mínimos para el propietario desde iPhone

1. Confirmar que la cuenta es ChillyRoom por correo o solo Apple/Game Center.
   No compartir contraseña, códigos 2FA ni tokens.
2. Verificar en el juego la versión 8.8.0.13 y que la nube esté activa.
3. Iniciar sesión en SK-Under con la cuenta iOS y comprobar que la descarga y el
   informe coinciden con los valores visibles en el juego.
4. Crear un respaldo manual y conservarlo.
5. Para una futura prueba, usar una cuenta secundaria o restaurable y autorizar
   **un solo campo de bajo riesgo**. No hacerlo aún con la cuenta principal.
6. Tras una eventual subida autorizada, descargar de nuevo, comparar SHA-256 y
   comprobar el valor en el juego; después probar la restauración.
7. Si la cuenta es solo Apple, probar el acceso oficial en el dispositivo y
   registrar únicamente éxito o error, nunca el token.

## Conclusión

SK-Under ya ofrece a iOS la misma experiencia de edición y preparación que
Android, con respaldos aislados y una explicación clara de lo que falta. La
subida remota no se habilita por parecido estructural: queda pendiente de una
prueba autorizada que demuestre aceptación y persistencia. Esa es la frontera
técnica real de esta fase.
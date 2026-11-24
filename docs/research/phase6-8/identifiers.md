# Identificadores observados: autenticación, instalación y guardado

**Estado:** documento de investigación, sin cambios de producción. **Alcance:** Soul Knight 8.8.0 Android Global y el contrato ejercitado en las fases 5.7 a 6.7. **Corte de evidencia:** 24 de noviembre de 2026.

Este documento no ejecuta tráfico nuevo ni pruebas reales. Ordena lo que el repositorio ya demuestra y separa explícitamente la evidencia de la hipótesis. No contiene correos, UID, `player.id`, tokens, `distro_id`, `unique_id` ni valores en claro. Los únicos hashes citados son los ya publicados en [`evidence.json`](../phase6-7/evidence.json).

Convención de lectura:

- **[C] Comprobado:** observado en una ejecución o en el código del repositorio, con el alcance indicado.
- **[H] Hipótesis plausible:** encaja con la evidencia, pero no se ha aislado la causa ni se ha probado fuera del caso observado.
- **[?] Desconocido:** no hay evidencia suficiente; no debe presentarse como hecho.

## 1. Método y fuentes

Se revisaron, entre otros, [`phase6-7/README.md`](../phase6-7/README.md), [`integration.md`](../phase6-7/integration.md) y [`evidence.json`](../phase6-7/evidence.json); [`native_auth.py`](../../../experiments/phase6-7/native_auth.py); [`phase5/autenticacion.md`](../phase5/autenticacion.md) y [`reconstruccion.md`](../phase5/reconstruccion.md); [`phase5-5/save-schema-880.md`](../phase5-5/save-schema-880.md); [`phase5-6/local-bridge.md`](../phase5-6/local-bridge.md) y [`schema-compatibility.md`](../phase5-6/schema-compatibility.md); [`phase5-9/protocol.md`](../phase5-9/protocol.md) y [`phase6-1/protocol.md`](../phase6-1/protocol.md); [`phase6-3/README.md`](../phase6-3/README.md) y [`phase6-4/authentication.md`](../phase6-4/authentication.md); y el código [`blob_wire.py`](../../../backend/app/cloud/blob_wire.py), [`accounts.py`](../../../backend/app/cloud/accounts.py) y [`cloud_save.py`](../../../backend/app/cloud_save.py).

También se buscaron referencias cruzadas en `docs/` y `backend/` para `x-distro-id`, `x-unique-id`, `platformId`, `cloudSaveId`, `ChillyUid`, `_crde_misc` y `crde`. La única familia sin ninguna aparición en ese corpus fue `_crde_misc`; se trata en la sección 6.

La terminología de este documento distingue cuatro cosas que el uso coloquial mezcla: **identificador** (valor que nombra algo), **atributo de identidad** (dato que permite vincular una cuenta), **credencial** (valor que concede acceso) y **secreto** (valor cuya revelación facilita abuso). Un identificador puede ser sensible sin ser una credencial.

## 2. Tabla comparativa

| Identificador | Qué es según la evidencia | Entidad | Estabilidad observada | Origen observado | Dónde se observó | Qué no se ha demostrado |
| --- | --- | --- | --- | --- | --- | --- |
| `x-distro-id` | Cabecera HTTP de contexto de distribución/instalación, obligatoria para el login observado. El gateway la valida. | Distribución / instalación | Estable para la instalación de laboratorio durante la fase; vida útil no medida. | No determinado. El cliente la conserva en `LastLoginHostWithDistroId`; el gateway la acepta o rechaza. | Cabecera de `UserAuth/Login`; también en `BlobSave/Download` y `BlobSave/Upload`. | Que sea única por instalación, que sea compartida por usuarios de la misma versión, que sea un secreto, o que baste como credencial. |
| `x-unique-id` | Cabecera HTTP de identificación de instalación. No es necesaria para el login, pero BlobSave la exige y rechaza un valor nuevo. | Instalación | Estable para la instalación de laboratorio; no se probó reinstalación ni cambio de dispositivo. | Originada en el cliente; el análisis estático la deriva de `CloudSaveUtil.mac` mediante `RefreshUniqueId`. El servidor la valida. | Cabeceras de login y BlobSave; extraída de una instalación autorizada. | Que sea el mismo valor que `ChillyUid`, `platformId` o `distro_id`; que sea un secreto; que pueda generarse de forma arbitraria. |
| `platformId` | Campo de texto obligatorio del agregado `CloudSaveGameData`, junto a `cloudSaveId`. Identifica la plataforma/canal del guardado. | Guardado | Desconocida: no se comparó entre dos descargas separadas. | Se observa en el agregado que produce el cliente; el punto exacto de asignación no se identificó. El servicio lo devuelve dentro del agregado. | Agregado `CloudSaveGameData`; validado por `reconstruct_cloud_save`; usado por `accounts._subject`. | Que sea igual a `x-distro-id`, a `x-unique-id` o a un identificador de cuenta; que sea estable entre plataformas. |
| `cloudSaveId` | Campo de texto obligatorio del agregado; identidad de la copia de guardado. Se usa junto con `platformId` para derivar el sujeto de cuenta. | Guardado | Desconocida; no se midió entre sesiones ni tras una migración. | Se observa en el agregado que produce el cliente; el punto exacto de asignación no se identificó. | Agregado `CloudSaveGameData`; validador y `accounts._subject`. | Que sea igual a `uid`, `player.id`, `pf_id` o al identificador local; que sea inmutable. |
| `ChillyUid` | Campo `string` de `SettingData`; aparece en `setting_*.data`. El puente local lo protege y no lo publica. | Instalación / ajustes locales (interpretación tentativa) | Desconocida: no se comparó entre copias, reinstalaciones ni cuentas. | Cliente local; no se observó emisión por el gateway. | `setting_*.data` 8.8.0; metadata de `SettingData` (`0x04005b76`). | Que sea el mismo valor que `x-unique-id`; que autentique; que sea estable o transferible entre cuentas. |
| `player.id` | Valor numérico del objeto `player` de la respuesta de login; el cliente lo normaliza a entero. La fase 6.7 lo comparó con la cuenta de laboratorio. | Cuenta / jugador | Coherente en la ejecución; estabilidad entre sesiones no medida. | Gateway de autenticación. | Respuesta de `UserAuth/Login`; resumen saneado en `evidence.json`. | Que sea igual a `session.uid` o `user.id`; que sea suficiente por sí solo para probar titularidad. |
| `session.uid` | Valor numérico del objeto `session` de la respuesta de login. En la ejecución observada coincidió con `user.id`. | Cuenta / sesión | Igual a `user.id` en la ejecución; no se midió entre sesiones. | Gateway de autenticación. | Respuesta de login; comprobación `session.uid == user.id`. | Que sea un identificador estable de cuenta en todos los canales; que sea el mismo que `player.id`. |
| `user.id` | Valor numérico del objeto `user` de la respuesta de login; identidad de la cuenta autenticada. | Cuenta | Coherente en la ejecución; no se midió su rotación. | Gateway de autenticación. | Respuesta de login; comparación con `session.uid`. | Que el correo sea una clave única de cuenta; que `user.id` sea igual a `player.id`. |
| `token` de sesión | Credencial opaca de 32 caracteres usada como `Authorization: Bearer`. Caduca aproximadamente a los siete días. | Sesión | Cambia en cada login observado; dos ejecuciones dieron hashes distintos. | Gateway de autenticación. | Respuesta de login; cabecera Bearer de BlobSave; nunca en la respuesta al navegador en el diseño propuesto. | Que sea un identificador de cuenta; que su renovación o revocación funcionen como se supone; que el `legacyGateway.token` sea equivalente. |

`cloudSaveId` se incluye como fila complementaria porque forma pareja con `platformId`; la lista mínima solicitada no lo exigía, pero sin él no se entiende la identidad de guardado ni el sujeto de cuenta del backend.

## 3. Lectura por identificador

### 3.1 `x-distro-id`

**[C]** Es una cabecera HTTP necesaria para el login observado. Sin ella, el gateway devolvió `502` con `errorCode=10003`; con un UUID aleatorio devolvió `400` con el mismo código; con el valor de la instalación de laboratorio devolvió `200` y una sesión nueva. El valor se aporta por separado y se obtuvo de la instalación oficial; no se observó derivación del correo ni de la contraseña. Se conserva en el cliente en `LastLoginHostWithDistroId` como parte de un `host_uuid` codificado en base64 ([`authentic-cloud-read.md`](../phase5-7/authentic-cloud-read.md)).

**[H]** Parece un identificador de registro de instalación o de último login; una constante de versión validada también es posible. El portal oficial describió un UUID de registro y otro de último login ([`cloud-save-acquisition.md`](../phase5-7/cloud-save-acquisition.md)); no se demostró cuál de ellos, si alguno, es exactamente el enviado en la cabecera, ni que sus valores sean distintos entre sí. La diferencia entre `502` y `400` sugiere etapas de validación distintas, pero el código de aplicación es el mismo y no se aisló su significado.

**[?]** Se desconoce su vida útil, si cambia al reinstalar o actualizar, si es por cuenta, por dispositivo o por canal, y si el mismo valor funciona con otra cuenta. Tampoco se sabe si el gateway lo contrasta contra un registro de la cuenta o contra una lista de distribuciones admitidas.

### 3.2 `x-unique-id`

**[C]** Es una cabecera de instalación. El login funcionó sin ella (`200`), pero BlobSave rechazó la descarga con un identificador nuevo de laboratorio (`400`) y aceptó el de la instalación autorizada. El análisis estático de `RefreshUniqueId` indica que se deriva de `CloudSaveUtil.mac` ([`phase5-9/protocol.md`](../phase5-9/protocol.md)); la hipótesis de que intervengan el canal y el Android ID no se confirmó.

**[H]** El servidor la vincula a la instalación registrada o a la cuenta, o ambas cosas. Es un identificador de contexto, no una credencial: por sí solo no inicia sesión y no se observó que sustituya al Bearer.

**[?]** No se ha demostrado que sea estable tras reinstalar, que sea único globalmente, que coincida con `ChillyUid` o que pueda regenerarse de forma legítima desde otro dispositivo. Generar valores nuevos para “saltar” la validación no es un experimento aceptable y, además, ya se observó que falla.

### 3.3 `platformId` y `cloudSaveId`

**[C]** Ambos están declarados como `string` en `CloudSaveGameData` 8.8.0: `cloudSaveId` en el token `0x0400577a` y `platformId` en `0x0400577b` ([`save-schema-880.md`](../phase5-5/save-schema-880.md)). El prototipo exige texto no vacío para los dos y conserva el resto del agregado ([`cloud_save.py`](../../../backend/app/cloud_save.py)). `accounts._subject` deriva el sujeto de cuenta con un HMAC de `[cloudSaveId, platformId]` y verifica ese sujeto en cada descarga ([`accounts.py`](../../../backend/app/cloud/accounts.py)).

**[H]** `platformId` describe la plataforma o el canal del guardado; `cloudSaveId` describe la copia o la cuenta de guardado. La fase 5 documenta que `GetCurrentAccountSaveId` consulta `pf_id` y `uid`, y que el cliente compara el identificador local con el de la cuenta; eso no demuestra una igualdad entre esos valores y los campos del agregado ([`autenticacion.md`](../phase5/autenticacion.md)).

**[?]** No se midió su estabilidad entre dos descargas, entre dos sesiones, entre canales ni tras una migración. Tampoco se demostró que `cloudSaveId` o `platformId` sean iguales a `uid`, `player.id`, `x-distro-id`, `x-unique-id` o `ChillyUid`. Son candidatos a identidad de guardado, no a credencial.

### 3.4 `ChillyUid`

**[C]** Es un campo `string` de `SettingData` (typeDef 3146, token `0x04005b76`) y aparece en `setting_*.data` 8.8.0, que tiene 35 claves observadas, entre ellas `ChillyUid` ([`schema-compatibility.md`](../phase5-6/schema-compatibility.md)). El puente local lo marca como protegido: `PROTECTED_TOP_LEVEL` incluye `ChillyUid`, `cloudSaveId` y `platformId`, y la edición de laboratorio no lo modifica ([`local_save.py`](../../../backend/app/local_save.py)).

**[H]** Es un identificador local ligado a la cuenta o al perfil de ajustes; su presencia en `SettingData` sugiere que el cliente lo usa para distinguir configuraciones. No hay evidencia de que lo emita el gateway ni de que se envíe como credencial.

**[?]** No se demostró que sea igual a `x-unique-id` ni a ningún otro identificador de la tabla. Tampoco que sea estable entre dispositivos, que se pueda copiar entre cuentas o que autentique. La etiqueta “PlayerPrefs” del enunciado no se confirma en el repositorio: en `shared_prefs` se observaron las claves de caché del SDK (`SdkUserCacheV2`, `SdkSessionCacheV2`, `LastLoginHostWithDistroId`), pero no se observó una clave `ChillyUid`; la observación directa de `ChillyUid` es en `setting_*.data`.

### 3.5 `player.id`, `session.uid` y `user.id`

**[C]** En la respuesta de login de la fase 6.7, `session.uid` y `user.id` fueron valores numéricos y coincidieron; `player.id` fue otro valor numérico y coincidió con la cuenta de laboratorio ([`README.md`](../phase6-7/README.md)). `native_auth.py` normaliza los tres a entero, exige que `session.uid == user.id` y que el correo devuelto coincida con el solicitado; no exige que `player.id` sea igual a ninguno de los dos.

**[H]** `user.id` y `session.uid` identifican la cuenta autenticada; `player.id` identifica el perfil de jugador de esa cuenta. El modelo del SDK declara `User.Id` y `User.PlayerId` como campos distintos ([`autenticacion.md`](../phase5/autenticacion.md)); eso apoya la distinción, pero no fija su semántica JSON.

**[?]** No se probó la estabilidad de `player.id` entre sesiones, canales o versiones, ni que `player.id` sea único globalmente. El correo no es una clave de cuenta: la documentación oficial citada en las fases previas advierte que Google y ChillyRoom pueden ser identidades distintas aunque compartan correo. Por eso `user.email` sirve como comprobación adicional, no como prueba única de titularidad.

### 3.6 Token de sesión

**[C]** Es una cadena opaca de 32 caracteres, emitida por el gateway, con `expire` futuro (aproximadamente siete días). Se usa como `Authorization: Bearer` en BlobSave. Dos logins reales produjeron hashes distintos (`a8004db6…` y `6bf0f95e…`, publicados en `evidence.json`), y el token de la sesión Linux fue distinto del de Android. `native_auth.Session.summary()` lo reduce a SHA-256 en los resúmenes ([`native_auth.py`](../../../experiments/phase6-7/native_auth.py)).

**[C]** El token no es un identificador de cuenta: la respuesta trae además `uid`, `user.id` y `player.id`. El `legacyGateway.token` es otro valor, con otro host; no se demostró que sea equivalente ni que sirva para las mismas rutas.

**[?]** No se verificó un endpoint de renovación aceptado, la revocación remota ni la semántica de `x-request-token`, que el cliente puede añadir pero que no fue necesario en las subidas observadas ([`phase6-1/protocol.md`](../phase6-1/protocol.md)). Un token caducado o revocado no debe confundirse con un identificador inválido.

## 4. Cuatro planos de identidad

| Plano | Identificadores implicados | Función | ¿Prueba de titularidad por sí solo? | Reutilización entre cuentas |
| --- | --- | --- | --- | --- |
| Autenticación | `user.id`, `session.uid`, `player.id`, `user.email` | Establecer qué cuenta y qué jugador responden. | No. El correo puede no ser único entre canales; `player.id` requiere contexto. | Prohibida. Cada cuenta conserva su propia identidad. |
| Instalación | `x-distro-id`, `x-unique-id` | Contextualizar la instalación/distribución ante el gateway y BlobSave. | No. Son contexto, no credenciales. | Prohibida sin autorización; no se demostró que sean transferibles. |
| Guardado | `cloudSaveId`, `platformId` | Identificar el agregado y vincularlo a una cuenta de guardado. | No. Se pueden copiar con el agregado; el backend local verifica la pertenencia y la política del servidor no se aisló. | Prohibida; el sujeto se deriva con HMAC y se verifica. |
| Sesión | `token` (Bearer), `legacyGateway.token`, cookie del navegador | Conceder acceso temporal. | No; una sesión válida demuestra acceso, no titularidad permanente. | Prohibida; una sesión por cuenta y por contexto. |

La distinción importante es que **`x-distro-id` no es el identificador de la cuenta**. La fase 6.7 demuestra que el gateway lo exige y lo valida para el login, pero no que ese valor pertenezca a la cuenta en el mismo sentido que `uid` o `player.id`. Tampoco es una API key: el login sigue necesitando correo y contraseña, y BlobSave sigue necesitando el Bearer.

Del mismo modo, `platformId` no es `x-distro-id`: el primero vive dentro del agregado de guardado y se valida como campo del documento; el segundo es una cabecera de transporte. Que ambos sean texto y puedan parecer UUID no autoriza a intercambiarlos.

La segunda parte de la hipótesis, “otros identificadores podrían ser de cuenta o instalación”, es compatible con esta separación: `user.id`, `session.uid` y `player.id` apuntan a la cuenta o al jugador; `x-unique-id` apunta a la instalación; `cloudSaveId` y `platformId` apuntan al guardado. Lo que no está demostrado es que alguno de esos planos pueda sustituir a otro, ni que `x-distro-id` sea el eslabón que une todos los planos.

## 5. La hipótesis del propietario sobre `x-distro-id`

La hipótesis es: “el identificador de distribución podría ser compartido por usuarios de la misma versión del juego; otros identificadores podrían ser de cuenta o instalación”.

### 5.1 Lo que la Fase 6.7 probó

| Experimento | Resultado observado | Lectura acotada |
| --- | --- | --- |
| Login sin `x-distro-id` | `502` / `errorCode=10003` | La cabecera es necesaria en el contrato observado; el `502` no prueba por sí solo una política de autorización. |
| Login con UUID aleatorio | `400` / `errorCode=10003` | El servidor no acepta un valor arbitrario; valida el valor o su registro. |
| Login con el valor de la instalación de laboratorio | `200`, sesión nueva | Ese valor concreto es aceptado para esa cuenta e instalación. |
| Login sin `x-unique-id` | `200` | `x-unique-id` no es necesaria para el login. |
| Descarga con un `unique_id` nuevo | `400` | BlobSave exige un identificador de instalación válido; no acepta uno nuevo. |

### 5.2 Lo que no probó

No probó que el valor sea **compartido por todos los usuarios de la misma versión**. Un identificador de versión podría estar en una lista blanca y seguir siendo rechazado si se inventa un UUID; por tanto, el `400` con UUID aleatorio no descarta esa posibilidad. Tampoco probó que sea **único por instalación**: solo se observó una instalación. Ni que sea **por cuenta**: solo se observó una cuenta.

Tampoco se aisló por qué la omisión produce `502` y el valor aleatorio `400`. La diferencia es real y reproducible, pero puede deberse a que el gateway trata de forma distinta una cabecera ausente y una cabecera presente con formato válido pero no registrado, sin que eso identifique el registro consultado.

### 5.3 Modelos compatibles con la evidencia

| Modelo | Predicción | Grado |
| --- | --- | --- |
| Constante de versión/canal, validada contra lista blanca | El mismo valor serviría a muchos usuarios de 8.8.0; un UUID inventado fallaría. | [H] posible, no observada. |
| UUID de registro de instalación, ligado a la cuenta | Cada instalación tendría uno; reinstalar podría cambiarlo; un valor ajeno fallaría. | [H] la más compatible con el portal y con el `400`. |
| UUID de último login de la cuenta | Podría cambiar al iniciar sesión en otro dispositivo; el portal muestra un UUID de último login. | [H] compatible, no aislada. |
| Combinación cuenta + instalación + canal | El valor solo vale para esa relación; no es portable. | [H] la más conservadora para diseñar. |

### 5.4 Veredicto

| Afirmación | Nivel |
| --- | --- |
| `x-distro-id` es obligatoria para el login observado. | [C] |
| El gateway rechaza un UUID aleatorio y acepta el valor de laboratorio. | [C] |
| El valor podría representar una instalación o un registro de distribución; también es posible una constante de versión validada. | [H] |
| El valor es compartido por los usuarios de la misma versión. | [?] No demostrado; el `400` aleatorio no lo descarta si hay lista blanca, pero tampoco lo apoya. |
| El valor es único por instalación. | [?] No medido. |
| El valor es un secreto o una credencial suficiente. | [?] No demostrado; no sustituye correo, contraseña ni Bearer. |

La lectura más defendible es que `x-distro-id` es un **identificador de contexto validado**, probablemente asociado a una instalación o a un registro de distribución de la cuenta. La parte “compartido por usuarios de la misma versión” es la más débil de la hipótesis: no hay ninguna observación con dos usuarios de la misma versión. Para confirmarla haría falta comparar valores de dos instalaciones autorizadas, no reutilizar el de una cuenta en otra.

## 6. `_crde_misc.platformId`: no tratarlo como formato de Soul Knight

`_crde_misc` no aparece en el formato original documentado. No está entre las 18 claves de `CloudSaveGameData` 8.8.0 identificadas en la metadata (`serialzedVersion`, `cloudSaveId`, `platformId`, `gameData` y las secciones), ni en la metadata inventariada, ni en la documentación de las fases 5 a 6.7. Una búsqueda en `docs/` y `backend/` por `_crde_misc` y `crde` no devolvió ocurrencias. La forma del nombre, con prefijo `_` y un contenedor no identificado en el juego, es compatible con metadatos añadidos por una herramienta externa; el origen concreto no está verificado y no debe afirmarse.

**No debe asumirse que `_crde_misc.platformId` sea equivalente a `CloudSaveGameData.platformId` ni a `x-distro-id`.** Las razones son de capa, de procedencia y de confianza:

1. **Capa distinta.** `CloudSaveGameData.platformId` es un campo declarado de nivel superior del agregado (token `0x0400577b`), con tipo `string` y tratamiento propio en el validador. `_crde_misc.platformId`, si existe, sería un campo anidado dentro de un contenedor no reconocido. El parser y el modelo no lo leen como identidad de guardado.
2. **Procedencia distinta.** El `platformId` superior se observa en el agregado que produce el cliente y el servicio lo devuelve dentro de esa copia. Un campo dentro de `_crde_misc` podría haberlo añadido una herramienta al editar, exportar o convertir una copia; no hay firma ni atestación en el agregado que permita saberlo.
3. **Confianza distinta.** `accounts._subject` deriva el sujeto de cuenta de los campos superiores `cloudSaveId` y `platformId`; no lee `_crde_misc`. Un `platformId` anidado no participa en esa vinculación. Si se usara como si participara, se estaría confiando en un campo que el backend nunca validó.
4. **Semántica no demostrada.** Aunque el texto coincidiera con el `platformId` superior o con `x-distro-id`, la igualdad de cadenas no demuestra igualdad de significado. `x-distro-id` es una cabecera validada por el gateway; el campo del agregado es identidad de guardado; el campo externo es, como máximo, metadata de una herramienta.
5. **Preservación no es validación.** `reconstruct_cloud_save` conserva miembros desconocidos en `extra_fields` para no perder datos ([`cloud_save.py`](../../../backend/app/cloud_save.py)). Que `_crde_misc` sobreviva a un roundtrip no significa que el cliente oficial lo acepte ni que forme parte del esquema. Un agregado con esa sección no se ha probado contra el cliente 8.8.0.

En resumen: no se encontró evidencia en el repositorio de que `_crde_misc` forme parte del formato de Soul Knight; no debe tratarse como tal sin una prueba independiente.

Recomendación: tratar `_crde_misc` como datos no confiables de origen desconocido. No usarlo para identidad, no derivar de él sujetos, no publicarlo y no subir una copia modificada con esa sección al servicio oficial sin una prueba controlada y autorizada. Si se investiga, debe hacerse con una muestra de control que no haya pasado por la herramienta externa y comparando claves y valores en local, sin publicar identificadores.

## 7. `ChillyUid`: identificador local, no credencial

`ChillyUid` es un `string` de `SettingData` y aparece en `setting_*.data`. El puente local lo protege explícitamente y no lo publica; el adaptador muestra solo enteros no sensibles ([`schema-compatibility.md`](../phase5-6/schema-compatibility.md), [`local-bridge.md`](../phase5-6/local-bridge.md)). Esa protección es deliberada: el valor no debe editarse a ciegas ni copiarse entre perfiles.

No hay evidencia de que `ChillyUid` sea el mismo valor que `x-unique-id`, `x-distro-id`, `cloudSaveId`, `platformId`, `uid` o `player.id`. Tampoco de que autentique: no se observó como cabecera, como Bearer ni como campo del cuerpo de login. Su presencia en los ajustes locales es compatible con un marcador de cuenta o de perfil, pero la función exacta es desconocida.

La consecuencia práctica es directa: **no se debe reutilizar `ChillyUid` entre cuentas**. Copiar un `setting_*.data` de una cuenta a otra, o inyectar su `ChillyUid` en un perfil distinto, puede mezclar estados locales y no está respaldado por ninguna prueba de que el servidor lo acepte. Si el backend necesita un identificador local para un perfil de instalación, debe obtenerlo por un flujo autorizado y guardarlo cifrado, no reutilizar el de otra cuenta.

## 8. Reutilización, aislamiento y almacenamiento

### 8.1 Matriz de tratamiento

La columna “guardar” es una recomendación de diseño; en el código actual, `CloudAccounts` guarda el sujeto HMAC, el hash del ticket, el hash de la cookie y una tupla cifrada con token, `unique_id` y `distro_id`. No guarda `cloudSaveId` ni `platformId` en claro.

| Identificador | ¿Guardar en backend? | Cifrado / derivación | ¿Mostrar al navegador? | ¿Registrar en claro? | Regla de aislamiento |
| --- | --- | --- | --- | --- | --- |
| `x-distro-id` | Sí, asociado a un perfil de instalación. | AES-SIV; el identificador de perfil es opaco. | No. | No; solo hash si hace falta correlación. | Un perfil por cuenta e instalación; no se comparte entre cuentas ni se usa para elegir cuenta. |
| `x-unique-id` | Sí, en el mismo perfil de instalación. | AES-SIV. | No. | No; solo hash. | Igual que `distro_id`; no se regenera ni se sustituye por uno de otra instalación. |
| `token` de sesión | Solo mientras la sesión esté vigente. | AES-SIV con la cuenta como dato asociado; caducidad explícita. | Nunca; el navegador recibe cookie propia. | Nunca. | Una sesión por cuenta; borrar al desconectar o al caducar; no se comparte entre cuentas. |
| `cloudSaveId` / `platformId` | No en claro; se guarda el sujeto HMAC. | HMAC-SHA-256 con clave y dominio; comparación en cada descarga. | No; solo metadatos y hashes. | No. | El sujeto identifica una cuenta de guardado; una discrepancia rechaza la lectura. |
| `ChillyUid` | Preferible no ingerirlo; si se usa, cifrado. | AES-SIV; nunca como clave de identidad. | No. | No. | No se copia entre cuentas ni se usa para emparejar perfiles. |
| `user.id` / `session.uid` | Solo hash o HMAC para auditoría. | SHA-256/HMAC; no se necesita el valor crudo. | No. | No. | Se vincula a la cuenta verificada; no se usa como identificador público. |
| `player.id` | Solo hash. | SHA-256. | No. | No. | Comprobación adicional; no sustituye a `user.id`. |
| `user.email` | Solo si es imprescindible, cifrado; preferible hash normalizado. | AES-SIV o SHA-256 del correo normalizado. | No. | No. | No se usa como clave única entre canales. |
| Cookie de navegador | Solo su hash. | SHA-256 del valor aleatorio; `HttpOnly`, `Secure`, `SameSite=Strict`. | La cookie en sí, no su hash. | No. | Una cookie por navegador; no se reutiliza como token de ChillyRoom. |
| `legacyGateway.token` | Evitar; si se guarda, cifrado. | AES-SIV; caducidad. | No. | Nunca. | Tratarlo como secreto independiente; no asumir que equivale al token principal. |

La regla general: **el backend puede guardar lo necesario para vincular, pero no necesita guardar identificadores en claro para operar**. Los hashes y HMAC permiten comparar y auditar sin conservar el valor original. El token y los identificadores de instalación son los datos de mayor cuidado; `cloudSaveId`/`platformId` también son pseudónimos de cuenta y no deben registrarse en claro. El navegador puede mostrar etiquetas locales, estado de conexión, metadatos y hashes; no debe recibir ninguno de los valores crudos de la tabla. Ninguno debe aparecer en claro en logs, trazas, métricas ni mensajes de error.

### 8.2 Vinculación con el diseño de la Fase 6.8

El diseño propuesto de la Fase 6.8 (perfiles de instalación aprovisionados por el propietario, binding de identidad y sesión por cuenta) encaja con esta matriz si se respetan cuatro reglas:

1. **Perfil de instalación, no identificador global.** Cada perfil debe representar una relación autorizada entre el propietario, una cuenta y una instalación. Debe guardar `distro_id` y `unique_id` cifrados, la procedencia (cómo se obtuvieron), la fecha de verificación y el consentimiento. No debe existir un “perfil compartido” por versión ni un valor tomado de otra cuenta.
2. **Binding por identidad de guardado y de cuenta.** El sujeto debe derivarse de `cloudSaveId` y `platformId` con HMAC, como ya hace `accounts._subject`, y complementarse con hashes de `user.id`, `session.uid` y `player.id`. La comprobación debe repetirse en cada descarga; un cambio de sujeto o una identidad contradictoria debe rechazar la operación, no “repararse” automáticamente.
3. **Sesión por cuenta, token invisible.** El token se guarda cifrado y asociado a la cuenta; el navegador solo recibe una cookie opaca y metadatos. El cierre de sesión borra el token y el acceso; no se afirma que revoque la sesión del cliente oficial. No debe haber un pool de tokens ni una sesión compartida entre cuentas.
4. **Aprovisionamiento explícito y revocable.** El propietario aporta los identificadores de su propia instalación por un canal privado; el backend no los extrae de terceros, no los genera al azar y no los reutiliza. Si el perfil caduca o se revoca, se solicita uno nuevo. La autorización del proveedor para este uso sigue pendiente y el endpoint debe permanecer deshabilitado mientras no exista.

La matriz también implica que el navegador nunca debe recibir `distro_id`, `unique_id`, `token`, `cloudSaveId`, `platformId` ni `ChillyUid`. La respuesta propuesta en [`integration.md`](../phase6-7/integration.md) ya evita el token y el correo; conviene extender la misma regla a los identificadores de instalación y de guardado.

## 9. Qué falta por comprobar

Ninguno de estos experimentos requiere eludir TLS, la validación de certificado ni el pinning; ninguno propone generar UUID aleatorios para “pasar” validaciones; ninguno reutiliza identificadores de una cuenta en otra; ninguno hace fuerza bruta ni pruebas de carga. Todos requieren una cuenta y una instalación propias, consentimiento del titular y, cuando corresponda, autorización del proveedor.

| Experimento | Pregunta que resolvería | Condición legítima | Límite o riesgo |
| --- | --- | --- | --- |
| Comparar `LastLoginHostWithDistroId` de dos instalaciones autorizadas de la misma versión. | ¿El valor es igual para usuarios distintos de 8.8.0? | Cada instalación con su propia cuenta y su propio consentimiento; comparar solo hashes. | No usar el valor de una cuenta para autenticar otra. |
| Observar el valor antes y después de reinstalar o de iniciar sesión en un dispositivo propio. | ¿Es estable por instalación o cambia por registro/login? | Cliente oficial, cuenta propia, una sola reinstalación planificada. | Consume vinculaciones; la documentación oficial limita a 5 por cuenta cada 90 días y exige 24 horas entre ellas. |
| Verificar si `x-distro-id` cambia al actualizar la versión. | ¿Está atado a la versión, al canal o a la instalación? | Actualización oficial en un dispositivo propio. | No repetir si el proveedor aplica bloqueos o `429`. |
| Confirmar estáticamente `RefreshUniqueId` y `CloudSaveUtil.mac` en el APK propio. | ¿De qué se deriva `x-unique-id`? | Análisis local del APK autorizado, sin modificar el cliente. | No convierte la hipótesis en contrato del servidor. |
| Comparar `cloudSaveId` y `platformId` de dos descargas autorizadas de la misma cuenta. | ¿Son estables entre sesiones? | Descargas de solo lectura, con la sesión del titular. | No publicar valores; comparar hashes. |
| Comparar esos campos entre dos cuentas autorizadas. | ¿Identifican cuentas distintas? | Dos cuentas propias, cada una con su propia sesión. | No cruzar identificadores; no usar la sesión de una para la otra. |
| Probar `platformId` en otro canal o plataforma propia. | ¿Describe el canal o la plataforma? | Instalación y cuenta propias en el canal alternativo. | Requiere autorización y puede consumir vinculaciones. |
| Comparar `ChillyUid` entre dos copias locales de la misma cuenta. | ¿Es estable en el tiempo? | Copias privadas, comparación local. | No editar ni copiar entre cuentas. |
| Comparar `ChillyUid` entre dos cuentas autorizadas. | ¿Es de cuenta o de instalación? | Solo con consentimiento y sin reutilizar el valor. | No demuestra por sí solo que autentique. |
| Reproducir `_crde_misc` con una herramienta externa sobre una copia de control. | ¿De dónde sale esa sección? | Copia local, sin subirla al servicio. | No tratarla como formato oficial; no usarla para identidad. |
| Repetir dos logins de la misma cuenta y comparar `uid`, `player.id`, `expire` y hashes de token. | ¿Qué identidad es estable y qué cambia por sesión? | Cuenta propia, límite de intentos respetado. | No publicar tokens; no automatizar reintentos. |
| Probar una lectura tras la caducidad de la sesión. | ¿Qué error devuelve el servicio y cómo se distingue de un identificador inválido? | Sesión propia caducada, una sola lectura. | No intentar renovar por vías no documentadas. |
| Determinar si `legacyGateway.token` sirve para alguna ruta de lectura. | ¿Es una credencial distinta o un residuo? | Solo lectura, host indicado por la respuesta. | No usarlo para escritura ni asumir equivalencia. |
| Repetir el aislamiento de dos cuentas con dos sesiones reales. | ¿El backend rechaza lecturas cruzadas? | Dos cuentas propias, dos perfiles separados. | No reutilizar `distro_id`, `unique_id` ni token entre perfiles. |

Quedan además pendientes, fuera del alcance de una prueba de identificadores: la autorización de ChillyRoom para el uso de terceros, el mecanismo oficial de aprovisionamiento, la renovación/revocación y el tratamiento de desafíos. Sin esas piezas, cualquier diseño de perfiles de instalación debe permanecer en laboratorio.

## 10. Referencias

Internas:

- [`phase6-7/README.md`](../phase6-7/README.md), [`integration.md`](../phase6-7/integration.md), [`evidence.json`](../phase6-7/evidence.json).
- [`experiments/phase6-7/native_auth.py`](../../../experiments/phase6-7/native_auth.py).
- [`phase5/autenticacion.md`](../phase5/autenticacion.md), [`phase5/reconstruccion.md`](../phase5/reconstruccion.md).
- [`phase5-5/save-schema-880.md`](../phase5-5/save-schema-880.md).
- [`phase5-6/local-bridge.md`](../phase5-6/local-bridge.md), [`phase5-6/schema-compatibility.md`](../phase5-6/schema-compatibility.md).
- [`phase5-7/authentic-cloud-read.md`](../phase5-7/authentic-cloud-read.md), [`phase5-7/cloud-save-acquisition.md`](../phase5-7/cloud-save-acquisition.md).
- [`phase5-9/protocol.md`](../phase5-9/protocol.md), [`phase5-9/download.md`](../phase5-9/download.md).
- [`phase6-1/protocol.md`](../phase6-1/protocol.md), [`phase6-3/README.md`](../phase6-3/README.md), [`phase6-4/authentication.md`](../phase6-4/authentication.md).
- [`backend/app/cloud/blob_wire.py`](../../../backend/app/cloud/blob_wire.py), [`backend/app/cloud/accounts.py`](../../../backend/app/cloud/accounts.py), [`backend/app/cloud_save.py`](../../../backend/app/cloud_save.py), [`backend/app/local_save.py`](../../../backend/app/local_save.py).

Oficiales, citadas en las fases previas y no verificadas de nuevo aquí:

- [Manual de Soul Knight para Android](https://soulknight.chillyroom.com/et/article/base/3).
- [Límites de guardado en la nube](https://soulknight.chillyroom.com/et/article/base/4).
- [Preguntas frecuentes de Soul Knight](https://soulknight.chillyroom.com/et/article/base/6).

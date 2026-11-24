# Identificadores de autenticación, jugador, instalación y guardado

**Alcance:** Soul Knight 8.8.0 Android Global. **Corte:** 24 de noviembre de 2026. **Estado:** conclusiones respaldadas por pruebas reales de solo lectura; los valores crudos no se publican.

Convención: **[C]** comprobado en una ejecución o en el código; **[H]** hipótesis compatible pero no aislada; **[?]** desconocido. Un identificador puede ser sensible sin ser una credencial.

## 1. Corrección de la Fase 6.7 sobre `x-distro-id`

La Fase 6.7 concluyó que «un UUID aleatorio devuelve 400/10003 y, por tanto, el valor se valida contra la cuenta o la instalación». La Fase 6.9 no reprodujo esa conclusión de forma general:

| Experimento nuevo | Resultado |
| --- | --- |
| Login de la cuenta de laboratorio con un UUID v4 nuevo, sin `x-unique-id` | **200** y sesión nueva. |
| Login de la misma cuenta con otro UUID v4 nuevo | **200**. |
| Login con el UUID original de la instalación de laboratorio | **200**. |
| Login con un valor no UUID (`GP`) | **400 / 10000** (formato inválido). |
| Login sin `x-distro-id` | **502 / 10003** (la cabecera es necesaria). |

La diferencia relevante no es «UUID registrado frente a UUID inventado», sino **qué jugador selecciona el UUID**. Un UUID nuevo es aceptado y crea o selecciona un jugador distinto. El UUID original selecciona el jugador que contiene la partida. Por eso un UUID nuevo no sirve para recuperar progreso, aunque el login sea correcto.

**Lectura corregida:** `x-distro-id` es un identificador de contexto de **jugador/instalación** aceptado por el gateway. El servidor no exige que sea un UUID ya registrado por el cliente oficial; exige un formato válido y usa el valor para resolver el jugador. La autorización sigue viniendo de la sesión y del token; el distro no es una credencial.

## 2. `x-unique-id`

### 2.1 Naturaleza

**[C]** Es un código de instalación/dispositivo. El login funciona sin él, pero BlobSave lo exige. El valor observado tiene la forma:

```text
xiaomioutseas_<16 dígitos hexadecimales en minúscula>
```

Longitud total 30. El prefijo `xiaomioutseas` es el canal/región observado en la instalación Android Global; el sufijo de 16 hex es el identificador de dispositivo que el cliente genera y persiste. El análisis estático de la Fase 5.9 ya situó su origen en `CloudSaveUtil.mac` y `RefreshUniqueId`; la Fase 6.9 confirmó que el servidor lo usa para vincular el dispositivo al jugador.

**[C]** No es una sesión: cambia con la instalación, no con cada login. No es el `uid`, el `player.id`, `cloudSaveId`, `platformId` ni `ChillyUid`.

### 2.2 Generación y persistencia

El backend genera un valor nuevo con `secrets.token_hex(8)` y el prefijo observado. Lo asocia al perfil de la cuenta, lo cifra con AES-SIV y lo reutiliza. No se copia de otra cuenta ni se regenera en cada acceso. Regenerarlo puede consumir vinculaciones y romper la continuidad de la partida.

### 2.3 Errores observados de BlobSave

| Código | Significado operativo | Acción del backend |
| --- | --- | --- |
| `100504` | El jugador seleccionado no tiene partida en la nube. | No se crea ni se sobrescribe nada; se prueba otro jugador del portal o se informa «sin partida». |
| `100505` | El código de dispositivo presentado no es aceptable. | Error tipado; no se reintenta con valores aleatorios. |
| `100509` | El proveedor limita la vinculación de un dispositivo nuevo. La respuesta incluye `bindDeviceWaitSeconds`/`timeWait`. | Se conserva el par, se guarda la espera y no se reintenta hasta que termine. |

La página oficial de Cloud Save documenta un límite de 5 vinculaciones por cuenta cada 90 días y al menos 24 horas entre vinculaciones. La Fase 6.9 no intentó eludirlo.

## 3. Portal oficial: la fuente del distro del jugador

El portal `accounts.chillyroom.com` usa Redwood `dbAuth` y una API GraphQL. La consulta `Profile` devuelve, por cuenta:

```text
getUserProfileByToken
  accountInfo { userId email }
  gamesInfo {
    gameId
    players {
      pid
      gameId
      gameName
      registerDistroId
      lastLoginDistroId
    }
  }
```

**[C]** El portal devolvió dos jugadores de Soul Knight para la cuenta de laboratorio. El jugador con `pid` igual al `player.id` del gateway tenía un `lastLoginDistroId` distinto del UUID local `LastLoginHostWithDistroId`, pero **ambos distros seleccionaron el mismo jugador** y permitieron descargar la misma partida. Esto demuestra que el jugador puede tener más de un distro válido (registro, último login, instalación) y que el portal es una fuente autorizada para recuperar uno de ellos.

**[C]** La consulta no expone la partida, el `unique_id` ni el token del juego. Solo identidad y jugadores. No se usó para escribir, migrar ni desvincular.

## 4. Identidad del guardado

| Identificador | Naturaleza | Relación con el login |
| --- | --- | --- |
| `cloudSaveId` | Campo del agregado; en el laboratorio `GPV2_<uid>`. | Identifica la copia. No es `x-distro-id` ni `x-unique-id`. |
| `platformId` | Campo del agregado; en el laboratorio `GP`. | Plataforma/canal. No es el distro. |
| `player.id` / `pid` | Jugador. El gateway y el portal coincidieron. | Selecciona la partida; el backend exige la coincidencia. |
| `session.uid` / `user.id` | Cuenta. Coinciden entre sí. | Identidad de la cuenta; no eligen el jugador. |
| `user.email` | Correo de la cuenta. | Se compara con el solicitado; no es clave única entre canales. |

El backend deriva el subject de identidad de `email + uid + player.id` y el subject de guardado de `cloudSaveId + platformId`, con HMAC-SHA-256. Una partida de otra cuenta se rechaza. En la prueba real, el subject y el respaldo quedaron aislados por cuenta.

## 5. Matriz de hipótesis

| Hipótesis | Experimento | Resultado | Conclusión |
| --- | --- | --- | --- |
| Un UUID nuevo es rechazado siempre | Login con UUID v4 nuevo | 200 | Falso. El UUID nuevo crea/selecciona otro jugador. |
| El distro identifica la cuenta | Login con distro nuevo y luego con el original | `player.id` distinto / original | El distro identifica al jugador, no a la cuenta. |
| El distro antiguo es imprescindible | Portal `lastLoginDistroId` + login | Mismo `player.id` y descarga | Hay varios distros válidos para el mismo jugador; el portal da uno. |
| El `unique_id` se puede inventar sin consecuencias | Unique nuevo + jugador correcto | Vinculación aceptada en la prueba completa; `100509` en otros intentos | El servidor lo vincula y aplica límites; hay que persistirlo. |
| El unique identifica la cuenta | Unique original + distro nuevo | `100504` (jugador vacío) | El unique no elige la partida; el jugador sí. |
| El portal entrega la partida | Consulta `Profile` | Solo identidad/jugadores | Falso. Entrega el distro, no el contenido. |
| El portal requiere el token del juego | Login de portal con correo/contraseña | 200 y datos | Falso; usa su propia sesión. |
| El portal sustituye la autorización del proveedor | Uso de la interfaz pública | Sin contrato de terceros | No. La autorización de ChillyRoom sigue pendiente. |

## 6. Qué no se demostró

- Que el portal sea un mecanismo autorizado para integraciones de terceros. Es una interfaz oficial usada con una cuenta propia, pero no hay contrato ni consentimiento del proveedor para SK-Under.
- Que el límite de vinculación se pueda o se deba evitar. No se intentó.
- Que todas las versiones, plataformas o regiones usen el mismo formato de `unique_id`.
- Que `ChillyUid` sea equivalente a `x-unique-id`.
- Que las tres cuentas facilitadas tengan contraseña de ChillyRoom. Fueron rechazadas tanto por el gateway como por el portal.

## 7. Consecuencia de diseño

El backend no debe inventar un distro y confiar en que verá la partida. Debe:

1. Consultar el portal una vez para obtener el distro del jugador.
2. Generar un `unique_id` nuevo con el formato observado.
3. Probar los jugadores del portal; distinguir `100504` (sin partida), `100509` (límite) y `200` (partida).
4. Guardar el par elegido cifrado y reutilizarlo.
5. Respetar el límite del proveedor y no reintentar automáticamente.

Eso es lo implementado. La parte que no se puede automatizar sin el proveedor es la autorización de terceros y, para las cuentas sin credenciales válidas, la autenticación misma.

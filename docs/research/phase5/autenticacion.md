# Arquitectura de autenticación

## Entrada del cliente Android

El manual público distingue el botón de Google del botón de cuenta de ChillyRoom. Una cuenta de ChillyRoom existente puede reutilizarse entre los juegos compatibles. Para recuperar un respaldo se debe utilizar el mismo método y la misma cuenta usados al guardarlo. Google y ChillyRoom pueden corresponder a identidades distintas aun cuando compartan una dirección de correo. [Manual oficial de Android](https://soulknight.chillyroom.com/et/article/base/3) · [Preguntas frecuentes](https://soulknight.chillyroom.com/et/article/base/6)

| Etapa | Evidencia estática |
| --- | --- |
| Pantalla de cuenta ChillyRoom | En `com.chillyroom.services.accounts.Runtime.dll`, `AccountLoginView.ClickLoginBtn` (`0x06000a0d`, máquina de estados `0x06000a1f`, VA `0x09cbb8d4`) normaliza la cuenta y llama a `AccountSdkController.EmailOrPhoneLogin`. |
| Validación y despacho | `EmailOrPhoneLogin` (`0x06000854`, máquina `0x060008ab`) llama a `CheckAccountValid` y `BaseLogin`. La máquina de `BaseLogin` (`0x06000897`) llama a `FrequentCheckUtil.CheckFrequent` y `PasswordAuthService.BaseLogin` (`0x060008c2`). Parte del cuerpo de este último queda sin resolver. |
| Resultado | El controlador contiene llamadas a `SdkEvents.OnLoginResultAction` para publicar resultados. El juego declara `NewCloudSaveAgent.OnLoginResultAction` (`0x06021beb`) y `SetAccountLogin` (`0x06021bec`). La relación entre el resultado exacto de la rama por contraseña y el primer fetch permanece pendiente. |
| Google y canales | La máquina de estados de `GooglePlayLoginAndCloudSaveAgent.Login` (`0x06021f7d`) llama a `AccountSdk.Login`. En `classes2.dex`, `BaseAccountAgent` ofrece callbacks de éxito, fallo y cambio de usuario. `BasePlayerActivity` reenvía eventos por `UnityPlayer.UnitySendMessage`. Los adaptadores Android varían por canal. |

El SDK de Unity es `ChillyRoom.Services.Accounts.AccountSdk` (tipo `0x020000c8` de `com.chillyroom.services.accounts.Runtime.dll`). En esa misma imagen residen `AccountStateManager` y `ChillyRoom.Services.UserAuthService.UserAuthClient`. La revisión pública no encontró un SDK o programa de acceso de terceros a los guardados de Soul Knight.

## Sesión y expiración

- `SdkState` (`0x020001db`) conserva el estado de sesión, `CurrentLoginType`, `User` y `Session`. El tipo de estado enumera, entre otros, `UnLogin`, `LoggedIn`, `Logining`, `Banned` e `Invalid`.
- `Session` (`0x020001da`) contiene `Token`, `Expire` y `LoginBy`. `Session.From` (`0x0600094d`, VA `0x09cac184`) convierte la expiración con `DateTimeOffset.FromUnixTimeSeconds`. `AccountStateManager.Login` (`0x06000958`) construye `User` y `Session`, llama a las cachés del SDK y a `PlayerPrefs.Save`. Quedan sin medir la duración de sesión, la revocación y la semántica del token.
- `AccountSdk.HasSession` (`0x060003fe`) comprueba el valor de sesión en caché. `AccountSdk.Login(LoginOptions)` (`0x06000402`) tiene una rama de `HasSession` → `Renew` y propiedades `AutoRenew` y `AfterRenew`. `Renew` (`0x06000400`) consulta caché y conectividad. Los callbacks publican `OnRenewResultAction`. Una sesión en caché por sí sola no demuestra que el servidor acepte una operación.
- `LoginErrorCode` incluye `Unauthenticated`, `LoginAttemptThrottled`, `NetworkUnavailable`, `Timeout`, `ServiceUnavailable`, `PlayerHasBeenBanned` y `Cancelled`. La asignación exacta de cada fallo de descarga a renovación, nuevo acceso o espera sigue pendiente de una observación autorizada.
- `BlobSaveClient` declara los callbacks `GetRequestToken` y `ResetRequestToken`. El cliente RPC `LoginApi` declara estado de acceso, ID de jugador y token en su propio modelo. La equivalencia entre ambas sesiones y la delegación del SDK para cada transporte quedan pendientes.

## Identidad y comprobaciones de titularidad

| Identificador | Hallazgo |
| --- | --- |
| `User.Id` y `User.PlayerId` | Campos distintos del tipo `User` (`0x020001d9` del SDK). El modelo conserva el proveedor de inicio de sesión, perfiles vinculados y la identidad nativa. |
| `uid`, `chilly_uid`, `channel_uid`, `pf_id` | Propiedades de `CloudSaveUtil` (`0x02001184` del juego). Corresponden a dominios de identidad que el código distingue. El mapa `assets/DefineCloudSaveID.json` relaciona 44 etiquetas de canal con identificadores de formato. |
| `cloudSaveId` y `platformId` | Campos de texto del agregado. `CloudSaveUtil.GetCurrentAccountSaveId` (`0x06009d8e`) consulta `pf_id` y `uid`. `get_LocalSaveIdValid` (`0x06009d93`) y `get_SaveIdValid` (`0x06009d94`) comparan el identificador local o el predeterminado con el de la cuenta actual, con ramas para cadenas vacías. |
| Vinculación con dispositivo | `LoginApi.CheckSaveMac` (`0x06009dec`) consulta identidad, plataforma y un valor de dispositivo denominado `mac` antes de una llamada RPC. El servicio documenta restricciones de dispositivo y cuenta. La interpretación criptográfica de ese valor y la política interna del servidor quedan abiertas. |

Para restaurar, el proveedor documenta un respaldo previo, sesión en la cuenta correspondiente, canal/plataforma compatible y elegibilidad del dispositivo. La guía de soporte explica el error de pertenencia para un guardado asociado a otra cuenta o canal. La comprobación del cliente y la respuesta de autorización del servidor son evidencias distintas. [Límites de guardado](https://soulknight.chillyroom.com/et/article/base/4) · [Soporte oficial por canal](https://www.chilly.tech/zh/soul-knight/support)

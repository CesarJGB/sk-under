# Fase 10.1 — Incompatibilidad iOS: metadatos de versión de BlobSave

Fecha: 2026-11-27

## Resultado

La causa del rechazo del cliente oficial de iOS no estaba en el guardado. El
documento enviado por SK-Under era byte a byte idéntico al original en la prueba
sin cambios de la Fase 10.2. La causa estaba en las **cabeceras de versión de la
petición `BlobSave`**: SK-Under envió `8.8.0.13` en `x-app-version` y
`x-game-version`, tomándolo de la versión visible de la distribución iOS. El
cliente oficial usa el **protocolo `8.8.0`**. El servidor guardó el blob como
perteneciente a una versión superior y, en cada recuperación posterior, devolvió
`VersionLowerThanBlobSave`; el cliente lo muestra como
`multi_remote/game_version_invalid` («La versión de tu juego es demasiado
antigua. Actualízala»).

La corrección separa la versión visible de la versión de protocolo. La escritura
iOS sigue en estado experimental y no se declara compatible hasta que el
propietario confirme la recuperación en un iPhone físico.

Durante la fase, el 2026-11-27, el propietario informó de que el cliente iOS
pasó a `8.8.0.14`. El cuarto componente sigue siendo compilación/hotfix; la
corrección no depende de ese número, sino de no enviarlo como versión de
protocolo. El valor visible de la distribución se actualizó a `8.8.0.14` y el
protocolo permanece en `8.8.0`. Si una compilación futura cambiara el protocolo,
el único punto a actualizar es `protocol_app_version`/`protocol_game_version`.

## 1. Evidencia de la causa raíz

### 1.1 El error lo produce el servidor, no el contenido

El metadato del cliente (APK 8.8.0, código compartido con iOS) contiene el
servicio `ChillyRoom.SoulKnight.BlobSaveService.V1` con `DownloadAsync` y
`UploadAsync`, y el enumerado `CommonErrorCodes` con, entre otros:

- `SaveDataNotFound`
- `DistroNoConfig`
- `DeviceParamsMissing`
- `VersionParamsMissing`
- **`VersionLowerThanBlobSave`**
- `DeviceHasBindMax`
- `DeviceBindThrottle`
- `BlobSaveClosed`

`VersionLowerThanBlobSave` es un error del servidor: compara la versión enviada
por el cliente con la registrada en el blob. El cliente lo traduce a
`multi_remote/game_version_invalid`. Los textos exactos se confirmaron en
`localization.ab`:

| Clave | Texto |
| --- | --- |
| `multi_remote/game_version_invalid` | «La versión de tu juego es demasiado antigua. Actualízala.» |
| `cloudsave/version_not_match` | «Has subido datos a la nube con una versión superior…» |
| `cloudsave_fetch_fail` | «No se pudo recuperar el progreso» |
| `cloudsave/cloud_save_not_found` | «No se encontró ningún archivo guardado en la nube» |

El mensaje observado por el propietario es el primero. No es un fallo de
deserialización ni un rechazo del JSON.

### 1.2 Confirmación por cuenta

El propietario comprobó que, tras la subida de SK-Under, la cuenta de prueba ya
no podía subir desde el cliente oficial porque el juego seguía diciendo que la
versión era vieja. Al cambiar a la cuenta modificada con CRDE, el cliente
funcionaba con normalidad. Esto descarta un problema global del cliente o del
dispositivo y lo localiza en los metadatos almacenados del blob de esa cuenta.
También descarta el contenido: CRDE reescribe el guardado y el cliente lo
acepta; SK-Under envió el mismo contenido y el cliente lo rechaza. La única
diferencia introducida por SK-Under fueron las cabeceras de la petición.

### 1.3 `8.8.0.13`/`8.8.0.14` no son la versión de protocolo

- La versión visible del cliente iOS era `8.8.0.13` durante la prueba y pasó a
  `8.8.0.14` el 2026-11-27; el cuarto componente es el número de
  compilación/hotfix.
- El APK 8.8.0 no contiene el literal `8.8.0.13` en sus metadatos y su carpeta
  de datos de juego es `VersionConfigs/8.8.0`.
- Las capturas de red de Android de fases anteriores muestran
  `x-app-version: 8.8.0` y `x-game-version: 8.8.0`.
- Los símbolos del cliente (`VersionCheckInGameClient`,
  `MultiGameVersionPostProcess`, `AppVersionCheck`, `gameBundleVersion`)
  comparan la versión de protocolo, no el número de compilación de la tienda.

Por tanto `8.8.0.13`/`8.8.0.14` son la versión de presentación/compilación, y
`8.8.0` es la versión que viaja en el protocolo y en los metadatos del blob.

### 1.4 Por qué la Fase 10.2 no lo detectó

La Fase 10.2 verificó que el servidor aceptaba la subida (HTTP 200 `true`) y que
una descarga posterior devolvía los mismos bytes. Ambas cosas eran ciertas. El
rechazo ocurre después, cuando el cliente oficial compara la versión del blob
con la suya. Un 200 y un SHA-256 igual no demuestran compatibilidad nativa. La
prueba física era el único nivel que podía descubrirlo y aún no se había hecho.

## 2. Significado de los identificadores

| Identificador | Dónde aparece | Significado |
| --- | --- | --- |
| `8.8.0.13` / `8.8.0.14` | Cliente iOS, ficha de la App Store | Versión visible + compilación |
| `8.8.0` | Cabeceras `x-app-version` / `x-game-version`, carpeta `VersionConfigs` | Versión de protocolo |
| `gameVersion: 2155` | `gameData.gameVersion` | Versión interna del documento de guardado |
| `AppVersion: 1531` (iOS) | `itemData.AppVersion` | Marcador de compilación del documento iOS |
| `AppVersion: 80800` (Android) | `itemData.AppVersion` | Marcador de compilación Android (`8.08.00`) |
| `serialzedVersion: 1` | Raíz del guardado | Versión de serialización del documento |
| `platformId: "IOS"` | Raíz del guardado | Plataforma del documento |
| `cloudSaveId: "IOS_…"` | Raíz del guardado | Identificador del registro en la nube |

`gameVersion 2155` y `AppVersion 1531` son metadatos del contenido y se conservan
sin cambios. No son las cabeceras que valida el servidor.

## 3. Diferencias Android/iOS relevantes

| Aspecto | Android | iOS |
| --- | --- | --- |
| Versión visible | `8.8.0` | `8.8.0.13` → `8.8.0.14` |
| Versión de protocolo | `8.8.0` | `8.8.0` |
| `x-platform` | `android` | `ios` |
| `AppVersion` del documento | `80800` | `1531` |
| `cloudSaveId` | `GP_` / `GPV2_` | `IOS_` |
| Estructura del documento | Compartida | Compartida |

La diferencia que rompía la nube era exclusivamente la versión de protocolo tomada
de la versión visible. Las demás diferencias ya estaban verificadas y no
causaban el rechazo.

## 4. Roundtrip sin modificaciones

Sobre la muestra nativa de iOS de la Fase 10.2 (115.175 bytes, SHA-256
`0b7da432aa8fe73183048d564aa44386351f31ee98493743a23a4e055ff567ca`), en local y
sin tocar la nube:

1. `parse_json` decodifica el documento.
2. `json.dumps(document, ensure_ascii=False)` con los separadores por defecto
   `(', ', ': ')` reconstruye el original **byte a byte**: mismo tamaño y mismo
   SHA-256.
3. `reconstruct_cloud_save` conserva la codificación, el tamaño y el hash de
   origen.
4. `decode_ios_save` recupera `platformId`, `cloudSaveId`, `serialzedVersion`,
   `gameVersion`, `AppVersion`, las 17 secciones y los campos desconocidos.

Con `ensure_ascii=True` el resultado difiere en el byte 77.715 porque escapa
acentos. Esa opción no se usa en la ruta de preparación.

Conclusión: el transporte y la serialización no introducen diferencias. El
único cambio relevante de la Fase 10.2 estaba en las cabeceras.

## 5. Corrección implementada

- `backend/app/native/distributions.py`: nuevos campos
  `protocol_app_version` y `protocol_game_version`, por defecto `8.8.0`. La
  versión visible sigue en `game_version` (`8.8.0.14` en iOS). Ambos se exponen
  en `public()`.
- `backend/app/native/service.py`: las factorías de descarga y subida usan las
  versiones de protocolo, no `game_version`.
- `backend/app/native/client.py`: las cabeceras de login usan también las
  versiones de protocolo.
- `backend/app/cloud/provider.py` y `backend/app/native/errors.py`: nuevo error
  tipado `cloud_save_version_ahead` / `native_save_version_ahead` (HTTP 409).
- `backend/app/cloud/modern.py`: detecta el marcador
  `VersionLowerThanBlobSave` en `errordetails` y lo convierte en el error
  tipado. No se adivina el código numérico.
- `backend/app/cloud/capabilities.py`: la evidencia de iOS refleja que la
  persistencia de la Fase 10.2 fue real pero el cliente oficial la rechazó por
  metadatos; la corrección está pendiente de validación física.
- Pruebas nuevas en `backend/tests/test_phase10_1_ios_protocol_versions.py` y
  ajustes en las pruebas de iOS y de la Fase 10.2.

La corrección no introduce valores arbitrarios: usa la misma versión de
protocolo que el cliente oficial y que Android. Tampoco elimina campos del
guardado ni cambia el cuerpo de la petición.

## 6. Diagnóstico

El error tipado permite distinguir:

| Estado | Cómo se observa |
| --- | --- |
| Autenticación correcta | Sesión y distro válidas |
| Descarga correcta | Documento recibido y decodificado |
| Guardado decodificado | `IosSave` con secciones y metadatos |
| Candidato preparado | SHA-256 y roundtrip verificados |
| Servidor acepta la subida | HTTP 200 `true` |
| Persistencia remota | Descarga posterior con el SHA del candidato |
| Recuperación nativa | Confirmación del cliente en iPhone |

`native_save_version_ahead` bloquea la operación cuando el blob remoto es más
nuevo que el cliente. No se intenta saltar la validación ni rebajar la versión
del servidor.

## 7. Pruebas

- Backend completo: **774 superadas, 16 omitidas**.
- Nuevas pruebas:
  - iOS muestra `8.8.0.14` pero el protocolo es `8.8.0`; Android no cambia.
  - Las factorías de descarga y subida usan `8.8.0` en iOS.
  - Las cabeceras de login iOS envían `x-platform: ios` y `8.8.0`.
  - `VersionLowerThanBlobSave` se convierte en `CloudProviderSaveVersionAhead`.
  - Un documento iOS con campos desconocidos sobrevive al roundtrip y al sobre
    de subida sin cambios.
- No se hizo ninguna escritura remota nueva durante esta fase.

## 8. Despliegue

- Commit de la corrección: `11fce68304c8c650e49c119b4edda6352ace5412`
  (`fix(phase10-1): use iOS BlobSave protocol version 8.8.0`), publicado en
  `main`.
- CI de GitHub ejecutado sobre ese commit.
- Despliegue verificado en producción el 2026-11-27:
  - `GET /api/v1/version` devolvió
    `commit: 11fce68304c8c650e49c119b4edda6352ace5412`.
  - `GET /api/v1/cloud/native/config` devolvió `ios-global` con
    `game_version: 8.8.0.14`, `protocol_app_version: 8.8.0` y
    `protocol_game_version: 8.8.0`.
- La escritura iOS general quedó inicialmente limitada por la matriz de
  capacidades a la cuenta experimental autorizada. El 2026-11-27 el propietario
  pidió habilitarla para probar la corrección; ver la sección 11.

## 9. Estado del blob envenenado

La cuenta de prueba quedó con un blob marcado `8.8.0.13`. El flujo normal de
SK-Under descarga antes de confirmar o restaurar, por lo que ahora recibe
`native_save_version_ahead` y no llega a subir. El cliente oficial tampoco sube
porque aborta al ver el blob más nuevo. No se ha implementado una reparación
especulativa: reducir la versión del blob requiere que el servidor lo acepte y
eso no está demostrado. Queda documentado como bloqueo operativo.

Si el servidor acepta una subida directa con la versión correcta, la reparación
sería subir de nuevo el original sin cambios con las cabeceras `8.8.0`. Debe
hacerse solo con autorización explícita, respaldo verificado y una prueba
posterior. No se debe presentar como resuelto hasta comprobarlo.

## 10. Validación manual en iPhone

1. Confirmar que la cuenta es ChillyRoom por correo (no solo Apple ID).
2. Abrir Soul Knight 8.8.0.13 o 8.8.0.14 y comprobar que la nube está activa.
3. Iniciar sesión en SK-Under con esa cuenta y descargar la partida.
4. Crear un respaldo y anotar el SHA-256.
5. Hacer un cambio pequeño y autorizado, preferiblemente en una cuenta
   secundaria.
6. Subir y esperar la verificación de SK-Under (descarga posterior con el mismo
   SHA).
7. Cerrar y abrir el juego en el iPhone; usar «Recuperar progreso».
8. Comprobar que el valor editado aparece y que no sale el mensaje de versión
   antigua.
9. Si falla, restaurar el respaldo desde SK-Under y comunicar el mensaje exacto
   sin compartir credenciales ni el guardado completo.

No se declara compatibilidad nativa hasta que este paso 8 sea correcto.

## 11. Modo de prueba de escritura (2026-11-27)

A petición explícita del propietario se habilitó la subida iOS para poder
probar la corrección de versión en un iPhone físico. El cambio es deliberado y
reversible:

- `IOS_WRITE_TEST_ENABLED = True` en `backend/app/cloud/capabilities.py`.
- La matriz declara iOS como `write_experimental`, no `write_verified`.
- Cualquier cuenta iOS con el interruptor global de escritura activo y el perfil
  listo puede subir. Ya no se exige el digest de la cuenta de la Fase 10.2,
  aunque ese mecanismo se conserva para volver al modo limitado.
- Cada subida sigue exigiendo respaldo completo, confirmación explícita,
  detección de cambios remotos y verificación por descarga posterior.
- La interfaz muestra que es un modo de prueba y que la compatibilidad nativa
  no está declarada.

Para desactivarlo, poner `IOS_WRITE_TEST_ENABLED = False` y desplegar. La
capacidad vuelve a `write_pending_validation` salvo para las cuentas cuyo digest
esté autorizado.

Este modo no demuestra que el cliente oficial recupere la partida. Si el
guarda remoto sigue marcado con una versión superior, `native_save_version_ahead`
bloquea la operación antes de subir. La validación real sigue siendo la prueba
manual del propietario en el iPhone.

### Procedimiento recomendado para la prueba

1. Usar preferiblemente una cuenta iOS secundaria para la primera subida.
2. Descargar y respaldar; anotar SHA-256.
3. Hacer un cambio pequeño y subir.
4. Comprobar que SK-Under verifica la persistencia.
5. Abrir el cliente oficial y usar «Recuperar progreso».
6. Si el cliente rechaza la copia, restaurar el respaldo y conservar el mensaje
   exacto. No repetir subidas sobre la misma cuenta hasta identificar la causa.
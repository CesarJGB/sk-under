# Adquisición de una referencia real de Soul Knight 8.8.0

**Resultado:** se obtuvo un perfil local auténtico de Soul Knight 8.8.0 desde
el APK oficial, ejecutado en un emulador propio y controlado, sin credenciales
de una cuenta y sin extraer datos de terceros. El perfil incluye las secciones
locales de `game.data`, `item_data`, `season_data`, `statistic`, `task`,
`setting`, `monsrise_data`, `misc_data`, `pvp_data`, `bp_data`,
`weapon_evolution_data`, `escape_season_data` y `mall_reload_data`, además de
los dos JSON de `sandbox`. **No se obtuvo el agregado de nube
`CloudSaveGameData`**: los campos de envoltura `serialzedVersion`,
`cloudSaveId` y `platformId` no existen en el perfil local.

## 1. Entorno y procedencia

| Dato | Valor |
| --- | --- |
| Juego | Soul Knight Android, paquete `com.ChillyRoom.DungeonShooter` |
| Versión | `versionName=8.8.0`, `versionCode=1080800` |
| APK | `soul-knight-8-8-0.apk`, SHA-256 `54bb332be9444596501ec99f745f21adfa55265feea3a15331c735009b517f34` |
| ABI instalada | `armeabi-v7a` (el APK también incluye `arm64-v8a`) |
| Emulador | Android 11 / API 30, imagen `google_apis` x86_64 `userdebug`; KVM |
| Cuenta | Perfil **Guest Account** creado por el propio cliente |
| Fecha de captura | 2026-11-23 UTC |
| Origen de los bytes | `/data/data/com.ChillyRoom.DungeonShooter/files/` del AVD propio |
| Acceso | `adb root` sobre la imagen `userdebug`; lectura del directorio de la aplicación |
| Credenciales | Ninguna. No se usó una cuenta existente, token, contraseña ni sesión de terceros |

La imagen `google_apis_playstore` no permite `adb root` ni `adb backup` con la
aplicación instalada; por eso la captura se hizo en una imagen `userdebug`
propia. La instalación se realizó con `adb install --abi armeabi-v7a` para
evitar la ruta ARM64 traducida, que en fases anteriores falló en este host.

## 2. Procedimiento reproducible

1. Arrancar un AVD Android 11 `google_apis` x86_64 `userdebug` con KVM.
2. `adb install --abi armeabi-v7a soul-knight-8-8-0.apk`.
3. Abrir `com.ChillyRoom.DungeonShooter/com.chillyroomsdk.sdkbridge.BasePlayerActivity`.
4. En la pantalla de acceso, elegir **Guest Account**. El cliente crea el
   perfil local y escribe los archivos de la tabla. No se envió usuario ni
   contraseña.
5. Esperar a que el cliente termine de escribir; cerrar la aplicación con
   `am force-stop`.
6. `adb root` y copiar el directorio `files/` a un directorio privado fuera del
   repositorio. Calcular tamaño y SHA-256 de cada archivo antes de analizarlo.
7. Conservar el original sin modificarlo. El análisis se hace sobre copias.

La copia privada se guarda en
`~/.config/sk-under/phase5-6/` o en un directorio equivalente con permisos
`0700`, nunca dentro de Git. El inventario privado contiene el SHA-256 y el
sufijo numérico del perfil; este documento no publica ninguno de los dos.

## 3. Inventario público redactado

Los nombres reales llevan un sufijo numérico del perfil. Aquí se sustituye por
`<perfil>`.

| Archivo | Bytes | Códec local | Sección | Versión observada |
| --- | ---: | --- | --- | ---: |
| `game.data` | 25 461 | XOR JSON | `AboGameData` | `gameVersion=0` |
| `item_data.data` | 3 552 | Base64 + DES-CBC + JSON | `ItemData` pre-login | `AppVersion=0` |
| `item_data_<perfil>.data` | 3 564 | Base64 + DES-CBC + JSON | `ItemData` | `AppVersion=80800` |
| `season_data.data` | 3 352 | Base64 + DES-CBC + JSON | `SeasonData` pre-login | — |
| `season_data_<perfil>.data` | 19 192 | Base64 + DES-CBC + JSON | `SeasonData` | — |
| `statistic.data` | 8 960 | Base64 + DES-CBC + JSON | `StatisticData` pre-login | — |
| `statistic_<perfil>.data` | 41 260 | Base64 + DES-CBC + JSON | `StatisticData` | — |
| `task_<perfil>.data` | 2 360 | Base64 + DES-CBC + JSON | `TaskDatas` | — |
| `setting_<perfil>.data` | 1 612 | Base64 + DES-CBC + JSON | `SettingData` | — |
| `misc_data_<perfil>.data` | 728 | Base64 + DES-CBC + JSON | `MiscData` | — |
| `monsrise_data_<perfil>.data` | 556 | Base64 + DES-CBC + JSON | `MonsterRiseData` | `version=1` |
| `pvp_data_<perfil>.data` | 608 | Base64 + DES-CBC + JSON | `PvpData` | — |
| `bp_data_<perfil>.data` | 120 | Base64 + DES-CBC + JSON | `BattlePassSaveData` | — |
| `weapon_evolution_data.data` | 128 | Base64 + DES-CBC + JSON | `WeaponEvolutionData` pre-login | — |
| `weapon_evolution_data_<perfil>.data` | 128 | Base64 + DES-CBC + JSON | `WeaponEvolutionData` | — |
| `escape_season_data_<perfil>.data` | 1 504 | Base64 + DES-CBC + JSON | `EscapeSeasonData` | `version=1` |
| `mall_reload_data_LOCAL.data` | 1 528 | Base64 + DES-CBC + JSON | `MallReloadData` local/pre-login | — |
| `mall_reload_data_<perfil>.data` | 768 | Base64 + DES-CBC + JSON | `MallReloadData` | — |
| `sandbox_config_<perfil>.data` | 50 | JSON plano | `SandboxConfigData` | — |
| `sandbox_maps_<perfil>.data` | 11 | JSON plano | `SandboxMaps` | — |

Los tamaños y los nombres de sección son información estructural. Los valores,
las huellas y el identificador del perfil permanecen en el inventario privado.

## 4. Formato local observado

- **Secciones JSON principales:** Base64 estándar de un bloque DES-CBC con
  relleno PKCS#7. El IV y las dos claves coinciden con las usadas por las
  muestras 8.6.0 configuradas en la Fase 3. El JSON va en UTF-8 y no lleva gzip.
- **`game.data`:** JSON UTF-8 ofuscado con un XOR repetido de 15 bytes. No es
  cifrado fuerte ni autenticación; es una capa de ofuscación local. Se decodificó
  y se volvió a codificar byte a byte con la muestra auténtica.
- **`sandbox_config` y `sandbox_maps`:** JSON plano, sin cifrar.
- **Nombres:** el cliente 8.8.0 usa `item_data_<perfil>.data`,
  `statistic_<perfil>.data`, etc. Las variantes sin sufijo son valores por
  defecto o caches pre-login; no son el perfil activo.

La pista del códec XOR y de las claves DES se contrastó con el paquete externo
[`soul-knight-data-processing`](https://pypi.org/project/soul-knight-data-processing/0.0.9/)
(licencia GPL-3.0), que a su vez cita a SKDEditor. La implementación de este
repositorio es propia; no se copió código GPL. La clave se corroboró con ese
paquete y se validó contra los bytes auténticos. La verificación se hizo contra
los bytes auténticos: el JSON XOR resultante tiene las 41 claves declaradas por
`AboGameData` y el `game.data` original se reproduce exactamente al recodificar.

## 5. Qué sigue siendo privado o desconocido

| Elemento | Estado |
| --- | --- |
| Valores de la partida | Privados; no se publican |
| SHA-256 de cada archivo | Privado; inventario local |
| Sufijo/ID del perfil | Privado; no se publica |
| `serialzedVersion`, `cloudSaveId`, `platformId` | Ausentes en el perfil local |
| Agregado `CloudSaveGameData` | No obtenido |
| Aceptación por el cliente oficial | No probada |
| Código de `FixData` | No decompilado |

## 6. Vías descartadas o no demostradas

- `adb backup` de la aplicación: el paquete no declara `ALLOW_BACKUP` y el
  Backup Manager está deshabilitado en la imagen Play Store.
- Copia desde la nube sin una cuenta propia: no se intentó; requeriría una
  sesión autorizada del titular y no hay una API pública.
- Exportación oficial a archivo: no está documentada.
- Soporte de ChillyRoom: no se contactó; no hay contrato machine-readable.
- Extracción de datos de otras cuentas o elusión de aislamiento: fuera de
  alcance y no realizada.

## 7. Conclusión

La referencia local 8.8.0 es auténtica, reproducible y suficiente para validar
el códec local, el esquema de las secciones y el roundtrip de 18 archivos. No
sustituye a una copia de nube: para cerrar la compatibilidad remota falta el
agregado que el servidor entrega al cliente y la prueba de restauración.

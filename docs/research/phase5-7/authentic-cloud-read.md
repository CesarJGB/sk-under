# Lectura auténtica de nube desde Linux

**Estado: LECTURA AUTÉNTICA DE `FetchGameData` CONSEGUIDA; `CloudSaveGameData`
NO OBTENIDO.** El token emitido por el cliente oficial fue aceptado por el
gateway desde Linux y `POST /Backup/FetchGameData` devolvió `200` con un JSON
de 600 bytes. Es un agregado legacy vacío, no el wrapper nuevo de la partida.
`/Backup/GetBlobSave` siguió devolviendo `500`.

## 1. Cómo se obtuvo el token

Se inició sesión en el cliente oficial dentro del AVD estable:

- **Invitado:** el cliente creó una cuenta nueva y guardó su sesión.
- **ChillyRoom email:** el login con la cuenta de laboratorio devolvió
  `login success, type: Email` y cargó el perfil.

El cliente persiste la sesión en
`/data/data/com.ChillyRoom.DungeonShooter/shared_prefs/com.ChillyRoom.DungeonShooter.v2.playerprefs.xml`.
Las claves relevantes son `SdkUserCacheV2`, `SdkSessionCacheV2`,
`SdkUserCacheV2.LegacyGateway` y `LastLoginHostWithDistroId`. El token y el
host se extrajeron a un archivo privado `0600` fuera del repositorio; **no se
imprimieron en logs ni se publican**.

## 2. Petición desde Linux

Host y token salen de la sesión; el `x-distro-id` sale del
`LastLoginHostWithDistroId` (base64 de `host_uuid`). La petición es de solo
lectura:

```http
POST https://api-gateway.soulknight.chillyroom.com/Backup/FetchGameData
Authorization: Bearer <token>
Content-Type: application/json
Accept: application/json
x-game-id: 1
x-game: Soulknight
x-app-version: 8.8.0
x-game-version: 8.8.0
x-platform: android
x-game-lang: en
x-locale: en_US
x-distro-id: <uuid>

{}
```

Respuesta observada:

```text
200 application/json; charset=utf-8
600 bytes
```

La respuesta se guardó en
`~/.config/sk-under/phase5-7/evidence/2026-11-23/20261123T151308Z-fetchgamedata.json`
(invitado) y `.../20261123T152633Z-owner-fetchgamedata.json` (titular), con
SHA-256 en `hashes.txt`. Son datos privados del laboratorio; no se publican.

## 3. Esquema de la respuesta

Las 17 claves de nivel superior son:

```text
activeShopState, activityEvents, battlePassData, createdAt, gameItemData,
heroData, heroRoomData, lastLoginTime, migratedInfo, petData, plantPotData,
playerTags, rebornCardUnlock, returnPlayerData, returnStatusEndTime,
returnTriggerVersions, weaponUpgradeData
```

En la cuenta de laboratorio, las colecciones están vacías:

| Campo | Valor observado |
| --- | --- |
| `heroData`, `petData`, `plantPotData`, `heroRoomData`, `gameItemData` | `{}` |
| `weaponUpgradeData` | `{weaponData:{}, moduleData:{}, eggGuaranteeData:{}}` |
| `battlePassData` | `{datas:{}}` |
| `activityEvents`, `playerTags`, `returnTriggerVersions` | `[]` |
| `returnPlayerData` | histórico vacío, `returnDay=0` |
| `createdAt`, `lastLoginTime` | timestamps de la cuenta |
| `migratedInfo` | `fromDistroId=null`, `toDistroId=null` |

No aparecen `serialzedVersion`, `cloudSaveId` ni `platformId`. Por tanto, esta
respuesta **no es** el `CloudSaveGameData` que el importador de SK-Under
espera; es el agregado legacy de `FetchGameData`. No se debe etiquetar como
“partida de nube” sin esa distinción.

## 4. Rutas probadas

| Ruta | Token | Resultado |
| --- | --- | --- |
| `POST /GameWorld/Time` | Ninguno | `200` · `{"timestamp":...}` |
| `POST /UserProfile/GetUserProfile` | Ninguno | `400` · `10001 Unauthenticated` |
| `POST /UserProfile/GetUserProfile` | `Bearer` | `500` sin cuerpo |
| `POST /Backup/FetchGameData` | Ninguno | `400` · `10001 Unauthenticated` |
| `POST /Backup/FetchGameData` | `Bearer` | **`200` JSON de 600 bytes** |
| `POST /Backup/GetBlobSave` | `Bearer`, cuerpo `{}` | `500` sin cuerpo |
| `POST /Backup/GetBlobSave` | `Bearer`, `cloudSaveId`/`platformId` | `500` sin cuerpo |
| `POST /BlobSave/Download` | `Bearer` | `404` |
| Host `legacy-save...` | Cualquiera | `503` HTML del ALB |

El host `legacy-save.soulknight.chillyroom.com` que el cliente guarda como
`LegacyGateway.host` devolvió `503` del balanceador incluso sin token. El host
operativo es `api-gateway.soulknight.chillyroom.com`, que es el que aparece en
`LastLoginHostWithDistroId`.

## 5. Qué demuestra y qué no

**Demuestra:**

- Que el token de sesión emitido por el cliente es aceptado por el gateway
  desde un proceso Linux, sin el cliente Android.
- Que la cabecera `Authorization: Bearer` y las cabeceras `x-*` probadas son
  suficientes para `FetchGameData`.
- Que existe una ruta de lectura real y reproducible, con respuesta JSON y
  tamaño/hash verificables.
- Que la cuenta de laboratorio no tiene progreso en ese agregado.

**No demuestra:**

- Que exista una partida no vacía en la cuenta.
- Que `/Backup/GetBlobSave` funcione o que su cuerpo sea el que se probó.
- Que el `CloudSaveGameData` de 8.8.0 se pueda descargar con este token.
- Que una copia modificada sea aceptada por el cliente.
- Que el `FetchGameData` legacy se pueda importar como las secciones locales de
  SK-Under.

## 6. Seguridad

- Solo se ejecutaron lecturas (`FetchGameData`, `GetBlobSave`,
  `GameWorld/Time`). No se llamó a `Upload`, `Migration`, `Save` ni a ningún
  endpoint de escritura.
- No se desactivó TLS, no se instaló una CA, no se intentó pinning bypass y no
  se modificó el cliente.
- El token se mantiene en archivos `0600` fuera de Git. No aparece en este
  documento, en logs públicos ni en la respuesta final.
- La sesión web del portal no se usó como token de juego; el token probado es
  el que emitió el cliente.

## 7. Próximo paso

1. Obtener una cuenta con progreso real o crear progreso en la cuenta de
   laboratorio y confirmar que `FetchGameData` deja de estar vacío.
2. Capturar el cuerpo exacto de `/Backup/GetBlobSave` desde el cliente estable
   (metadata, instrumentación autorizada o contrato oficial) y probarlo con el
   token actual.
3. Comparar el agregado legacy con el `CloudSaveGameData` y decidir si el
   proveedor Linux debe exponer ambos o solo el nuevo.
4. Añadir un proveedor de solo lectura para `FetchGameData` con pruebas
   sintéticas, etiquetado explícitamente como agregado legacy.

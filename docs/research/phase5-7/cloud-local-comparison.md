# Comparación entre la partida local y la nube

**Estado: BLOQUEADA.** Se dispone de la referencia local auténtica de 8.8.0 y
de una lectura real de `/Backup/FetchGameData` (agregado legacy vacío de 600
bytes), pero **no de una copia de nube no vacía ni de `CloudSaveGameData`**. La
comparación de campos, identificadores, checksums y transformaciones no se puede
ejecutar sin la muestra remota. La lectura nueva está en
[lectura auténtica](authentic-cloud-read.md).

## 1. Hipótesis

`CloudSaveGameData` contiene un agregado con `serialzedVersion`, `cloudSaveId`,
`platformId`, `gameData` y doce secciones opcionales. La partida local de 8.8.0
es una representación por archivos de las mismas secciones. Comparar ambas
permitiría identificar qué campos son exclusivos de la nube, qué identificadores
son estables y qué se usa para detectar conflictos.

## 2. Referencia local disponible

| Elemento | Valor |
| --- | --- |
| Cliente | 8.8.0, `versionCode=1080800`, ABI `armeabi-v7a` |
| Perfil | Invitado local, 20 archivos inventariados |
| Archivos decodificados | 18 (17 DES-CBC + `game.data` XOR) |
| JSON planos | `sandbox_config`, `sandbox_maps` |
| Roundtrip | 18/18 binario exacto en Linux |
| Hashes | Conservados en el laboratorio privado; no se publican |
| Secciones | `gameData`, `itemData`, `statisticData`, `settingData`, `taskData`, `seasonData`, `mallReloadData`, `monsterRiseData`, `weaponEvolutionData`, `miscData`, `pvpData`, `battlePassSaveData`, `escapeSeasonData` |

La referencia es un **perfil local**, no el agregado de nube. No contiene
`serialzedVersion`, `cloudSaveId` ni `platformId` (verificado en 5.6).

## 3. Comparación prevista

| Pregunta | Estado | Qué se necesitaría |
| --- | --- | --- |
| ¿Qué campos son idénticos? | No ejecutado | Copia de nube auténtica |
| ¿Qué campos se generan solo para la nube? | No ejecutado | Copia de nube + local del mismo estado |
| ¿Qué campos cambian al subir? | No ejecutado | Lectura antes/después de una subida controlada |
| ¿Qué identificadores son estables? | Parcial: el portal da `gameId=1` y un `pid`; no el `cloudSaveId` | Copia de nube |
| ¿Qué datos detectan conflictos? | No observado | Respuesta de conflicto o metadatos de revisión |
| ¿Hay checksums, firmas o MAC? | **No observado**; `CheckSaveMac` existe en el cliente | Respuesta real o código de `CheckSaveMac` |
| ¿Hay transformación intermedia? | **Hipótesis**: el cliente parsea `JsonPayload.Data` con `ParseJsonToCloudSaveGameData` | Cuerpo real |

## 4. Evidencia relacionada

- El portal oficial devuelve `gameId=1` y un jugador, pero no el contenido del
  guardado. [Adquisición](cloud-save-acquisition.md)
- La metadata del cliente declara `ParseJsonToCloudSaveGameData(string)` y
  `JsonPayload.Data`; la Fase 5.4 confirmó la llamada. Esto sostiene que la
  nube entrega un texto JSON, pero no fija la clave de red ni el envoltorio.
- `LoginApi.CheckSaveMac` sugiere un MAC o comprobación de integridad; no se
  obtuvo su respuesta ni su algoritmo. No se debe asumir que una copia editada
  pasará esa comprobación.

## 5. Resultado

No hay comparación. No se puede afirmar que las secciones locales sean
idénticas a las de nube, ni que `cloudSaveId`/`platformId` sean estables, ni
que no exista una firma. La única afirmación sostenida es que el modelo de 8.8.0
declara las secciones y que el perfil local no contiene la envoltura.

## 6. Limitaciones

- Sin muestra remota, cualquier tabla de “campos idénticos” sería inventada.
- El perfil local es de invitado; la cuenta de nube tiene otra identidad y otro
  `pid`. No se puede comparar el mismo estado sin una descarga.
- El cliente arranca en la configuración arm64 documentada, pero la cuenta de
  laboratorio no tiene progreso y la lectura legacy está vacía; no hay un
  “mismo estado” que comparar con la copia local.

## 7. Conclusión

La comparación local/nube sigue siendo el bloqueo de mayor valor. La Fase 5.7
no lo cierra. El siguiente paso es obtener una copia auténtica y recién
descargada de la cuenta, no reconstruir una “nube sintética” y presentarla como
real.

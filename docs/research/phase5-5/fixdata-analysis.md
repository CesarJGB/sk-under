# `FixData` y migraciones declaradas en 8.8.0

**Resultado: la superficie de migración está identificada; su comportamiento
no se decompiló.** Los métodos `FixData` y `FixDataIfNotExist` existen por
subsistema, y `NewCloudSaveAgent.FixData` devuelve `string`, lo que encaja con
una corrección del JSON antes de parsearlo. El APK protege esos cuerpos con
ACE, así que no se puede afirmar qué campos corrige cada uno.

## 1. Métodos identificados

| Tipo | Método | Token | Params | Retorno |
| --- | --- | --- | ---: | --- |
| `CloudSaveGameData` | `CreateFromPlayerPref` | `0x060072d9` | 0 | `CloudSaveGameData` |
| `CloudSaveGameData` | `CoverPlayerPref` | `0x060072db` | 0 | `void` |
| `AboGameData` | `CreateFromPlayerPref` | `0x0600730a` | 0 | `AboGameData` |
| `AboGameData` | `CoverPlayerPref` | `0x0600730c` | 0 | `void` |
| `AboGameData` | `CoverPlayerPrefSafely` | `0x06007310` | 0 | `void` |
| `RGSaveManager` | `FixData` | `0x060092a2` | 1 | `void` |
| `RGScript.Other.NewCloudSaveAgent` | `FixData` | `0x06021bf5` | 1 | `string` |
| `ItemData` | `FixData` | `0x06007364` | 1 | `void` |
| `ItemData` | `FixDataIfNotExist` | `0x06007365` | 0 | `void` |
| `SettingData` | `FixData` | `0x06007515` | 1 | `void` |
| `SettingData` | `FixDataIfNotExist` | `0x06007516` | 0 | `void` |
| `StatisticData` | `FixData` | `0x0600757c` | 1 | `void` |
| `StatisticData` | `FixDataIfNotExist` | `0x0600757d` | 0 | `void` |
| `MonsterRiseData` | `FixDataIfNotExist` | `0x06007410` | 0 | `void` |
| `SeasonData` | `FixDataIfNotExist` | `0x060074af` | 0 | `void` |
| `ModeSeason.Escape.Scripts.EscapeRunSaveData` | `FixDataIfNotExist` | `0x06019a50` | 0 | `void` |
| `ModeSeason.Escape.Scripts.EscapeSeasonData` | `FixDataIfNotExist` | `0x06019b28` | 0 | `void` |
| `RGScript.WeaponEvolution.WeaponEvolutionData` | `FixDataIfNotExist` | `0x060212aa` | 0 | `void` |
| `RGScript.Data.BattlePassSaveData` | `FixDataIfNotExist` | `0x0602ae0c` | 0 | `void` |
| `RGScript.Data.MiscData` | `FixDataIfNotExist` | `0x0602b518` | 0 | `void` |
| `RGScript.Data.PvpData` | `FixDataIfNotExist` | `0x0602b57c` | 0 | `void` |
| `RGScript.Data.TaskDatas` | `FixDataIfNotExist` | `0x0602b6e0` | 0 | `void` |
| `RGScript.Data.Mall.MallReloadData` | `FixDataIfNotExist` | `0x0602bc19` | 0 | `void` |

`SandboxConfigData`, `SandboxMaps` y `BattleDataList` también tienen ambos
métodos (tokens `0x06001fe6`, `0x06001ff9`, `0x0600729f`).

## 2. Lectura estructural

- `NewCloudSaveAgent.FixData(string) -> string` es el punto más compatible con
  una **corrección textual antes de `ParseJsonToCloudSaveGameData`**.
- `CreateFromPlayerPref()` construye el agregado desde el almacenamiento local;
  `CoverPlayerPref()` lo persiste. Son la frontera entre el modelo y el
  `PlayerPrefs` del cliente.
- `FixDataIfNotExist()` no recibe datos: su nombre sugiere crear la sección si
  falta, no migrar un valor concreto.
- `FixData(bool)` en `RGSaveManager` recibe un booleano; el significado
  (¿forzar? ¿silencioso?) no está verificado.

## 3. Qué no se puede afirmar

No se puede afirmar:

- qué campos añade, elimina o renombra cada `FixData`;
- si `FixData` convierte 8.6.0 en 8.8.0 o solo rellena valores por defecto;
- si el `serialzedVersion` del agregado cambia;
- si una copia editada pasa por `FixData` antes de aplicarse;
- si el cliente acepta un archivo con campos nuevos/desconocidos.

La matriz de campos nuevos en
[`schema-diff-860-880.md`](schema-diff-860-880.md) es el mejor indicio de qué
podría corregir `FixData`, pero **no sustituye** una prueba de restauración.

## 4. Próximo experimento

Con una muestra 8.8.0 real y una copia 8.6.0 del mismo titular:

1. Conservar ambas fuera de Git y calcular SHA-256.
2. Comparar `serialzedVersion`, claves presentes y tipos.
3. Ejecutar el cliente oficial con la copia 8.6.0 y observar si `FixData`
   rellena o rechaza.
4. Documentar el resultado sin publicar valores.

Sin ese par no se implementa una migración destructiva.

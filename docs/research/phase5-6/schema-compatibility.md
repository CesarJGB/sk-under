# Compatibilidad 8.6.0 → 8.8.0 con datos reales

**Resultado:** las nueve estructuras reales de 8.6.0 conservan todas sus claves
superiores en el perfil local real de 8.8.0. Aparecen cinco campos nuevos en
`itemData` y siete en `statisticData`, además de cuatro secciones nuevas
(`game.data`, `setting`, `mall_reload_data` y `escape_season_data`). No se
observó ninguna clave 8.6.0 eliminada. Las diferencias de representación de
colecciones vacías no se interpretan como cambios de tipo del modelo.

## 1. Método

Se compararon:

- las nueve muestras reales 8.6.0, descifradas en Linux con el códec de la Fase
  3;
- el perfil local real 8.8.0 obtenido en la Fase 5.6, descifrado con el mismo
  códec y con la capa XOR de `game.data`;
- la metadata 8.8.0 ya inventariada en la Fase 5.5.

La comparación es de **claves y tipos JSON observados**. No se compararon
valores concretos: los valores y las huellas permanecen privados.

## 2. Resumen por sección

| Sección | Claves 8.6.0 | Claves 8.8.0 | Claves nuevas | Claves 8.6.0 ausentes | Campos declarados 8.8.0 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `gameData` (`AboGameData`) | — | 41 | 41 | — | 41 |
| `itemData` | 77 | 82 | **5** | 0 | 118 |
| `statisticData` | 157 | 164 | **7** | 0 | 171 |
| `seasonData` | 70 | 70 | 0 | 0 | 78 |
| `taskData` | 12 | 12 | 0 | 0 | 16 |
| `settingData` | — | 35 | 35 | — | 47 |
| `miscData` | 17 | 17 | 0 | 0 | 19 |
| `pvpData` | 10 | 10 | 0 | 0 | 12 |
| `monsriseData` | 18 | 18 | 0 | 0 | 23 |
| `battlePassSaveData` | 3 | 3 | 0 | 0 | 5 |
| `weaponEvolutionData` | 4 | 4 | 0 | 0 | 6 |
| `escapeSeasonData` | — | 38 | 38 | — | 42 |
| `mallReloadData` | — | 23 | 23 | — | 28 |
| `sandboxConfig` | — | 3 | 3 | — | — |
| `sandboxMaps` | — | 1 | 1 | — | — |

“Claves nuevas” significa que no aparecían en la muestra 8.6.0 comparada; no
implica que el modelo 8.8.0 las haya añadido todas en esa versión. La tabla de
campos declarados procede de la metadata y sirve para separar “nuevo observado”
de “declarado en el modelo”.

## 3. Campos nuevos observados en `itemData`

Los cinco campos que aparecen en el perfil 8.8.0 y no en la muestra 8.6.0 son:

- `forgeWeaponMaterialPayments`
- `mechInRoomPaymentMaterials`
- `mechInRoomPaymentName`
- `mechInRoomProductId`
- `trainingJourney`

Los cinco están declarados en `ItemData` 8.8.0. La muestra 8.6.0 no los tenía.
No se les asigna un valor por defecto ni se declara que sean obligatorios: son
estructuras observadas en un perfil nuevo.

## 4. Campos nuevos observados en `statisticData`

- `CommonCheckinRecords`
- `KrppCountedOrderIds`
- `KrppVerifiedUsdCents`
- `PaySignInRecords`
- `googlePlayClearedMaps`
- `googlePlayEventCounts`
- `googlePlayHistoricalAchievementsSynced`

Los siete están declarados en `StatisticData` 8.8.0. Varios tienen nombres de
integración con Google Play o con el sistema de pagos; su presencia en un perfil
guest recién creado no demuestra que el cliente los use en todas las cuentas.

## 5. Diferencias de representación, no de tipo

En colecciones vacías se observaron estas diferencias entre la muestra 8.6.0 y
el perfil 8.8.0:

| Campo | 8.6.0 | 8.8.0 | Lectura |
| --- | --- | --- | --- |
| `bpShopOthersPurchaseCounts` | lista | objeto vacío | Representación de colección vacía |
| `seasonData` (BP) | lista de registros | objeto vacío | Representación de colección vacía |
| `Christmas2024RedeemRecords` | lista | objeto vacío | Representación de colección vacía |
| `SchoolRedeemRecords` | lista | objeto vacío | Representación de colección vacía |
| `achieve_record` (pre-login) | lista | objeto vacío | Representación de colección vacía |
| `lastOpenBoxStoreId` y otros | texto | `null` | Campo opcional o valor vacío |
| `_usedEmoji` | lista | objeto vacío | Representación de colección vacía |

**No se declara un cambio de tipo C#.** Un diccionario vacío y una lista vacía
pueden ser dos representaciones del mismo contenedor; sin una muestra 8.8.0 con
entradas no se puede distinguir. El adaptador acepta ambas formas solo cuando la
lista es vacía o cuando sus entradas cumplen el esquema conocido.

## 6. `gameData` y las secciones nuevas

- `game.data` contiene `AboGameData` con 41 claves, exactamente las 41 declaradas
  en metadata. Es JSON UTF-8 con XOR local, no un agregado de nube.
- `setting_<perfil>.data` tiene 35 claves: ajustes, posiciones de controles y
  `ChillyUid`. El adaptador muestra solo los enteros no sensibles y no publica
  el identificador.
- `mall_reload_data_<perfil>.data` tiene 23 claves; los contadores de compras
  son enteros y el objeto de historial está vacío en el perfil nuevo.
- `escape_season_data_<perfil>.data` tiene 38 claves y `version=1`.
- `sandbox_config` y `sandbox_maps` son JSON plano; no usan el códec DES.

## 7. Clasificación de compatibilidad

| Nivel | Qué se puede afirmar |
| --- | --- |
| **Confirmada por prueba real** | El códec local 8.8.0 y el roundtrip binario de 18 archivos; las claves superiores 8.6.0 siguen presentes en el perfil 8.8.0 |
| **Compatible estructuralmente** | Los esquemas 8.6.0 encajan en los modelos 8.8.0 para las nueve secciones; el adaptador acepta ambas versiones de `itemData` (`80300`, `80800`, `0`) |
| **Probable** | Los campos nuevos son parte del modelo 8.8.0 y se emiten en un perfil nuevo; `FixData` podría rellenar campos ausentes |
| **Desconocida** | Aceptación de una copia 8.6.0 por el cliente 8.8.0; valores por defecto; campos declarados que no aparecen en el perfil; `serialzedVersion` de nube |
| **Incompatible** | Ninguna observada en las claves o tipos comparados |

## 8. `FixData` y migración

Siguen identificados `RGSaveManager.FixData(bool)`,
`NewCloudSaveAgent.FixData(string) -> string` y los `FixData`/`FixDataIfNotExist`
por sección. **No se decompiló su cuerpo** ni se observó una migración 8.6.0 →
8.8.0. No se implementa una conversión destructiva ni se rellenan campos nuevos
con valores arbitrarios. La compatibilidad declarada es de esquema y de códec,
no de aceptación por el cliente.

## 9. Pruebas asociadas

- `backend/tests/test_real_save.py`: versiones 80300/80800/0, secciones nuevas,
  rechazo de 80700, `game.data` XOR y exportación intacta.
- `backend/tests/test_private_save_roundtrip.py`: nueve muestras 8.6.0.
- `backend/tests/test_private_880_roundtrip.py`: 18 archivos 8.8.0, incluido
  `game.data`; se ejecuta solo con el entorno privado.
- `backend/tests/test_local_bridge.py`: vectores sintéticos y límites.

Resultado con el entorno privado: **229 passed** (véase el README de la fase).

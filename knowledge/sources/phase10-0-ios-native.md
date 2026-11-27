# Observaciones propias — fase 10.0, iOS nativo

Investigación de solo lectura sobre una cuenta iOS propia, vinculada a una
cuenta ChillyRoom. No se conservan credenciales, tokens, correos, `pid`,
identificadores de dispositivo, distros ni guardados completos en el
repositorio. Las muestras originales permanecen fuera del repositorio.

## Metodología

- El portal oficial resolvió los jugadores de Soul Knight y sus distros.
- El login se realizó contra el gateway oficial con la distribución iOS y la
  versión 8.8.0.13.
- La partida se descargó con `POST /BlobSave/Download`, sin subida ni
  modificación remota.
- La muestra nativa se comparó con la exportación RAW de CRDE de la misma
  cuenta y con dos partidas Android de versiones y progreso distintos.
- Los identificadores publicados son claves de configuración del juego. Los
  identificadores de cuenta se omiten.

## Muestras

| Muestra | Plataforma | `gameVersion` | `itemData.AppVersion` | Tamaño | Secciones |
| --- | --- | ---: | ---: | ---: | ---: |
| Android avanzada | Android | 2145 | ausente | 912.375 B | 14 |
| Android nueva | Android | 2155 | 80800 | 222.148 B | 17 |
| iOS nativa | iOS | 2155 | 1531 | 279.230 B | 17 |
| iOS vía CRDE | iOS | 2155 | 1531 | 235.438 B | 14 + `_crde_misc` |

La muestra iOS nativa conserva `cloudSaveId` con prefijo `IOS_`,
`platformId: "IOS"`, `serialzedVersion: 1` y `maps`. CRDE retira esos cuatro
campos del nivel superior, conserva `platformId` y `maps` en `_crde_misc` y
convierte enteros grandes de tiempo a cadenas
`__CRDE_LARGE_INT64__<valor>`. No se observaron otras diferencias de valores.

## Comparación

- Las secciones de juego son las mismas que Android 8.8.0: `gameData`,
  `itemData`, `statisticData`, `settingData`, `seasonData`, `taskData`,
  `weaponEvolutionData`, `mallReloadData`, `monsterRiseData`,
  `battlePassSaveData`, `pvpData`, `escapeSeasonData` y `miscData`, además de
  `maps`.
- Los catálogos y códigos de personajes, mascotas, planos y objetos son
  compatibles.
- `platformId` y `cloudSaveId` son marcadores de plataforma. `AppVersion` es un
  marcador de compilación.
- Las diferencias de progreso y desbloqueos entre muestras se explican por la
  cuenta, no por la plataforma.
- No se encontró ningún campo de juego exclusivo de iOS en 8.8.0.
- La selección remota de la partida depende del distro, no de la cabecera
  `x-platform`.

## Evidencia

| Observación | Nivel | Alcance |
| --- | --- | --- |
| Estructura de secciones y claves compartida con Android 8.8.0 | E2 | Una cuenta iOS propia, 8.8.0.13 |
| `platformId: "IOS"` y `cloudSaveId` con prefijo `IOS_` | E2 | Muestra nativa |
| `itemData.AppVersion` 1531 en iOS frente a 80800 en Android 8.8.0 | E2 | Una muestra por plataforma |
| Login y descarga directa con distro iOS | E3 | Acción controlada de solo lectura |
| Separación de respaldos por plataforma | E3 | Verificación en vivo |
| Lectura de recursos, personajes, habilidades, skins, mascotas, planos y progreso | E2 | Informe generado |
| Escritura local o remota iOS | H | No probada |
| Semántica de decoraciones y vestíbulo en iOS | H | Pendiente |

## Limitaciones

- No se ha validado ningún candidato de escritura en un dispositivo iOS físico.
- No se ha probado una cuenta que use exclusivamente Apple ID o Game Center.
- El mecanismo interno de CRDE para obtener partidas iOS es desconocido.
- Una sola muestra iOS no permite separar todas las diferencias de versión de
  las de plataforma; la comparación con Android 8.8.0 reduce esa ambigüedad.
- Los niveles E3/E4 de Android no se extrapolan a iOS.
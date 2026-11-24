# Compatibilidad de versiones

| Versión o esquema | Muestras y alcance |
| --- | --- |
| Android 8.5.0 | Versión citada por el autor del tutorial de Discord. Los estados y umbrales del tutorial son E1. |
| Android 8.6.0 | Nueve `.data` de una cuenta privada. Las muestras carecen de `game.data` y PlayerPrefs y sus árboles no contienen los cinco campos de gemas. Se observaron planos con estados de texto, 167 armas de evolución y un registro de pase con `Key`/`Value`. |
| Android Global 8.8.0, `versionCode 1080800` | Guardado local, agregado y preferencias en cuentas propias. Los mapas del inventario pueden estar vacíos. `lastOpenMachineHistoryStr0` es `null` local y puede faltar en nube. |
| Android Global 8.8.0.11 | Hotfix del cliente Global en AVD de laboratorio. Recompensas, gasto, guardado, reinicio y recuperación legítimos documentados en 6.11. |
| SKDFE 8.8.0 | Salida del extractor del commit fijado. Su catálogo describe identificadores de una extracción. La región, la posesión y la disponibilidad por cuenta se comprueban de forma independiente. |
| `serialzedVersion: 1` | Versión de esquema del agregado aceptada para las escrituras de gemas de esta fase. Es una comprobación independiente de la versión comercial del APK. |
| Android Vietnam, TapTap e iOS | No hay equivalencia de PlayerPrefs o persistencia validada para estas distribuciones en esta fase. |

Para una diferencia de versión, registra por separado la ruta de archivo, la versión del APK, el hotfix, el valor `serialzedVersion` y la estructura por capa. Conserva las diferencias de tipo verificadas en el [mapa](save-file-mapping.md) y evita normalizar formatos al reabrir respaldos históricos.

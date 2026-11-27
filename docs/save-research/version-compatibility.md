# Compatibilidad de versiones

| Versión o esquema | Muestras y alcance |
| --- | --- |
| Android 8.5.0 | Versión citada por el autor del tutorial de Discord. Los estados y umbrales del tutorial son E1. |
| Android 8.6.0 | Nueve `.data` de una cuenta privada. Las muestras carecen de `game.data` y PlayerPrefs y sus árboles no contienen los cinco campos de gemas. Se observaron planos con estados de texto, 167 armas de evolución y un registro de pase con `Key`/`Value`. |
| Android Global 8.8.0, `versionCode 1080800` | Guardado local, agregado y preferencias en cuentas propias. El agregado de 114.778 bytes tiene 17 claves superiores: 13 secciones de estado, `maps`, `cloudSaveId`, `platformId` y `serialzedVersion`. Los mapas del inventario pueden estar vacíos. `lastOpenMachineHistoryStr0` es `null` local y puede faltar en nube. `gameData.fishChip` existe como entero y los historiales de fichas están presentes y vacíos en las muestras. |
| Android Global 8.8.0.11 | Hotfix del cliente Global en AVD de laboratorio. Recompensas, gasto, guardado, reinicio y recuperación legítimos documentados en 6.11. |
| SKDFE 8.8.0 | Salida del extractor del commit fijado. Su catálogo describe identificadores de una extracción. La región, la posesión y la disponibilidad por cuenta se comprueban de forma independiente. |
| `serialzedVersion: 1` | Versión de esquema del agregado aceptada para las escrituras de gemas de esta fase. Es una comprobación independiente de la versión comercial del APK. |
| Android Vietnam, TapTap e iOS | No hay equivalencia de PlayerPrefs o persistencia validada para estas distribuciones en esta fase. |
| iOS Global 8.8.0.13 / 8.8.0.14 | Login y descarga verificados con la cuenta iOS autorizada. `8.8.0.14` es la versión visible/compilación; el protocolo BlobSave sigue siendo `8.8.0`. La escritura está en modo experimental: el servidor acepta y persiste el blob, pero la recuperación en el cliente oficial sigue pendiente de la prueba física del propietario. `gameVersion=2155`, `AppVersion=1531`, `serialzedVersion=1`. |

En 8.6.0 los campos de tienda de fichas existen en `item_data` (`fishChipConfigId` y cuatro historiales) aunque no se dispone de `game.data` para comprobar `fishChip`. En 8.8.0 el saldo, los historiales, la preferencia de mobiliario y los contadores de compra se observaron por separado; ninguno tenía un valor positivo en las muestras. La configuración `FishChipStoreConfig.json` del cliente está cifrada y no se interpretó como guardado.

Para una diferencia de versión, registra por separado la ruta de archivo, la versión del APK, el hotfix, el valor `serialzedVersion` y la estructura por capa. Conserva las diferencias de tipo verificadas en el [mapa](save-file-mapping.md) y evita normalizar formatos al reabrir respaldos históricos.

## Registro automático de la Fase 10.3

`backend/app/cloud/compatibility.py` es la fuente única de compatibilidad. No
presupone equivalencias entre estas capas:

- versión comercial de la distribución (Android Global `8.8.0`, iOS Global
  `8.8.0.14`);
- última versión publicada en App Store o Google Play;
- versión de protocolo `x-app-version` / `x-game-version` (`8.8.0`);
- `gameData.gameVersion` (`2155` en iOS);
- `itemData.AppVersion` (`1531` en iOS, `80800` en Android);
- `serialzedVersion` (`1`);
- plataforma (`platformId`) y distribución.

Estados: `compatible`, `experimental`, `new_version_detected`,
`pending_verification` y `read_only`. Solo `compatible` y `experimental`
permiten preparar y escribir; `experimental` exige respaldo, confirmación y
verificación posterior. Una versión nueva o un marcador desconocido queda en
solo lectura y no actualiza los valores de escritura.

La consulta de tiendas es de solo lectura, con caché de 6 horas y timeout de 5
segundos. Un fallo de la tienda se guarda como `unavailable` y nunca se
interpreta como una versión válida. App Store entrega la versión visible; la
ficha actual de Google Play no expone la versión en el HTML sin JavaScript, por
lo que Android puede quedar sin observación automática hasta disponer de una
fuente estable.

Antes de preparar, confirmar o restaurar se ejecuta un preflight que comprueba
cuenta, distribución, plataforma, integridad, esquema, metadatos del original,
catálogos, protocolo validado y hash remoto. El candidato queda vinculado al
hash del original, al hash del plan, a la cuenta y a la versión. Cualquier cambio
invalida el candidato. La restauración exacta del original se permite incluso
si la versión es nueva, siempre que la partida sea legible y no se recomponga
ningún campo.

Procedimiento para una versión futura: descargar una copia autorizada, registrar
las capas por separado, comparar estructura/campos/catálogos, validar el
protocolo real y una escritura pequeña con respaldo y restauración, añadir un
perfil nuevo con fuente/fecha/evidencia y solo entonces actualizar la
distribución. No se cambia `serialzedVersion` para forzar compatibilidad.
Detalle completo en
[`../research/phase10-3/README.md`](../research/phase10-3/README.md).

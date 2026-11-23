# Experimentos de escritura y persistencia

Todos los horarios son UTC. La cuenta es exclusivamente de laboratorio y el propietario autorizó sobrescribirla. Las credenciales se cargaron desde los artefactos privados existentes y nunca se imprimieron.

## 0. Línea base

| Paso | Resultado |
| --- | --- |
| Descarga autenticada desde Linux, Android detenido | `114.778` bytes, 17 secciones, `serialzedVersion=1`, `gameData.gems=1000` |
| SHA-256 del agregado | `eeef81390418a60cf6f4da25932ab93c0ee22bc418eeb60bf595f28f13f6f97c` |
| Copia privada | `original.json`, modo `0400` |
| Candidato de subida | gzip de `17.386` bytes, SHA-256 `6b8dd01126d65366954de17ec4b7728532eb4d589e9f96fde1d43df6f98d9bbc` |

La descarga coincidió byte a byte con la copia de la Fase 6.0.

## 1. Subida idéntica

**Hipótesis:** el contrato reconstruido permite escribir sin `x-request-token`.

**Ejecutado:** `POST /BlobSave/Upload` con el gzip del agregado original y las cabeceras de la sesión.

| Campo | Valor |
| --- | --- |
| Hora | `20:40:08` |
| Estado | `200 OK` |
| Respuesta | `true` |
| Cable | `30` bytes, SHA-256 `0635…ac27` |
| Error de transporte | Ninguno |

**Verificación:** nueva descarga a las `20:40:12`; `114.778` bytes y SHA-256 `eeef…97c`, idéntico al original.

**Conclusión:** la solicitud fue aceptada. Esta prueba por sí sola no distingue una escritura real de un no-op, porque el contenido era idéntico al remoto. Se mantiene como evidencia de aceptación, no como prueba de persistencia.

## 2. Modificación mínima

**Campo elegido:** `gameData.gems`, un entero visible en el panel de nube y en el hall. Se cambió `1000` por `1001`. No se tocaron compras, monedas premium, progreso competitivo ni datos de terceros.

**Construcción:** reemplazo de un solo byte en el agregado original, conservando el resto del documento y su formato. El resultado tiene los mismos `114.778` bytes y un único byte distinto en el desplazamiento `2419`.

| Campo | Valor |
| --- | --- |
| SHA-256 del agregado modificado | `3f4b7617b04da3f1bd3b1b01197c46cf99d6ebd2a048c733d1738657239f492a` |
| Cuerpo gzip | `17.386` bytes, SHA-256 `3de0e59ce3ab9451e9cf149dc9f3e2a8e790bcb40304e39059124b9640012900` |

**Ejecutado:** subida a las `20:40:27` con el mismo contrato.

| Campo | Valor |
| --- | --- |
| Estado | `200 OK` |
| Respuesta | `true` |
| Cable | `30` bytes, mismo SHA-256 `0635…ac27` |

**Verificación:** descarga a las `20:40:31`. Devolvió `3f4b…92a`, exactamente el archivo subido, con `gameData.gems=1001` y los mismos `114.778` bytes.

**Conclusión:** el servidor conservó el contenido transmitido y lo devolvió sin transformarlo. La diferencia byte a byte entre original y descarga es únicamente el dígito modificado.

## 3. Repetición con el código del repositorio

**Ejecutado:** la CLI `python -m app.cloud.blob_roundtrip modified-gems-1001.json --confirm-experimental-write` con `SK_CLOUD_WRITE_EXPERIMENTAL=1` y las credenciales privadas.

| Campo | Valor |
| --- | --- |
| Subida | `200`, `accepted=true`, cuerpo `17.386` bytes |
| Descarga de verificación | `modern-cloud`, `114.778` bytes |
| `matches_uploaded` | `true` |
| SHA-256 remoto | `3f4b…92a` |

Esto demuestra que el transporte implementado en el backend, no solo el script privado, ejecuta la escritura y la comprobación.

## 4. Recuperación con el cliente oficial

Se arrancó el AVD de laboratorio con el cliente 8.8.0 y la sesión conservada. El panel de nube mostró inicialmente «Cloud save not found» mientras cargaba y después la fila superior con **1001** gemas, frente a **1000** en la fila local. Se pulsó **Retrieve Progress**, se aceptó la advertencia de sobrescritura y el panel mostró **1001** en ambas filas.

El registro incluyó `CloudSaveGameData:CoverPlayerPref()` y `CloudSaveRunner:AutoDnloadAsync`. Después de entrar al juego, `game.data` local se decodificó con 41 claves y `gems=1001`, y el hall abrió mostrando **1001** en el contador superior derecho.

Detalle en [cliente oficial](client-validation.md).

## 5. Reproducibilidad y límites

- La respuesta `true` fue idéntica en las tres solicitudes; su valor no transporta una revisión ni un hash.
- No se repitieron solicitudes sin cambios más allá de las necesarias para la comprobación.
- No se probó un rollback del servidor; la copia original se conserva localmente y puede reenviarse.
- La cuenta quedó con `1001` en la nube y en el perfil local. El propietario autorizó este estado.
- No se intentó una segunda modificación ni valores fuera de rango. La aceptación de un entero pequeño no generaliza a otros campos.

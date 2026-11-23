# Roundtrip de la referencia real 8.8.0

**Resultado:** los 18 archivos locales decodificados se reabren y se vuelven a
serializar sin cambios con los mismos bytes (roundtrip binario). Una edición
controlada de `item_data` y de `game.data` conserva los campos no modificados y
vuelve a abrirse con el valor nuevo (roundtrip estructural). **No se probó la
aceptación por el cliente oficial**; por tanto, no se declara compatibilidad de
cliente.

## 1. Tres resultados distintos

| Resultado | Qué significa | Estado |
| --- | --- | --- |
| Roundtrip estructural | El documento interpretado se conserva al reabrir, incluidos los campos desconocidos | Confirmado en laboratorio |
| Roundtrip binario | La copia sin cambios reproduce exactamente los bytes originales | Confirmado en 18/18 archivos |
| Compatibilidad con el cliente | Soul Knight 8.8.0 acepta la copia | **No probado** |

No se usa el segundo para afirmar el tercero.

## 2. Archivos comprobados

Se decodificaron y reabrieron:

- `game.data` (XOR JSON, `AboGameData`, 41 claves);
- `item_data.data` y `item_data_<perfil>.data`;
- `season_data.data` y `season_data_<perfil>.data`;
- `statistic.data` y `statistic_<perfil>.data`;
- `task_<perfil>.data`;
- `setting_<perfil>.data`;
- `misc_data_<perfil>.data`;
- `monsrise_data_<perfil>.data`;
- `pvp_data_<perfil>.data`;
- `bp_data_<perfil>.data`;
- `weapon_evolution_data.data` y `weapon_evolution_data_<perfil>.data`;
- `escape_season_data_<perfil>.data`;
- `mall_reload_data_LOCAL.data` y `mall_reload_data_<perfil>.data`.

Los dos JSON de `sandbox` se copian intactos pero no se interpretan como
secciones del perfil. El sufijo `<perfil>` no se publica.

## 3. Roundtrip binario

Para cada archivo decodificado:

1. se conservó el original;
2. se abrió con `LocalSaveLab.open`;
3. se generó un informe sin cambios;
4. se comparó el SHA-256 de entrada y salida.

Resultado: **18/18 idénticos**. En particular, `game.data` se ofusca con XOR,
se decodifica a JSON, se vuelve a codificar y reproduce los 25 461 bytes
originales. La prueba privada se ejecuta con:

```bash
SK_PHASE56_880_DIR=/ruta/privada/files \
SK_PHASE4_CIPHER_ENV_FILE=/ruta/privada/cipher.env \
  .venv/bin/python -m pytest tests/test_private_880_roundtrip.py -q
```

En el entorno del laboratorio: **5 passed**.

## 4. Roundtrip estructural con edición

Se probaron dos ediciones de laboratorio:

| Archivo | Ruta | Antes | Después | Resultado |
| --- | --- | --- | --- | --- |
| `item_data` | `cumulativeFishCount` | valor original | entero grande `2^60` | Reabre; campos desconocidos intactos |
| `item_data` | `trainingJourney.revision` | entero original | `5` | Reabre; resto intacto |
| `game.data` | `gems` | valor original | valor + 1 | Reabre; 40 claves restantes intactas |

En ambos casos:

- el original no cambió;
- el diff binario registra el primer byte distinto;
- el diff semántico solo contiene la ruta solicitada;
- los campos desconocidos se conservan;
- la copia generada se vuelve a identificar con el mismo esquema y la misma
  versión.

La edición es de **laboratorio**. No se habilitó en las rutas HTTP de producción
ni se declara que el juego la acepte.

## 5. Qué se preserva

- Claves desconocidas de nivel superior y anidadas; las ediciones se limitan a valores escalares, no a reemplazar objetos completos.
- Enteros grandes de 53+ bits (se serializan como enteros JSON, sin pasar por
  coma flotante).
- Listas y diccionarios anidados.
- El orden de las claves no se impone; el roundtrip binario solo se garantiza
  cuando no hay cambios y se devuelve el original.
- El marcador de versión y los identificadores no se editan.

## 6. Límites

- No hay `CloudSaveGameData` completo: faltan `serialzedVersion`,
  `cloudSaveId` y `platformId`.
- No se verificó el checksum/MAC que pueda usar el proveedor.
- No se ejecutó `FixData`.
- No se restauró una copia editada en el cliente oficial.
- La edición de `game.data` está limitada a las rutas existentes y a los tipos
  originales; no crea campos nuevos.

## 7. Pruebas públicas

`backend/tests/test_local_bridge.py` reproduce el roundtrip y la edición con
vectores sintéticos; `backend/tests/test_real_save.py` prueba las rutas HTTP con
secciones 8.8.0 sintéticas y `game.data` XOR. Las pruebas privadas solo se
ejecutan cuando el entorno define `SK_PHASE56_880_DIR` y
`SK_PHASE4_CIPHER_ENV_FILE`.

## 8. Conclusión

El sistema puede importar, interpretar y reconstruir sin pérdida estructural la
referencia local 8.8.0. No puede declarar todavía que una copia editada sea
aceptada por el cliente ni que el agregado de nube esté completo.

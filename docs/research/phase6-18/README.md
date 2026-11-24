# Fase 6.18 — Habilidades confirmadas y editor experimental de skins

**Estado:** el desbloqueo de habilidades queda **confirmado por el propietario**
para el alcance probado (E3). El desbloqueo de skins se publica como
**Experimental · E2**; la comprobación en el cliente oficial y en un dispositivo
Android físico sigue pendiente y no se declara completada.

## 1. Alcance y resultado

Esta fase tiene dos entregas independientes:

1. **Consolidación de habilidades.** Se retira la etiqueta experimental de la
   interfaz, se actualiza la política interna a `confirmed_by_owner`, se eleva
   la evidencia a E3 y se documenta la prueba real del propietario. La
   implementación funcional de `gameData.heroSkillUnlock` **no cambia**.
2. **Desbloqueo de skins.** Se añade un editor para activar skins existentes de
   `gameData.skinLock`, con selección individual, por personaje, entre
   personajes y masiva, respaldo cifrado, confirmación explícita, verificación
   por descarga y restauración.

No se extrapola la evidencia de habilidades a skins. Tampoco se extrapola la
evidencia de personajes o habilidades a todos los valores de `skinLock`.

| Campo | Política | Nivel | Alcance |
| --- | --- | --- | --- |
| `gameData.heroUnlock` | `confirmed_by_owner` | E3 | Desbloqueo masivo, subida, recuperación y visibilidad en Android físico; sin prueba de persistencia posterior |
| `gameData.heroSkillUnlock` | `confirmed_by_owner` | E3 | Habilidades pendientes seleccionadas, edición, subida, recuperación y disponibilidad comprobada en Android físico; sin prueba de persistencia posterior |
| `gameData.heroSkill` | solo lectura | E2 | Se conserva sin cambios; sigue siendo una hipótesis de habilidad equipada |
| `gameData.skinLock` | `experimental` | E2 | Solo cambia a `1` posiciones existentes seleccionadas; sin validación física |
| `gameData.currentSkinDatas` | solo lectura | E2 | Selección registrada dispersa; no se usa como prueba de posesión ni se modifica |

## 2. Confirmación de habilidades

En un dispositivo Android físico, con el cliente oficial y la versión 8.8.0, el
propietario:

- descargó la partida actual desde SK-Under;
- seleccionó **todas las habilidades pendientes** en el editor;
- revisó y aplicó la edición;
- subió la partida modificada a la nube;
- recuperó la partida desde el cliente oficial en Android;
- comprobó dentro del juego que todas las habilidades seleccionadas aparecían
  disponibles.

La implementación de habilidades no se modificó en esta fase: solo cambiaron
la etiqueta de la interfaz, la política interna, el nivel de evidencia y la
documentación. **No** se realizó una prueba de persistencia después de guardar
de nuevo desde el cliente oficial; por eso la evidencia es E3 y no E4.

## 3. Evidencias y muestras utilizadas

Se reutilizaron las muestras auténticas y los catálogos de las fases anteriores:

- partida local auténtica de Android Global 8.8.0, descifrada y sin modificar;
- agregado de nube de la misma cuenta, conservado en el almacén privado del
  propietario;
- capturas de PlayerPrefs de Android Global 8.8.0;
- catálogo empaquetado `backend/app/catalogs/characters-880.json`;
- recursos del APK 8.8.0, inspeccionados de forma estática y sin modificar el
  APK, el cliente ni sus archivos.

No se incluyen credenciales, tokens, identificadores de cuenta ni contenidos
privados en este repositorio. Las muestras completas permanecen fuera del
control de versiones.

### Investigación de configuración del APK

Se extrajeron los `TextAsset` de `config.ab` y se descifraron con la clave XOR
repetida `soulKnight` (10 bytes). Los archivos resultantes son CSV de Luban:

- `skins.txt` contiene solo `Key,ControllerPath`; por ejemplo
  `skin/character/knight/skin_0` → `Skin/Character/Knight/Skin_0/skin.controller`.
  No contiene precio, condición de desbloqueo ni estado de posesión.
- `characters.txt` contiene estadísticas base.
- `decorate_skins.txt` contiene 29 skins de decoración del salón, taller, jardín
  y zona mágica, no skins de personaje.
- `luban_config.ab` no se pudo descifrar con la misma clave; su contenido tiene
  alta entropía y no se identificó un flujo zlib/gzip/bz2/lzma. No se usó para
  inventar campos ni valores.
- Los bundles `character_drawing/<personaje>/skin_<N>.ab` contienen recursos
  visuales, no configuración de desbloqueo.
- El metadata de IL2CPP confirma símbolos como `CheckSkinIsUnlock`,
  `GetCurrentSkin`, `SkinData`, `skinLock`, `currentSkinDatas`, `BuySkin`,
  `unlock_by_obtain`, `unlock_by_blueprint`, `unlock_by_activity`,
  `unlock_by_season_task` y `unlock_in_egg_machine`. Estos nombres indican que
  existen distintas condiciones de desbloqueo, pero no permiten asignar una
  condición fiable a cada skin desde la partida.

La inspección fue de solo lectura. No se modificó el APK, no se parcheó el
cliente, no se usaron PlayerPrefs como vía de escritura y no se recurrió a
herramientas externas de edición.

## 4. Estructura de `gameData.skinLock`

Objeto con un código de personaje por clave. Cada valor es una lista de
entradas:

```json
{
  "Knight": [
    { "Key": 0, "Value": 1 },
    { "Key": 1, "Value": 0 },
    { "Key": 2, "Value": 12000 }
  ]
}
```

Observaciones en la muestra local 8.8.0:

- 42 personajes y 802 entradas en total.
- Cada lista tiene claves `Key` secuenciales `0..N-1`, sin huecos.
- `Key` coincide con el índice de la skin dentro del personaje en el catálogo.
- `Value` es un entero, no un booleano.
- 43 entradas valen `1`: las 42 skins `Key=0` (la skin inicial de cada
  personaje) y `Warlock` `Key=3` (`Possessed Girl`).
- Las 759 entradas restantes no valen `1`.
- No se observaron códigos de personaje desconocidos, claves duplicadas ni
  entradas con tipos distintos en las muestras.

Distribución completa de `Value` en la muestra local:

| Valor | Entradas | Interpretación usada |
| --- | ---: | --- |
| `1` | 43 | Desbloqueada (hipótesis E2) |
| `0` | 221 | Estado bruto; no se reinterpreta |
| negativos | 371 | Condiciones especiales sin identificar |
| positivos distintos de `1` | 167 | Posibles precios o condiciones; no se reinterpretan |

Valores negativos observados: `-1` (10), `-2` (1), `-3` (4), `-4` (9),
`-5` (28), `-6` (112), `-7` (1), `-8` (12), `-10` (25), `-12` (3),
`-13` (146), `-15` (1), `-16` (1), `-19` (8), `-20` (10).

Valores positivos distintos de `1` observados: `233` (1), `2000` (20),
`4000` (1), `5000` (15), `6000` (3), `8000` (14), `9999` (9),
`10000` (12), `11999` (1), `12000` (59), `15000` (17), `16000` (10),
`18000` (5).

La única interpretación aplicada por el editor es:

```text
Value == 1  →  skin desbloqueada
Value != 1  →  skin pendiente o estado desconocido; no se modifica salvo selección
```

Esta interpretación es **E2**, no una semántica confirmada. Es coherente con que
las 42 skins iniciales estén en `1`, pero no demuestra que todos los valores
`0`, negativos o positivos signifiquen lo mismo ni que cambiar un valor especial
a `1` reproduzca la vía legítima de desbloqueo.

## 5. `gameData.currentSkinDatas`

Es un diccionario disperso de código de personaje a índice de skin. En la
muestra local está vacío. En el agregado de nube de la fase 5.8 aparecen seis
entradas:

```text
Assassin=19, Elves=13, Joker=0, Paladin=19, Taoist=13, Viking=20
```

En esa muestra esos personajes estaban bloqueados en `heroUnlock`. Por tanto,
`currentSkinDatas` no demuestra posesión ni que la skin esté equipada
actualmente; puede representar la última selección, una vista previa o un
estado de interfaz. El editor **nunca modifica** este campo y no lo usa para
decidir qué skins desbloquear.

## 6. Catálogo y correspondencia

El catálogo empaquetado declara 8.8.0, 42 personajes, 105 habilidades y 802
skins. Cada skin tiene:

```json
{ "index": 0, "key": "c0_skin0", "name": "Knight" }
```

La correspondencia usada es:

```text
código estable del personaje → entrada del catálogo → índice de skin → nombre/clave
```

Comprobaciones de la fase:

- 42 códigos de personaje en catálogo y partida, sin diferencias.
- 802 skins de catálogo y 802 posiciones de `skinLock`.
- Para cada personaje, las claves de la partida son exactamente
  `0..len(skins)-1`.
- No hay claves de catálogo repetidas dentro de un personaje.
- No hay personajes del catálogo ausentes de la partida ni viceversa.

Una skin del catálogo tiene un nombre vacío: `Joker` `c34_skin1`. El backend
acepta el nombre vacío como dato real; la interfaz muestra la clave
`c34_skin1` y avisa de que el catálogo no trae nombre. No se inventa un nombre.

PlayerPrefs replica las 802 claves con el patrón `c<ID>_skin<N>` y los mismos
enteros. Se usó solo como evidencia de estructura; la escritura se realiza
sobre el agregado de nube, no sobre PlayerPrefs.

### Recursos visuales

No se encontró una correspondencia fiable entre cada skin del catálogo y una
imagen concreta. `skins.txt` solo aporta rutas de controladores y los bundles de
dibujo contienen recursos internos. Por eso la interfaz usa un marcador neutral
`◇` y muestra el nombre, personaje, índice, clave y estado. No se inventan
imágenes, rutas ni nombres.

## 7. Compatibilidad y exclusiones

| Clasificación | Cantidad | Decisión |
| --- | ---: | --- |
| Estructura válida en catálogo y partida | 802 | Se pueden seleccionar si están pendientes |
| Incompatibles por estructura | 0 | No se crean posiciones |
| Ya desbloqueadas (`Value=1`) | 43 | No se modifican ni se vuelven a bloquear |
| Pendientes (`Value!=1`) | 759 | Seleccionables bajo hipótesis E2 |
| Condiciones especiales no identificadas | 759 posibles | No se garantiza el desbloqueo; el editor solo cambia el valor de posesión |

No se excluyó estructuralmente ninguna skin porque las 802 posiciones existen y
tienen el tipo esperado. Sin embargo, **no se afirma** que las 759 pendientes
sean desbloqueables de forma independiente ni que todas compartan el mismo
mecanismo. Las skins ligadas a eventos, compras, planos, actividades, temporadas
o máquinas de huevos quedan fuera de la garantía funcional. El editor no
aproxima campos de precio, planos, eventos ni recibos: solo cambia a `1` la
posición de propiedad existente.

Casos especiales documentados:

- **Skins iniciales:** `Key=0` en los 42 personajes, ya `1`; se conservan.
- **Warlock `Key=3`:** única skin no inicial observada con `1`; se conserva.
- **Variantes visuales:** el catálogo puede incluir variantes o packs; no se
  asume que cada entrada sea una compra independiente.
- **Personaje bloqueado:** la skin puede prepararse, pero la interfaz avisa de
  que `heroUnlock` no se modifica y el personaje podría no estar utilizable.
- **Valores negativos o positivos:** se conservan y no se convierten a `1`
  salvo que el usuario seleccione explícitamente esa skin.

## 8. Implementación backend

### Endpoint

```http
POST /api/v1/cloud/native/prepare-skins
Content-Type: application/json

{
  "skins": [
    { "code": "Knight", "index": 1 },
    { "code": "Ranger", "index": 1 }
  ],
  "source_sha256": "<sha256 de la descarga actual>"
}
```

La respuesta reutiliza el sobre existente:

- `field`: `gameData.skinLock`;
- `original_unlocked_count`, `new_unlocked_count`, `total_skins`;
- `selected_skins`, `newly_unlocked_skins`;
- `affected_codes`, `locked_character_codes`;
- `backup` con `field: "skins"` y `skin_selections: [{code,index}]`;
- `changed_fields`, `byte_diff` y SHA-256 del candidato;
- `experimental: true`;
- `validation.only_skins_changed: true`;
- `validation.evidence_level: "E2"`.

La confirmación, verificación y restauración reutilizan `/confirm`, `/verify` y
`/restore`. Los resultados incluyen `remote_skins`.

### Cambio aplicado

Para cada selección válida:

```text
gameData.skinLock[código][índice].Value = 1
```

Solo si la entrada ya existe y su `Key` coincide con el índice del catálogo. En
caso contrario se rechaza la operación; no se crean listas, entradas ni claves.

Se conservan sin cambios:

- `gameData.currentSkinDatas`;
- `gameData.heroUnlock`;
- `gameData.heroLevel`;
- `gameData.heroSkill` y `gameData.heroSkillUnlock`;
- recursos, materiales, semillas, mascotas, planos y cualquier otro campo;
- todas las skins no seleccionadas, incluidas las ya desbloqueadas.

### Validaciones

El editor rechaza de forma controlada:

- selección vacía, duplicada o con más de 802 posiciones;
- personaje desconocido;
- índice inexistente para ese personaje;
- `skinLock` ausente o con estructura incompatible;
- listas o entradas incompletas;
- `Key` no entero, negativo, repetido o no perteneciente al catálogo;
- `Value` no entero o booleano;
- códigos de personaje no presentes en el catálogo;
- catálogo ausente, corrupto o inválido;
- borrador obsoleto que ya no reproduce el candidato.

Códigos principales: `invalid_skin_selection`, `unknown_skin_character`,
`unknown_skin_index`, `skin_field_missing`, `incomplete_skin_structure`,
`unsupported_skins_structure`, `skin_catalog_missing`,
`skin_verification_failed`, `outdated_skin_draft`.

### Idempotencia y respaldo

Si todas las posiciones seleccionadas ya valen `1`, el candidato es byte a byte
igual al original, `changed` es `false` y no se permite confirmar una subida.
El respaldo cifrado guarda la selección `{code,index}`; la restauración
reproduce el candidato desde el original y exige coincidencia de bytes y
SHA-256. La comprobación inversa restaura el mapa original de `skinLock` y
verifica que el agregado vuelve a ser idéntico al descargado.

## 9. Interfaz

La sección **Skins** aparece después de **Habilidades** y antes del informe de
solo lectura.

Incluye:

- resumen de skins identificadas, desbloqueadas, pendientes, selección
  registrada, incompatibles (solo si existen) y personajes con datos;
- búsqueda por nombre de personaje, nombre de skin, código o clave;
- filtros por pendientes, desbloqueadas, personaje bloqueado e incompatibles;
- tarjetas desplegables por personaje;
- renderizado diferido: las filas de una tarjeta solo se montan al abrirla, para
  no crear 802 filas de golpe en móvil;
- casilla individual solo para skins pendientes y compatibles;
- botón para seleccionar todas las pendientes compatibles de un personaje;
- acciones globales para seleccionar todas las pendientes, deseleccionar y
  preparar el desbloqueo;
- nombre, personaje, índice, clave, valor observado, estado y compatibilidad por
  skin;
- aviso cuando la selección incluye personajes bloqueados;
- resumen previo con skins nuevas, personajes afectados, nombres, campos y
  aviso **Experimental E2**;
- confirmación explícita, subida, verificación y restauración mediante el flujo
  existente.

La sección de habilidades ya no muestra **Experimental · E2** ni el aviso de
validación pendiente. Muestra la confirmación del propietario y aclara que la
evidencia es E3 y que no se probó persistencia posterior. La sección de skins
mantiene su etiqueta E2 independiente y no se presenta como confirmada.

## 10. Pruebas

### Backend

```bash
cd backend
uv run --locked pytest -q
```

Cobertura añadida:

- lectura de las 802 skins de los 42 personajes;
- desbloqueo individual, múltiple, por personaje y masivo;
- conservación de skins ya desbloqueadas, incluida Warlock `Key=3`;
- conservación de `currentSkinDatas`, `heroUnlock`, habilidades, niveles y
  recursos;
- personajes bloqueados reportados sin modificar `heroUnlock`;
- rechazo de selecciones vacías, duplicadas, desconocidas o fuera del catálogo;
- campo ausente, estructura incompleta, tipos incorrectos, claves repetidas,
  `Value` booleano y catálogo ausente;
- idempotencia, borrador obsoleto y reproducción inversa byte a byte;
- respaldo, confirmación, verificación, restauración e integridad del registro;
- rutas nativas `/prepare-skins` y políticas de escritura;
- regresiones de personajes, habilidades, gemas y fichas.

Resultado final de la ejecución de cierre: **572 passed, 16 skipped**.

### Frontend

```bash
cd frontend
npm run build
npx playwright test
```

La compilación TypeScript/Vite debe finalizar sin errores. Las pruebas de
Playwright cubren:

- resumen y contadores de skins;
- búsqueda por nombre de skin y personaje;
- filtros por estado e incompatibilidad;
- tarjetas cerradas sin filas montadas;
- selección individual, por personaje y global;
- deselección y preparación masiva;
- resumen previo, confirmación, subida y verificación;
- conservación y aviso de `currentSkinDatas`;
- ausencia de la etiqueta experimental en habilidades y presencia de la
  confirmación E3;
- diseño móvil sin desbordamiento horizontal.

Resultado de cierre: **46 pruebas de Playwright aprobadas**.

### Imagen Docker

```bash
cd backend
docker build -t sk-under-backend:phase6-18 .
docker run --rm -e PYTHONPATH=/app -v "$PWD/tests:/check:ro" \
  --entrypoint python sk-under-backend:phase6-18 /check/verify_image_catalog.py
```

La imagen validó 42 personajes, 105 habilidades y 802 skins con el catálogo
empaquetado, incluyendo el nombre vacío real de Joker, y ejecutó la preparación
individual, múltiple y masiva de skins y los rechazos de estructura y catálogo.
El script terminó con `VALIDACIÓN DE IMAGEN COMPLETA: OK`, se ejecutó con
`uid=10001` y no dependió de archivos fuera de la imagen.

## 11. Limitaciones pendientes

- La semántica de `Value=1` es una hipótesis E2; no se ha confirmado con una
  skin individual en el cliente oficial.
- No se ha probado el desbloqueo de skins en Android físico ni la persistencia
  tras guardar de nuevo desde el cliente.
- No se distingue con fiabilidad una skin de evento, compra, plano, actividad,
  temporada o máquina de huevos; el editor no implementa esos mecanismos.
- `currentSkinDatas` no se interpreta como equipo actual ni como posesión.
- No hay imágenes de catálogo asociadas de forma fiable; se usa un marcador
  neutral.
- No se editan niveles, habilidades, personajes, mascotas, materiales, semillas,
  precios, recibos ni estados comerciales.
- El nombre vacío de Joker se conserva tal cual; no se completa con una
  invención.

## 12. Validación manual en Android

Para comprobar el desbloqueo de skins y su persistencia:

1. Abre SK-Under en el móvil y entra en **Partida**.
2. Inicia sesión con la cuenta de prueba y descarga la partida actual.
3. Genera y conserva un respaldo antes de modificar.
4. Abre el editor y localiza **Skins**.
5. Revisa el resumen: skins identificadas, desbloqueadas, pendientes y
   selección registrada. Comprueba que las skins iniciales aparecen
   desbloqueadas.
6. Selecciona una skin pendiente individual; prueba también una selección por
   personaje y una selección masiva. Revisa el aviso si el personaje está
   bloqueado.
7. Pulsa **Preparar desbloqueo de skins seleccionadas**.
8. Revisa el resumen: skins que se desbloquean, personajes afectados, campos y
   conservación de `currentSkinDatas`, personajes, habilidades y niveles. El
   aviso debe seguir indicando **Experimental E2**.
9. Marca la confirmación explícita y pulsa **Desbloquear skins y verificar**.
   Debe aparecer que la nube conserva la copia modificada.
10. Cierra la sesión de SK-Under, abre Soul Knight y recupera la partida desde la
    nube con el cliente oficial.
11. Comprueba dentro del juego que las skins seleccionadas aparecen disponibles.
12. Equipa una de las skins recién desbloqueadas.
13. Úsala en una partida y vuelve a guardar desde el cliente oficial.
14. Recupera de nuevo la partida en SK-Under y verifica que el desbloqueo y la
    skin equipada persisten.
15. Si algo falla, vuelve a **Partida**, localiza el respaldo de skins y usa
    **Restaurar**.

Registra versión del juego, cuenta, personaje y skins probadas, si aparecieron
en el cliente, si se pudieron equipar y usar en una partida, y si el cambio
persistió tras guardar de nuevo. **No se declara esta prueba como superada hasta
que el propietario la confirme.**
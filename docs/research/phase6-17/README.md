# Fase 6.17 — Personajes confirmados y editor experimental de habilidades

**Estado:** personajes confirmados por el propietario para el alcance probado;
editor de habilidades publicado originalmente como **Experimental · E2**.

> **Actualización de la Fase 6.18:** el propietario confirmó el desbloqueo de
> habilidades en un dispositivo Android físico con el cliente oficial. La
> política pasa a `confirmed_by_owner` y la evidencia a E3; no se declara E4
> porque falta una prueba de persistencia posterior. La implementación
> funcional documentada aquí no cambió. Consulta
> [la Fase 6.18](../phase6-18/README.md).

## 1. Alcance y resultado

Esta fase tiene dos entregas independientes:

1. **Consolidación de personajes.** Se retira la etiqueta experimental de la
   interfaz, se actualiza la política interna a `confirmed_by_owner` y se
   registra la evidencia del propietario. La implementación funcional de
   `gameData.heroUnlock` no cambia.
2. **Desbloqueo de habilidades.** Se añade un editor para activar habilidades
   existentes en `gameData.heroSkillUnlock`, con selección individual, múltiple
   por personaje, múltiple entre personajes y masiva, respaldo cifrado,
   confirmación explícita, verificación por descarga y restauración.

La evidencia de personajes no se extrapola a habilidades. Son dos políticas
distintas:

| Campo | Política | Nivel | Alcance |
| --- | --- | --- | --- |
| `gameData.heroUnlock` | `confirmed_by_owner` | E3 | Desbloqueo masivo, subida y recuperación en Android físico; visibles en el cliente oficial |
| `gameData.heroSkillUnlock` | experimental | E2 | Estructura observada y pruebas automatizadas; sin prueba del propietario en el juego |
| `gameData.heroSkill` | solo lectura | E2 | Se conserva sin cambios; hipótesis de habilidad equipada |

## 2. Evidencias utilizadas

### Partidas y capturas

- Partida local auténtica 8.8.0:
  `/home/cesar/sk-under-private/phase5-6/authentic-880/final/decrypted/game.data.json`.
- Agregado de nube:
  `/home/cesar/.config/sk-under/phase5-8/memory-cloud-aggregate.json`.
- Capturas de PlayerPrefs:
  `/home/cesar/.config/sk-under/phase6-4/playerprefs.xml` y
  `/home/cesar/.config/sk-under/phase5-9/shared_prefs/com.ChillyRoom.DungeonShooter.v2.playerprefs.xml`.
- Muestras descargadas y restauradas en `/tmp/sk57avd/` durante fases
  anteriores.

Las muestras contienen `heroUnlock`, `heroLevel`, `heroSkill` y
`heroSkillUnlock` con los 42 códigos. No se encontró ninguna partida con una
segunda habilidad desbloqueada ni ninguna prueba controlada de cambio de
habilidad equipada.

### Catálogo

`backend/app/catalogs/characters-880.json` es la fuente única. Declara la
versión 8.8.0, 42 personajes, 105 habilidades y 802 skins. El catálogo de
habilidades se amplió en su día desde SKDFE 8.8.0 y no se inventaron códigos ni
índices en esta fase.

### Confirmación del propietario

En un dispositivo Android físico, con la versión desplegada de la fase 6.16:

- el catálogo local de personajes funcionó en producción;
- la selección masiva de personajes funcionó;
- se desbloquearon todos los personajes faltantes de una cuenta;
- la partida modificada se subió correctamente a la nube;
- el cliente oficial recuperó la partida;
- todos los personajes aparecieron desbloqueados dentro del juego.

Esta evidencia confirma `heroUnlock` y el flujo de subida/recuperación. **No**
incluye una prueba de persistencia posterior tras guardar de nuevo desde el
cliente oficial; por eso el nivel es E3 y no E4.

## 3. Estructura de los campos

### `gameData.heroSkillUnlock`

Objeto con un código de personaje por clave. Cada valor es una lista de
entradas:

```json
{
  "Knight": [
    { "Key": 0, "Value": true },
    { "Key": 1, "Value": false },
    { "Key": 2, "Value": false }
  ]
}
```

Observaciones en 8.8.0:

- 105 entradas en total.
- 28 personajes con 3 habilidades, 7 con 2 y 7 con 1.
- `Key` es el índice de habilidad del catálogo para ese personaje.
- `Value` es booleano: `true` = disponible, `false` = bloqueada.
- En todas las muestras, solo `Key=0` es `true` para cada personaje: 42
  verdaderas, 35 falsas en `Key=1` y 28 falsas en `Key=2`.
- No hay claves adicionales, personajes desconocidos ni valores no booleanos en
  las muestras.
- PlayerPrefs contiene exactamente 105 claves
  `c_<código>_skill_<N>_unlock` con la misma distribución.

No se asume que todos los personajes tengan tres habilidades. El editor usa la
cantidad real del catálogo.

### `gameData.heroSkill`

Objeto de 42 códigos con un entero por personaje. En todas las muestras vale 0,
que coincide con el índice de la primera habilidad del catálogo. La hipótesis
principal es que representa la habilidad equipada, pero no se observó un cambio
controlado. El editor **no lo modifica** y exige que permanezca idéntico.

### Correspondencia de habilidades

La correspondencia usada es:

```text
personaje (código estable) → entrada del catálogo → índice de habilidad → nombre
```

El índice de la lista de `heroSkillUnlock` coincide con el índice del catálogo.
El nombre se obtiene del catálogo empaquetado, nunca de una etiqueta genérica
inventada por la interfaz.

Personajes con cantidades especiales verificadas:

| Personajes | Habilidades |
| --- | --- |
| 28 personajes, incluido Knight | 3 |
| Transcendent, Ninja, Fighter, Joker, Bard, Shooter, Captain | 2 |
| Envoy, Beheaded, SpecialForces, AiGirl, YinYang, GunsExpert, LadyChef | 1 |

## 4. Campos modificados

La operación solo escribe:

```text
gameData.heroSkillUnlock.<código>[<índice>].Value = true
```

para posiciones que ya existen y que el catálogo declara para ese personaje.

No se crean:

- personajes ausentes del mapa;
- listas de habilidades ausentes;
- entradas `{Key, Value}` ausentes;
- claves de habilidad que no estén en el catálogo.

`gameData.heroSkill`, `heroUnlock`, `heroLevel`, `skinLock`,
`currentSkinDatas`, recursos, materiales y el resto del agregado se conservan.
La comprobación inversa restaura el mapa original de habilidades y exige que el
agregado vuelva a ser idéntico byte a byte al descargado.

## 5. Backend

### Endpoint

```http
POST /api/v1/cloud/native/prepare-skills
Content-Type: application/json

{
  "skills": [
    { "code": "Knight", "index": 1 },
    { "code": "Transcendent", "index": 1 }
  ],
  "source_sha256": "<sha256 de la descarga actual>"
}
```

La respuesta sigue el mismo sobre que personajes, fichas y gemas:

- `field`: `gameData.heroSkillUnlock`;
- `original_unlocked_count`, `new_unlocked_count`, `total_skills`;
- `selected_skills`, `newly_unlocked_skills`, `affected_codes`;
- `backup`: respaldo cifrado con `field: "skills"` y
  `skill_selections: [{code,index}]`;
- `changed_fields`;
- `experimental: true`;
- `validation.evidence_level: "E2"`;
- `byte_diff` y SHA-256 del candidato.

La confirmación, verificación y restauración reutilizan `/confirm`, `/verify` y
`/restore`. Los resultados incluyen `remote_skills` con el número de habilidades
disponibles tras la operación.

### Validaciones

El editor rechaza de forma controlada:

- selección vacía, duplicada o con más de 105 posiciones;
- personaje desconocido;
- índice inexistente para ese personaje;
- `heroSkillUnlock` ausente o con estructura incompatible;
- listas o entradas incompletas;
- `Key` no entero/no booleano, `Value` no booleano o claves repetidas;
- catálogo ausente, corrupto o inválido;
- borrador obsoleto que ya no reproduce el candidato.

Códigos de error principales: `invalid_skill_selection`,
`unknown_skill_character`, `unknown_skill_index`, `skill_field_missing`,
`incomplete_skill_structure`, `unsupported_skills_structure`,
`skill_catalog_missing`, `skill_verification_failed`,
`outdated_skill_draft`.

### Idempotencia

Si todas las posiciones seleccionadas ya están disponibles, el candidato es
byte a byte igual al original, `changed` es `false` y no se puede confirmar una
subida. Repetir una operación ya aplicada no crea un cambio adicional.

## 6. Interfaz

La sección **Habilidades** aparece dentro del editor de partidas, después de
**Personajes**.

Incluye:

- resumen de habilidades conocidas, desbloqueadas, bloqueadas, equipadas y
  personajes con datos;
- búsqueda por nombre o código de personaje;
- filtros por habilidades pendientes, disponibles, personajes bloqueados y
  datos incompletos;
- tarjetas desplegables por personaje con nombre, estado del personaje,
  disponibilidad `x / total`, nombre y estado de cada habilidad;
- casilla individual solo para habilidades bloqueadas con dato observado;
- botón para seleccionar todas las bloqueadas de un personaje;
- acciones globales para seleccionar todas las bloqueadas, deseleccionar y
  preparar el desbloqueo;
- aviso específico cuando la selección incluye habilidades de un personaje que
  todavía aparece bloqueado. La sección no modifica `heroUnlock`;
- resumen previo con personajes afectados, habilidades, cantidad de
  modificaciones, campos y aviso E2;
- confirmación explícita, subida, verificación y restauración mediante el flujo
  existente.

La sección de personajes ya no muestra la etiqueta **Experimental · E2** ni el
aviso de validación pendiente. Muestra la confirmación del propietario y separa
explícitamente esa evidencia de la persistencia posterior aún no probada. La
sección de habilidades conserva su propia etiqueta E2 independiente.

## 7. Decisiones técnicas

- **Solo `heroSkillUnlock`.** No se identificó ninguna dependencia adicional
  necesaria. `heroSkill` se conserva porque no hay evidencia de que sea
  necesario modificarlo y porque cambiar la habilidad equipada está fuera del
  alcance.
- **No crear estructuras.** Una posición ausente se considera estructura
  incompleta. Crear entradas especulativas podría producir un guardado que el
  cliente no entienda.
- **Catálogo como autoridad de índices, no de posesión.** El catálogo dice qué
  habilidades existen; no demuestra que una cuenta las tenga.
- **Conservar posiciones extra.** Si una partida contiene códigos o claves
  adicionales no reconocidos, se conservan; nunca se eliminan.
- **Personajes bloqueados.** Se permite preparar sus habilidades, pero se avisa
  claramente de que esta sección no desbloquea al personaje. No se modifica
  `heroUnlock` de forma silenciosa.
- **Respaldo y reproducción.** El respaldo guarda la selección exacta
  `{code,index}`. Al restaurar o verificar, el candidato se reproduce desde el
  original y se compara por SHA-256 y por bytes.
- **Catálogo empaquetado.** Se reutiliza el catálogo de `app/catalogs`, incluido
  en la imagen con `COPY app/ ./app/`. No hay dependencias de `docs/`, archivos
  externos, variables de entorno ni pasos manuales de Coolify.

## 8. Pruebas ejecutadas

### Backend

```bash
cd backend
uv run --locked pytest -q
```

Resultado real: **554 passed, 16 skipped**.

Cobertura añadida en `backend/tests/test_skill_editor.py`:

- lectura de las 105 habilidades y de la habilidad equipada;
- desbloqueo individual, múltiple en un personaje y entre personajes;
- desbloqueo masivo de las 63 posiciones bloqueadas observadas;
- conservación de habilidades ya disponibles y de `heroSkill`;
- personajes con 1, 2 y 3 habilidades;
- rechazo de índices inexistentes, personajes desconocidos, duplicados,
  selección vacía, campo ausente y estructuras incompletas o incompatibles;
- catálogo ausente o corrupto;
- operación repetida/idempotente;
- respaldo, confirmación, verificación y restauración;
- conservación de todos los campos no autorizados;
- regresiones de personajes, gemas y fichas.

También se añadieron pruebas de la ruta nativa `/prepare-skills` y de las
políticas `character_write_policy=confirmed_by_owner` y
`skill_write_policy=experimental`.

### Frontend

```bash
cd frontend
npm run build
npx playwright test
```

Resultado real: compilación TypeScript/Vite correcta y **43 pruebas de
Playwright aprobadas**. Las nuevas pruebas cubren resumen, tarjetas, búsqueda,
filtros, selección individual, selección masiva, deselección, resumen previo,
confirmación, subida, contador y ausencia del catálogo.

### Imagen Docker

```bash
cd backend
docker build -t sk-under-backend:phase6-17 .
docker run --rm -e PYTHONPATH=/app -v "$PWD/tests:/check:ro" \
  --entrypoint python sk-under-backend:phase6-17 /check/verify_image_catalog.py
```

Resultado real: build correcto; `python -m app.catalogs.verify` validó 42
personajes, 105 habilidades y 802 skins dentro de la imagen; el script se
ejecutó con `uid=10001`, encontró legible
`/app/app/catalogs/characters-880.json` y terminó con
`VALIDACIÓN DE IMAGEN COMPLETA: OK`.

No se declaran pruebas que no se hayan ejecutado.

## 9. Limitaciones pendientes

- No se ha probado el desbloqueo de habilidades en el cliente oficial ni en un
  dispositivo Android físico.
- No se ha observado una partida real con una segunda habilidad desbloqueada.
- La persistencia de personajes después de guardar de nuevo desde el cliente
  oficial no se ha probado; no se declara E4.
- La relación exacta de `heroSkill` con la habilidad equipada sigue siendo una
  hipótesis E2.
- No se editan niveles, habilidad equipada, skins, mascotas, materiales ni
  semillas.

## 10. Validación manual en Android

Para comprobar el desbloqueo de habilidades:

1. Abre SK-Under en el móvil y entra en **Partida**.
2. Inicia sesión con la cuenta de prueba y descarga la partida actual.
3. Abre el editor y localiza **Habilidades**.
4. Comprueba el resumen y que las habilidades ya disponibles aparecen marcadas.
5. Selecciona una habilidad bloqueada de un personaje con 3 habilidades y otra
   de un personaje con 1 o 2 habilidades. Usa también **Seleccionar todas las
   bloqueadas** para la prueba masiva.
6. Pulsa **Preparar desbloqueo de seleccionadas**.
7. Revisa personajes afectados, habilidades, cantidad de cambios y campos. El
   aviso debe seguir indicando **Experimental E2**.
8. Marca la confirmación explícita y pulsa **Desbloquear habilidades y
   verificar**. Debe aparecer que la nube conserva la copia modificada.
9. Cierra la sesión de SK-Under, abre Soul Knight y recupera la partida desde la
   nube con el cliente oficial.
10. Comprueba dentro del juego que las habilidades seleccionadas aparecen
    disponibles y que la habilidad equipada no cambió.
11. Guarda de nuevo desde el cliente y vuelve a abrir la partida para comprobar
    la persistencia.
12. Si algo falla, vuelve a SK-Under, abre **Partida**, localiza el respaldo de
    habilidades y usa **Restaurar**.

Registra el resultado con: versión del juego, tipo de cuenta, personajes y
habilidades probadas, si aparecieron en el cliente, si la habilidad equipada se
mantuvo y si el cambio persistió tras guardar de nuevo.
# Skins de arma y efectos de eliminación — fase 9.3

## Alcance y evidencia

Esta fase investiga dos categorías independientes del guardado y las integra en
el borrador global:

- **Skins de arma**: `weaponEvolutionData.weapons.<arma>.UnlockedSkins` y
  `CurrentSkinIndex`.
- **Efectos de eliminación**: `miscData.unlockedKillEffectIds` y
  `miscData.equippedKillEffectIdByScene`.

La implementación se promovió a **E3** el **2026-11-26** tras la validación del
propietario en un dispositivo Android físico. Se mantiene sin cambios la lógica
de mutación que ya funcionaba: solo se añaden skins e IDs evidenciados, no se
modifica la skin equipada ni la escena activa. La semántica de
`CurrentSkinIndex` y de las claves de escena sigue sin confirmarse (H), y la
posesión del arma base es una dependencia independiente.

## CRDE como referencia técnica

Se revisó el editor externo autorizado <https://crde.pages.dev/> en modo de solo
lectura. Su interfaz ofrece acciones de servidor para desbloquear skins de arma y
efectos de eliminación, y un editor RAW que devuelve el documento descodificado.
No se encontró ni se utilizó ningún token, no se enviaron modificaciones, no se
crearon pedidos y no se copió código propietario.

La comparación se limitó a estructura y campos. CRDE no publica el catálogo
interno de efectos ni la semántica de las escenas; esas mutaciones ocurren en su
servidor. Por tanto, SK-Under no depende de CRDE para leer, generar catálogos ni
editar.

## Validación física del propietario

El propietario probó la versión de producción en Android físico y confirmó:

- todas las skins de arma seleccionadas quedaron desbloqueadas y el juego las
  reconoce;
- todos los efectos de eliminación seleccionados quedaron desbloqueados y el
  juego los reconoce;
- algunas armas base siguen bloqueadas aunque sus skins estén disponibles.

El último punto no invalida la skin: demuestra que la creación del registro
`weaponEvolutionData.weapons.<arma>` y su lista `UnlockedSkins` no concede la
posesión del arma base. Esa dependencia se investiga en la fase 9.4 mediante
`statisticData.object2ObtainTime` y la disponibilidad de forja.

Por tanto, la mutación de skins y efectos asciende a E3 para existencia, tipo,
semántica de disponibilidad y persistencia observada. `CurrentSkinIndex`, las
claves de escena, los IDs 9–10 y la relación exacta entre contador de obtención
y forja permanecen como incógnitas.

## Muestras comparadas

| Muestra | Plataforma | Perfil | `gameVersion` | `AppVersion` | Resultado relevante |
| --- | --- | --- | ---: | ---: | --- |
| A | Android | Avanzada | 2145 | ausente | 1 arma en `weaponEvolutionData`; sin `miscData` |
| B | Android | Nueva | 2155 | 80800 | 2 armas; efectos 0 y 1; escenas 1 y 0 |
| C | iOS | Avanzada, vía CRDE | 2155 | 1531 | 180 armas, 192 skins; efectos 0–6 |
| D | Android | Avanzada 8.6.0 | 8.6.0 | — | 167 armas, 177 skins; efectos 0–10 |

Las muestras confirman una diferencia importante: **la presencia de armas y
skins no es universal**. Las cuentas Android Global 8.8.0 revisadas suelen tener
`weapons: {}`; la muestra iOS avanzada contiene el catálogo completo. Esto no se
interpreta como una diferencia de plataforma demostrada, sino como distinto
progreso y versión.

Los detalles saneados por muestra están en
[`knowledge/sources/phase9-3-observations.md`](../../knowledge/sources/phase9-3-observations.md).

## Estructura de skins de arma

```json
{
  "weaponEvolutionData": {
    "weapons": {
      "weapon_006": {
        "Name": "weapon_006",
        "Level": 0,
        "CurrentSkinIndex": 1,
        "UnlockedSkins": ["weapon_006_s_1"]
      }
    }
  }
}
```

Hechos observados:

- Cada registro usa exactamente `Name`, `Level`, `CurrentSkinIndex` y
  `UnlockedSkins`.
- `UnlockedSkins` es una lista de cadenas `weapon_XXX_s_N`.
- Los 192 identificadores del catálogo se resuelven contra 180 armas.
- La muestra iOS contiene 192 skins; la muestra Android 8.6 contiene 177 y
  conserva 15 del catálogo sin registrar.
- `CurrentSkinIndex` vale 0 o 1 en las muestras. La correspondencia exacta entre
  el entero y `weapon_XXX_s_N` no está confirmada.
- `Level` no se interpreta ni se modifica.
- `weapons` puede faltar, estar vacío o contener solo algunas armas. Las claves
  opcionales `favorWeapons`, `lastOpenMachineHistoryStr0` y
  `blindBoxOpenCount0` varían entre versiones y se conservan.

El editor crea un registro ausente únicamente con
`{Name: <arma>, Level: 0, CurrentSkinIndex: 0, UnlockedSkins: [...]}`. **Crear
este registro no demuestra ni concede la posesión del arma.** La usabilidad de
la skin puede depender de otro registro de obtención no identificado.

## Estructura de efectos de eliminación

```json
{
  "miscData": {
    "unlockedKillEffectIds": [0, 1],
    "equippedKillEffectIdByScene": [
      { "Key": 1, "Value": 1 },
      { "Key": 0, "Value": 1 }
    ]
  }
}
```

Hechos observados:

- `unlockedKillEffectIds` es una lista de enteros.
- `equippedKillEffectIdByScene` es una lista de pares `{Key, Value}` enteros.
- Las muestras usan las claves 0 y 1. No se ha demostrado qué modo representa
  cada una; no se etiquetan como PvE/PvP.
- Android Global 8.8.0 suele traer los efectos 0 y 1 y ambas escenas en 0.
- La muestra iOS trae los efectos 0–6 y selecciones 1 y 3.
- La muestra Android 8.6 trae los efectos 0–10.

El catálogo independiente contiene **9 efectos (ID 0–8)**:

| ID | Nombre | Objeto | Evidencia |
| ---: | --- | --- | --- |
| 0 | Default / Predeterminado | — | Localización |
| 1 | Starlight Sparkle / Destello estelar | `customization_kill_effect_1` | Item + prefab |
| 2 | Zap! / ¡Zas! | `customization_kill_effect_2` | Item + prefab |
| 3 | Bring It On / ¡Adelante! | `customization_kill_effect_3` | Item + prefab |
| 4–8 | Sin nombre localizado | `customization_kill_effect_4..8` | Item + prefab |
| 9–10 | Desconocidos | — | Solo observados en 8.6.0 |

Los ID 9 y 10 no se ofrecen y se conservan si ya existen. Los nombres 4–8 no se
inventan.

## Implementación

Backend:

- `backend/app/cloud/weapon_skin_editor.py`: lectura, validación, creación
  segura de registros, desbloqueo individual/masivo, roundtrip, idempotencia y
  comprobación de campos colaterales.
- `backend/app/cloud/kill_effect_editor.py`: lectura, validación, desbloqueo
  individual/masivo, conservación de ID desconocidos y de la selección activa.
- `backend/app/catalogs/weapon-skins-880.json` y
  `backend/app/catalogs/kill-effects-880.json`: proyecciones empaquetadas.
- `unified_editor.py`, `models.py`, `native.py`, `lab_service.py` y
  `backup_store.py`: integración en el plan unificado, respaldos, confirmación y
  restauración.
- El orden del plan es: gemas, fichas, progreso de pesca, personajes,
  habilidades, skins de personaje, **skins de arma**, **efectos**, avanzado,
  niveles, afinidad, planos y decoraciones.

Frontend:

- Categorías **Skins de arma** (`armas`) y **Efectos de eliminación**
  (`efectos`).
- Edición rápida con filas masivas para ambas.
- Editor de skins agrupado por arma, búsqueda por skin/arma/ID, filtros
  pendientes/todos/desbloqueados, selección por arma y estado de la skin en uso
  en solo lectura.
- Editor de efectos con los 9 elementos evidenciados, estado, selección masiva y
  escenas activas en solo lectura.
- Advertencia E2 y nota de que crear un registro de arma no concede el arma.

## Corrección 9.3.1

La primera publicación de la fase mostraba ambas categorías como «No
disponible» en producción. El flujo de `POST /api/v1/cloud/native/login` y de
`POST /api/v1/cloud/native/installation` construía el resumen de la partida en
`backend/app/native/service.py` sin `weapon_skins` ni `kill_effects`. El editor
recibía ese resumen de la sesión, no descargaba otra copia porque ya contenía
`report`, y ambos componentes caían en el texto de catálogo ilegible. La ruta
`GET /api/v1/cloud/native/save` sí incluía los catálogos, lo que explicaba que el
fallo apareciera solo tras iniciar sesión.

La corrección añade un resumen compartido de ambas categorías a las dos rutas de
sesión (`_candidate_save` y `_verify_save`), con la política experimental
correspondiente. Si un catálogo falla, solo esa categoría devuelve
`available: false`; el resto de la partida sigue disponible.

También se ajustó la lectura y preparación para las formas reales observadas:

- `weaponEvolutionData.weapons` puede faltar. Se lee como inventario vacío y la
  edición crea el mapa solo si se desbloquea una skin.
- Un registro de arma puede omitir `UnlockedSkins`. Se lee como lista vacía y la
  edición crea la lista sin modificar `Name`, `Level`, `CurrentSkinIndex` ni
  campos desconocidos.
- `miscData` puede faltar por completo (muestra A). Se lee como inventario vacío
  y la edición crea únicamente `{ "unlockedKillEffectIds": [...] }`.
- `miscData` puede existir sin `unlockedKillEffectIds`; se conservan el resto de
  claves y las escenas equipadas.

La verificación de la edición restaura exactamente el estado original de la
sección afectada y compara la serialización completa. Así se demuestra que no
cambió ningún campo ajeno, incluso cuando la sección se creó durante la edición.
No se añadió ninguna escritura remota ni se elevó la evidencia E2.

Archivos corregidos:

- `backend/app/native/service.py`
- `backend/app/cloud/weapon_skin_editor.py`
- `backend/app/cloud/kill_effect_editor.py`
- `backend/tests/test_customization_editors.py`
- `backend/tests/test_native_api.py`

Las pruebas nuevas reproducen el fallo anterior: con el commit `467027f`
fallan la lectura sin mapa `weapons`, la lectura sin `miscData` y la respuesta de
login sin catálogos. Con la corrección pasan. Las muestras privadas A y B
también se procesaron localmente: A devuelve 192 skins/1 desbloqueada y 9
efectos/0 desbloqueados; B devuelve 192/2 y 9/2, conservando sus escenas. Un plan
combinado sobre ambas reabrió correctamente el candidato.

## Pruebas automatizadas

- Backend: `uv run pytest -q` → **735 pasaron, 16 omitidas**.
- Catálogos: `uv run python -m app.catalogs.verify` → 192 skins/180 armas y 9
  efectos.
- Frontend: `npm run build` → sin errores de TypeScript.
- Playwright: 115 pruebas (92 ejecutadas, 23 omitidas por entorno); las tres
  nuevas cubren edición rápida, selección individual, filtros, estados de solo
  lectura y capturas sin desbordamiento a 320, 390, 768 y 1280 px.

## Verificación en producción

La corrección se publicó en `main` con el commit `b10604b` y se verificó contra
las cuentas reales de laboratorio, sin subir ningún candidato.

- **Backend.** Coolify recreó el contenedor con la imagen del commit
  `b10604b5deaa9dcf33ce0269e7f1155d7deab0c9`. `GET /api/v1/version` devuelve ese
  commit y mantiene las capacidades de respaldo. El contenedor quedó saludable.
- **CI.** Backend, frontend, Playwright y la comprobación de higiene y secretos
  terminaron en `success`. Cloudflare Pages registró el despliegue
  `80889b43-5d64-4969-ad49-f34b678601d7` también como `success`.
- **Frontend.** No fue necesario cambiar código: el bundle servido
  (`assets/index-YYRUz-u4.js`) ya contenía los editores de la Fase 9.3. El fallo
  estaba en la respuesta de login del backend.
- **Login real.** `POST /api/v1/cloud/native/login` devolvió ambos catálogos. La
  cuenta avanzada mostró 192 skins y 9 efectos, con 1 skin desbloqueada y 0
  efectos; la cuenta nueva mostró 192 skins y 9 efectos, con 2 skins y 2 efectos
  desbloqueados. Las políticas de escritura siguen siendo `experimental`.
- **Interfaz.** En móvil, el editor rápido mostró «Skins de arma 1/192» y
  «Efectos de eliminación 0/8» en la cuenta avanzada, y «2/192» y «2/9» en la
  nueva. Las categorías listaron 192 skins agrupadas por arma y 9 efectos, con
  buscador, filtros y estados. Ya no apareció «No disponible» ni el texto de
  catálogo ilegible.
- **Selección.** «Seleccionar pendientes» marcó 190 skins y 7 efectos en la
  cuenta nueva; «Quitar selección» volvió a 0 cambios. En la cuenta avanzada se
  seleccionaron individualmente una skin y un efecto.
- **Preparación combinada.** La cuenta avanzada preparó un candidato con 1 skin y
  1 efecto. La vista previa mostró ambas categorías, el aviso de respaldo
  restaurable y el botón «Guardar en la nube» deshabilitado hasta confirmar. No
  se marcó la confirmación ni se pulsó el botón.
- **Sin escritura remota.** El SHA-256 de la partida avanzada en producción
  coincide exactamente con la muestra privada previa
  (`ccb659f127b779569e0f0c70bd93dac1c65e33c7e53e28f0c015dd634c72a7d9`), de modo
  que la preparación no modificó la partida remota.

Limitación observada: cuando `unlockedKillEffectIds` no existe, el efecto
predeterminado (ID 0) aparece como «Bloqueado» aunque su casilla está
deshabilitada y los IDs 1–8 siguen siendo seleccionables. No impide usar la
categoría; se deja anotado para no ampliar el alcance de esta corrección.

Las capturas de producción se conservan fuera del repositorio, en el
almacenamiento privado del propietario, porque muestran datos de cuentas.

## Validación física pendiente

El propietario debe probar en Android Global con respaldo automático:

1. **Skin individual con arma poseída**: elegir una skin bloqueada de un arma
   que ya use la cuenta; preparar, revisar que solo cambia `UnlockedSkins`;
   guardar y verificar la descarga. Reiniciar el cliente y abrir el selector de
   skins del arma. Confirmar si aparece disponible y si se puede equipar. No se
   edita `CurrentSkinIndex` desde SK-Under.
2. **Skin de arma sin registro**: repetir con un arma sin entrada en
   `weaponEvolutionData`; comprobar si el juego conserva el registro creado y si
   la skin es utilizable. Si el arma no está poseída, registrar el resultado como
   limitación, no como fallo del guardado.
3. **Varias skins**: seleccionar varias skins de varias armas y confirmar que
   solo se añaden a `UnlockedSkins` y que las armas no seleccionadas no cambian.
4. **Todas las pendientes**: ejecutar el lote completo y comprobar que las 192
   posiciones del catálogo quedan cubiertas sin duplicados.
5. **Efecto individual**: desbloquear el ID 2 y comprobar que aparece en el
   selector de efectos. La escena activa debe permanecer igual.
6. **Todos los efectos evidenciados**: añadir 3–8, conservar 0–1 y verificar que
   los ID 9/10 de una cuenta antigua no se eliminan.
7. **Operación combinada**: desbloquear una skin y un efecto en el mismo
   candidato; comprobar que el resumen muestra ambas categorías y que la subida
   es única.
8. **Reversión**: si el cliente rechaza o corrige algo, restaurar el respaldo
   exacto y confirmar que el guardado vuelve al SHA original.

**Estado:** validado por el propietario en Android físico el 2026-11-26 para
skins y efectos. La checklist se conserva como plantilla de regresión para
futuras versiones. El caso de arma base bloqueada se traslada a la validación de
progresión de armas de la fase 9.4.

## Limitaciones

- No se ha demostrado la semántica de `CurrentSkinIndex`.
- No se ha demostrado la correspondencia de las claves de escena.
- La creación de un registro de arma no concede el arma base; algunas armas
  siguen bloqueadas tras desbloquear todas sus skins.
- La relación exacta entre `statisticData.object2ObtainTime`, la colección y la
  forja se investiga en la fase 9.4 y aún requiere validación física.
- Los nombres de los efectos 4–8 y la identidad de 9–10 siguen sin resolver.
- La muestra iOS procede de un editor externo; no se usa para trasplantar
  identidad ni para afirmar compatibilidad de escritura iOS.
- Los estados de compra y derechos de servidor siguen siendo de solo lectura.
# Skins de arma y efectos de eliminación — fase 9.3

## Alcance y evidencia

Esta fase investiga dos categorías independientes del guardado y las integra en
el borrador global:

- **Skins de arma**: `weaponEvolutionData.weapons.<arma>.UnlockedSkins` y
  `CurrentSkinIndex`.
- **Efectos de eliminación**: `miscData.unlockedKillEffectIds` y
  `miscData.equippedKillEffectIdByScene`.

La implementación es **experimental E2**. Se apoya en estructuras observadas en
muestras autorizadas y en catálogos con procedencia, pero no se ha validado en
un dispositivo Android físico. No se declara E3 ni E4, no se modifica la skin
equipada, no se cambia la escena activa y no se afirma que el cliente acepte las
entradas añadidas.

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

## Pruebas automatizadas

- Backend: `uv run pytest -q` → **727 pasaron, 16 omitidas**.
- Catálogos: `uv run python -m app.catalogs.verify` → 192 skins/180 armas y 9
  efectos.
- Frontend: `npm run build` → sin errores de TypeScript.
- Playwright: 115 pruebas (92 ejecutadas, 23 omitidas por entorno); las tres
  nuevas cubren edición rápida, selección individual, filtros, estados de solo
  lectura y capturas sin desbordamiento a 320, 390, 768 y 1280 px.

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

Registrar por prueba: plataforma, versión, si el arma estaba poseída, si la skin
apareció, si se pudo equipar, si el efecto apareció, escena observada y cualquier
corrección automática del cliente. Solo entonces se podrá elevar la evidencia.

## Limitaciones

- No se ha demostrado la semántica de `CurrentSkinIndex`.
- No se ha demostrado la correspondencia de las claves de escena.
- No se ha comprobado que el cliente acepte skins o efectos añadidos.
- La creación de un registro de arma no concede el arma.
- Los nombres de los efectos 4–8 y la identidad de 9–10 siguen sin resolver.
- La muestra iOS procede de un editor externo; no se usa para trasplantar
  identidad ni para afirmar compatibilidad de escritura iOS.
- Los estados de compra y derechos de servidor siguen siendo de solo lectura.
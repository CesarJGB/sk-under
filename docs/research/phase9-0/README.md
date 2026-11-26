# Fase 9.0 — Progresión de personajes, mascotas y planos

Fecha: 2026-11-25

Esta fase retoma la investigación funcional de SK-Under después de las fases
visuales 8.x. Se implementaron tres escritores nuevos y se integraron en el
borrador unificado y en la interfaz móvil:

- niveles permanentes de personaje (`gameData.heroLevel`);
- afinidad de mascotas (`statisticData.event2Count`);
- estados de planos (`itemData.blueprints`).

También se investigaron forja, jardín, joyería y vestíbulo. Esos sistemas se
documentan abajo, pero permanecen en solo lectura porque falta evidencia para
un escritor determinista.

## Regla de evidencia

La evidencia sobre el **significado del campo** y la evidencia sobre la
**eficacia del escritor** se mantienen separadas.

| Función | Semántica del campo | Escritor |
| --- | --- | --- |
| Niveles de personaje | E3, mejora legítima observada Caballero 0→1 | Experimental; no validado en juego |
| Afinidad de mascotas | E2, valores máximos observados en muestra completa | Experimental; no validado en juego |
| Planos | E2, estados `Got`/`Researched` observados | Experimental; no validado en juego |

Ningún escritor sube a E3/E4 por el hecho de serializar, reabrir y verificar el
candidato. Esas comprobaciones demuestran integridad del archivo, no que Soul
Knight acepte y conserve el cambio. La validación dentro del juego queda para
el propietario en un Android físico.

## 1. Niveles de personaje

### Campo y estructura

- Ruta: `gameData.heroLevel`.
- Tipo observado: mapa `código de personaje -> entero`.
- Catálogo: `backend/app/catalogs/characters-880.json` (42 personajes).
- Rango habilitado: `0..7`.
- El escritor solo modifica claves existentes del mapa; no inserta personajes
  ausentes ni crea el mapa si falta.
- No modifica `gameData.heroUnlock`, habilidades, skins, gemas ni recibos.

### Significado y evidencia

La semántica está respaldada por una mejora legítima del Caballero que cambió
`heroLevel.Knight` de `0` a `1` (E3). La persistencia observada es E2.

El máximo `7` proviene del sistema clásico documentado de siete mejoras
permanentes con costes 500/1000/1500/2000/2500/5000/8000 gemas. No se recuperó
el valor concreto de `CharactersLevelUpData.MaxLevel` para cada personaje: el
tipo y el manager existen en la metadata, pero la tabla Luban sigue cifrada.
Por eso:

- no se ofrecen máximos distintos por personaje;
- no se habilita el nivel 8, asociado a un sistema retirado;
- el máximo 7 se muestra como límite documentado, no como configuración local
  recuperada.

### Implementación

Archivo: `backend/app/cloud/hero_level_editor.py`.

- `normalize_hero_level_plan`: valida códigos del catálogo y enteros `0..7`.
- `hero_levels_snapshot`: expone nivel, presencia, tipo, estado de desbloqueo,
  ruta y editabilidad. Un valor ausente o no entero se muestra como desconocido,
  nunca como cero.
- `prepare_hero_level_edit`: rechaza bajar niveles, claves ausentes, valores no
  enteros y niveles fuera de rango. Aplica solo diferencias efectivas.
- Serializa, reabre, comprueba los valores solicitados, restaura los originales
  y exige que la restauración reproduzca byte a byte el guardado de origen.
- `require_hero_level_write_compatibility`: reproduce el plan al confirmar.

Plan unificado:

```json
{
  "hero_levels": [
    { "code": "Knight", "level": 5 }
  ]
}
```

Cambios declarados: `gameData.heroLevel.<code>`.

### Interfaz

Dentro de **Personajes**:

- lista compacta con nivel actual y máximo documentado;
- edición individual;
- mejora masiva de elegibles;
- exclusión individual de la operación masiva;
- los personajes bloqueados se pueden editar, pero se identifican como tales;
- la combinación desbloqueo + nivel se realiza en el mismo candidato porque
  son rutas distintas (`heroUnlock` y `heroLevel`).

### Limitaciones pendientes

- Confirmar en juego si el nivel escrito sin descontar gemas se conserva y si
  el siguiente nivel sigue la progresión normal.
- Confirmar el comportamiento en personajes bloqueados.
- Recuperar `CharactersLevelUpData.MaxLevel` para sustituir el límite global 7
  por máximos por personaje.
- Confirmar si existe validación del servidor para niveles.

## 2. Afinidad de mascotas

### Campo y estructura

- Ruta: `statisticData.event2Count`.
- Claves por mascota: `pet_<ID>_intimacy`, `pet_<ID>_full_intimacy`,
  `pet_<ID>_action_unlock`.
- Clave global: `pet_full_intimacy`.
- Catálogo: `backend/app/catalogs/pets-880.json` (58 mascotas, 12 variantes).

La muestra completa observada contiene los IDs numéricos 0–26 y 28–55. Faltan
27, 56 y 57. Los máximos empíricos son:

- IDs 30 y 31: `180`;
- ID 34: `300`;
- resto de IDs presentes 0–55: `240`.

No se asume un máximo universal. Los IDs 27, 56 y 57 quedan en solo lectura
por no tener máximo observado. `PetsLevelUpConfig` y `PetIntimacyConfig`
existen en la metadata (`PetIntimacyData` declara `Min`/`Max`), pero sus tablas
no se pudieron deserializar.

### Implementación

Archivo: `backend/app/cloud/pet_affinity_editor.py`.

- Solo edita `pet_<ID>_intimacy` si la clave ya existe.
- Solo permite subir, nunca bajar.
- Solo permite valores hasta el máximo empírico conocido.
- Si el objetivo alcanza el máximo, exige que exista
  `pet_<ID>_full_intimacy` y lo pone a `1`.
- Rechaza bajar la afinidad cuando `full_intimacy` ya está activo.
- No crea claves, no toca `_action_unlock` y no recalcula el contador global
  `pet_full_intimacy` (la muestra completa tenía 35 con 56 mascotas llenas; su
  fórmula no está demostrada).
- Verifica el candidato y demuestra ausencia de cambios colaterales con la
  misma restauración byte a byte que el resto de escritores.

Plan unificado:

```json
{
  "pet_affinity": [
    { "code": "Cat", "value": 220 }
  ]
}
```

Cambios declarados: `statisticData.event2Count.pet_<ID>_intimacy` y, cuando
corresponde, `..._full_intimacy`.

### Interfaz

Dentro de **Mascotas**, sección **Afinidad**:

- valor actual y máximo conocido;
- edición individual;
- maximización masiva de mascotas compatibles;
- exclusión individual;
- nota discreta de función experimental.

El alimento, las baterías, las skins, la mascota activa y los contadores ajenos
se conservan.

### Limitaciones pendientes

- Confirmar que el juego acepta la afinidad escrita sin consumir alimento.
- Confirmar la relación exacta entre intimidad máxima, `full_intimacy` y el
  contador global.
- Recuperar las tablas `PetsLevelUpConfig`/`PetIntimacyConfig` para sustituir
  los máximos empíricos.
- Confirmar el comportamiento de los indicadores `_action_unlock`.

## 3. Planos

### Campo y estructura

- Ruta: `itemData.blueprints`.
- Tipo observado: mapa `identificador -> "Got" | "Researched"`.
- Muestra completa: 275 entradas; 273 `Researched`, 2 `Got`
  (`multi_room_skin_20`, `multi_room_skin_21`).
- El catálogo empaquetado tiene 265 planos con prefijo `blueprint_`.
- Algunos guardados usan alias sin prefijo (`multi_room_skin_20`,
  `garden_skin_*`, `hall_skin_*`, etc.).

`Got` representa un plano obtenido; `Researched`, un plano investigado. La
ausencia de una clave no se interpreta como estado cero. No se pudo demostrar
la dependencia exacta con materiales de investigación, fabricación o
disponibilidad final del objeto.

### Implementación

Archivo: `backend/app/cloud/blueprint_editor.py`.

- Resuelve primero el identificador exacto del catálogo y después el alias sin
  `blueprint_`.
- Solo edita claves presentes en el guardado; no inserta planos ausentes.
- Solo admite `Got` y `Researched`.
- Rechaza estados desconocidos y colisiones de alias.
- Conserva claves no identificadas y las informa en la interfaz.
- Verifica valores y ausencia de cambios colaterales.

Plan unificado:

```json
{
  "blueprints": [
    { "id": "blueprint_multi_room_skin_0", "status": "Researched" }
  ]
}
```

Cambios declarados: `itemData.blueprints.<clave resuelta>`.

### Interfaz

Categoría **Planos**:

- búsqueda y filtro por estado;
- estado individual;
- operación masiva para investigar los planos obtenidos;
- exclusión individual;
- aviso de claves no identificadas conservadas.

### Limitaciones pendientes

- Confirmar si `Researched` habilita fabricación o solo marca la investigación.
- Confirmar la relación con materiales y con planos ausentes.
- Validar alias de versiones anteriores.
- No se habilitan estados distintos de `Got`/`Researched`.

## 4. Forja y evolución de armas

Investigado, sin escritor:

- `itemData.forgeWeapons` es una lista de cuatro posiciones con nombres de arma
  o `null`. La muestra completa contenía
  `[null, "weapon_init_priestxx10", "weapon_init_priestxx7", "weapon_init_priestxx9"]`
  y otra cuenta `["weapon_034", "weapon_057", "weapon_062", null]`. Parece una
  cola o ranuras de forja, no un progreso permanente por arma.
- `forgeWeaponMaterialPayments` está ausente cuando no hay pagos y usa
  `{slot, weaponName, materials}`.
- La metadata incluye `IsWeaponForgeUnlockByObtainTimes`,
  `ObtainWeaponTimes`, `InitForgeWeapons`, `ConsumeForgeWeapon0`, además de
  estadísticas de armas usadas/construidas/comidas.
- `weaponEvolutionData.weapons` usa `{Name, Level, CurrentSkinIndex,
  UnlockedSkins}`; `Level` es evolución, no disponibilidad de forja.
- Los catálogos de armas y materiales existen, pero no se demostró la regla
  exacta que convierte obtenciones en desbloqueo permanente.

Por seguridad, no se implementó un editor de `forgeWeapons` ni se etiquetó como
progreso. Queda pendiente recuperar la regla de desbloqueo y la relación con
estadísticas, pagos y evoluciones.

## 5. Jardín, joyería y vestíbulo

Investigados y mantenidos en solo lectura:

- **Jardín**: `itemData.plants` es una lista de 8 posiciones con
  `{plantName, state, watered, fertilized}` o `null`. La muestra tenía
  `state: 1`, `watered: false`, `fertilized: false`; no se conocen todos los
  estados de crecimiento ni la relación exacta con semillas y fertilizante.
- **Joyería**: `itemData.jewelryData` es un mapa
  `objeto -> {item, durability, rune1, rune2}`. La muestra tenía durabilidad
  `5000000` y runas `"None"`, pero no se demostró que 5 000 000 sea el máximo.
  `jewelryBlueprints` y `jewelryPlayerData` tampoco tienen semántica suficiente.
- **Vestíbulo**: `roomDecorateDic` observó objetos con listas `[0]`;
  `roomObjectLevel`, `unlockRoomDecorate`, `roomDecorateCurSkinDic` y
  `currentRoomDecorate` no tienen límites ni estados demostrados. No se
  interpreta `[0]` como nivel máximo.

No se implementaron escritores para estos campos para evitar valores
arbitrarios y cambios laterales.

## 6. Integración unificada

Los tres escritores se aplican únicamente a través del plan unificado, en este
orden fijo después de las categorías existentes:

1. `hero_levels`
2. `pet_affinity`
3. `blueprints`

El flujo conserva las garantías de las fases anteriores:

- una descarga y un SHA de origen;
- un candidato compuesto sobre los mismos bytes;
- un respaldo cifrado previo;
- una confirmación explícita y una sola subida;
- detección de conflictos por SHA remoto;
- verificación remota posterior;
- borrador conservado ante errores;
- reproducción del candidato desde el plan al confirmar.

Cada escritor valida estructura, tipos, identificadores y rangos; conserva
claves desconocidas; rechaza operaciones incompatibles; detecta cambios
efectivos; serializa y reabre; comprueba los valores solicitados; y demuestra
la ausencia de cambios colaterales restaurando los originales y exigiendo
igualdad byte a byte.

No se añadió un editor arbitrario de rutas JSON.

## 7. Pruebas automatizadas

Comandos ejecutados:

```bash
cd backend
PYTHONPATH=. .venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
.venv/bin/python -m app.catalogs.verify

cd ../frontend
npm run build
npx playwright test tests/phase8-editor.spec.ts --reporter=line
```

Resultados:

- Backend: **689 passed, 16 skipped**.
- Compilación backend: correcta.
- Catálogos: 42 personajes, 105 habilidades, 802 skins, 343 materiales,
  47 semillas, 58 mascotas, 12 variantes de mascota, 265 planos.
- Frontend: build correcto.
- Playwright: **40 passed**, incluyendo el flujo móvil de 320 px que combina
  niveles, afinidad y planos, y las capturas de 320/360/375/390/430/768/1280.
- Knowledge Engine: 616 campos, 39 dependencias, 25 catálogos y validación
  correcta.

`backend/tests/test_phase9_editors.py` cubre lectura, edición individual,
límites, claves ausentes o incompatibles, identificadores desconocidos,
ausencia de cambios colaterales, repetición del plan, combinación unificada,
respaldo único, subida única y restauración del original.

Las pruebas usan documentos sintéticos. No se escribió en cuentas reales.

## 8. Archivos principales

Backend:

- `backend/app/cloud/hero_level_editor.py`
- `backend/app/cloud/pet_affinity_editor.py`
- `backend/app/cloud/blueprint_editor.py`
- `backend/app/cloud/advanced_editor.py`
- `backend/app/cloud/unified_editor.py`
- `backend/app/cloud/backup_store.py`
- `backend/app/models.py`
- `backend/app/api/native.py`
- `backend/app/catalogs/blueprints.py`
- `backend/app/catalogs/blueprints-880.json`
- `backend/app/catalogs/verify.py`
- `backend/tests/test_phase9_editors.py`
- `backend/tests/test_advanced_editor.py`
- `backend/tests/test_knowledge_tools.py`

Frontend:

- `frontend/src/api.ts`
- `frontend/src/draft.ts`
- `frontend/src/pages/EditorOverview.tsx`
- `frontend/src/pages/EditorWorkspace.tsx`
- `frontend/src/styles.css`
- `frontend/tests/phase8-editor.spec.ts`

Conocimiento:

- `knowledge/fields/overrides.json`
- `knowledge/fields/fields.json`
- `knowledge/dependencies/dependencies.json`
- `knowledge/manifest.json`
- `knowledge/tools/build_backend_blueprints.py`

## 9. Validación manual en Android físico

Usar una cuenta de prueba y un respaldo verificado. No probar primero en la
cuenta principal.

### Niveles

1. Abrir SK-Under y descargar la partida.
2. En **Personajes**, anotar el nivel actual de un personaje con `heroLevel > 0`
   si existe, o del Caballero.
3. Subir un nivel individual (por ejemplo, Caballero de 0 a 1), preparar y
   guardar.
4. Abrir Soul Knight, entrar al personaje y comprobar el nivel, las estadísticas
   y la habilidad.
5. Volver a SK-Under, descargar de nuevo y confirmar que el nivel persiste.
6. Probar una mejora masiva con una exclusión y comprobar que el excluido no
   cambió.
7. Probar desbloqueo + nivel en el mismo lote.
8. Observar si el juego descuenta gemas o si el siguiente nivel conserva la
   progresión esperada.

### Afinidad

1. Anotar intimidad actual y si la mascota está al máximo.
2. Subir la afinidad sin llegar al máximo; guardar y comprobar en juego.
3. Alcanzar el máximo de una mascota compatible; comprobar que se marca como
   completa y que el juego no reinicia el valor.
4. Verificar que el alimento, las baterías, las skins y la mascota activa no
   cambiaron.
5. Anotar el contador global antes y después.
6. Repetir con una mascota de máximo 180, 240 y 300 si la cuenta las tiene.
7. Confirmar que las mascotas 27/56/57 siguen sin controles de escritura.

### Planos

1. Anotar un plano `Got` y otro `Researched`.
2. Cambiar `Got` a `Researched`, guardar y abrir la investigación o fabricación
   en Soul Knight.
3. Comprobar si el objeto queda disponible o si solo cambia la marca.
4. Probar la operación masiva y confirmar que las claves desconocidas se
   conservaron.
5. Volver a descargar la partida y verificar persistencia.

### Restauración

1. Crear un respaldo antes de cada prueba.
2. Tras validar, restaurar el respaldo y comprobar que el juego vuelve al estado
   anterior.
3. Si el juego rechaza o revierte un cambio, conservar el respaldo y documentar
   el resultado; no repetir la escritura sobre la cuenta principal.

## 10. Pendientes y bloqueos

- Tablas Luban cifradas: impiden recuperar máximos por personaje y
  configuraciones de afinidad.
- Validación física de los tres escritores.
- Regla exacta de desbloqueo permanente de forja.
- Estados de crecimiento del jardín y límites de parcelas.
- Máximo de durabilidad y semántica de runas de joyería.
- Semántica de niveles y skins del vestíbulo.
- Confirmar si el servidor valida niveles, afinidad o planos.
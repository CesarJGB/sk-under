# Fase 11.0 — Investigación avanzada de guardado y ampliación del editor

Fecha: 2026-11-27
Estado: implementación completada y probada localmente; validación física pendiente
Commit: `PENDING`

## 1. Resultado

Esta fase no se limita a documentación ni a corregir el conflicto de planos. Añade
dos operaciones nuevas utilizables desde el editor y una tercera corrección
estructural:

1. **Conflicto Planos ↔ Decoraciones resuelto de forma determinista.** Los cuatro
   planos decorativos compartidos tienen un único propietario: Decoraciones. Ya no
   importa si el usuario selecciona antes Planos o Decoraciones, ni si Planos está
   en modo `Got` o `Researched`. La protección genérica contra solapamientos sigue
   activa para cualquier otro campo.
2. **Skin de arma activa (experimental E2).** Se puede escribir
   `weaponEvolutionData.weapons.<arma>.CurrentSkinIndex` con una skin desbloqueada
   del catálogo o con `0` para la predeterminada. No crea registros de arma ni
   modifica `Level` o `UnlockedSkins`.
3. **Banderas funcionales del vestíbulo (experimental E2).** Se pueden activar
   siete instalaciones/modos que usan `statisticData.event2Count.room_unlock_*`:
   jardín, taller, tablero de misiones, Badass, defensa, temporada y Monster Rise.
   Son desbloqueos funcionales, no posesión de muebles ni progreso dentro del modo.

Además se auditaron los sistemas candidatos restantes. Logros, títulos
honoríficos, estilos de mano, monturas, joyas, armas mitológicas, niveles de
evolución de arma, Monster Rise, temporada de escape, trofeos de temporada,
`itemUnlock` y las parcelas de plantas se mantienen en solo lectura porque las
muestras no permiten demostrar su semántica completa.

## 2. Evidencia utilizada

No se usaron credenciales nuevas ni se publicaron partidas. El análisis se hizo
sobre las copias privadas ya autorizadas:

| Muestra | Tamaño | Versión | Uso |
| --- | ---: | --- | --- |
| Android avanzada A | 912.375 B | `gameVersion=2145` | Objetos, banderas, planos, evolución, colecciones |
| Android B | 222.148 B | `gameVersion=2155`, `AppVersion=80800` | Cuenta con poca progresión; estados ausentes/cero |
| Android nueva 10.2 | 115.168 B | 8.8.0 | Línea base de cuenta nueva |
| iOS nueva 10.2 | 114.008 B | 8.8.0.14 | Comparación de estructura y marcadores |
| iOS avanzada C (fase 9.2) | 235.438 B | `gameVersion=2155`, `AppVersion=1531` | Planos enteros, banderas y referencias de plataforma |

Hechos utilizados:

- Las claves decorativas conservan el prefijo `blueprint_`:
  `blueprint_room_decorate_drink_seller`, `_fishbowl`, `_magic_well` y
  `_mysteriou_statue`.
- En A y C los cuatro planos están en `Researched`/`2`; B no los tiene.
- A tiene activas las banderas de jardín, taller, tablero, Badass, defensa,
  temporada y todas las de objetos. C tiene además `room_unlock_monster_rise=1`.
  B no declara ninguna de estas banderas.
- `weaponEvolutionData.weapons` solo existe para armas con registro. B contiene
  `weapon_363` con `s_1` y `CurrentSkinIndex=0`, y `weapon_407` con `s_1` y
  `CurrentSkinIndex=1`. A contiene `weapon_311` con `CurrentSkinIndex=0`.
- El catálogo asigna `skin_index=1` a `s_1`. La correlación observada es
  `0 = predeterminada`, `N = skin_index del catálogo`. Es evidencia E2, no una
  validación en juego.
- Los planos aceptan texto (`Got`/`Researched`) o entero (`1`/`2`). Los escritores
  conservan la codificación original de la cuenta.

## 3. Conflicto de planos: causa y corrección

### Causa reproducida

El error original era:

```text
Dos operaciones intentan cambiar el mismo campo:
itemData.blueprints.blueprint_room_decorate_drink_seller,
itemData.blueprints.blueprint_room_decorate_fishbowl,
itemData.blueprints.blueprint_room_decorate_magic_well,
itemData.blueprints.blueprint_room_decorate_mysteriou_statue
```

Planos y Decoraciones escribían los mismos cuatro campos:

- Planos podía escribirlos como `Got` si el modo global estaba en «Obtener».
- Decoraciones los elevaba después a `Researched` porque son requisito del objeto.
- El editor unificado detectaba correctamente el solapamiento y abortaba.
- Si Planos estaba en `Researched`, Decoraciones no generaba cambio y el error no
  aparecía. Por eso la selección «Unlock All T13» podía no reproducirlo.

### Corrección estructural

En `normalize_unified_plan` se eliminan del plan de Planos los IDs requeridos por
los objetos decorativos seleccionados. Decoraciones queda como único propietario
y garantiza `Researched`. Si el plan de Planos queda vacío, se omite la categoría.
El frontend aplica exactamente la misma regla en `buildDraftPlan`, de modo que el
contador visible y el plan enviado coinciden.

No se eliminó `UnifiedOverlap`: cualquier otro par de editores que intente cambiar
el mismo campo sigue siendo rechazado.

Pruebas añadidas:

- Planos `Got` + un objeto decorativo: sin solapamiento; el plano compartido queda
  `Researched`; otros planos sí se aplican.
- Solo el plano compartido + Decoraciones: la categoría Planos desaparece y el
  cambio total sigue siendo coherente.
- Los cuatro objetos + los cuatro planos en `Got`: solo se ejecuta Decoraciones.
- Orden de categorías irrelevante: el plan normalizado es un mapa y la deducción
  se hace antes de preparar.
- Prueba de interfaz que selecciona el plano compartido y el objeto, guarda y
  comprueba que `plan.blueprints` no existe y `decorations.objects` sí.

## 4. Skin de arma activa

### Semántica implementada

Entrada unificada:

```json
"weapon_skin_equip": [
  {"weapon_id": "weapon_363", "skin_id": "weapon_363_s_1"},
  {"weapon_id": "weapon_002", "skin_id": null}
]
```

Reglas:

- `weapon_id` debe existir en el catálogo de 192 skins.
- `skin_id` debe pertenecer a esa arma. `null` significa predeterminada (`0`).
- El arma debe tener ya un registro en `weaponEvolutionData.weapons`; equipar no
  crea registros.
- La skin debe estar en `UnlockedSkins` del registro. En el plan unificado se
  puede desbloquear y equipar en la misma operación porque `weapon_skins` se
  aplica antes que `weapon_skin_equip`.
- Se conserva `Name`, `Level`, `UnlockedSkins` y cualquier campo desconocido.
- Solo se declaran cambios reales; repetir el estado actual devuelve bytes
  idénticos y `changed=false`.
- La verificación reabre la copia, comprueba el índice, vuelve a poner el valor
  anterior y exige que el binario sea igual al original. Así se demuestra que no
  se tocó ningún otro campo.

### Límites

- E2: la relación `CurrentSkinIndex = skin_index` está observada, no probada en el
  cliente. El propietario debe confirmar que el modelo/icono cambia y persiste.
- No se escribe `Level`, no se desbloquean armas base y no se inventan registros.
- No se modifican índices de armas sin registro.

## 5. Banderas del vestíbulo

Se añadió la sección **Instalaciones y modos** dentro de Decoraciones, con selección
individual y masiva, búsqueda y contador compartido.

| Bandera | Instalación/modo | Evidencia |
| --- | --- | --- |
| `room_unlock_garden` | Jardín | A=1, C=1, B ausente |
| `room_unlock_work_shop` | Taller | A=1, C=1, B ausente |
| `room_unlock_quest_board` | Tablero de misiones | A=1, C=1, B ausente |
| `room_unlock_badass` | Modo Badass | A=1, C=1, B ausente |
| `room_unlock_defence_mode` | Modo defensa | A=1, C=1, B ausente |
| `room_unlock_season_mode` | Modo temporada | A=1, C=1, B ausente |
| `room_unlock_monster_rise` | Monster Rise | C=1; A/B ausente |

Reglas:

- Solo se crean o elevan a `1`; nunca se reduce un valor mayor.
- Se preservan contadores desconocidos y contadores no relacionados.
- `room_unlock_statements_count` y `room_unlock_road` quedan fuera: el primero
  tiene valor 85 en C y el segundo no tiene semántica confirmada.
- La interfaz explica que desbloquear la bandera no acredita progreso interno.

## 6. Sistemas auditados y no implementados

| Sistema | Campos observados | Motivo para no escribir |
| --- | --- | --- |
| Logros y recompensas | `statisticData.achieve_record`, `hasGetAchievement*RewardList` | Recompensas y estados de compra son de solo lectura; no hay catálogo de nombres ni reglas de canje |
| Títulos honoríficos | `HonoraryTitleSnapshot`, `equippedHonoraryTitles` | Sin catálogo; A usa `"Gold"` y B usa `0`; no se conoce el rango ni el efecto de equipar |
| Estilos de mano | `handStyleIndexList` | Sin catálogo ni evidencia de selección |
| Monturas | Catálogo de 4, `settingData.mountPosition` | No se localizó un estado de desbloqueo/posesión escribible |
| Joyas | `jewelryData`, `jewelryPlayerData` | Durabilidad máxima no confirmada (100 en A, 5.000.000 en C) y runas desconocidas |
| Armas mitológicas | `mythicWeapons` | Nivel 3 observado, pero no se demuestra máximo, posesión ni efecto |
| Niveles de evolución | `weaponEvolutionData.weapons.*.Level` | Solo se observó 0; máximo y requisitos no confirmados |
| Monster Rise | `monsterRiseData` | A/B casi vacíos; no hay evidencia de desbloqueo individual |
| Temporada de escape | `escapeSeasonData` | A/B vacíos; no se puede separar desbloqueo permanente de estado de partida |
| Trofeos de temporada | `seasonData.*Trophy*` | Todos en 0 incluso en A; semántica desconocida |
| `itemUnlock` | Lista con `Motorcycle`, `plant_pot3..7` | La política existente lo marca de solo lectura; no se conoce relación con compras |
| Plantas | `itemData.plants` | Estados 1–4 observados, pero sin catálogo de crecimiento ni prueba de madurez |

Estos sistemas quedan documentados para una fase posterior. No se añadieron
controles especulativos.

## 7. Compatibilidad Android/iOS

- Las rutas nuevas (`statisticData.event2Count`, `weaponEvolutionData.weapons`)
  existen en ambas plataformas con la misma forma observada.
- No se copiaron estructuras completas entre plataformas ni se tocaron
  `platformId`, `cloudSaveId`, `AppVersion`, `gameVersion` o distribución.
- iOS sigue en modo experimental. El nuevo equipamiento de skin se etiqueta E2 y
  requiere prueba física iOS antes de promoverlo.
- Los planes conservan texto o entero según la codificación original.
- El preflight de vinculación y la verificación remota no se relajaron.

## 8. Integración y rendimiento

- La skin activa se integra en la categoría **Armas → Skins de arma** con un
  selector compacto por arma. Solo aparecen armas con registro y skins
  desbloqueadas o seleccionadas en el mismo borrador.
- Las instalaciones se integran en **Decoraciones**, con búsqueda, checkboxes y
  contador global. También hay una fila en la edición rápida.
- No se crearon inventarios duplicados ni botones de guardado por categoría.
- El plan sigue siendo único por partida y las cuentas de cambios se derivan del
  plan real, no de estimaciones.
- El conflicto se resuelve antes de preparar; no se añadió ninguna copia completa
  ni recorrido cuadrático. Las cachés de elegibilidad y los mapas por arma
  mantienen el comportamiento de la Fase 10.2.

## 9. Pruebas ejecutadas

Backend:

```text
backend/.venv/bin/python -m pytest -q
800 passed, 16 skipped
```

Frontend:

```text
cd frontend
npm run build
# tsc --noEmit + vite build: correcto

npm run test:browser -- --reporter=line
103 passed, 22 skipped
```

Casos nuevos cubiertos:

- Planos/Decoraciones con una y cuatro coincidencias.
- Planos en `Got` y en `Researched`.
- Plan vacío tras deduplicar.
- Banderas de instalaciones, contador desconocido preservado y bandera inválida.
- Skin activa, restauración a predeterminada, arma sin registro rechazada,
  idempotencia y desbloqueo+equipamiento en un solo plan.
- Interfaz móvil a 320 px sin desbordamiento.

No se realizaron escrituras en cuentas reales durante esta fase. Las pruebas de
persistencia y aceptación por el cliente siguen pendientes y no se presentan como
evidencia física.

## 10. Pruebas físicas que debe realizar el propietario

Usar las cuentas de prueba ya autorizadas, con respaldo independiente antes de
cada escritura y restauración final verificada. No publicar credenciales, correos,
tokens ni partidas.

### T11-01 — Conflicto de planos

1. Crear respaldo independiente de la cuenta Android.
2. Seleccionar **Planos → Obtener ausentes** y, sin cambiar el modo, seleccionar
   los cuatro objetos decorativos. Guardar.
3. Repetir con Planos en **Investigar** y con la selección hecha en orden inverso.
4. Repetir con la selección máxima de todas las categorías.
5. Confirmar que no aparece el error de solapamiento, que los cuatro planos quedan
   investigados y que los objetos aparecen en el vestíbulo.
6. Restaurar el original y comprobar el hash.

### T11-02 — Instalaciones del vestíbulo

1. En una cuenta nueva, activar una sola bandera (por ejemplo jardín), subir y
   entrar al juego.
2. Confirmar que la instalación está disponible; reiniciar el cliente y repetir.
3. Probar taller, tablero, Badass, defensa, temporada y Monster Rise por separado.
4. Verificar que no se alteran contadores ajenos y que las banderas ya activas no
   se reducen.
5. Restaurar el respaldo.

### T11-03 — Skin de arma activa

1. Usar un arma con registro y una skin desbloqueada (por ejemplo `weapon_363_s_1`).
2. Elegir la skin activa, guardar, recuperar y comprobar modelo/icono en el
   vestíbulo y en una partida.
3. Reiniciar el cliente y confirmar persistencia.
4. Volver a **Predeterminada**, repetir y confirmar que el cambio se revierte.
5. Probar desbloquear y equipar en la misma operación.
6. Repetir en iOS experimental y anotar cualquier diferencia.

### T11-04 — Integridad e idempotencia

1. Preparar dos veces la misma selección y confirmar que la segunda no produce
   cambios ni un candidato distinto.
2. Comparar todos los campos no editados antes/después.
3. Descargar el respaldo, restaurarlo y verificar SHA-256 original.
4. Repetir en Android e iOS y revisar los marcadores de versión.

## 11. Archivos modificados

- `backend/app/cloud/decoration_editor.py`
- `backend/app/cloud/weapon_skin_editor.py`
- `backend/app/cloud/unified_editor.py`
- `backend/app/models.py`
- `backend/app/api/native.py`
- `backend/tests/test_phase9_1_features.py`
- `frontend/src/api.ts`
- `frontend/src/draft.ts`
- `frontend/src/pages/EditorOverview.tsx`
- `frontend/src/pages/EditorWorkspace.tsx`
- `frontend/src/pages/WeaponSkinsEditor.tsx`
- `frontend/tests/phase8-editor.spec.ts`
- `README.md`
- `docs/research/phase11-0/advanced-editor-report.md`

## 12. Estado de las cuentas de prueba

No se ejecutaron escrituras en la nube ni restauraciones sobre cuentas reales en
esta fase. Las copias locales y los respaldos previos permanecen intactos. El
estado final de las cuentas debe confirmarse después de ejecutar T11-01 a T11-04;
hasta entonces no se declara aceptación física ni persistencia E3/E4 para las
funciones nuevas.
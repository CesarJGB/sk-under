# Fase 9.5 — Desbloqueo real de armas para la mesa de forja

Fecha: 2026-11-26

## Objetivo

Completar la fase 9.4: no basta con registrar un arma con un contador positivo.
La mesa de forja compara ese contador con un umbral individual. Esta fase
investiga la regla exacta, extiende el catálogo con el requisito de cada arma y
añade una operación separada para desbloquear la forja sin reducir progreso ni
tocar sistemas ajenos.

Toda la investigación de muestras y de CRDE fue de solo lectura. No se
consumieron créditos, no se modificaron cuentas remotas y no se atribuye a CRDE
ninguna implementación interna que no se haya observado.

## Conclusión principal

El cliente 8.8.0 compara el contador de `statisticData.object2ObtainTime` con
`UIForge.UnlockCountDict[nivel]`. Si la clave del nivel no existe, usa `8`. La
tabla estándar es:

| Nivel | Umbral | Evidencia |
| --- | --- | --- |
| 0 | 2 | E2 (desensamblado + wiki + observación física de blancas) |
| 1 | 3 | E2 |
| 2 | 4 | E2 |
| 3 | 6 | E2 |
| 4 | 6 | E2 |
| 5 | 8 | E2 (fallback del diccionario) |
| 6 o ausente | 8 | E2 (fallback del diccionario) |

La semántica del contador y su relación con la forja se registran como **E3**
por la validación física del propietario en Android 8.8.0.13. La operación
masiva de forja sigue en **E2** hasta su comprobación física.

## Método

Se reutilizaron:

- Guardado iOS avanzado C obtenido con la vista RAW autorizada de CRDE.
- Cuenta Android avanzada A y cuenta Android nueva B.
- Guardados locales 8.6 y 8.8.0 del repositorio.
- APK 8.8.0 original y `libil2cpp-arm64.so` con metadata descifrada.
- Catálogos SKDFE, `weapons.txt`, `weapons-880.json` y la documentación pública
  de la mesa de forja.

No se usaron como prueba los valores concretos de la cuenta iOS para deducir el
umbral. Esa cuenta tiene las 995 armas con valores entre 10 y 82 (mediana 46),
muy por encima de cualquier umbral. Son contadores de una cuenta avanzada, no
una tabla de requisitos.

## Evidencia de desensamblado

Metadata 8.8.0 (`Assembly-CSharp`):

- `UIForge` (tipo 5191) contiene `UnlockCountDict : Dictionary<int,int>` y
  `GetWeaponUnlockCount`.
- `UIForge.GetWeaponUnlockCount(int)` devuelve
  `UnlockCountDict.GetValueOrDefault(clave, 8)`.
- La sobrecarga que recibe un arma obtiene primero su nivel con
  `UIForge.GetWeaponLevel` y consulta el diccionario por ese nivel.
- `UIForge.IsUnlockedByObtainTime` lee el contador con
  `StatisticData.GetObtainTime`, obtiene el nivel, consulta
  `UnlockCountDict.TryGetValue(level, out required)` y devuelve
  `count >= required`; si no hay entrada, `required = 8`.
- `UIForge.GetWeaponLevel` intenta `TbWeapons.DataMap[clave].Level`, luego
  `WeaponInfo` y finalmente el prefab.
- `WeaponForgeDetailWindow` muestra `_unlockProgressRoot` y
  `_fusionUnlockProgressRoot`, y distingue `ForgeFailReason.WeaponNotUnlock`.
- `TaskSystem.ProgressChecker` usa los mismos contadores
  (`ObtainWeaponTimes`, `WeaponUnlockForgeCount`).

La tabla `TbWeapons` vive dentro del bundle Luban cifrado y no se pudo extraer
completamente. Por eso el catálogo usa el nivel del prefab (`RGWeapon.item_level`)
como aproximación y marca explícitamente las excepciones. No se afirma que ese
nivel sea siempre idéntico a `TbWeapons.Level`.

## Objetivos de fusión

Los objetivos de fusión son la excepción conocida. `weapon_337` (Subfusil UZI
Romántico) es objetivo de `weapon_005` (UZI) y el propietario observó **1/2** en
el juego, no 1/6. Por eso:

- `weapon_337` tiene requisito confirmado **2**, evidencia **E3**.
- Los otros 60 objetivos de fusión forjables usan el umbral estándar de su nivel
  de prefab como **proxy provisional** (`Aurora`, nivel 3 → 6; `Rayo de Zeus`,
  nivel 4 → 6) y quedan con estado `pending_fusion_research`.
- El proxy aplica el mínimo estándar, no un 8 arbitrario. Si `TbWeapons.Level`
  difiere del prefab, el contador puede quedar por encima del umbral real, pero
  nunca por debajo si el nivel de prefab es igual o mayor.
- No se presenta el proxy como umbral confirmado para esas 60 armas.

No hay evidencia suficiente para afirmar que todos los objetivos de fusión usen
2. Tampoco se escribe `fusionWeaponPathUnlock` ni `forgeWeaponMaterialPayments`.

## Otras excepciones y sistemas

- **No forjables**: 501 armas del catálogo. No se seleccionan ni se escriben.
- **Mitológicas**: `itemData.mythicWeapons` es una lista de `{id, level}`. No se
  ha demostrado que esa lista conceda la posesión ni que el nivel máximo sea 3.
  Solo se documenta; no se añadió escritura mítica.
- **Planos**: `itemData.blueprints` es independiente. No se ha demostrado que
  una arma requiera plano para desbloquear la forja.
- **Evolución**: `weaponEvolutionData.weapons` es cosmético y no concede el arma
  base. No se modifica.
- **Cola de forja**: `itemData.forgeWeapons` es transitoria. Se lee, pero no se
  escribe.
- **Anillos**: el catálogo 8.8.0 marca cuatro anillos como forjables de nivel 0;
  se tratan con la regla estándar 2, sin evidencia física específica.

## Cambios en el catálogo

`knowledge/tools/build_backend_weapons.py` añade a las 995 filas:

- `required_obtains`: umbral confirmado o `null`.
- `recommended_obtains`: objetivo seguro para la operación.
- `requirement_status`: `standard_level`, `observed_fusion_exception`,
  `pending_fusion_research`, `pending_level_research` o `not_forgeable`.
- `unlock_method`: `obtain_counter`, `fusion` o `not_forgeable`.
- `requirement_basis`, `requirement_evidence`, `additional_requirements` y
  `requirement_source`.

Distribución resultante:

- 433 armas con regla estándar.
- 60 objetivos de fusión con umbral estándar provisional.
- 1 excepción de fusión confirmada (`weapon_337`).
- 501 armas no forjables.

`backend/app/catalogs/weapons.py` valida estados, tipos, fuentes y que un arma
no forjable no declare contador objetivo.

## Implementación del editor

Se mantienen dos operaciones distintas:

### A. Descubrir armas

`prepare_weapon_progression_edit` conserva el comportamiento 9.4: eleva
contadores ausentes o en cero a 1. No reduce valores, no toca la cola de forja y
restaura exactamente el subárbol de estadísticas para verificar que no cambió
nada más.

### B. Desbloquear para forja

`prepare_weapon_forge_unlock_edit` eleva cada arma seleccionada a
`max(contador_actual, recommended_obtains)`. Para armas estándar el objetivo es
el umbral de su nivel; para objetivos de fusión es el mismo umbral de nivel como
proxy provisional. La operación:

- Es idempotente: si todas las armas ya alcanzan el objetivo, devuelve el mismo
  documento sin cambios.
- Nunca reduce contadores.
- Conserva claves desconocidas, enemigos, jefes, anillos y contadores ajenos.
- No escribe `itemData.forgeWeapons`.
- No escribe planos, evolución, skins ni mitológicas.
- Verifica reapertura, serialización estable y restauración byte a byte del
  resto del árbol.

El plan unificado usa una clave separada, `weapon_forge_unlock`. Si el usuario
selecciona la misma arma para descubrir y para forjar, la operación de forja
subsume el descubrimiento y se evita un conflicto de campos.

## Interfaz

La categoría Armas conserva su estructura y añade dos pestañas claras:

- **Descubrir armas**: la vista 9.4.
- **Desbloquear para forja**: selección individual y masiva por categoría.

Cada fila muestra nombre, identificador, rareza inferida del nivel, estado de
descubrimiento, contador actual, umbral requerido, contador propuesto, estado de
forja y requisitos adicionales. Los filtros permiten ver pendientes, todas,
bloqueadas, desbloqueadas, solo forjables y no forjables. La edición rápida
incluye una acción separada «Desbloqueo para forja».

## Pruebas

Cubiertas en backend y Playwright:

- Umbrales 2, 3, 4, 6 y 8 por nivel.
- Excepción física `weapon_337`.
- Umbral provisional por nivel para objetivos de fusión.
- Contadores en 1 creados por 9.4, contadores superiores y contadores ausentes.
- Armas no forjables y selección vacía.
- Conservación de cola de forja, claves desconocidas y estadísticas ajenas.
- Idempotencia y rollback exacto.
- Plan unificado con descubrimiento, forja, skins y efectos.
- Interfaz móvil, filtros y propuesta actual/objetivo.

## Limitaciones y preguntas abiertas

- Extraer `TbWeapons.Level` del bundle Luban para eliminar la aproximación por
  nivel de prefab.
- Confirmar si los 60 objetivos de fusión restantes usan el nivel de prefab o
  un `TbWeapons.Level` distinto, como ocurre con `weapon_337`.
- Confirmar si alguna arma requiere plano, evolución, investigación u otra
  condición además del contador.
- Confirmar en dispositivo que la operación masiva abre la forja de todas las
  armas estándar.
- Verificar la interacción con armas mitológicas antes de añadir escritura en
  `itemData.mythicWeapons`.

## Lista de validación física

1. Aplicar «Desbloquear para forja» a un arma blanca, verde, azul, morada y
   naranja; comprobar que la mesa muestra el arma y permite forjarla.
2. Repetir con `weapon_337` y otro objetivo de fusión; comprobar si 2 basta o si
   el juego exige otro valor.
3. Comprobar que un arma con contador superior al umbral conserva su valor.
4. Verificar que enemigos, jefes, anillos y contadores desconocidos no cambian.
5. Verificar que las skins y los efectos de eliminación siguen intactos.
6. Confirmar que las armas no forjables y las mitológicas no se alteran.
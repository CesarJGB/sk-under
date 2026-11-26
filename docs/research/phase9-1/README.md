# Fase 9.1 — Decoraciones, desbloqueos y progresión avanzada

## Alcance y método

La fase combina la comparación de las dos cuentas autorizadas con la
implementación de escritores y controles en el editor. Las cuentas se usaron
solo en lectura: se descargaron sus agregados de nube, se verificó su formato y
se compararon sin subir ningún candidato. No se publican credenciales, tokens,
identificadores privados ni guardados completos.

## Autenticación y descargas

- Cuenta A (mayor progreso): inicio de sesión correcto y descarga de nube
  correcta. Agregado descodificado de 912.375 bytes; `serialzedVersion` 1;
  `gameVersion` 2145; 6.679.101 gemas.
- Cuenta B (menor progreso): inicio de sesión correcto y descarga de nube
  correcta. Agregado descodificado de 222.148 bytes; `serialzedVersion` 1;
  `gameVersion` 2155; `itemData.AppVersion` 80800; 447.500 gemas.
- Ambas descargas fueron de solo lectura. No se preparó ni se subió ninguna
  partida remota durante la investigación.

## Diferencias estructurales relevantes

### Mascotas

- A: `statisticData.event2Count` con 307 claves y 115 claves de mascota.
  Todas las mascotas presentes tienen `_intimacy`, `_full_intimacy = 1` y
  `_action_unlock = 1`. `pet_full_intimacy = 35`.
- B: 23 claves en `event2Count`, **ninguna clave de mascota** y sin
  `pet_full_intimacy`, pero `gameData.petUnlock` contiene las 58 mascotas en
  `true`.
- La ausencia de `pet_<ID>_intimacy` en una mascota desbloqueada representa el
  estado inicial cero. No se observó ninguna clave de acción especial creada
  automáticamente al desbloquear.
- A confirma máximos de 240 para la mayoría de ids 0..55, 180 para 30/31 y 300
  para 34. Los ids 27, 56 y 57 no aparecen; su máximo sigue sin demostrarse.

### Planos

- A usa texto: 344 claves, 312 `Researched` y 32 `Got`.
- B usa enteros: 21 claves, todas con valor `1`. Las claves de B coinciden en su
  mayoría con estados `Got` de A, por lo que `1` se interpreta como obtenido.
  `2` como investigado es una deducción del mismo enum y queda marcada como no
  confirmada.
- A contiene simultáneamente la forma con prefijo y sin prefijo para algunos
  decorados, por ejemplo `blueprint_multi_room_skin_1` (Researched) y
  `multi_room_skin_1` (Got). El escritor conserva la forma existente y no
  duplica alias.
- 228 claves de A no tienen una fila reconocida en el catálogo ampliado. Se
  añadieron 31 identificadores observados con evidencia E2; el resto permanece
  intacto y se muestra como no reconocido, sin sobrescribirse.

### Vestíbulo y decoraciones

- A: los diez objetos observados están presentes en
  `itemData.roomDecorateDic`, todos con valor `[0]`.
- B: solo `ItemEggMachine: [0]`.
- `gameData.unlockRoomDecorate` está vacío en ambas cuentas y no sirve como
  indicador de desbloqueo de objetos.
- `gameData.roomObjectLevel`: A tiene `Book`, `CatFood`, `Planet` y `Safe` en 5
  y `Chest` en 1; B tiene todas las claves en 0. Se usa el máximo observado por
  clave y no se extrapola a claves nuevas.
- `gameData.currentRoomDecorate` es `"Common"` (texto) en A y `0` (entero) en B.
  El mapa de selección no está determinado; la interfaz lo muestra en solo
  lectura.
- Las apariencias temáticas se poseen como planos sin prefijo
  (`multi_room_skin_*`, `garden_skin_*`, `hall_skin_*`, `magic_area_skin_*`,
  `work_shop_skin_*`). La obtención y la investigación se gestionan desde
  Planos; la selección activa no se edita.

### Joyería, plantas y forja

- A tiene 9 joyas con `durability = 5000000`, `rune1 = "None"` y
  `rune2 = "None"`; B no tiene joyas. No se demostró que 5.000.000 sea el
  máximo universal ni se conocen identificadores de runas válidas.
- A tiene 8 parcelas con plantas reales y estados 1, 2 y 4; B tiene 3 plantas y
  5 posiciones nulas. No se demostró qué representa cada estado de crecimiento,
  por lo que no se implementa maduración.
- `itemData.forgeWeapons` contiene cuatro posiciones con armas o `null` en ambas
  cuentas y no representa el desbloqueo permanente. No se encontró una
  representación fiable del desbloqueo permanente por contadores de obtención.

## Causa de los bloqueos de la fase 9.0

- **Afinidad:** el lector exigía que existiera una clave de intimidad o de
  máximo para considerar editable la mascota. La cuenta B demuestra que una
  mascota desbloqueada puede no tener ninguna clave; además, las mascotas de A
  ya estaban en el máximo, por lo que tampoco eran editables. El problema era
  del editor, no una prueba de rechazo del juego.
- **Planos:** el escritor solo aceptaba claves ya presentes y los controles
  deshabilitaban los planos ausentes. La cuenta B usa otra codificación
  (enteros) que el lector anterior no contemplaba. El bloqueo era del editor,
  no del cliente.

## Funciones implementadas

- Creación controlada de `pet_<ID>_intimacy = 0` para mascotas desbloqueadas;
  al alcanzar el máximo se crea `_full_intimacy = 1`. Nunca se toca
  `_action_unlock` ni `pet_full_intimacy`.
- Edición individual, maximización individual y masiva de afinidad con
  exclusiones y explicación del motivo de incompatibilidad.
- Planos: obtención e investigación individual y masiva, creación de registros
  ausentes del catálogo, alias, búsqueda, filtros y conservación de claves
  desconocidas. Sin retrocesos `Researched → Got`.
- Nueva categoría Decoraciones: apariencias en solo lectura, desbloqueo de los
  diez objetos observados y mejora de niveles hasta el máximo observado.
- Integración en el borrador global, preparación unificada, respaldo, una sola
  subida por lote, verificación y restauración.

## Funciones experimentales pendientes de validación física

- Escritura de afinidad y de la marca de máximo.
- Creación de planos en cuentas con codificación entera y valor `2` para
  investigado.
- Desbloqueo de objetos del vestíbulo mediante creación de `[0]`.
- Mejora de niveles de mobiliario.
- Cualquier selección de apariencia activa.

## Pendiente con motivo técnico

- **Selección de apariencias:** `currentRoomDecorate` cambia de tipo entre las
  dos cuentas y no se conoce el mapa de valores; no se inventa.
- **Máximos de afinidad 27/56/57:** no hay claves ni configuración recuperada.
- **Joyería:** no se conoce el máximo de durabilidad ni identificadores de runas.
- **Cultivos:** no se conoce la semántica de `state` ni el ciclo de crecimiento.
- **Forja permanente:** no se localizó un contador fiable de desbloqueo por arma.
- **Nivel máximo de la sala:** solo se observó `roomLevel` 0 y 1; no se extrapola.

## Verificación

- Backend: 697 pruebas superadas, 16 omitidas.
- Frontend: compilación TypeScript y build de producción correctos.
- Playwright: 89 pruebas superadas, 23 omitidas.
- Pruebas nuevas con estructuras anonimizadas derivadas de A/B: creación de
  afinidad inicial, máximo con marca, planos de texto y enteros, alias, sin
  retrocesos, decoraciones, niveles, exclusiones en el plan y combinación de
  varias categorías en un mismo borrador.

## Validación manual sugerida en Android

1. Afinidad: elegir una mascota desbloqueada sin registro, subir a un valor
   intermedio, guardar, reiniciar y comprobar el valor. Después maximizar y
   comprobar que la acción especial y el contador global no cambian.
2. Planos: obtener un plano ausente y otro ya obtenido, investigar uno, guardar
   y comprobar los estados en el juego. Repetir en una cuenta con codificación
   entera.
3. Decoraciones: desbloquear un objeto ausente, comprobar que aparece en el
   vestíbulo y que no se modifica ninguna clave desconocida.
4. Mobiliario: subir un objeto por debajo del máximo observado y comprobar que
   el juego conserva el nivel.
5. Restauración: deshacer el lote y verificar que desaparecen las claves
   creadas y que el guardado vuelve a su SHA original.

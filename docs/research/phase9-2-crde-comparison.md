# Fase 9.2 — Comparación CRDE, desbloqueos avanzados y formato iOS

Fecha: 2026-11-26

## Alcance

Esta fase combina tres fuentes: una cuenta Android avanzada (A), una cuenta
Android nueva (B) y una cuenta iOS avanzada (C) leída a través del editor
externo CRDE. El objetivo fue explicar por qué SK-Under podía cambiar el nivel
de un objeto del vestíbulo sin desbloquearlo, corregir el escritor y separar la
compatibilidad del formato de partida de la compatibilidad de autenticación y
sincronización.

Toda la investigación fue de solo lectura. No se envió ningún formulario de
modificación a CRDE, no se subió ningún candidato de SK-Under y no se alteró la
cuenta remota.

## Acceso a CRDE

- El inicio de sesión con la cuenta de pruebas autorizada funcionó.
- La cuenta de juego vinculada es de canal iOS, juego SK, versión 8.8.1.
- El editor muestra categorías de modificación masiva (recursos, planos,
  vestíbulo, héroes, mascotas, skins, monturas, trofeos, pase de batalla), además
  de un editor RAW.
- El editor RAW de su propia interfaz devolvía `400 Bad Request` al solicitar
  el documento. El endpoint de visualización invocado directamente desde el
  contexto autenticado de la página devolvió el guardado completo en JSON.
- El documento llegó ya descodificado. No se observó compresión ni un sobre
  adicional en esa respuesta.
- No se copió código, diseño ni implementación privada de CRDE. Solo se usaron
  sus funciones normales de visualización y exportación.

La muestra C se conserva fuera del repositorio. El repositorio solo contiene
resultados saneados, recuentos y estructuras sintéticas.

### Funciones observadas en la interfaz

| Área | Observación |
| --- | --- |
| Cuenta vinculada | Cuenta de juego de canal iOS, juego SK, versión 8.8.1 |
| Recursos | Gemas, monedas de temporada, materiales, peces y plantas |
| Progreso | Pase de batalla, tarjeta de renacimiento, macetas y monedas iniciales |
| Vestíbulo | Desbloqueo masivo del vestíbulo y skins del vestíbulo |
| Personajes | Desbloqueo de héroes y habilidades |
| Mascotas | Desbloqueo de mascotas |
| Apariencias | Skins, skins de arma, monturas, efectos de muerte y trofeos |
| Planos y forja | Investigación masiva de planos y desbloqueo de la mesa de forja |
| Datos | Editor RAW y migración de datos entre cuentas |
| Exportación | No se localizó un botón independiente de descarga o respaldo; la visualización RAW fue el mecanismo utilizado |

La interfaz presenta estas operaciones como casillas masivas, no como edición
granular por identificador. SK-Under mantiene la edición granular por categoría,
el borrador único y la verificación; no se copió la implementación de CRDE.

## Muestras

| Muestra | Plataforma | Perfil | `gameVersion` | `AppVersion` | Tamaño | Secciones |
| --- | --- | --- | --- | --- | --- | --- |
| A | Android | Avanzada | 2145 | ausente | 912.375 B | 14 |
| B | Android | Nueva | 2155 | 80800 | 222.148 B | 17 |
| C | iOS (CRDE) | Avanzada | 2155 | 1531 | 235.438 B | 14 + `_crde_misc` |

Hashes SHA-256 de los documentos descodificados:

- A: `dd938340c39b96e4daf5bcb3c7362de949adf371ae5efda3999680c5bc82b0a4`
- B: `dcb8ab17c9c59a7544643a2b8184be7e3a9c463cbe5f83cc88ca76f3d25b7d5a`
- C: `c3e22a8c1e67580078583fffa1755dca6cf4a106b869e3a8e8f30fd5fe4cddee`

A y B incluyen `cloudSaveId`, `platformId`, `serialzedVersion` y `maps` en el
nivel superior. C no los incluye: CRDE los conserva en `_crde_misc`
(`platformId` de canal iOS y `maps` vacío). `_crde_misc` es metadato del editor
externo, no una sección del guardado del juego.

## Comparación estructural

### Secciones comunes

Las tres muestras comparten `gameData`, `itemData`, `statisticData`,
`settingData`, `seasonData`, `taskData`, `weaponEvolutionData`,
`mallReloadData`, `monsterRiseData` y `battlePassSaveData`/`pvpData`/`escapeSeasonData`
según la versión. A y B conservan el sobre de nube de Android; C llega sin ese
sobre y con metadatos del editor.

### Campos exclusivos o con tipos distintos

| Campo | A | B | C | Interpretación |
| --- | --- | --- | --- | --- |
| `serialzedVersion` | 1 | 1 | ausente | Sobre de nube, no estructura de juego |
| `platformId` | UUID | `GP` | en `_crde_misc` | Metadato de cuenta/plataforma |
| `cloudSaveId` | presente | presente | ausente | Sobre de nube |
| `maps` | presente | presente | ausente | Sobre de nube |
| `currentRoomDecorate` | `"Common"` | `0` | `0` | Tipo no determinado; selección |
| `blueprints` | texto | entero | entero | Codificación por cuenta/versión |
| `itemData.AppVersion` | ausente | 80800 | 1531 | Versión de esquema de items |
| `jewelryData` | 9 joyas | `{}` | `{}` | Progreso, no plataforma |
| `plants` | 8 parcelas | 3 + 5 nulos | 3 + 5 nulos | Progreso |
| `passInfo` | amplio | `{}` | `{}` | Progreso/versión |
| `trainingJourney` | ausente | vacío | vacío | Estructura de versión nueva |
| `_crde_misc` | ausente | ausente | presente | Metadato del editor externo |

No se atribuye ninguna diferencia a iOS por sí sola: A usa una versión anterior
y C tiene otro progreso. Las diferencias de tipo de `blueprints` y
`currentRoomDecorate` ya aparecían entre A y B, ambas Android.

### Identificadores compartidos

Los identificadores de objetos, planos, personajes, mascotas y decorados
coinciden entre plataformas. No se encontró un espacio de nombres distinto para
iOS. Los valores de cuenta (`cloudSaveId`, `platformId`) no son identificadores
de objeto y no deben transferirse entre cuentas.

## Hallazgo principal: desbloqueo del vestíbulo

La fase 9.1 creaba `itemData.roomDecorateDic.<objeto> = [0]` y subía
`gameData.roomObjectLevel`. Las pruebas del propietario confirmaron que el nivel
se conservaba, pero algunos objetos seguían bloqueados. La comparación A/B/C
muestra que la posesión y la disponibilidad funcional son estados distintos:

- A y C poseen los mismos diez objetos en `roomDecorateDic`, todos `[0]`.
- B solo posee `ItemEggMachine` y no tiene ninguna bandera `room_unlock_*`.
- A y C tienen banderas `statisticData.event2Count.room_unlock_*` para las
  instalaciones disponibles.
- Los cuatro decorados investigables tienen plano `room_decorate_*`
  `Researched` (texto en A, entero `2` en C).

La correlación es perfecta, pero no se ejecutó una modificación controlada en
el juego. Por eso la causa se clasifica como **Probable E2**, no como
confirmada. La corrección implementada crea la posesión y los requisitos
conocidos en el mismo candidato, sin declarar el objeto funcional hasta la
prueba física.

Detalle completo en [lobby-unlocks.md](lobby-unlocks.md).

## Otras estructuras investigadas

### Niveles y desbloqueo de personajes

- `gameData.heroLevel`: mapa personaje → entero. A tiene 37 entradas y ocho
  personajes en nivel 8; C tiene 42 entradas y `Knight` en 8. B tiene 42
  entradas, todas en 7.
- El máximo observado es 8, no 7. La maximización al 7 está confirmada en
  Android físico; el 8 observado no se ha validado con un escritor.
- `heroUnlock`: mapa personaje → booleano. A tiene 37, B y C 42.
- `heroSkill`: índice de habilidad seleccionada, no nivel.
- `heroSkillUnlock`: mapa personaje → lista `{Key, Value}`.
- `skinLock`: mapa personaje → lista `{Key, Value: 1}`.
- `currentSkinDatas`: mapa personaje → índice de skin seleccionada. El mapa
  índice → catálogo no está determinado.

### Mascotas

- `petUnlock`: A 46 entradas, B y C 58.
- `event2Count.pet_<id>_intimacy`: C confirma `pet_57 = 240` con
  `_full_intimacy = 1` y `_action_unlock = 1`.
- Los ids 27 y 56 siguen sin máximo observado.
- Los máximos 180/240/300 se mantienen como empíricos por id.

### Planos

- A: 344 claves de texto (312 `Researched`, 32 `Got`).
- B: 21 claves enteras de valor 1.
- C: 198 claves enteras, 24 de valor 1 y 174 de valor 2. Esto confirma
  `1 = Got`, `2 = Researched`.
- Los alias con y sin prefijo `blueprint_` se conservan según la forma existente.

### Vestíbulo y apariencias

- `roomObjectLevel`: A {Book 5, CatFood 5, Chest 1, Planet 5, Safe 5};
  B todo 0; C todo 5. El máximo observado por clave es 5, incluido `Chest`.
- `unlockRoomDecorate`: vacío en las tres cuentas; no es indicador.
- `roomLevel`: A 1, B 0, C 0; no indica desbloqueo.
- `roomDecorateCurSkinDic`: `{}` en las tres.
- `currentRoomDecorate`: texto en A, entero en B y C; mapa no determinado.
- Las apariencias se poseen como planos; la selección activa no se edita.

### Colecciones

- `handbookCollectionUserPropertiesInitialized`: ausente en A, `true` en B y C.
- `handbookEnemyCollectionTrackedLevels`: ausente en A, `{}` en B, enemigos con
  valor 6 en C.
- `handbookWeaponCollectionTrackedLevels`: ausente en A, `{}` en B y C.
- No se conoce la semántica del valor 6 ni la relación con recompensas. Solo se
  documenta; no se implementa escritor.

### Joyería, plantas y forja

- A tiene nueve joyas con `durability = 100` y runas `None`. No se conoce el
  máximo de durabilidad; la observación anterior de 5.000.000 no se replica en
  esta muestra.
- A tiene ocho plantas con estados 1, 2 y 4; B y C tres plantas con estado 1 y
  cinco posiciones nulas. Semántica de estados desconocida.
- `forgeWeapons` contiene tres armas y un `null` en las tres cuentas. No se
  identificó un contador permanente por arma.

## Matriz de compatibilidad

| Capacidad | Android A/B | iOS C | ¿Reutilizable? |
| --- | --- | --- | --- |
| Lectura de JSON descodificado | Sí | Sí | Sí, con adaptador de sobre |
| Secciones de juego | Sí | Sí | Sí |
| `blueprints` texto/entero | Sí | Entero | Sí, ya soportado |
| `roomDecorateDic` + banderas | Sí | Sí | Sí, tras corregir el escritor |
| Niveles de personaje | Sí | Sí | Sí, máximo 8 observado |
| `currentSkinDatas` | Sí | Sí | Lectura, no escritura |
| `serialzedVersion` | Sí | No en la respuesta CRDE | Escritura iOS sin validar |
| Autenticación y descarga | SK-Under existente | CRDE externo | No reutilizable tal cual |
| Sincronización | Validada en Android | No investigada | No declarar compatible |

## Clasificación de certeza

- **Confirmado**: los niveles de mobiliario se conservan en juego; `2` es
  `Researched` en la codificación entera (observado en C).
- **Probable**: las banderas `room_unlock_*` son el gate funcional; los planos
  `room_decorate_*` habilitan expendedora, pecera, pozo y estatua; el máximo de
  personaje observado es 8.
- **Experimental**: escribir banderas/planos para desbloquear; escribir nivel 8;
  crear intimidad; crear planos ausentes.
- **Desconocido**: gate exacto de expendedora y estatua sin plano; efecto de
  `room_decorate_fishbowl_level`; selección de apariencias; semántica de
  colecciones, estados de plantas, durabilidad de joyas y desbloqueo permanente
  de forja.

## Consecuencias para SK-Under

- El escritor de decoraciones crea `roomDecorateDic[objeto] = [0]`, la bandera
  `room_unlock_*` conocida y el plano `room_decorate_*` cuando corresponde.
- La interfaz distingue posesión, requisitos pendientes y disponibilidad
  funcional.
- `Chest` pasa a máximo 5; el máximo de personaje pasa a 8; el id 57 de mascota
  pasa a tener máximo 240.
- Se conservan las claves desconocidas, los tipos y la reversión byte a byte.
- El soporte iOS de escritura no se habilita en producción.

## Límites

- No se modificó la cuenta remota ni se subió ningún candidato.
- La lectura iOS depende de un editor externo; no se obtuvo un guardado nativo
  de iOS ni se investigó su autenticación.
- La muestra C no permite separar diferencias de plataforma de diferencias de
  versión o progreso.
- La eficacia del nuevo desbloqueo requiere prueba manual en dispositivo.
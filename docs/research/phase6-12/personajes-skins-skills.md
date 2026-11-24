# Personajes, skins y habilidades

## Catálogo de referencia

El catálogo versionado `backend/app/catalogs/characters-880.json`
proviene de SKDFE en el commit fijado
`57b9b86335c080caca55e178c8409cb67658ccf6` (8.8.0). Contiene:

- 42 personajes, en el orden del juego, con código (`Knight`, `Ranger`, …).
- 105 habilidades, tres por personaje, con índice, clave y nombre.
- 802 skins, agrupadas por personaje, con índice, clave `c<I>_skin<N>` y nombre.

El catálogo **identifica**; no demuestra que una cuenta posea el elemento. Las
claves de guardado se cruzan por código de personaje y por índice numérico. Un
ID desconocido se conserva como desconocido y no se traduce a ciegas.

## Rutas de guardado

Todas las rutas siguientes están en `gameData` del agregado y en
`files/game.data` local. Las preferencias Android proyectan algunas de ellas.

| Campo | Forma observada | Uso estructural | Nivel |
| --- | --- | --- | --- |
| `heroUnlock` | objeto código → bool (42) | Disponibilidad declarada del personaje | E2 |
| `heroLevel` | objeto código → entero (42) | Nivel de mejora del personaje | E3 para `Knight` |
| `heroSkill` | objeto código → entero (42) | Índice de habilidad seleccionada | E2 |
| `heroSkillUnlock` | objeto código → lista `[{Key, Value}]` | 105 entradas; 28 personajes con 3, 7 con 2 y 7 con 1; `Value` booleano | E2 |
| `skinLock` | objeto código → lista `[{Key, Value}]` | 802 entradas; `Value` entero | E2 |
| `currentSkinDatas` | objeto código → entero | Selección de skin; disperso | E2 |
| `petUnlock` | objeto código → bool (58) | Disponibilidad de mascota | E2 |
| `certificates` | lista de objetos | Certificados con héroe, tiempo, piedra y armas | E2 |
| `normalModePassCertificates` | lista | Certificados de pase normal | E2 |
| `roomObjectLevel` | objeto de 5 claves | Niveles de objetos del vestíbulo | E2 |
| `unlockRoomDecorate` | lista | Decoraciones desbloqueadas | E2 |

`heroUnlock`, `heroLevel`, `heroSkill` y `heroSkillUnlock` tienen exactamente 42
códigos en la copia de nube. `skinLock` contiene 42 listas y 802 entradas
totales. `petUnlock` tiene 58 códigos. Estos conteos coinciden con el catálogo
de personajes y con la observación previa de 58 mascotas.

## Estados observados

En la copia de nube 8.8.0:

- `heroLevel` vale 0 para los 42 personajes.
- `heroSkill` vale 0 para los 42; no se observó otra selección.
- `heroSkillUnlock` tiene 105 entradas: 42 con `(Key=0, Value=True)`, 35 con
  `(Key=1, Value=False)` y 28 con `(Key=2, Value=False)`. La forma es
  consistente, pero solo la primera habilidad aparece desbloqueada en esa
  cuenta. No se generaliza a todas las cuentas.
- `skinLock` contiene 802 entradas `{Key, Value}`. Los valores observados
  incluyen `1`, `0`, enteros negativos y enteros positivos de cuatro y cinco
  cifras. La distribución no es uniforme: `0` aparece 221 veces, `-13` 146
  veces, `-6` 112 veces y `12000` 59 veces. Son **estados crudos**, no precios
  ni posesión confirmada.
- `currentSkinDatas` está vacío en esa copia. En las capturas del cliente
  aparecen entradas dispersas, por ejemplo el personaje con la skin 0
  seleccionada. La ausencia de una entrada no se interpreta como “sin skin”.
- `petUnlock` contiene 58 booleanos; solo uno aparece verdadero en la copia de
  nube. El catálogo de mascotas no define por sí solo el estado.

### Lectura de `skinLock`

La forma real es un diccionario por personaje cuyos valores son listas de
objetos. El siguiente es un ejemplo sintético de forma, no una cuenta:

```json
"skinLock": {
  "Ejemplo": [
    {"Key": 0, "Value": 1},
    {"Key": 1, "Value": 2000},
    {"Key": 2, "Value": -2}
  ]
}
```

Hipótesis compatibles con lo observado:

- `Key` es el índice de skin dentro del personaje y se cruza con
  `c<I>_skin<N>`.
- `Value=1` puede representar la skin inicial o una posesión normal.
- Los valores positivos grandes pueden ser precios o costes de compra.
- Los valores negativos pueden ser requisitos, bloqueos o estados internos.

Ninguna de esas hipótesis tiene todavía una acción controlada. En particular,
no se debe convertir un valor positivo en “desbloqueado” ni un negativo en
“bloqueado” sin una prueba. Editar una skin podría romper una relación con
`currentSkinDatas`, con la tienda o con las preferencias.

La forma de `heroSkillUnlock` es análoga pero tiene una clave por habilidad del catálogo (105 en total; no todos los personajes tienen tres). La descripción histórica que asumía tres claves por
personaje. En la muestra, la clave 0 está desbloqueada y las claves 1 y 2 no.
Las preferencias usan nombres como `<perfil>_c_<código>_skill_<N>_unlock`; el
cruce exacto entre el índice del JSON y el sufijo XML está pendiente.

## Progreso y acceso

La única relación de progreso con evidencia E3 en esta fase es la mejora del
Caballero: una acción controlada de mejora por 500 gemas cambió
`heroLevel.Knight` de 0 a 1, acompañada del cargo de gemas y de un cambio en
`event2Count.tutorial_830_group_3_stage`. La estrella del HUD y la persistencia
tras reiniciar respaldan el resultado. No se observó el desbloqueo de un
personaje nuevo ni el de una habilidad.

Por tanto:

- `heroLevel` es progreso modificable por una acción legítima, pero su escala y
  sus requisitos por nivel no se conocen.
- `heroUnlock` declara disponibilidad; no se sabe si un `false` significa
  “no comprado”, “no desbloqueado por progreso” o “sin inicializar”.
- `heroSkillUnlock` y `skinLock` mezclan posesión, requisitos y posiblemente
  precios; no se editan.
- Las compras premium y los entitlements de tienda son de solo lectura.

## Diferencias entre capas y modos

- La nube y `game.data` comparten los nombres y la forma de los seis mapas
  principales. Las preferencias proyectan subconjuntos.
- `escapeSeasonData` tiene su propia selección (`selectedHero`,
  `selectedSkill`, `selectedSkin`) y no sustituye a `currentSkinDatas`.
- `pvpData.pvpCharacterSelectionByGameName` y
  `pvpSkinSelectionByHero` son selecciones de PvP.
- `monsterRiseData.lastCharacterIdx` y `lastCharacterSkinIdx` son índices de
  ese modo, no códigos de personaje.
- La muestra 8.6.0 no contiene `game.data`; no se puede comparar estos mapas
  con 8.8.0 en esa capa.

## Preparación para una fase posterior

La infraestructura de lectura ya permite:

1. cargar 42 personajes y cruzar códigos con el catálogo;
2. listar niveles, habilidades y skins sin imprimir valores;
3. comparar dos capturas por ruta exacta, incluyendo índices de lista;
4. distinguir campo ausente, `null`, `false` y `0`.

Antes de escribir cualquier campo de personaje habría que demostrar, con una
acción oficial y una recuperación, qué valor representa posesión, cuál es
precio y cuál es selección. Hasta entonces la política es de solo lectura.
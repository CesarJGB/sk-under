# Oportunidades de la Fase 7.0

Este informe clasifica futuras funciones del editor según la información ya
disponible en el Save Knowledge Engine. No propone habilitar escrituras en esta
fase. Su objetivo es decidir qué categorías pueden pasar a validación controlada
y qué experimentos faltan.

## Criterios

- **Información**: campos, catálogo y estructura disponibles.
- **Claridad**: rutas y tipos estables frente a semántica pendiente.
- **Evidencia**: nivel máximo confirmado para el aspecto que se quiera editar.
- **Catálogos**: cobertura de identificadores y nombres.
- **Dependencias**: relaciones confirmadas u observadas que deban conservarse.
- **Complejidad**: esfuerzo de diseño, edición y verificación.
- **Riesgo**: probabilidad de romper otra estructura o de que el cliente ignore
  el cambio.
- **Experimentos**: pruebas mínimas antes de exponer un control.

## Prioridades

### 1. Inventario

| Aspecto | Estado |
| --- | --- |
| Campos | `itemData.materials`, `seeds`, `plants`, `blueprints`, `commodities`, `tokenTickets`, `specialTickets`, `jewelryData` |
| Evidencia | Existencia y tipo E2; semántica de materiales E2; blueprints E2 |
| Catálogos | 343 materiales (154 con nombre), 47 semillas, 47 plantas, 265 planos (4 con nombre), 19 tokens, 15 joyas |
| Dependencias | Planos ↔ materiales; semillas ↔ plantas; tickets/vales; jardín |
| Complejidad | Media |
| Riesgo | Medio |
| Listo para validación | **Sí, por subfamilias** |

**Qué hacer primero**: materiales y semillas. Son mapas con identificadores
estables y catálogo razonable. Los planos tienen 265 claves pero solo 4 nombres
localizados; conviene resolver el nombre desde el objetivo antes de exponer una
lista al usuario.

**Experimentos**:

1. Editar un único material en una copia de laboratorio, conservar todas las
   demás claves y confirmar lectura en el cliente.
2. Añadir/retirar una semilla y comprobar la relación con `plants` y el jardín.
3. Cambiar el estado de un plano (`Got`/`Researched`) y verificar que el cliente
   lo acepta sin alterar materiales.
4. Repetir tras un re-guardado oficial para comprobar persistencia.

### 2. Mascotas

| Aspecto | Estado |
| --- | --- |
| Campos | `gameData.petUnlock` |
| Evidencia | Estructura E2; semántica de desbloqueo E2/E3 parcial |
| Catálogos | 58 mascotas, 57 habilidades; 56 con nombre |
| Dependencias | `petUnlock` ↔ catálogo de mascotas; selección activa no localizada |
| Complejidad | Baja |
| Riesgo | Medio |
| Listo para validación | **Sí, desbloqueo individual** |

**Ventaja**: el campo es un mapa booleano por código, con catálogo directo. Es
una de las categorías más pequeñas y verificables.

**Cuidado**: `Hide` (id 17) no tiene nombre y `Fish Chip King` (id 57) no tiene
código. La selección activa de mascota no está identificada con evidencia
suficiente; no debe inferirse de `petUnlock`.

**Experimentos**:

1. Desbloquear una mascota no poseída y conservar el resto del mapa.
2. Confirmar aparición en el cliente y persistencia tras re-guardado.
3. Verificar que no cambia la mascota seleccionada.
4. Documentar el comportamiento de los identificadores sin nombre.

### 3. Niveles de personaje

| Aspecto | Estado |
| --- | --- |
| Campos | `gameData.heroLevel`, `heroUnlock`, `heroSkill`, `heroSkillUnlock` |
| Evidencia | Semántica E3 en nivel y desbloqueos; persistencia E2 |
| Catálogos | 42 personajes, 105 habilidades, 802 skins |
| Dependencias | Proyección XML `_c<ID>_level`; desbloqueo previo; límites funcionales desconocidos |
| Complejidad | Baja-media |
| Riesgo | **Alto** |
| Listo para validación | **Sí, con límites conservadores** |

**Ventaja**: el catálogo resuelve códigos y el campo ya tiene evidencia E3 para
su semántica. **Riesgo**: no se conoce el límite funcional por personaje; subir
por encima del máximo puede ser rechazado o mostrar un estado inconsistente. La
persistencia posterior a un re-guardado sigue pendiente.

**Experimentos**:

1. Subir un nivel dentro de un rango conservador y confirmar la proyección XML.
2. Verificar el límite visible en el cliente antes y después.
3. Re-guardar desde el cliente oficial y comprobar persistencia.
4. Repetir con un personaje no desbloqueado para documentar la dependencia.

### 4. Armas

| Aspecto | Estado |
| --- | --- |
| Campos | `weaponEvolutionData.weapons`, `Level`, `CurrentSkinIndex`, `UnlockedSkins`, `favorWeapons`, `itemData.forgeWeapons` |
| Evidencia | Estructura E2; semántica de evolución parcial |
| Catálogos | 1.081 armas (963 con nombre), 192 skins |
| Dependencias | Arma ↔ skin; forja ↔ materiales; planos de evolución/fusión |
| Complejidad | **Alta** |
| Riesgo | **Alto** |
| Listo para validación | **No todavía; separar por subfamilias** |

**Qué falta**: distinguir nivel de arma, progreso de forja, evolución, skin
equipada y skins desbloqueadas. `OriginalWeapon` no tiene semántica confirmada.
La relación entre `weapon_full.json` y las filas de configuración no es 1:1.

**Experimentos**:

1. Cambiar solo `Level` de un arma y verificar el cliente.
2. Desbloquear una skin sin cambiar `CurrentSkinIndex`.
3. Cambiar `CurrentSkinIndex` a una skin ya desbloqueada.
4. Probar una evolución con receta completa y confirmar materiales.
5. Repetir tras re-guardado.

### 5. Jardín

| Aspecto | Estado |
| --- | --- |
| Campos | `itemData.seeds`, `plants`; relación con `gameData.roomLevel` |
| Evidencia | Estructura E2 |
| Catálogos | 47 semillas y 47 plantas, todas con nombre |
| Dependencias | Semilla ↔ planta; inventario ↔ jardín |
| Complejidad | Media |
| Riesgo | Medio |
| Listo para validación | **Sí, después de inventario** |

El catálogo es completo en nombres, pero faltan estados de crecimiento y
espacios. Conviene validar primero la semilla y después la planta.

### 6. Vestíbulo y decoraciones

| Aspecto | Estado |
| --- | --- |
| Campos | `unlockRoomDecorate`, `roomObjectLevel`, `roomDecorateDic`, `currentRoomDecorate` |
| Evidencia | Estructura E2; `furniture_chest` XML E3 |
| Catálogos | 49 elementos; 28 con nombre; 4 planos de decoración |
| Dependencias | Desbloqueo ↔ mueble; nivel ↔ objeto; plano ↔ decoración |
| Complejidad | Media-alta |
| Riesgo | Medio-alto |
| Listo para validación | **Investigación adicional** |

Faltan nombres para 21 elementos y no está claro qué estructura controla cada
estado. Los planos de decoración son solo 4; el resto del vestíbulo requiere
resolver identificadores.

### 7. Progreso y estadísticas

| Aspecto | Estado |
| --- | --- |
| Campos | 169 en Estadísticas, 33 en Progreso y acceso |
| Evidencia | Mayoritariamente E2; semántica H |
| Catálogos | Enemigos, armas y personajes parcialmente relacionados |
| Dependencias | Registros de armas/enemigos, certificados, contadores |
| Complejidad | Alta |
| Riesgo | Alto |
| Listo para validación | **Solo lectura / diagnóstico** |

Es la categoría más amplia y la de menor claridad semántica. Muchos campos
parecen contadores internos. No se recomienda edición hasta aislar un contador
con efecto visible y reversibilidad.

### 8. Temporadas y pase de batalla

| Aspecto | Estado |
| --- | --- |
| Campos | 78 en Temporada, 9 en Pase de batalla |
| Evidencia | Estructura E2 |
| Catálogos | Contenido de temporada 10 claves; sin nombres |
| Dependencias | Monedas, chips, niveles, historiales de compra |
| Complejidad | Media-alta |
| Riesgo | Alto |
| Listo para validación | **Investigación adicional** |

`seasonData.chips` no es lo mismo que los chips de Monster Rise. Los historiales
de compra y las recompensas acumuladas pueden estar gestionados por servicios
externos.

### 9. Economía y derechos de compra

| Aspecto | Estado |
| --- | --- |
| Campos | Gemas (E4), fichas de pesca (E4), contadores acumulados, recibos |
| Evidencia | Fuerte en gemas y fishChip; compras externas E1 |
| Catálogos | Materiales y fichas |
| Dependencias | `gems = lastGems + varGems`; `fishChip` ↔ `material_fish` |
| Complejidad | Baja para saldos; alta para derechos |
| Riesgo | **Crítico** |
| Listo para validación | **Saldos sí; compras solo lectura** |

No deben modificarse recibos, derechos, estados de pago ni historiales. La
tarjeta de resurrección sigue sin campo escribible confirmado.

### 10. Skins y habilidades

| Aspecto | Estado |
| --- | --- |
| Campos | `skinLock`, `currentSkinDatas`, `heroSkill`, `heroSkillUnlock` |
| Evidencia | Semántica E3; persistencia E2 |
| Catálogos | 802 skins, 105 habilidades |
| Dependencias | Desbloqueo previo; selección equipada separada |
| Complejidad | Baja |
| Riesgo | Medio |
| Listo para validación | **Ya implementado; consolidar persistencia** |

No requiere una función nueva. La oportunidad es cerrar la prueba de
persistencia posterior a un re-guardado y documentar la diferencia entre
desbloqueo y selección.

### 11. Joyería, chips, monturas y seguidores

| Aspecto | Estado |
| --- | --- |
| Evidencia | E1 desde una muestra externa con forma de guardado |
| Catálogos | 15 joyas, 18 chips, 4 monturas, 6 seguidores |
| Dependencias | Monster Rise / estadísticas; no confirmadas |
| Complejidad | Media |
| Riesgo | Alto |
| Listo para validación | **No; falta observación propia** |

Los catálogos son útiles para nombres y relaciones, pero no hay estructura
observada en un guardado propio que confirme dónde vive cada estado.

## Agrupación para futuras fases

| Grupo | Categorías | Motivo |
| --- | --- | --- |
| A | Inventario + mascotas | Campos pequeños, catálogo amplio y experimentos independientes |
| B | Niveles + habilidades/skins | Comparten proyección de personaje y límites funcionales |
| C | Armas + planos | Requieren separar forja, evolución, nivel y skins |
| D | Jardín + vestíbulo | Dependen de inventario y desbloqueos |
| E | Temporadas + economía | Mayor riesgo; mantener saldos confirmados y compras en solo lectura |

## Recomendación

Empezar por **inventario de materiales y semillas** y por **desbloqueo de una
mascota**. Son los experimentos con menor superficie, catálogo suficiente y
dependencias acotadas. Después, cerrar la persistencia de **niveles de
personaje**. Las armas deben esperar a una fase específica que separe sus
subsistemas.

Ninguna de estas líneas debe habilitar escritura arbitraria por ruta JSON ni
automatizar escrituras en cuentas reales. Cada función debe reutilizar respaldo,
confirmación, verificación y restauración, y actualizar la evidencia solo después
del experimento correspondiente.
# Evidencia, hipótesis descartadas e incógnitas

## Niveles aplicados

| Nivel | Qué se observó en esta fase | Qué no se puede concluir |
| --- | --- | --- |
| E1 | Nombres de clases y métodos en la metadata 8.8.0; referencias de la wiki y de la comunidad | Que una ruta concreta sea la que usa el cliente en una transacción. |
| E2 | Presencia, tipo y forma de campos en el agregado y en archivos propios; conteos de catálogo | El significado de un valor, la autoridad del servidor o la persistencia tras una acción. |
| E3 | Una mejora legítima del Caballero cambió `heroLevel.Knight` y los campos de gemas; una recuperación restauró una copia anterior | Que la misma regla valga para todas las acciones o versiones. |
| E4 | La persistencia de gemas ya validada en 6.11 | Cualquier campo nuevo de esta fase: no hubo una transacción positiva de fichas ni un desbloqueo controlado de skin. |

## Evidencia por grupo

### Agregado y archivos

- La copia de nube real de 8.8.0 tiene 114.778 bytes y 17 entradas superiores.
  Se enumeraron sus 13 secciones de estado, `maps`, dos identificadores y
  `serialzedVersion`.
- La muestra local 8.8.0 contiene `game.data` y 18 archivos decodificados; la
  de 8.6.0 contiene nueve `.data` sin `game.data`.
- La comparación de esquemas no muestra claves superiores eliminadas entre 8.6
  y 8.8, pero sí campos nuevos. Esto es E2; no demuestra aceptación ni
  migración por el servidor.
- Las capturas Android muestran `game.data`, `item_data`, `statistic` y
  `shared_prefs` cambiando en momentos distintos. El guardado visible no es
  una copia instantánea de todas las capas.

### Gemas

La evidencia E3/E4 de 6.11 se conserva sin cambios. La fase 6.12 no modificó la
ruta de edición ni la política de bloqueo. La relación `gems = lastGems +
varGems` y el efecto de la recuperación siguen siendo el límite conocido.

### Fichas de pesca

- `gameData.fishChip` es entero en todas las muestras propias. Se encontraron
  34 ocurrencias de `fishChip` con valor 0 al recorrer 221 archivos JSON
  privados; ninguna positiva.
- La preferencia `<perfil>_furniture_fish_chips` aparece con valor 0 en el XML
  de 8.8.0 y en capturas posteriores a una recuperación. No estaba en las
  capturas previas.
- `_buyItemUseFishChipTimes` contiene usos históricos en 8.6.0, pero no un
  saldo.
- La metadata 8.8.0 muestra `AboGameData.fishChip` como `int` y métodos de
  `ItemData` para leer, sumar, consumir y convertir fichas.
- **No hubo una acción legítima de obtención o gasto de fichas.** Por tanto no
  se puede elevar `fishChip` a E3/E4, ni afirmar si el saldo mostrado procede
  del guardado local o del servidor.

### Personajes, skins y habilidades

- Se cruzaron 42 personajes, 105 habilidades y 802 skins con los mapas de
  `gameData`. Los conteos coinciden con el catálogo fijado.
- `skinLock` tiene 802 entradas con estados enteros muy variados; no se les
  asigna una semántica definitiva.
- `heroSkillUnlock` tiene 105 entradas, tres por personaje. La forma es estable;
  el significado de cada bool es una hipótesis razonable, no una prueba.
- `heroLevel.Knight` tiene E3 para una mejora. No se probó el desbloqueo de un
  personaje, una skin o una habilidad.

### Recursos

- Los mapas de materiales, semillas, cupones y planos son E2 en 8.6.0. En la
  nube 8.8.0 inspeccionada están vacíos o casi vacíos, así que su forma moderna
  poblada no está cubierta.
- Los planos de 8.6.0 usan valores de texto como `Researched`; no se
  convierten a un modelo numérico.
- Los catálogos reconocen la mayoría de los IDs, pero no todos. La ausencia de
  traducción no autoriza a borrar el ID.
- `object2ObtainTime` incluye armas, enemigos y jefes; no es un mapa exclusivo
  de armas.

## Hipótesis descartadas o corregidas

| Hipótesis inicial | Por qué no se sostiene | Corrección |
| --- | --- | --- |
| “Las fichas de pesca son `seasonData.chips`.” | Son 20 objetos con nombre, nivel y refinamiento de habilidad de temporada; no hay relación con la tienda de peces. | Mantenerlas como chips de temporada. |
| “`cumulativeFishCount` es el saldo de fichas.” | Es un contador de peces capturados; no tiene la forma de una moneda y no aparece junto a la tienda. | Es un contador histórico distinto. |
| “`buyFishCount*` son fichas.” | Son contadores de paquetes de peces en `mallReloadData`; no cambian con una transacción de fichas observada. | No vincularlos al saldo. |
| “La preferencia de fichas es una simple copia de `fishChip`.” | Solo se observó la igualdad en 0 y la aparición tras recuperar. No hubo un saldo positivo. | H, no E3. |
| “`fishChip` se puede editar como `gems`.” | No hay método de conciliación equivalente ni prueba de aceptación; el saldo nunca fue positivo. | Solo lectura. |
| “`skinLock` positivo significa desbloqueado.” | Los valores incluyen precios, requisitos y estados no explicados; no hay acción controlada. | Conservar el valor crudo. |
| “`generalSeed` cambió por la mejora.” | Varía entre capturas y no tiene relación causal con el nivel o las gemas. | No atribuirlo a la acción. |
| “La recuperación reconstruye todas las secciones.” | En 6.1 solo se actualizó `gems` entre los cinco campos; en 6.11 se restauró un estado anterior parcial. | La recuperación es selectiva y dependiente de la copia. |
| “El archivo sin sufijo siempre es la copia activa.” | Coexisten archivos sin sufijo y por perfil con tamaños distintos; no se probó la prioridad. | Elegir por perfil y contenido; no borrar. |
| “8.6.0 tiene las mismas rutas de nube.” | La muestra 8.6.0 no contiene `game.data` ni preferencias. | No extrapolar sin una muestra completa. |

## Incógnitas abiertas

1. ¿El saldo de fichas mostrado se lee de `gameData.fishChip`, de la
   preferencia o de una respuesta del servidor?
2. ¿Qué acción legítima produce fichas y cuál las consume?
3. ¿La recuperación proyecta `fishChip` igual que `gems` o solo crea la
   preferencia con 0?
4. ¿Los historiales de tienda son contadores, índices de producto o marcas de
   sincronización?
5. ¿Qué significan exactamente los valores de `skinLock` y `heroSkillUnlock`?
6. ¿`heroUnlock` distingue compra, progreso, tutorial o inicialización?
7. ¿Qué archivo gana entre la copia sin sufijo y la copia por perfil?
8. ¿`maps` y `sandbox_maps` son la misma estructura?
9. ¿Qué secciones adicionales (`battles`, `escape_run_save`) viajan en la nube
   en otras cuentas o versiones?
10. ¿El servidor acepta un agregado con una sección nueva, una ausente o un
    tipo cambiado? No se probó por seguridad.

## Pruebas que no se hicieron

- Compra o obtención de fichas de pesca.
- Conversión de fichas antiguas.
- Desbloqueo de un personaje, skin o habilidad.
- Recuperación de nube con fichas positivas.
- Pruebas en iOS o variantes regionales.
- Escritura de cualquier campo distinto de las gemas ya validadas.

No se rellenan estos huecos con inferencias. La fase 6.13 propone cómo
cerrarlos sin poner en riesgo la cuenta ni la integridad del guardado.
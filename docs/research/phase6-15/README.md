# Fase 6.15 — Edición conjunta de fichas de pesca y `material_fish`

La prueba manual de la Fase 6.14 confirmó que la nube conserva el valor editado de
`gameData.fishChip`, pero el saldo no apareció ni en el resumen de la partida ni
dentro del juego. El propietario recordó que un editor anterior requería cambiar
**dos** valores de pesca y que el segundo era `material_fish`. Esta fase convierte
esa pista en una prueba experimental conjunta, sin presentarla como validada.

> **Resultado posterior (Fase 6.16).** El propietario confirmó en un dispositivo
> Android físico que la modificación conjunta funciona: la nube conserva la copia,
> el saldo aparece dentro del juego, la compra de paquetes descuenta el importe
> correcto y el cliente oficial guarda el cambio posterior. La etiqueta
> experimental se retiró de la interfaz y el campo quedó en E4 para ese alcance.

## Alcance

El editor **Experimental · E2** de `/partida` aplica el mismo entero introducido
por el usuario a exactamente estas dos rutas del agregado:

| Ruta | Tipo observado | Papel |
| --- | --- | --- |
| `gameData.fishChip` | entero de 32 bits | saldo candidato de fichas de pesca |
| `itemData.materials.material_fish` | entero de 32 bits | material de pesca; segunda pista del propietario |

`material_fish` es una clave dentro del mapa `itemData.materials`, no un objeto
independiente. La edición conserva las demás claves del mapa, por ejemplo
`material_ticket`, y no toca `cumulativeFishCount`, los historiales
`fishChipStore*`, `mallReloadData.buyFishCount*` ni otros recursos. Si la clave
`material_fish` no existiera, se crea con el valor solicitado; la restauración
vuelve a eliminarla para reproducir el original byte a byte.

## Evidencia y límites

- **E2/H:** el agregado real 8.8.0 contiene ambas rutas, con
  `itemData.materials = {"material_fish": 0, "material_ticket": 5}`. Una muestra
  local 8.6.0 conserva `material_fish = 99999999`, lo que confirma que es una
  cantidad real de inventario, no una cadena de configuración.
- **E1/H:** la pista del propietario sobre el editor anterior. No se localizó una
  fuente pública que documente que ambos campos deban cambiarse juntos.
- La documentación de la Fase 6.12 clasificó `material_fish` como material de
  pesca separado del saldo de fichas. Por eso esta fase no afirma que sea una
  moneda ni que sustituya a `gameData.fishChip`: solo prueba la hipótesis de que
  el cliente necesita ambos valores sincronizados.
- No se ha validado la autoridad del servidor, la lectura por el cliente oficial,
  la aparición del saldo en el juego, el gasto, el reinicio ni el guardado
  posterior desde Android. La comprobación final corresponde al propietario en
  un dispositivo real.

## Flujo y verificaciones

1. Preparar la edición valida el sobre JSON, la serialización canónica, el tipo
   entero de ambas rutas y el rango 0..2 147 483 647.
2. El candidato cambia solo las dos rutas; la comprobación inversa restaura los
   valores originales y exige que el agregado sea idéntico al original.
3. La vista previa muestra el valor original y el nuevo de `fishChip` y de
   `material_fish`, además de `changed_fields`.
4. Se conserva el respaldo cifrado, la confirmación autenticada, la verificación
   por descarga y la restauración de la Fase 6.14. Los respaldos anteriores de
   solo `fishChip` siguen siendo legibles.
5. La subida verifica que la nube devuelve el candidato exacto. Esa comprobación
   demuestra persistencia remota, **no** efectividad dentro del juego.

## Comprobación local

La preparación se ejecutó sobre una copia real 8.8.0 de 114 778 bytes: el
candidato cambió `gameData.fishChip` de 0 a 7 y
`itemData.materials.material_fish` de 0 a 7, conservó `material_ticket = 5`,
mantuvo el tamaño y produjo un único tramo de diferencia binaria. La
comprobación inversa reprodujo el original. No se subió esa copia durante la
prueba automatizada.

## Validación

| Capa | Estado en 6.15 | Confirmación en 6.16 |
| --- | --- | --- |
| Persistencia en la nube | Comprobada por descarga posterior | Confirmada |
| Recuperación por el cliente oficial | Pendiente | Confirmada |
| Aparición del saldo dentro del juego | Pendiente | Confirmada |
| Capacidad de gastar las fichas | Pendiente | Confirmada con descuento correcto |
| Persistencia tras reiniciar | Pendiente | No comprobada por separado; el guardado posterior conserva el valor |
| Persistencia tras volver a guardar desde Android | Pendiente | Confirmada |

## Fuera de alcance

No se modifican XML ni PlayerPrefs, no se tocan autenticación, gemas, personajes,
habilidades, skins ni otros inventarios, y no se habilitan funciones ajenas a la
pesca. La edición de gemas mantiene su flujo y sus pruebas.
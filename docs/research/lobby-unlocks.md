# Desbloqueo de máquinas y objetos del vestíbulo

## Problema

La fase 9.1 desbloqueaba objetos creando
`itemData.roomDecorateDic.<objeto> = [0]` y subía
`gameData.roomObjectLevel`. Las pruebas manuales del propietario mostraron que
el nivel se conservaba, pero algunos objetos seguían sin estar disponibles.

## Causa identificada

La posesión y la disponibilidad funcional son estados distintos:

- `itemData.roomDecorateDic` indica que la cuenta **posee** la clave del objeto.
- `statisticData.event2Count.room_unlock_*` indica que la instalación está
  **habilitada**.
- Los decorados investigables requieren además su plano
  `itemData.blueprints.blueprint_room_decorate_*` en estado `Researched`.

Las cuentas avanzadas A (Android) y C (iOS) poseen los mismos diez objetos y
tienen las banderas de las instalaciones. La cuenta nueva B solo posee
`ItemEggMachine` y no tiene ninguna bandera `room_unlock_*`. La correlación es
perfecta. No se ejecutó una modificación controlada en el juego, por lo que la
causa se clasifica como **Probable E2**, no confirmada.

## Requisitos por objeto

| Objeto | Bandera | Plano | Evidencia |
| --- | --- | --- | --- |
| `ItemEggMachine` | — | — | B lo posee sin banderas ni planos; inicial |
| `ItemTrashCan` | `room_unlock_trash_can` | — | A/C |
| `ObjectBooks` | `room_unlock_book` | — | A/C |
| `ObjectPlant` | `room_unlock_plant` | — | A/C |
| `ObjectSafe` | `room_unlock_safe` | — | A/C |
| `PetFood` | `room_unlock_pet_food` | — | A/C |
| `ObjectMagicWell` | `room_unlock_magic_area` | `blueprint_room_decorate_magic_well` | A/C, correlación |
| `ObjectDrinkSeller` | — conocida | `blueprint_room_decorate_drink_seller` | A/C |
| `ObjectFishBowl` | — conocida | `blueprint_room_decorate_fishbowl` | A/C |
| `ObjectMysteriouStatue` | — conocida | `blueprint_room_decorate_mysteriou_statue` | A/C |

No se inventan banderas para la expendedora ni para la estatua. Tampoco se
asocia `Planet` a una bandera sin evidencia.

`room_decorate_fishbowl_level` vale 3 en A y C, pero es un nivel del acuario, no
una bandera de desbloqueo. Su rango y efecto no están demostrados; el editor no
lo modifica.

## Estructuras de ejemplo

Ejemplo sintético de una instalación con bandera:

```json
{
  "itemData": {
    "roomDecorateDic": {
      "ObjectSafe": [0]
    }
  },
  "statisticData": {
    "event2Count": {
      "room_unlock_safe": 1
    }
  }
}
```

Ejemplo sintético de un decorado investigable:

```json
{
  "itemData": {
    "roomDecorateDic": {
      "ObjectDrinkSeller": [0]
    },
    "blueprints": {
      "blueprint_room_decorate_drink_seller": 2
    }
  }
}
```

En una cuenta con planos de texto, el mismo estado sería
`"Researched"`. El escritor conserva la codificación existente.

## Comportamiento implementado

Al desbloquear o reparar un objeto, `prepare_decoration_edit`:

1. Crea `roomDecorateDic[objeto] = [0]` solo si falta.
2. Crea o sube a `1` cada bandera conocida del objeto. Si la bandera existe con
   un entero mayor o igual que 1, no la toca. Rechaza valores no enteros,
   negativos o contenedores ausentes.
3. Crea o eleva a `Researched` el plano conocido, respetando la codificación de
   la cuenta y el alias con o sin prefijo. No degrada `Researched` a `Got`.
4. Al subir un nivel, activa la bandera asociada a `Book`, `CatFood`, `Chest` o
   `Safe`. No toca `Planet`.
5. Conserva todas las claves desconocidas y no cambia tipos existentes.
6. Serializa, reabre, comprueba los valores solicitados y revierte el candidato
   para exigir igualdad byte a byte con el original.
7. Aplica solo diferencias efectivas y declara todas las rutas modificadas.

La operación es idempotente: repetir el mismo plan no crea claves duplicadas ni
cambia valores ya correctos.

## Interfaz

La categoría **Decoraciones** muestra por objeto:

- `Disponible`: poseído y todos los requisitos cumplidos.
- `Incompleto`: poseído pero falta una bandera o un plano.
- `Bloqueado`: no poseído.

La fila indica el requisito pendiente. La sección mantiene la etiqueta
experimental y no promete que el objeto funcione dentro del juego hasta la
validación física.

## Pruebas manuales necesarias

Usar una cuenta de prueba y un respaldo verificado.

1. Descargar la partida y anotar los objetos y banderas actuales.
2. Desbloquear un objeto con bandera, por ejemplo la caja fuerte.
3. Preparar y guardar el candidato.
4. Abrir Soul Knight, entrar al vestíbulo y comprobar que el objeto aparece y
   se puede usar.
5. Reiniciar el juego y confirmar que sigue disponible.
6. Volver a descargar la partida y comprobar que la bandera y la posesión
   persisten.
7. Repetir con un decorado investigable, por ejemplo la expendedora, y
   comprobar si el plano `Researched` basta.
8. Probar el pozo mágico, que combina bandera y plano.
9. Subir un nivel de mobiliario y comprobar que se conserva y que la bandera
   asociada no se pierde.
10. Restaurar el respaldo y verificar que el guardado vuelve al SHA original.

## Preguntas abiertas

- ¿La bandera por sí sola basta o el cliente exige además una animación o estado
  de construcción?
- ¿La expendedora y la estatua necesitan otro contador además del plano?
- ¿Qué efecto tiene `room_decorate_fishbowl_level` y cuál es su máximo?
- ¿`roomDecorateDic` posee el objeto o solo registra skins?
- ¿El cliente iOS acepta las mismas banderas y planos que Android?

Hasta responder estas preguntas, el desbloqueo se mantiene como experimental y
la validación real corresponde al propietario.
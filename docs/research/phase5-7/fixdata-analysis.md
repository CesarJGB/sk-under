# Investigación de `FixData`

**Estado: PARCIAL, SIN COMPORTAMIENTO CONFIRMADO.** La Fase 5.7 volvió a
confirmar la existencia y las firmas de los métodos de corrección, pero no
decompiló sus cuerpos ni observó una migración real. No se añadieron pruebas de
comportamiento porque no hay una transformación confirmada que reproducir.

## 1. Hipótesis

`FixData` corrige el JSON antes de `ParseJsonToCloudSaveGameData`, completa
secciones ausentes o migra campos entre versiones. Si se conoce su efecto, una
copia local editada podría prepararse para que el cliente la acepte.

## 2. Evidencia estática

La metadata de 8.8.0 declara, entre otros:

| Tipo | Método | Firma |
| --- | --- | --- |
| `RGScript.Other.NewCloudSaveAgent` | `FixData` | `(string) -> string` |
| `RGSaveManager` | `FixData` | `(bool) -> void` |
| `CloudSaveGameData` | `FuncForHotFixBeforeCover` | `() -> void` |
| `CloudSaveGameData` | `FuncForHotFixAfterCover` | `() -> void` |
| `ItemData`, `SettingData`, `StatisticData`, ... | `FixDataIfNotExist` | `() -> void` |
| `ItemData`, `SettingData`, `StatisticData`, ... | `FixData` | `(bool) -> void` |

La Fase 5.5 ya había inventariado los tokens de estos métodos y los había
relacionado con `CreateFromPlayerPref`/`CoverPlayerPref`. La Fase 5.7 no aportó
cuerpos nuevos: el binario sigue protegido por ACE y el cliente no alcanza un
estado estable para leer los métodos en runtime.

## 3. Qué se puede afirmar

- **Confirmado:** los métodos existen, sus nombres y firmas son los indicados.
- **Confirmado:** `NewCloudSaveAgent.FixData` devuelve `string`; encaja con una
  corrección textual antes del parser, pero no demuestra el contenido.
- **Confirmado:** `CreateFromPlayerPref` y `CoverPlayerPref` son la frontera
  entre el modelo y el almacenamiento local.
- **No confirmado:** qué campos corrige, si migra 8.6.0 → 8.8.0, si normaliza
  valores, si toca campos desconocidos o si participa en la restauración de
  nube.

## 4. Lo que no se hizo

- No se decompiló `NewCloudSaveAgent.FixData` ni `RGSaveManager.FixData`.
- No se ejecutó una restauración 8.6.0 en el cliente 8.8.0.
- No se creó una prueba unitaria que “reproduzca” una migración inventada.
- No se modificó el cliente para forzar el paso por `FixData`.

## 5. Pruebas existentes relacionadas

Las pruebas nuevas de la fase cubren lo que sí está confirmado del agregado:

- roundtrip JSON y gzip;
- conservación de `extra_fields` desconocidos;
- rechazo de tamaños/huellas inconsistentes;
- rechazo de respuestas no reconocidas.

No hay una prueba de `FixData` porque no hay una transformación observada que
afirmar. Una prueba basada en nombres de métodos sería una hipótesis
disfrazada de resultado.

## 6. Próximo experimento

Con una copia 8.8.0 auténtica y una 8.6.0 del mismo titular:

1. Comparar `serialzedVersion`, claves y tipos.
2. Restaurar la 8.6.0 en el cliente 8.8.0 y observar si `FixData` rellena,
   rechaza o corrompe.
3. Registrar solo el resultado observable, sin publicar valores.
4. Si se confirma una transformación, escribir una prueba que la reproduzca
   con datos sintéticos.

## 7. Conclusión

`FixData` sigue siendo una **caja gris**: superficie conocida, cuerpo no
observado. No se debe usar como garantía de compatibilidad ni como excusa para
declarar que una copia editada será aceptada.

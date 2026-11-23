# Validación de la vista previa

**La excepción de `GetExtraDescribe` no se reprodujo con datos sintéticos y
tampoco se descartó.** La evidencia de 5.3 sitúa el fallo al construir la
descripción de diferencias, después de `LoadGame`, y señala cinco colecciones
y un argumento `restoreRole` en el formateador. El editor puede validar hoy la
estructura del agregado y distinguir una sección nula de una ausente; no puede
decidir qué colección exige cada versión del cliente.

## Evidencia

| Elemento | Observación | Confianza |
| --- | --- | --- |
| `ArgumentNullException` | Primer intento autenticado de 5.1, 451 ms después de `CreateFromPlayerPref`, antes del diálogo. | **Observado** |
| `GetExtraDescribe` | Aparece en la traza de la excepción y en el formateador. | **Observado** |
| `LoadGame` | Lee `LoadedGameData` (+0x70) o usa `CreateNew`; construye la comparación. | **Estático** |
| Cinco colecciones | Héroes, skins, habilidades, mascotas y plantas; `ToList`/`Except`/`Where`. | **Estático** |
| `restoreRole` | Quinto argumento de `AppendItemDescribe`, además de `intersectWithRestoreRole`. | **Estático** |
| Argumento nulo exacto | No se registró el nombre del parámetro ni el valor de las opciones. | **Desconocido** |
| Condición mínima | Entrar al tutorial sin conexión y abrir un cofre coincidió con el segundo intento exitoso. | **Observado, no aislado** |

Direcciones y reproducción: [comparación FetchData](../phase5-3/fetch-comparison.md) ·
[error de vista previa](../phase5-3/preview-error.md).

## Argumentos potencialmente nulos

| Candidato | Dónde entra | Por qué podría ser nulo | Cómo validarlo |
| --- | --- | --- | --- |
| `LoadedGameData` | `LoadGame` +0x70 | No hubo descarga o se invalidó la caché. | `LoadGame` ya contempla `CreateNew`; el editor debe distinguir agregado ausente. |
| Colección de héroes | `ToList` → `AppendItemDescribe` | El agregado no trae la lista o trae `null`. | Exigir lista (posiblemente vacía) antes de formatear. |
| Skins / habilidades | `Where` → `ToList` | Igual que héroes; además dependen de catálogo. | Validar tipo y distinguir nulo de vacío. |
| Mascotas / plantas | `Except` → `ToList` | Una entrada nula en `Except` puede fallar. | Validar la colección y sus miembros. |
| `restoreRole` | `AppendItemDescribe` | Puede no existir en versiones antiguas o en una rama de canal. | Validar presencia o usar un valor por defecto explícito. |
| `ExtraDescribeOptions` | `GetExceptRMBPayDescribe` | Construcción incompleta o localización ausente. | No se puede validar sin el modelo del cliente. |
| Catálogo / localización | `GetExtraDescribe` | `RMB_Skill`, `ScriptLocalization`, separador. | Fuera del agregado; requiere el cliente y sus recursos. |

## Qué puede validar el editor

`backend/app/cloud/preview.py` expone `preview_issues(save)`:

| Código | Significado | Acción sugerida |
| --- | --- | --- |
| `null_section` | La sección existe con valor `null`. | No tratarla como vacía; avisar antes de interpretar. |
| `missing_section` | La sección no está en el agregado. | Distinguirla de `null`; no inventar datos. |

El módulo **no** afirma que una sección nula cause la excepción. Solo conserva
la distinción que el agregado ya permite y que la vista previa puede necesitar.
El fixture sintético de 8.8.0 permite probar los dos estados:

```python
from pathlib import Path
from app.cloud.importer import import_from_transport
from app.cloud.preview import preview_issues
from app.cloud.transport import SimulatedProviderTransport

result = import_from_transport(
    SimulatedProviderTransport(Path("tests/fixtures/cloud-save-880-sintetico.json"))
)
issues = preview_issues(result.copy.aggregate)
# null_section: settingData, maps
# missing_section: mallReloadData
```

## Qué no puede validar el editor

- El esquema exacto de `gameData` y de los subsistemas de 8.8.0.
- Qué colección exige cada rama de `LoadGame`/`GetExtraDescribe`.
- El valor de `restoreRole` en la sesión del titular.
- La inicialización del catálogo, la localización y `RMB_Skill`.
- La diferencia entre un fallo de datos y un fallo de recursos del cliente.

Una lista vacía es un caso válido y distinto de `null`. El código de 5.3 usa
`ToList` después de materializar, por lo que una lista vacía no debería ser el
argumento nulo; esa es una **inferencia**, no una prueba. El argumento nulo
pudo ser una referencia copiada, una entrada de `Except`, `restoreRole` o un
insumo del catálogo.

## Reproducción sintética

No se puede ejecutar `GetExtraDescribe` sin el cliente IL2CPP y sus recursos.
El parser de Python no ejercita ese formateador. Por tanto, 5.4 no afirma haber
reproducido la excepción. Lo que sí se probó:

| Prueba | Resultado |
| --- | --- |
| Agregado con `settingData` nulo y `mallReloadData` ausente | Aceptado; `preview_issues` distingue ambos estados. |
| Agregado sin `gameData` o con tipo incompatible | Rechazado por el reconstructor. |
| Sección de objeto con tipo distinto | Rechazada. |
| Hash/tamaño incorrectos | Rechazados antes de interpretar. |

## Validación previa recomendada

Antes de enviar un agregado a una vista previa:

1. Verificar tamaño y SHA-256 de la copia.
2. Rechazar un agregado sin `serialzedVersion`, `cloudSaveId`, `platformId` o
   `gameData` objeto.
3. Registrar `null_section` y `missing_section` por separado.
4. No convertir `null` en `{}` ni en `[]` de forma implícita.
5. Detenerse si el usuario no ha confirmado que la copia es suya y que la
   restauración es segura.
6. No intentar interpretar una sección sin modelo verificado.

## Experimento discriminante pendiente

Con la misma cuenta, versión, idioma y respaldo:

1. Abrir el panel, recuperar y detenerse en la vista previa.
2. Registrar solo el tipo de excepción, el nombre del parámetro si se expone y
   los marcos del formateador.
3. Comparar un estado local nuevo con otro que ya tenga progreso autorizado.
4. Repetir tras entrar y salir del tutorial, sin abrir el cofre, manteniendo la
   conectividad.
5. No modificar el cliente ni sus mecanismos de autenticación o restauración.

El resultado permitiría saber si el nulo es de datos, de opciones o de
catálogo. Sin esa medición, la validación del editor debe seguir siendo
estructural y conservadora. [Sesión autenticada](authenticated-session.md) ·
[Referencia 8.8.0](real-880-save-validation.md)

# Fase 6.16 — Fichas de pesca confirmadas y desbloqueo de personajes

Esta fase cierra la investigación pendiente de las fichas de pesca y añade el
primer editor de personajes. El cambio de fichas deja de ser experimental; el
desbloqueo de personajes se publica como experimental hasta que el propietario
complete la comprobación en un dispositivo Android físico.

> **Corrección 6.16.1:** el catálogo de personajes ahora viaja dentro del
> backend (`backend/app/catalogs/characters-880.json`), se resuelve desde el
> módulo y se valida durante el build de la imagen. Consulta
> [la corrección del catálogo](6.16.1-correccion-catalogo.md).

## 1. Consolidación de las fichas de pesca

El propietario realizó la prueba manual pendiente con la modificación conjunta de
`gameData.fishChip` e `itemData.materials.material_fish`. En el dispositivo
Android comprobó:

- subida y recuperación de la copia desde la nube;
- visualización del saldo correcto dentro del juego;
- compra de paquetes con las fichas;
- descuento del importe correspondiente;
- guardado posterior desde el cliente oficial.

Con esta evidencia, `fishChip` sube a **E4** para el alcance probado y la
interfaz deja de mostrar la etiqueta **Experimental · E2**, el aviso de autoridad
no validada y el texto de prueba pendiente. El flujo funcional no cambió: sigue
aplicando el mismo entero a las dos rutas, conserva el resto de `materials`,
crea un respaldo cifrado, exige confirmación autenticada, verifica por descarga y
permite restaurar. `cumulativeFishCount`, los historiales `fishChipStore*` y
`mallReloadData.buyFishCount*` permanecen fuera de la edición.

## 2. Campos del desbloqueo de personajes

La evidencia localizada en las fases 6.12 y 6.16 identifica una única ruta
necesaria:

| Ruta | Tipo | Papel |
| --- | --- | --- |
| `gameData.heroUnlock` | objeto código → bool | disponibilidad declarada de los 42 personajes |

En la copia real de 8.8.0 inspeccionada, `heroUnlock` contiene los 42 códigos y
solo `Knight` y `CostumePrince` aparecen como `true`. Los personajes bloqueados
conservan `heroLevel = 0`, `heroSkill = 0`, `heroSkillUnlock` con la misma forma
de tres entradas y `currentSkinDatas` vacío, igual que los disponibles. Ninguna
otra ruta diferencia la disponibilidad. Por eso el editor:

- activa únicamente `heroUnlock[código] = true` para los personajes elegidos;
- añade el código si faltara en el mapa, sin tocar los demás;
- conserva los personajes que ya estaban disponibles;
- no cambia niveles, habilidades, skins ni recursos;
- no vuelve a bloquear personajes;
- no modifica el orden ni el resto del agregado.

La comprobación inversa restaura el mapa original completo y exige que el
agregado vuelva a ser idéntico byte a byte al descargado.

## 3. Funcionalidades del editor

La sección **Personajes** de `/partida` muestra los 42 códigos del catálogo con
nombre, nivel observado y estado:

- **Disponible** para los personajes ya desbloqueados;
- **Bloqueado** para los seleccionables;
- **Sin dato** cuando la partida no declara el código, en cuyo caso no se
  modifica.

Incluye selección individual mediante casillas, selección múltiple, botón para
seleccionar todos los bloqueados, botón para deseleccionar todos y un contador
`desbloqueados / total`. Antes de subir se muestra un resumen con los nombres
seleccionados, el recuento original y el nuevo, los campos que cambiarán y el
recordatorio de que niveles, habilidades y skins permanecen intactos. El envío
requiere la confirmación explícita habitual. Los respaldos de personajes
aparecen en el historial de **Partida** y se pueden verificar o restaurar como
los de gemas y fichas.

## 4. Flujo técnico

1. `POST /api/v1/cloud/native/prepare-characters` recibe `codes` y el SHA-256 de
   la descarga actual.
2. El backend valida el sobre, la serialización canónica, `heroUnlock` como mapa
   booleano, el catálogo local y una selección de 1 a 42 códigos únicos.
3. Prepara un candidato determinista, lo reabre, comprueba que solo cambiaron
   los códigos seleccionados y guarda un respaldo cifrado con la selección.
4. La confirmación reutiliza `POST /api/v1/cloud/native/confirm` y exige que el
   candidato se pueda reproducir desde el original.
5. La verificación por descarga y la restauración reutilizan los endpoints
   existentes. Los respaldos de gemas, fichas y personajes conviven en el mismo
   historial.

Los errores específicos (`invalid_character_selection`, `unknown_character`,
`character_field_missing`, `unsupported_characters_structure`,
`character_verification_failed`, `outdated_character_draft`) se traducen a
mensajes claros sin exponer contenido privado de la partida.

## 5. Integridad y límites

- Solo se escriben rutas `gameData.heroUnlock.<código>` de la selección.
- Los niveles no se inicializan, maximizan ni modifican.
- No se activan habilidades ni se desbloquean o equipan skins.
- Los personajes no seleccionados y los ya disponibles no cambian.
- El candidato debe conservar el tamaño del agregado salvo el crecimiento propio
  de los valores añadidos y reproducir el original al revertir.
- La escritura sigue deshabilitada por defecto y solo se habilita con la
  configuración de escritura de la cuenta.

## 6. Pruebas

Se añadieron pruebas de backend para:

- desbloqueo individual, múltiple y masivo de los 41 personajes bloqueados;
- conservación de personajes ya disponibles, niveles, habilidades, skins, gemas
  y materiales;
- selección vacía, duplicada, desconocida, mapa ausente o con valores no
  booleanos;
- respaldo, reproducción del candidato, confirmación, verificación y
  restauración;
- compatibilidad con los flujos de gemas y fichas.

En el frontend se cubren la selección individual, la selección múltiple, el
botón de todos los bloqueados, la deselección, el resumen previo, la subida y el
contador. Las pruebas de fichas se actualizaron para exigir la ausencia de la
etiqueta experimental. También se ejecutan las pruebas completas de backend,
`tsc --noEmit` y la suite de Playwright.

La corrección 6.16.1 añade pruebas de regresión que verifican que el catálogo
está dentro del paquete `app`, que el `.dockerignore` lo incluye, que el
Dockerfile ejecuta `python -m app.catalogs.verify` y que un catálogo ausente no
queda memorizado en la caché. La imagen Docker real se valida además con
`backend/tests/verify_image_catalog.py`.

## 7. Validación pendiente

| Capa | Estado |
| --- | --- |
| Estructura de `heroUnlock` en 8.8.0 | E2, observada en copias reales |
| Cambio preparado y verificado en la nube | Cubierto por pruebas automatizadas |
| Persistencia en la nube | Verificada por descarga posterior |
| Desbloqueo visible dentro del juego | Pendiente de comprobación del propietario |
| Niveles, habilidades y skins intactos en el cliente | Pendiente de comprobación del propietario |
| Catálogo empaquetado en la imagen de producción | Validado en Docker local con `uid=10001`; pendiente el redespliegue en Coolify |

La función se identifica como **Experimental · E2** en la interfaz para permitir
una prueba controlada sin presentarla como definitiva.

## 8. Fuera de alcance

No se editan niveles de personajes, habilidades, skins, materiales, semillas,
tickets ni planos. Tampoco se vuelve a bloquear un personaje, no se cambia el
protocolo de autenticación o guardado y no se rediseña el editor. Las fichas de
pesca no reciben más investigación: su implementación se mantiene intacta.
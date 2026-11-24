# Fase 8.0 — rediseño Mobile First, edición rápida y gestor global

Esta fase parte de `main` (`854a30e`) y transforma el editor de Side en una
aplicación de edición compacta, con un único borrador y un único proceso de
guardado. No añade sistemas de desbloqueo nuevos.

## 1. Resumen

Objetivos cumplidos:

- la edición rápida es la pantalla inicial del editor;
- los editores detallados se abren desde una cuadrícula de categorías, sin
  apilar todos los formularios en una página;
- ambos modos comparten el mismo borrador global;
- una barra inferior persistente muestra los cambios reales, permite descartar
  y abre la revisión;
- la revisión compone un candidato único, agrupa los cambios por categoría y
  realiza una sola subida;
- el respaldo, la verificación, la restauración y la detección de conflictos se
  conservan;
- las operaciones de mascotas, skins de mascotas y alimento se consolidan como
  E3 confirmadas por el propietario.

No se modificaron recibos, compras ni derechos del servidor.

## 2. Arquitectura anterior

Antes de esta fase, `/editor` era una página larga con secciones independientes:

1. saldo de gemas;
2. fichas de pesca y progreso acumulado;
3. materiales, semillas, moneda de temporada, renacimiento y pase de batalla;
4. tarjetas de desbloqueo de personajes, habilidades, skins y mascotas;
5. rutas sueltas `/editor/personajes`, `/editor/habilidades`, `/editor/skins` y
   `/editor/mascotas`.

Cada sección tenía su propio estado, su propia llamada de preparación y su
propio botón de confirmación. Cada confirmación creaba un respaldo y subía la
partida por separado. Esto producía:

- desplazamiento vertical excesivo;
- componentes y textos repetidos;
- varios procesos de guardado para una sola sesión de edición;
- riesgo de que una operación posterior reescribiera el resultado de otra sin
  una vista consolidada.

En el backend existían endpoints independientes (`/prepare`,
`/prepare-fish-chip`, `/prepare-advanced`, `/prepare-characters`,
`/prepare-skills`, `/prepare-skins`) y una confirmación común.

## 3. Arquitectura nueva

### Navegación

- `/editor`: edición rápida (inicio).
- `/editor/categorias`: cuadrícula de categorías.
- `/editor/categoria/<id>`: un único editor detallado.
- Las rutas antiguas de categorías redirigen a la ruta nueva.

Cambiar de modo o de categoría no descarga la partida ni reinicia el borrador.
La partida base se mantiene en `NativeEditor` y `EditorWorkspace` conserva el
estado mientras se navega.

### Pantallas

- **Rápida:** filas compactas de casilla, nombre y, cuando corresponde, un campo
  numérico alineado a la derecha.
- **Categorías:** nueve tarjetas: Monedas y recursos, Personajes, Habilidades,
  Skins, Mascotas, Materiales, Semillas, Temporada y Pase de batalla. La
  cuadrícula usa tres columnas en móvil, dos en pantallas muy estrechas y cinco
  en escritorio.
- **Detalle:** búsqueda, filtros, selección individual, selección múltiple,
  contadores, edición numérica y acciones masivas de la categoría.
- **Revisión:** resumen agrupado por categoría, detalle expandible, campos
  afectados y una única confirmación.

### Barra inferior

Muestra el número de campos con diferencia real, el número de operaciones y los
botones Descartar y Guardar/Revisar. Es fija, respeta `env(safe-area-inset-bottom)`
y el contenido reserva espacio para no quedar inaccesible. No existe otra barra
de guardado dentro de las categorías.

## 4. Gestor global de cambios

El gestor vive en `frontend/src/draft.ts`. Es una representación pura y
serializable de la intención del usuario, separada de la partida descargada.

### Estado

- `bulk`: activa una operación masiva por categoría.
- `manual`: elementos elegidos individualmente.
- `excluded`: elementos excluidos de una operación masiva.
- `quick`: valores de gemas, fichas, progreso de pesca, moneda de temporada y
  mínimos de materiales, semillas, alimento y baterías.
- `materialEdits`, `seedEdits`, `petFoodEdits`: valores detallados por
  identificador.
- `reborn` y `battlePass`: beneficios concretos.

Selección efectiva:

```text
(bulk ? elegibles : ∅) ∪ manual − excluded
```

Consecuencias:

- activar «todos los personajes» y excluir uno desde el catálogo mantiene la
  exclusión;
- desactivar la operación masiva no borra las selecciones manuales;
- «seleccionar todo» limpia las exclusiones de esa categoría;
- los elementos ya desbloqueados o no editables no forman parte de la selección.

### Cantidades y solapamientos

- Las operaciones de mínimo calculan `max(valor actual, mínimo)`; nunca reducen
  una cantidad superior.
- Una edición manual de un material, semilla o alimento prevalece sobre el
  mínimo rápido.
- El mínimo de alimento de mascotas prevalece sobre el mínimo general para
  `material_grain` y `material_battery`.
- `material_fish` se excluye del plan de materiales porque las fichas de pesca
  tienen su propio escritor y su propio campo.
- Los valores vacíos, negativos o fuera de rango no se incorporan al plan.
- Las operaciones sin diferencia real no cuentan ni se envían.
- El contador principal cuenta campos únicos con diferencia; el secundario
  cuenta operaciones.

### Resolución determinista

El plan se construye en este orden:

1. gemas;
2. fichas de pesca;
3. progreso acumulado de pesca;
4. personajes;
5. habilidades;
6. skins;
7. materiales, semillas, moneda de temporada, renacimiento, pase, mascotas y
   alimento.

El backend aplica exactamente el mismo orden sobre un candidato progresivo. Si
dos pasos intentan cambiar el mismo campo, la operación se rechaza con
`UnifiedOverlap` en lugar de elegir silenciosamente un ganador. El frontend evita
los solapamientos conocidos antes de enviar.

## 5. Guardado unificado

Flujo:

1. cargar la partida;
2. editar en rápida o en categorías;
3. revisar el contador y pulsar Guardar;
4. `POST /api/v1/cloud/native/prepare-unified` descarga una vez, comprueba el SHA
   de origen y compone los escritores existentes sobre el mismo candidato;
5. se crea un único respaldo cifrado y restaurable;
6. la vista previa agrupa los cambios;
7. el usuario confirma una vez;
8. `POST /confirm` sube el candidato una sola vez;
9. se descarga de nuevo y se verifica el SHA remoto;
10. solo si la verificación es correcta se limpia el borrador y se anuncia el
    éxito.

Endpoints antiguos conservados por compatibilidad. El nuevo endpoint no sustituye
a los escritores: los compone.

### Integridad

- validación de tipos, identificadores y rangos;
- conservación de claves desconocidas;
- comprobación del SHA de la partida base antes de preparar y antes de subir;
- rechazo de planes vacíos, duplicados o contradictorios;
- un respaldo por operación;
- replay del plan al cargar el respaldo para comprobar que reproduce el
  candidato byte a byte;
- protección contra confirmaciones duplicadas;
- conflicto remoto explícito: el borrador se conserva y se ofrece descargar de
  nuevo;
- si falla la preparación o la subida, el borrador permanece;
- aviso `beforeunload` y confirmación al cerrar sesión con cambios pendientes.

## 6. Inventario de equivalencia

| Función anterior | Nueva ubicación |
| --- | --- |
| Saldo de gemas | Rápida → Gemas; Recursos |
| Fichas de pesca | Rápida → Fichas de pesca; Recursos |
| Progreso acumulado de pesca | Rápida → Recompensas de pesca; Recursos |
| Moneda de temporada | Rápida → Monedas de temporada; Temporada |
| Materiales y edición masiva | Rápida → Materiales; Materiales |
| Semillas | Rápida → Semillas; Semillas |
| Alimento de mascotas | Rápida → Alimento; Mascotas |
| Baterías | Rápida → Baterías; Mascotas |
| Desbloquear todos los personajes | Rápida → Todos los personajes; Personajes |
| Desbloquear todas las habilidades | Rápida → Todas las habilidades; Habilidades |
| Desbloquear todas las skins | Rápida → Todas las skins; Skins |
| Desbloquear todas las mascotas | Rápida → Todas las mascotas; Mascotas |
| Desbloquear skins de mascotas | Rápida → Skins de mascotas; Mascotas |
| Tarjeta de renacimiento | Rápida → Beneficios; Recursos |
| Pase de batalla | Rápida → nivel máximo; Pase de batalla |
| Progresión de mascotas | Mascotas, solo lectura |
| Búsqueda, filtros y selección | Editores detallados de cada categoría |
| Vista previa y confirmación | Revisión y guardado unificado |
| Respaldo, restauración y verificación | Partida y revisión |
| Inicio de sesión, perfiles, descarga | Sin cambios funcionales |

## 7. Cambios técnicos

### Backend

- `backend/app/cloud/unified_editor.py` (nuevo): normalización del plan,
  composición de escritores, detección de solapamientos y verificación.
- `backend/app/cloud/backup_store.py`: campo `unified`, plan y replay.
- `backend/app/cloud/lab_service.py`: preparación y confirmación unificadas.
- `backend/app/models.py`: `CloudLabUnifiedPrepareInput` y resumen unificado.
- `backend/app/api/native.py`: `POST /prepare-unified`.
- `backend/app/native/service.py`: delegación de sesión.
- `backend/app/cloud/advanced_editor.py`: política de mascotas E3; solo el pase
  de batalla permanece experimental.

### Frontend

- `frontend/src/draft.ts` (nuevo): modelo y cálculo del borrador.
- `frontend/src/pages/EditorWorkspace.tsx` (nuevo): rápida, categorías, detalle,
  revisión y barra inferior.
- `frontend/src/pages/NativeAuthPage.tsx`: el editor usa el workspace; se
  conservan autenticación, descarga y respaldos.
- `frontend/src/api.ts`: tipos y método `prepareUnified`.
- `frontend/src/styles.css`: estilos Mobile First, cuadrícula y barra segura.
- `frontend/tests/phase8-editor.spec.ts` (nuevo): flujos y capturas.

### Componentes reutilizables

`QuickRow`, `CheckAll`, `SelectionToolbar`, `LockList`, `numberEdits`,
`MaterialsEditor`, `SeedsEditor`, `PetsEditor`, `SeasonEditor`,
`BattlePassEditor`, `ResourcesEditor`, `CategoryGrid` y la barra persistente.
Los editores detallados comparten el mismo contrato de borrador.

## 8. Evidencia de mascotas

El propietario confirmó en Soul Knight Android físico:

- desbloqueo de mascotas;
- desbloqueo de skins de mascotas;
- edición de alimento;
- edición de baterías.

Se actualizó `knowledge/fields/overrides.json` (`gameData.petUnlock` a E3,
`confirmed_by_owner`), se regeneró `knowledge/fields/fields.json` y se registró
la prueba en `knowledge/sources/owner-confirmations-phase7-2.md`. Las funciones
confirmadas ya no muestran advertencias experimentales. El pase de batalla sigue
E2. No se elevó nada a E4 y no se validó la maximización directa de niveles o
afinidad.

## 9. Pruebas

Resultados reales de esta fase:

- backend: **651 passed, 16 skipped**;
- build del frontend: correcto (`tsc --noEmit && vite build`);
- Playwright: **35 passed, 24 skipped**;
- `native-auth.spec.ts`: 19 pruebas del editor antiguo marcadas `fixme` porque
  dependían de la interfaz eliminada; los flujos equivalentes están cubiertos por
  `phase8-editor.spec.ts`;
- `advanced-editor.spec.ts` y `pets-editor.spec.ts`: pruebas de la UI antigua
  marcadas `fixme`; los flujos de materiales, semillas, temporada, renacimiento,
  pase, mascotas, skins y alimento se prueban en la nueva suite.

Casos cubiertos por la suite nueva:

- edición rápida como pantalla inicial;
- borrador compartido y exclusión individual de una operación masiva;
- candidato consolidado y una sola subida;
- composición de categorías detalladas;
- mínimos que no reducen cantidades;
- descarte con confirmación;
- conflicto remoto que conserva el borrador;
- capturas en 320, 360, 375, 390, 430, 768 y 1280 px sin desbordamiento
  horizontal.

### Capturas

- `screenshots/phase8-quick-320.png`
- `screenshots/phase8-quick-390.png`
- `screenshots/phase8-quick-1280.png`
- `screenshots/phase8-categories-320.png`
- `screenshots/phase8-categories-390.png`
- `screenshots/phase8-categories-1280.png`

## 10. AGENTS.md

Se añadió la sección permanente «Diseño y experiencia de usuario» con las reglas
de la fase: Mobile First, densidad útil, filas compactas, categorías dedicadas,
borrador global, ausencia de guardados por sección, información técnica
secundaria, advertencias contextuales, accesibilidad, integridad y revisión
visual en móvil antes de terminar.

## 11. Limitaciones y pendientes

- No se declara validación en Android físico de esta fase: las pruebas de
  mascotas fueron las del propietario en la fase 7.2.
- El pase de batalla continúa E2 y requiere una prueba real cuando haya un pase
  disponible.
- Las pruebas Playwright antiguas del editor se conservan como `fixme`; una
  limpieza futura puede reescribirlas sobre el workspace actual.
- La vista previa agrupa y permite expandir detalles, pero no muestra un diff
  línea a línea; el SHA y los campos afectados siguen siendo verificables.
- La virtualización de listas no fue necesaria para los tamaños actuales; la
  arquitectura limita el renderizado inicial y está preparada para añadirla.
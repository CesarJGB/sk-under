# Fase 7.2 — consolidación y editor de mascotas

Esta fase parte de `main` (`88d43a2`) y tiene dos objetivos: consolidar las
funciones de la fase 7.1 que el propietario confirmó en Android físico e
investigar e implementar el editor de mascotas, variantes de skin, progresión y
alimento.

## 1. Consolidación de la fase 7.1

El propietario probó la página desplegada y Soul Knight en un dispositivo
Android físico. La evidencia se registra en
`knowledge/sources/owner-confirmations-phase7-2.md`.

### Confirmaciones explícitas

| Función | Resultado | Nivel |
| --- | --- | --- |
| Materiales, incluida la edición masiva | Funciona | E3 |
| Recompensas acumuladas de pesca | Se canjean correctamente con `itemData.cumulativeFishCount` | E3 |
| Tarjeta de renacimiento permanente | `gameData.rebornCard = true` bastó; aparece comprada | E3 |

### Validación general

La validación general también comprende:

- semillas (`itemData.seeds`), E3;
- monedas de temporada (`seasonData.coin`), E3.

### Pase de batalla

No había un pase disponible para comprar y validar. El pase de batalla sigue
experimental E2; no se interpreta como un fallo del editor. No se elevó ninguna
función a E4 porque no hay evidencia de persistencia posterior suficiente.

Las políticas se actualizaron a `confirmed_by_owner` en
`knowledge/fields/overrides.json` y se regeneró `knowledge/fields/fields.json`.
La interfaz de la fase 7.1 distingue ahora el bloque confirmado E3 del pase E2.

## 2. Investigación de mascotas

### Desbloqueo local y en la nube

- Archivo local: `files/game.data`, campo `petUnlock`.
- Agregado de nube: `gameData.petUnlock`.
- Proyección de PlayerPrefs observada: `shared_prefs/com.ChillyRoom.DungeonShooter.v2.playerprefs.xml:{perfil}_p<ID>_unlock`.
- Estructura: objeto `código de mascota → booleano`.
- Catálogo: 58 mascotas.
- El código 57 es `FishChipKing`. No aparece en `pet_code_name.json` de SKDFE,
  pero sí en `gameData.petUnlock` de guardados y nube reales; su nombre fiable es
  `Fish Chip King` / `Rey de las fichas de pez` / `鱼干之王`.

El editor conserva todos los códigos existentes, incluidos los desconocidos, y
solo activa los seleccionados. Si un código del catálogo está ausente y el mapa
`petUnlock` ya existe como objeto, lo inserta como `true`; no crea el mapa si no
existe.

### Skins de mascota

No se encontró un mapa de bloqueo de skins separado ni una clave de PlayerPrefs
equivalente a `skinLock` de personajes. Las variantes observadas con prefijo de
la mascota base son:

`Cat1`…`Cat7`, `Dog1`…`Dog3`, `Pig1`, `Rabbit1` (12 variantes).

Se catalogan en `knowledge/catalogs/pet_skins.json` como hipótesis E2:
comparten `gameData.petUnlock.<variante>`. La interfaz agrupa las variantes por
mascota base y, al seleccionar una variante, incluye la mascota base si está
pendiente. No se modifica la skin equipada ni `currentSkinDatas`. La relación
base-variante todavía debe validarse en Android físico.

### Progresión

La progresión real se observa en `statisticData.event2Count`:

| Clave | Significado observado |
| --- | --- |
| `pet_<ID>_intimacy` | Intimidad actual (entero). |
| `pet_<ID>_full_intimacy` | `1` cuando la mascota alcanzó su máximo. |
| `pet_<ID>_action_unlock` | `1` cuando la acción especial está desbloqueada. |
| `pet_full_intimacy` | Contador global de mascotas con intimidad completa. |

El `<ID>` es el identificador numérico del catálogo (`0` Cat, `20` Cat1, etc.).
En una muestra modificada se observaron valores 180, 240 y 300 para distintas
mascotas, lo que confirma que el máximo no es una constante global. La
configuración completa `PetsLevelUpConfig` / `PetIntimacyConfig` no está
recuperada, por lo que no se conoce el máximo individual ni se implementan
escrituras de progresión. La interfaz muestra la intimidad y la marca de máximo
en solo lectura. No se usan valores arbitrarios como 999, 9999 o
`Int32.MaxValue`.

### Alimento

Los consumibles identificados son:

| ID | Nombre en | Nombre es | Almacenamiento |
| --- | --- | --- | --- |
| `material_grain` | Pet Treats | Bocadillos de mascotas | `itemData.materials` |
| `material_battery` | Battery | Batería | `itemData.materials` |

`ChoosePetData` expone `grainCount`, `batteryCount`, `preferFoodType` y
`extraFood`, y la metadata incluye `PetFeedPetFood`. No se encontró un contador
de alimento separado en el agregado de nube. El editor de alimento reutiliza el
escritor de `itemData.materials`; si el mismo ID aparece en `materials` y
`pet_food` con cantidades distintas, el lote se rechaza.

## 3. Implementación

### Backend

- `backend/app/catalogs/pets.py`: cargador de la proyección empaquetada.
- `backend/app/catalogs/pets-880.json`: 58 mascotas y 12 variantes, generado por
  `knowledge/tools/build_backend_pets.py --check`.
- `backend/app/cloud/advanced_editor.py`:
  - plan atómico ampliado con `pets` y `pet_food`;
  - desbloqueo en `gameData.petUnlock`;
  - alimento fusionado en `itemData.materials` con detección de conflictos;
  - snapshot de mascotas, variantes, alimento y progresión;
  - verificación de reapertura, reversión byte a byte y ausencia de cambios
    colaterales.
- `backend/app/models.py` y `backend/app/api/native.py`: campos `pets` y
  `pet_food` en `/api/v1/cloud/native/prepare-advanced`.
- `backend/app/cloud/lab_service.py`: evidencia dinámica E3 para el lote
  confirmado y E2 cuando incluye pase o mascotas.

### Frontend

- `frontend/src/pages/PetsEditorSection.tsx`: sección Mascotas con resumen,
  alimento, acciones masivas, catálogo, skins y progresión de solo lectura.
- Ruta `/editor/mascotas` y tarjeta de acceso desde el editor.
- Reutiliza los patrones de búsqueda, filtros, selección y confirmación de
  personajes, habilidades y skins.
- Etiqueta experimental E2 visible para todas las funciones nuevas.

### Knowledge Engine

- `pets.json` corregido (`FishChipKing`).
- Nuevo catálogo `pet_skins.json` (12 variantes).
- Nuevo `statisticData.event2Count` documentado para la progresión.
- `gameData.petUnlock` documentado como editor experimental E2.
- Nuevas dependencias: variante → mascota base, alimento → materiales,
  intimidad → `event2count`, y consolidación E3 de renacimiento y pesca.
- Nueva fuente `owner-confirmations-phase7-2.md`.
- Manifest, hashes, cobertura y traducciones regenerados.

## 4. Seguridad

El lote sigue el flujo existente: respaldo previo, vista previa, confirmación
explícita, escritura atómica, serialización y reapertura del candidato,
verificación de cada valor, reversión y comprobación de que el original se
reproduce byte a byte. No se modifican gemas, fichas de pesca, recompensas
reclamadas, recibos, compras ni derechos de servidor.

## 5. Pruebas

Resultados ejecutados el 24 de noviembre de 2026:

| Suite | Resultado |
| --- | --- |
| Backend `pytest` | 644 passed, 16 skipped |
| Frontend `npm run build` (TypeScript + Vite) | correcto |
| Playwright Chromium | 53 passed |
| Validación del Knowledge Engine | correcta (25 catálogos, 4.298 elementos, 616 campos, 35 dependencias, 17 fuentes) |
| Proyecciones `build_backend_items` y `build_backend_pets` | sincronizadas |
| `compileall` y `app.catalogs.verify` | correctos |
| `git diff --check` | sin errores |

Las pruebas añadidas cubren desbloqueo individual/masivo, mascotas ausentes,
identificadores inválidos, dependencia de variantes, conservación de datos,
alimento válido e inválido, conflicto entre editores, combinación con el lote
confirmado, restauración y ausencia de cambios colaterales. Ninguna de estas
pruebas demuestra por sí sola el comportamiento dentro de Soul Knight.

## 6. Validación pendiente en Android físico

1. Abrir `/editor/mascotas` y comprobar el contador 58/58 del catálogo.
2. Seleccionar una mascota bloqueada, preparar el lote, confirmarlo y comprobar
   que aparece desbloqueada tras reiniciar el juego.
3. Seleccionar una variante de skin y comprobar que la mascota base también se
   desbloquea y que la skin puede equiparse sin alterar otras mascotas.
4. Editar `material_grain` o `material_battery`, alimentar una mascota y
   comprobar el consumo.
5. Comprobar que la intimidad mostrada coincide con el juego y que el editor no
   ofrece maximizarla.
6. Confirmar que las funciones E3 de la fase 7.1 siguen funcionando y que el
   pase de batalla continúa marcado como experimental E2.

Las pruebas automatizadas no demuestran el comportamiento dentro de Soul Knight.
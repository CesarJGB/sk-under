# Fase 10.2 — Estabilización multiplataforma, versiones y rendimiento

Fecha: 2026-11-27.

Esta fase no añade categorías de edición. Corrige el rechazo del nivel 8,
endurece la detección de versiones, reduce el trabajo repetido del editor y
somete a Android e iOS a una matriz real de escrituras, combinaciones y
restauraciones con la cuenta de pruebas autorizada por el propietario.

## Resumen ejecutivo

- El nivel 8 fallaba por una discrepancia entre el límite del editor
  (`HERO_LEVEL_MAX = 8`) y el modelo Pydantic de la API (`le=7`). Se corrigió el
  contrato y se añadieron regresiones en el límite HTTP.
- Se cerró el hueco de marcadores de versión de Android: `gameVersion` y
  `AppVersion` deben coincidir exactamente con el perfil. Un valor ausente o
  distinto deja la escritura en `pending_verification`.
- Se sustituyó `deepcopy` por un clonador JSON especializado en los 14 editores.
  El `prepare` local bajó de 414,2 a 314,3 ms en frío y de 287,7 a 189,9 ms en
  caliente con el guardado Android real.
- Se optimizó la selección masiva del frontend: conteo sin materializar objetos,
  fast path para selección total, caché de progreso y agrupaciones lineales.
- Se ejecutaron T01–T16 en Android y T01–T16 en iOS, con restauración del
  guardado base entre escenarios. Todos los escenarios aplicables terminaron
  correctamente.
- El Unlock All real movió 2.975 operaciones en Android y 2.175 en iOS. La nube
  aceptó el guardado, la verificación posterior confirmó todas las categorías y
  la restauración devolvió el hash original.
- Se descubrió y corrigió un segundo límite: el registro cifrado del respaldo
  rechazaba el plan normalizado de T13 Android por superar los 64 KB históricos.
- Ambos guardados quedaron restaurados y verificados al finalizar.

## 1. Causa raíz del fallo del nivel 8

El editor, el snapshot y el frontend usaban el máximo documentado `8`:

- `backend/app/cloud/hero_level_editor.py`: `HERO_LEVEL_MAX = 8`.
- El snapshot enviaba `advanced.hero_levels.max = 8`.
- `frontend/src/draft.ts` aceptaba valores hasta `levels.max`.
- `frontend/src/pages/EditorWorkspace.tsx` marcaba inválido solo lo superior a
  ese máximo.

Sin embargo, el contrato de entrada de la API tenía un límite distinto:

```python
class CloudHeroLevelChange:
    level: StrictInt = Field(ge=0, le=7)
```

Pydantic rechazaba el nivel 8 antes de que el editor pudiera validarlo. Por eso
el nivel 7 funcionaba y el 8 devolvía un error de contrato tanto en Android como
en iOS. No era un problema de representación interna ni del catálogo.

Corrección aplicada:

- `CloudHeroLevelChange.level` acepta `0..8`, alineado con `HERO_LEVEL_MAX`.
- Se añadieron regresiones en `backend/tests/test_native_api.py` para los niveles
  1, 6, 7 y 8, valores inválidos `-1`, `9` y `100`, personajes bloqueados y
  desbloqueados, y varios personajes en la misma edición.
- El editor sigue sin reducir niveles ni crear claves ausentes, y no modifica
  `heroUnlock` al cambiar el nivel.

Alcance de la evidencia: la API y la nube aceptan el nivel 8 y la descarga
posterior lo conserva (E3). La validación física en el juego solo está
confirmada para Knight; no se debe afirmar que todos los personajes tengan el
mismo máximo efectivo. El guardado expone `level_max: null` por personaje, así
que el máximo individual no se puede demostrar desde el servidor.

## 2. Correcciones implementadas

1. Nivel 8 aceptado en el límite de la API y cubierto por regresiones.
2. Marcadores Android `gameVersion=2155` y `AppVersion=80800` declarados en el
   perfil; las comprobaciones exigen coincidencia exacta.
3. El fixture canónico de pruebas conserva el formato original y declara los
   marcadores reales de Android.
4. `clone_json` reemplaza `deepcopy` en los editores de las 14 categorías.
5. El frontend evita reconstruir todos los elementos para contar seleccionados,
   cachea el progreso por guardado y agrupa apariencias en una sola pasada.
6. El límite del registro de respaldo sube de 64 KB a 256 KB, con una prueba que
   guarda, relee y valida un plan unificado de tamaño real.
7. Se registra el desbloqueo de skins de arma en iOS como evidencia física E4 del
   propietario, separado de la validación E3 de Android y de la aceptación de la
   nube.

## 3. Funcionamiento del sistema de versiones

El sistema separa explícitamente cinco capas:

| Capa | Ejemplo observado | Dónde vive |
| --- | --- | --- |
| Versión comercial | Android `8.8.0`, iOS `8.8.0.14` | Distribución/perfil |
| Versión de tienda | Apple Store `8.8.0`; Google Play no la expone | Consulta informativa con caché |
| Protocolo | `8.8.0` | Cabeceras del cliente nativo |
| Marcadores del guardado | `gameData.gameVersion=2155`, `itemData.AppVersion` iOS `1531` / Android `80800` | Documento |
| Serialización | `serialzedVersion=1` | Documento |

La detección combina la distribución de la sesión, el perfil de compatibilidad y
los marcadores del guardado. El perfil Android declara los marcadores esperados;
si el guardado no los contiene o difieren, la decisión pasa a
`pending_verification` y se bloquean preparación y escritura. No se corrigen,
incrementan ni reemplazan versiones de forma automática.

Antes de escribir:

- `prepare-unified` recibe el SHA-256 de la descarga y lo compara con la nube.
- El preflight vinculante incluye plataforma, distribución, protocolo, cuenta y
  hash del plan.
- `confirm` vuelve a descargar y exige que el hash remoto siga siendo el del
  original respaldado.
- Si la nube cambió entre preparación y confirmación, la operación se rechaza sin
  escribir. T16 lo comprobó en ambas plataformas.
- La restauración histórica crea un respaldo preventivo y verifica el hash
  esperado antes de subir.

Limitación documentada: el servidor no puede conocer con certeza la versión de la
aplicación instalada en el dispositivo físico. Solo observa los marcadores del
guardado y la distribución de la sesión. Cualquier versión inferida se presenta
como observación, no como confirmación del cliente instalado.

## 4. Cuellos de botella identificados

Backend:

- Cada categoría copiaba el árbol JSON completo con `deepcopy`, lo serializaba,
  lo reabría y lo verificaba. Con 13–15 categorías encadenadas, la copia y la
  serialización dominaban el `prepare`.
- El plan normalizado se guardaba dentro del registro cifrado del respaldo. El
  límite histórico de 64 KB era menor que el plan máximo real de Android.
- La red domina la operación remota: la confirmación tarda aproximadamente
  1,7–2,5 s y la verificación 0,39–0,70 s.

Frontend:

- `effective()` construía un objeto con todos los identificadores elegibles en
  cada consulta de conteo o estado.
- `quickChecked`, `selectedCount` y `unlockProgress` recorrían las categorías
  varias veces por fila y por render.
- `toggleItem` clonaba mapas completos y buscaba con `includes` lineal.
- Las apariencias de decoración se agrupaban con spread acumulativo O(n²).
- La comprobación de mínimos usaba un `.some` anidado por fila y cambio.

## 5. Comparativa de rendimiento

Benchmark local de 5 rondas sobre los guardados reales, sin red:

| Plataforma | Prepare frío antes | Prepare frío después | Prepare caliente antes | Prepare caliente después |
| --- | ---: | ---: | ---: | ---: |
| iOS 114.008 B | 347,6 ms | 273,1 ms | 254,2 ms | 186,2 ms |
| Android 115.168 B | 414,2 ms | 314,3 ms | 287,7 ms | 189,9 ms |

Mejora aproximada: 21–24 % en frío y 27–34 % en caliente. El `load` del guardado
ronda 20–22 ms, el preflight 0,2 ms y la confirmación simulada 20–23 ms. El
cuello restante es la serialización/reparseo por categoría; no se refactorizó
porque el tiempo interno ya es menor que la latencia de red.

T13 real, extremo a extremo:

| Plataforma | Operaciones | Plan | Payload | Prepare | Confirm | Verify | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| iOS | 2.175 | 71.138 B | 71.221 B | 876,3 ms | 2.229,9 ms | 392,6 ms | 3.498,8 ms |
| Android | 2.975 | 94.092 B | 94.175 B | 999,8 ms | 2.492,5 ms | 389,0 ms | 3.881,3 ms |

El frontend se validó con `tsc`, build de producción y 101 pruebas Playwright.
No se conserva una medición de interfaz estable y reproducible en dispositivo
físico; la mejora aplicada es algorítmica (eliminación de reconstrucciones
O(n²), conteo O(1) sobre exclusiones y caché de progreso), no un porcentaje
presentado como confirmado.

## 6. Matriz de resultados reales

Cada escenario se ejecutó sobre el guardado base, se confirmó y verificó, y se
restauró antes del siguiente. El tamaño del guardado fue constante: iOS
114.008 B, Android 115.168 B. El payload es el plan normalizado más 83 bytes de
metadatos.

| Prueba | Operaciones iOS | Operaciones Android | Plan iOS | Plan Android | Total iOS | Total Android | Resultado |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| T01 personaje individual | 1 | 1 | 45 B | 25 B | 3.085,7 ms | 2.608,8 ms | OK |
| T02 nivel 7 | 1 | 1 | 45 B | 45 B | 2.710,9 ms | 3.014,2 ms | OK |
| T03 nivel 8 | 1 | 1 | 45 B | 45 B | 2.751,1 ms | 2.780,4 ms | OK |
| T04 niveles masivos | 41 | 42 | 1.229 B | 1.257 B | 2.630,6 ms | 2.923,6 ms | OK |
| T05 skins de personaje | N/A | 759 | — | 22.514 B | — | 3.369,3 ms | iOS ya tenía 802/802 |
| T06 skins de arma | 192 | 192 | 3.290 B | 3.290 B | 2.584,3 ms | 2.762,8 ms | OK |
| T07 efectos de eliminación | 7 | 7 | 32 B | 32 B | 2.926,5 ms | 2.933,9 ms | OK |
| T08 mascotas y afinidad | 171 | 171 | 2.331 B | 2.331 B | 3.035,9 ms | 3.484,7 ms | OK |
| T09 decoraciones | 25 | 25 | 311 B | 311 B | 2.623,9 ms | 2.758,8 ms | OK |
| T10 personajes + niveles + skins | 42 | 841 | 1.257 B | 24.202 B | 2.962,5 ms | 2.820,5 ms | OK |
| T11 skins de arma + efectos | 199 | 199 | 3.321 B | 3.321 B | 2.655,8 ms | 2.901,5 ms | OK |
| T12 varias categorías | 266 | 306 | 9.908 B | 10.331 B | 3.100,1 ms | 3.036,1 ms | OK |
| T13 Unlock All | 2.175 | 2.975 | 71.138 B | 94.092 B | 3.498,8 ms | 3.881,3 ms | OK |
| T14 repetición | 1 | 1 | 45 B | 25 B | 2.771,8 ms | 2.584,0 ms | Segundo prepare `changed=false` |
| T15 restaurar respaldo | — | — | — | — | 2.699,5 ms | 2.398,1 ms | Restauración histórica OK |
| T16 guardado desactualizado | — | — | — | — | — | — | Confirmación obsoleta rechazada |

T10 iOS solo tuvo la categoría `hero_levels` porque la cuenta iOS ya tenía todos
los personajes y todas las skins de personaje. T05 iOS se omitió por la misma
razón. La restauración posterior de cada escenario devolvió el hash base.

Diferencias semánticas observadas: el resumen `remote_characters` de Android pasó
de 1 a 2 al subir Knight a nivel 8, aunque el guardado seguía teniendo solo
Knight desbloqueado. No se alteró ningún campo ajeno, pero esa métrica del
resumen no equivale uno a uno a `heroUnlock`; queda pendiente aclarar su
definición. No se encontró corrupción ni pérdida de datos.

## 7. Resultado del Unlock All

El plan incluyó todas las categorías habilitadas y evitó campos de solo lectura,
espejos protegidos y el pase sin registros:

- personajes y skins de personaje bloqueados;
- 63 habilidades;
- 993 armas no descubiertas y 493 desbloqueos de forja;
- 192 skins de arma;
- 7 efectos de eliminación;
- 338 materiales, 47 semillas, 2 alimentos de mascota y 57 mascotas;
- 42 niveles de personaje;
- 56 afinidades;
- 296 planos;
- 10 objetos de decoración y 5 niveles;
- recursos y progreso de pesca.

Android usó además monedas de temporada y tarjeta de renacimiento. No se
incluyeron `material_gem`, `material_fish` ni `material_season_coin` como
materiales para no duplicar espejos; `material_battery` y `material_grain` se
enviaron por la vía de alimento de mascota.

Resultado posterior a la subida, en ambas plataformas: 0 personajes, habilidades,
skins, skins de arma, efectos, mascotas, afinidades, niveles, planos o
decoraciones pendientes; 995 armas descubiertas. La restauración devolvió el hash
base. La prueba demuestra que la API acepta el volumen y que no hay conflicto
entre categorías, pero no sustituye la comprobación visual del propietario en el
juego.

## 8. Fallos adicionales descubiertos y corregidos

1. **Registro de respaldo de 64 KB.** T13 Android fallaba en `prepare` con
   `backup_integrity` después de componer el candidato, porque el plan
   normalizado se guarda en `record.json` y superaba el límite histórico. Se
   elevó a 256 KB y se añadió una regresión que guarda y relee un plan máximo.
2. **Marcadores Android no vinculantes.** El perfil Android no declaraba
   `gameVersion` ni `AppVersion`; un guardado con marcadores ausentes podía pasar.
   Ahora se exige coincidencia exacta.
3. **T14 mal planteado.** La primera versión de la matriz repetía el plan antes
   de confirmar. Se corrigió para repetirlo después y comprobar `changed=false`.
4. **Conteo de operaciones del resumen.** `change_count` cuenta rutas cambiadas,
   no elementos; T07 habría reportado 1 efecto en lugar de 7. La matriz ahora
   cuenta `newly_unlocked`/`changes` y conserva `changed_fields_count` aparte.

## 9. Problemas pendientes y limitaciones

- iOS sigue en `write_experimental`; no se declara compatible de forma general.
- La versión instalada en el dispositivo físico no es observable desde el
  servidor.
- El máximo de nivel por personaje no está expuesto (`level_max: null`); el 8 es
  el máximo global documentado, no una confirmación individual.
- La semántica exacta de `CurrentSkinIndex` y de la posesión del arma base al
  crear un registro de skin sigue sin confirmarse.
- La métrica `remote_characters` no está alineada de forma evidente con
  `heroUnlock`.
- La restauración exacta omite el binding de compatibilidad por diseño; los
  respaldos antiguos sin binding se aceptan para no romper el historial.
- La versión de Google Play no está disponible y la tienda es informativa.
- No se añadió un botón público de Unlock All. T13 fue una prueba de carga.

## 10. Confirmación de restauración

Al terminar todas las pruebas se descargaron ambos guardados, se restauró el
respaldo base con `/restore-history` usando el hash actual como expectativa y se
volvió a descargar y verificar:

| Plataforma | SHA-256 final | Tamaño | Resultado |
| --- | --- | ---: | --- |
| iOS | `d34be908a95843684a3c4340ecf2f5d3cb5e87c613220556fb45dd36f6eafe4f` | 114.008 B | `matches_original: true` |
| Android | `e3063462f514da148b7874e2936f144405e25bf070811fccde1a714960e7ad52` | 115.168 B | `matches_original: true` |

La restauración respondió `uploaded: false` porque la nube ya coincidía con el
original. No se dejó ninguna modificación de prueba en la cuenta.

## 11. Commits, CI y despliegue

- `b9f1c6c` — nivel 8 aceptado en el límite de la API.
- `e20ef38` — marcadores de versión y optimizaciones de backend/frontend.
- `6be4402` — límite de registro de respaldo y regresión.
- CI de `main`: ejecución `46081418006`, conclusión `success`.
- Imagen desplegada: `6be4402b56543f718e5607982b562cb21f30b8a4`, contenedor
  saludable.
- Suite local final: 794 pruebas backend aprobadas, 16 omitidas; 101 pruebas
  Playwright aprobadas, 22 omitidas; `npm run build` correcto.

## 12. Pruebas físicas que debe realizar el propietario

1. Abrir el juego en Android y comprobar que el guardado restaurado sigue
   mostrando el progreso original.
2. Repetir la comprobación en iOS y confirmar que el cliente no muestra el aviso
   de versión incompatible.
3. Validar en el juego un nivel 8 en un personaje distinto de Knight, en ambas
   plataformas, para convertir el máximo global en evidencia física por
   personaje.
4. Probar una selección masiva desde un dispositivo móvil y confirmar que la
   interfaz responde sin bloqueos perceptibles.
5. Si se desea elevar el Unlock All a E4, repetir una selección máxima controlada
   y comprobar en el juego que las categorías aparecen; la prueba remota de esta
   fase solo acredita persistencia en la nube.
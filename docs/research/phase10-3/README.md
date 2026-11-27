# Fase 10.3 — Compatibilidad automática de versiones y rendimiento del editor

Fecha: 2026-11-27.

Esta fase no añade categorías ni desbloqueos. Centraliza la compatibilidad de
versiones, impide escrituras sobre partidas cuyo esquema no está validado y
elimina el trabajo repetido que hacía que preparar una selección masiva tardara
varios minutos.

## Resultado

- Registro único de compatibilidad por distribución, versión comercial, versión
  de protocolo, esquema y catálogos.
- Detección de la última versión publicada en App Store y Google Play mediante
  consultas de solo lectura, con caché de 6 horas. Un fallo de la tienda no se
  interpreta como una versión nueva.
- Una versión nueva o desconocida queda en `pending_verification` o
  `new_version_detected`: se puede leer, pero no preparar ni escribir. Nunca se
  actualizan automáticamente los números usados para escribir.
- Preflight obligatorio antes de preparar, confirmar y restaurar. Vincula el
  candidato con la cuenta, distribución, plataforma, versión, esquema,
  catálogos, hash del original y hash del plan.
- Cache de agregados canónicos y supresión de diferencias binarias intermedias.
  Una edición unificada ya no valida, analiza y serializa el documento completo
  una vez por categoría.
- El respaldo guarda el hash del plan normalizado. Cargar un respaldo nuevo ya
  no recompone todas las categorías; un plan manipulado sigue siendo rechazado.
- La interfaz de Partida muestra el estado de compatibilidad y las etapas reales
  del guardado, sin porcentajes inventados.

## Causa de la lentitud

La preparación unificada encadenaba los editores granulares existentes sobre los
mismos bytes. Cada editor:

1. validaba el sobre de nube y el tamaño;
2. descomprimía y analizaba el JSON completo;
3. comprobaba que la serialización canónica coincidiera con el original;
4. hacía una copia profunda de todo el agregado;
5. serializaba el candidato y lo volvía a analizar;
6. volvía a leer el candidato para comprobar el valor;
7. restauraba el original y serializaba de nuevo para comparar;
8. recorría ambos documentos para calcular la diferencia binaria.

Con quince categorías eso ocurría quince veces sobre documentos cada vez
mayores. Además, un solo guardado real ejecutaba aproximadamente cuatro
preparaciones completas: al preparar, al guardar el respaldo, al cargarlo para
confirmar y al comprobar la compatibilidad del candidato. La lectura de la
partida repetía el análisis completo en cada lector de categoría.

En la muestra iOS autorizada de 115 KB, una preparación de 14 categorías tardaba
**630,7 ms** antes de la fase. En el VPS, con documentos mayores y las cuatro
repeticiones, el conjunto podía superar varios minutos.

## Qué se cambió

### Compatibilidad centralizada

`backend/app/cloud/compatibility.py` es la única fuente de:

- capas de versión: comercial, tienda, protocolo de aplicación, protocolo de
  juego, `gameVersion`, `AppVersion`, `serialzedVersion`, plataforma y
  distribución;
- perfiles validados por distribución y versión;
- decisión de compatibilidad y capacidades de lectura, preparación y escritura;
- binding de preflight y comparación estricta entre preparación y confirmación.

`backend/app/catalogs/version.py` declara la versión de los catálogos
empaquetados. No es la versión comercial ni la de protocolo.

`backend/app/native/distributions.py` valida al importarse que toda distribución
habilitada tenga un perfil compatible y que sus versiones de protocolo
coincidan. Una distribución nueva sin evidencia no puede habilitarse por
accidente.

### Capas que no se igualan

| Capa | Dónde se observa | Ejemplo validado |
| --- | --- | --- |
| Versión comercial | Distribución / tienda | Android `8.8.0`; iOS `8.8.0.14` |
| Protocolo de aplicación | `x-app-version` | `8.8.0` |
| Protocolo de juego | `x-game-version` | `8.8.0` |
| `gameData.gameVersion` | Documento descargado | iOS `2155` |
| `itemData.AppVersion` | Documento descargado | iOS `1531`; Android `80800` |
| `serialzedVersion` | Raíz del agregado | `1` |
| Plataforma / distribución | `platformId`, perfil | `IOS`, `android-global` |

El cuarto componente de iOS (`8.8.0.14`) es compilación/hotfix. Enviarlo como
versión de protocolo fue la causa del rechazo de la Fase 10.1. El registro lo
mantiene separado.

### Detección externa

Fuentes implementadas, siempre de solo lectura y con timeout:

- Apple iTunes Lookup:
  `https://itunes.apple.com/lookup?bundleId=com.ChillyRoom.DungeonShooter&country=us`.
- Google Play, ficha pública:
  `https://play.google.com/store/apps/details?id=com.ChillyRoom.DungeonShooter`.
- Metadatos del agregado descargado.
- Evidencia técnica del repositorio y validación manual del propietario.

La consulta se guarda en una caché con TTL de 6 horas. En producción se
actualiza en segundo plano al arrancar; una edición nunca espera a la tienda.
`peek` devuelve la última observación sin red.

Estado real de las fuentes:

| Fuente | Qué se obtiene | Límite |
| --- | --- | --- |
| App Store | Versión visible (`8.8.0` en la consulta del 2026-11-27) | No informa del protocolo ni del esquema |
| Google Play | La ficha actual no expone la versión en el HTML sin ejecutar JavaScript | Se registra `unavailable`; no se inventa un valor |
| ChillyRoom | No hay endpoint público estable de versiones | Requiere revisión manual |
| Guardado | `gameVersion`, `AppVersion`, `serialzedVersion`, `platformId`, `cloudSaveId` | Solo describe la copia descargada |

Una versión de tienda mayor que el perfil validado produce
`new_version_detected`. No se adopta como versión de escritura. Para habilitarla
hace falta un perfil nuevo con evidencia del protocolo, esquema y catálogos.

### Preflight y binding

Antes de preparar o confirmar se comprueba:

- identidad de la cuenta mediante digest con separación de dominio;
- distribución, plataforma y versión comercial;
- integridad y tamaño del agregado;
- `serialzedVersion` y marcadores `gameVersion` / `AppVersion`;
- compatibilidad de los catálogos empaquetados;
- hash y tamaño del original;
- hash del plan normalizado, cuando existe;
- detección de cambios remotos entre preparación y confirmación.

El binding se guarda en el respaldo. Si cambia la cuenta, la versión, el esquema,
los catálogos, el original o el plan, la confirmación falla con
`cloud_compatibility_changed` y exige preparar de nuevo. Un respaldo histórico
sin binding sigue protegido por el hash remoto y el preflight actual.

La restauración exacta del original es la única operación que se permite sobre
una versión nueva o desconocida, y solo si la partida se puede leer. No recompone
campos ni inventa versiones; recupera bytes ya verificados. Si la plataforma no
es reconocida, se bloquea también la restauración.

### Rendimiento

`backend/app/cloud/aggregate_cache.py` guarda hasta 16 agregados canónicos ya
validados (32 MiB), indexados por SHA-256 y tamaño. Los editores siguen haciendo
su copia profunda antes de mutar. No se cachean fallos.

`prepare_unified_edit` suprime las diferencias binarias intermedias: cada editor
sabe si cambió por su propia estructura, y solo se calcula la diferencia exacta
del candidato final. Los editores granulares conservan su comportamiento cuando
se usan por separado.

El respaldo almacena `unified_plan_sha256`. Al cargar un respaldo nuevo se
comprueba el hash del plan y los hashes de original/candidato sin volver a
ejecutar todas las categorías. Un plan alterado no coincide con el hash y se
rechaza. Los respaldos antiguos sin hash siguen usando la reproducción completa.

## Benchmarks

Muestra real autorizada de iOS, 115.175 bytes, `serialzedVersion=1`,
`gameVersion=2155`, `AppVersion=1531`. Los casos de 1 MB y 5 MB son la misma
partida con un campo superior desconocido y canónico añadido para alcanzar el
tamaño; no se publican datos privados.

| Tamaño | Antes: preparar | Después: frío | Después: caliente | Objetivo |
| --- | --- | --- | --- | --- |
| 115 KB | 630,7 ms (14 categorías, sin el resto del guardado) | 438,4 ms | 290,3 ms | < 3 s |
| 1 MB | 1.451,9 ms | 914,3 ms | 619,0 ms | < 3 s |
| 5 MB | 5.838,8 ms | 2.859,0 ms | 2.929,0 ms | < 3 s |

Tiempo por etapa del servicio con 13 categorías disponibles y 28 cambios:

| Etapa | 115 KB | 1 MB | 5 MB |
| --- | --- | --- | --- |
| Descarga/lectura simulada | 26,9 ms | 49,3 ms | 142,4 ms |
| Preflight | 0,2 ms | 1,4 ms | 6,5 ms |
| Preparar candidato | 530,1 ms | 858,7 ms | 2.981,5 ms |
| Cargar respaldo | 4,1 ms | 11,4 ms | 35,2 ms |
| Confirmar y verificar (sin red real) | 17,5 ms | 47,5 ms | 190,3 ms |

La preparación y la canalización local cumplen los objetivos (< 3 s y < 5 s)
incluso en el caso sintético de 5 MB. La red, el respaldo en disco y la
respuesta de ChillyRoom se miden aparte; no se incluyen en estas cifras.

## Interfaz

La sección Partida muestra un estado compacto:

- **Compatible**: lectura, preparación y escritura validadas.
- **Compatibilidad experimental**: permite el flujo con respaldo y confirmación,
  pero no se declara validado por el cliente oficial.
- **Nueva versión detectada**: solo lectura hasta revisar el perfil.
- **Verificación pendiente**: solo lectura.
- **Solo lectura**: no se habilita preparación ni escritura.

El detalle técnico (capas, fuente, fecha, catálogos y validación manual) está en
un desplegable. Durante el guardado se muestran las etapas conocidas del flujo
en su orden real, sin porcentajes ficticios; la respuesta final reemplaza al
indicador. El botón se bloquea mientras hay una operación en curso para evitar
solicitudes duplicadas.

## Cómo añadir una versión futura

1. Descargar una copia autorizada con la nueva versión y registrar plataforma,
   distribución, `gameVersion`, `AppVersion` y `serialzedVersion`.
2. Comparar estructura, campos y catálogos con el perfil anterior. No normalizar
   formatos históricos.
3. Verificar el protocolo real (`x-app-version`, `x-game-version`) con una sesión
   legítima. No usar el cuarto componente de iOS ni el `versionCode` de Android
   como protocolo.
4. Validar lectura, preparación y una escritura pequeña con respaldo,
   confirmación, descarga posterior y restauración.
5. Añadir un `CompatibilityProfile` nuevo en
   `backend/app/cloud/compatibility.py`, con fuente, fecha, nivel de evidencia y
   capacidades explícitas. Si cambia el protocolo, actualizar la distribución.
6. Añadir o actualizar los catálogos versionados; nunca cambiar el número de
   `serialzedVersion` para forzar una escritura.
7. Ejecutar las pruebas de compatibilidad, respaldo, API y Playwright.
8. Solo entonces actualizar la versión comercial de la distribución. Hasta ese
   momento la versión nueva permanece en solo lectura.

## Pruebas

- Backend: 781 pruebas aprobadas, 16 omitidas.
- Frontend: `npm run build` correcto.
- Playwright: 101 pruebas aprobadas, 22 omitidas.
- Nuevas pruebas: perfiles y capas, versión desconocida, tienda con versión
  mayor, fallo de tienda cacheado, binding alterado, bloqueo antes de respaldo y
  binding almacenado en el respaldo.
- Verificado en local sobre la muestra privada iOS autorizada; no se envió
  ninguna escritura a la nube durante esta fase.

## Limitaciones

- La detección automática no puede demostrar que un cliente oficial acepte un
  blob. Un HTTP 200 y un SHA-256 igual no sustituyen la prueba en el dispositivo.
- Google Play no entrega la versión en el HTML actual; queda pendiente una fuente
  estable o revisión manual.
- El perfil iOS sigue en experimental. La validación física con el cliente
  oficial es la última comprobación.
- El caso de 5 MB es sintético y añade un campo superior desconocido; las
  partidas reales observadas son mucho menores.
- La cache de agregados es por proceso. Varios workers mantienen copias
  independientes, lo cual es seguro pero no comparte memoria.
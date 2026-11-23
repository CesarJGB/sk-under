# Fase 5.3 · Adquisición y reconstrucción de respaldos

**Linux reconstruyó byte por byte los nueve archivos locales 8.6.0 desde JSON.** El importador de agregados adquirió una fuente real de archivos, comprobación de revisión y extracción de secciones. La validación de un agregado remoto 8.8.0 continúa bloqueada en la entrega autorizada de los bytes. La corrida del cliente oficial llegó al formulario de cuenta tras un fallo y un relanzamiento.

## Resultados y evidencia

| Criterio | Estado | Qué se pudo verificar |
| --- | --- | --- |
| A · Trazabilidad autenticada | PARCIAL | Se conserva la sesión autenticada histórica y se obtuvo una cronología monotónica nueva hasta el formulario. Falta una sesión autenticada instrumentada por etapas. [Sesión](session-timeline.md) |
| B · Correlación panel/confirmación | PENDIENTE | El panel puede llamar a FetchData(false) con HasFetchData a cero y otro predicado activo. La vista previa puede reutilizar LoadedGameData. El ensayo carece de una solicitud autenticada identificada y de la revisión aplicada. [Métodos](fetch-comparison.md) |
| C · Capas de formato | PARCIAL | Se distinguen DTO, Data, rama RPC, agregado y subsistemas. Se identificaron límites y retornos distintos. Falta el códec interior RPC y una copia real del DTO. [Formato](blob-format.md) |
| D · Independencia para copia suministrada | COMPLETO | Archivo local JSON/gzip compatible hasta sección, en Linux. Reconstrucción exacta de las nueve referencias reales por el códec local. La validación de un agregado **remoto real** es una comprobación distinta y sigue BLOQUEADA. [Importador](importer.md) · [Referencias reales](real-save-validation.md) |
| E · Entradas malformadas | COMPLETO | Se probaron límites, corrupción, truncado, formatos desconocidos, errores de identidad de la copia y distinción entre sección ausente y nula. [Pruebas de integración](../../../backend/tests/test_local_cloud_import.py) |
| F · Compatibilidad | COMPLETO | Pasaron las suites del backend y navegador y la compilación del frontend. La verificación cubre la regresión local. |
| G · Evidencia | COMPLETO | Los informes distinguen ejecuciones, versiones, mediciones y conclusiones condicionales. La reproducción privada requiere tener acceso legítimo al APK o al inventario de muestras. |

**Hechos demostrados.** En el ABI del AVD se trazó la ruta condicional ShowView → UseOldLogic → FetchData(false). La sobrecarga de éxito conserva el agregado y la vista previa lee ese campo. Los desbloqueos pasan por materialización de listas y el formateador también recibe colecciones de referencia. El cliente volvió a presentar el formulario vacío. Cuatro de los archivos 8.6.0 se reserializaron con JSON compacto, cuatro con dos espacios y uno requirió la sangría original por línea. [Carga y caché](fetch-comparison.md) · [Formateador](preview-error.md) · [Medición real](real-save-validation.md)

**Inferencias.** La caché hace plausible que confirmar use trabajo previo. Alcanzar GetExtraDescribe en la rama base reduce la probabilidad de que una lista recién materializada estuviera nula. El catálogo usado para comparar los desbloqueos aporta otro candidato.

**Hipótesis sin comprobar.** Falta medir si esa precarga ocurrió en la sesión del titular y si hubo otra descarga al confirmar. También siguen abiertos el parámetro que causó la excepción y la correspondencia entre un agregado remoto y los archivos 8.8.0.

## Comparación entre fases

| Pregunta | 5.1 | 5.2 | 5.3 |
| --- | --- | --- | --- |
| Sesión y UI | Login, fallo inicial, diálogo y restauración visibles | Medición previa al login por UID y SNI | Nueva cronología con reloj del invitado, crash y relanzamiento hasta formulario vacío |
| Adquisición | FetchData mencionado sin correlación | Resolución de rutas BlobSave y RPC | Ruta condicional de precarga en el panel y escritura, lectura e invalidación del agregado identificadas |
| Procesamiento en Linux | Regresión de nueve archivos locales | Contrato de fuente y resumen de una fuente sintética | Fuente local, manifiesto opcional, extracción, clasificación RPC y reserialización exacta de nueve árboles reales |
| Vista previa | Excepción y cambio tras tutorial | Cinco colecciones y opciones | Materialización previa y argumento adicional restoreRole en los cinco caminos |
| Copia remota en manos del backend | Sin bytes | Sin bytes | Sin exportación propia 8.8.0 accesible |

[Registro 5.1](../phase5-experimental/README.md) · [Registro 5.2](../phase5-trace/README.md)

## Implementación y pruebas

La entrada programática conserva `summarize_copy` y añade `import_copy(LocalFileSource(...))`. La CLI imprime el informe o una sección explícita. La clasificación RPC conserva la parte desconocida. Se incorporaron un fixture con once vectores, tests sintéticos, un verificador privado de referencias y un sondeo Android que emite medidas agregadas. [Ejemplo local](importer.md) · [Matriz de operaciones](emulator-dependency.md)

| Verificación desde backend/ o frontend/ | Antes, b3c2fd5 | Después |
| --- | ---: | ---: |
| Python, suite completa con las nueve referencias privadas habilitadas | 132 aprobadas | 163 aprobadas |
| Playwright, Chromium | 4 aprobadas | 4 aprobadas |
| TypeScript y build de Vite | Correcto | Correcto |
| Ensayo de reserialización desde el árbol JSON | — | 9/9 idénticos |

La suite pública se ejecuta con `cd backend && uv run --locked pytest -q`. Las nueve regresiones previas de archivos privados requieren las variables documentadas en [validación real](real-save-validation.md). Las 31 pruebas nuevas usan datos sintéticos. La compilación y la suite de navegador se ejecutan en frontend/ con `npm run build` y `npm run test:browser`.

## Dependencias, compatibilidad y Fase 5.4

La recepción de un archivo ya suministrado, verificación, descompresión gzip, reconocimiento y extracción de secciones se ejecutan en Linux. Continúan en el cliente oficial la autenticación, la consulta del respaldo de cuenta y la restauración. Los esquemas y las reglas de serialización de 8.6.0 corresponden a esas nueve referencias. Cambios de versión, canal, FixData, parches en ejecución o variantes del códec local pueden cambiar el resultado. La edición de progreso real sigue sin validación de juego. [Dependencias y mecanismos oficiales](emulator-dependency.md)

La primera entrega medible de 5.4 sería **una revisión propia autorizada de 8.8.0 procesada de extremo a extremo**. Solicitar al proveedor una exportación con capa, tamaño y huella o un mecanismo delegado aprobado. En paralelo, repetir panel → recuperar → cancelar y, si procede, la confirmación segura con el titular en la sesión oficial. Correlacionar inicio y fin de adquisición, revisión consumida y resumen restaurado. Si el proveedor solo ofrece restauración dentro del juego, la investigación puede verificar la reutilización del agregado mediante diagnóstico autorizado, mientras la adquisición independiente permanece bloqueada.

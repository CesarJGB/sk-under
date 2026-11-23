# Fase 5 · Acceso y reconstrucción de partidas de ChillyRoom

El inicio de sesión seguido de descarga automática en el editor web **queda pendiente de un mecanismo autorizado por ChillyRoom para aplicaciones externas**. La vía pública verificada permite al titular restaurar progreso dentro de Soul Knight. La revisión no encontró un contrato de acceso de terceros ni una exportación pública del agregado original. [Manual oficial de Android](https://soulknight.chillyroom.com/et/article/base/3) · [Preguntas frecuentes](https://soulknight.chillyroom.com/et/article/base/6)

El backend contiene un [reconstructor aislado](../../../backend/app/cloud_save.py) de solo lectura y sin acceso a red. Acepta JSON UTF-8 o ese mismo JSON en gzip, genera un agregado tipado y produce un resumen de secciones. Se probó con un fixture sintético. La correspondencia del formato de entrada con un respaldo remoto real queda pendiente.

| Informe | Alcance |
| --- | --- |
| [Autenticación](autenticacion.md) | SDK, sesión, identidad, titularidad y errores |
| [Flujo de descarga](flujo-descarga.md) | Obtención de metadatos, transporte, deserialización y aplicación local |
| [RPC frente a BlobSave](rpc-y-blobsave.md) | Evidencia de cada ruta y límites de atribución |
| [Reconstrucción de CloudSaveGameData](reconstruccion.md) | Esquema observado, vínculos locales, migraciones y prototipo |
| [Pruebas con cuenta propia](pruebas-cuenta.md) | Búsqueda de un mecanismo oficial, bloqueo y resultados locales |
| [Presets](presets.md) | Campos candidatos, dependencias y pruebas requeridas |
| [Limitaciones y riesgos](limitaciones-y-riesgos.md) | Límites de evidencia, identidad, compatibilidad y conservación de datos |
| [Plan de Fase 6](plan-fase6.md) | Integración autorizada de lectura y criterios de aceptación |

## Cómo verificar las referencias

El APK tiene SHA-256 `54bb332be9444596501ec99f745f21adfa55265feea3a15331c735009b517f34`, comprobado de nuevo durante esta fase. Se reutilizó el procedimiento de Fase 4 para leer DEX, localizar tipos y métodos IL2CPP, correlacionar los identificadores con punteros del ELF AArch64 y seguir llamadas directas seleccionadas. Los símbolos del juego pertenecen a `Assembly-CSharp.dll` salvo donde se indica otra imagen. Cada token está calificado por su imagen y las direcciones virtuales corresponden exclusivamente a este APK. Las llamadas describen el código distribuido. Las instancias genéricas, los cuerpos parcialmente legibles y los hotfix limitan la reconstrucción del flujo en ejecución. [APK y procedimiento de Fase 4](../phase4/apk.md)

Una **declaración** prueba que existe un tipo, miembro o método en metadatos. Una **llamada observada** prueba un enlace en código estático. Una **prueba local** usa el fixture del módulo o las nueve muestras de 8.6.0. Las afirmaciones del **proveedor** se limitan al canal y al flujo que documenta la fuente citada.

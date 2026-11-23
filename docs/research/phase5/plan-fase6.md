# Plan de implementación para la Fase 6

## Validar la fuente autorizada

1. Confirmar con ChillyRoom si existe un mecanismo aprobado de consentimiento y lectura de metadatos y respaldo por parte de un tercero. Solicitar la especificación de identidad, formatos, versiones, límites y errores, y un entorno de lectura para la cuenta propia. En paralelo, consultar si soporte puede proporcionar una exportación del agregado para probar la reconstrucción. [Soporte](https://www.chillyroom.com/en/support)
2. Si está disponible el cliente oficial en un dispositivo adecuado, comprobar en el panel la identidad de cuenta, el canal y la existencia del respaldo. Registrar solo presencia, versión cuando se muestre, marcas temporales y estado. Ante verificación que requiera intervención del titular, detener el ensayo hasta que la complete en la interfaz del proveedor. Una restauración en un dispositivo dedicado solo verifica la materialización local.
3. Cuando haya bytes autorizados, registrar su procedencia y SHA-256 antes de ninguna transformación. Identificar la envoltura, validar la descompresión y comparar el agregado con los archivos y preferencias de la misma cuenta, canal y compilación. Derivar fixtures sanitizados y verificar el comportamiento con una segunda copia representativa.
4. Si hay exportación oficial pero carece de acceso delegado para la web, usarla para validar el esquema y mantener el estado de conexión automática como pendiente. La importación existente de archivos locales conserva su papel en la investigación comparativa.

## Arquitectura condicional de lectura

| Componente | Responsabilidad | Condición de activación |
| --- | --- | --- |
| Frontend en Cloudflare Pages | Mostrar conexión pendiente o iniciar el consentimiento alojado por el proveedor. Tras conectar, presentar estado de guardado, metadatos básicos y resumen. Mostrar presets como candidatos hasta validar cada transformación. | Vía de consentimiento y respuestas verificadas. La interfaz nunca solicita la contraseña de ChillyRoom. |
| Sesión del editor en Coolify | Vincular el usuario del editor a la identidad que confirma el proveedor. Conservar la sesión remota solo en el servidor, con expiración y revocación según el contrato. Verificar la sesión propietaria antes de devolver metadatos o resultados. | Identidad verificable y autorización de lectura limitada al guardado propio. |
| Conector de solo lectura | Consultar metadatos y copiar el respaldo asociado a esa sesión. Distinguir guardado ausente, sesión expirada, verificación requerida, límite y error temporal. Procesar reintentos y límites según las respuestas documentadas. | Operaciones autorizadas de consulta y descarga, con respuestas observadas. |
| Reconstrucción | Validar origen en el conector, separar su envoltura documentada y entregar al módulo el JSON o gzip correspondiente. Conservar el original según la retención acordada, comparar integridad y proyectar el resumen. | Formato real comprobado y perfil de versión derivado de muestras. |
| Presets | Mostrar una vista previa de cambios propuestos sobre una copia aislada, con reglas verificadas por versión y catálogo. | Evidencia por campo, revisión de dependencias y pruebas de preservación. La sincronización requiere una fase independiente. |

## Criterios para anunciar conexión funcional

- Un titular completa el consentimiento por la vía aprobada y el editor consulta automáticamente los metadatos del respaldo correcto.
- El editor descarga una copia intacta, conserva su SHA-256 y reconstruye un agregado real de una versión admitida. La prueba documenta procedencia, formato y correspondencias locales.
- Las pruebas cubren guardado inexistente, cancelación, expiración, límite del proveedor, versión no admitida y aislamiento de sesión. El frontend muestra qué parte del flujo está disponible.
- El resumen y las vistas previas son de solo lectura respecto a ChillyRoom. La sincronización se decide y valida por separado.

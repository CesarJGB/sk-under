# Acceso web directo y puente Android

## A · Backend web directo

La revisión pública del manual, las preguntas frecuentes y soporte confirma que el cliente oficial puede restaurar un respaldo propio. En esas fuentes no se encontró un acceso delegado para aplicaciones externas, una API de lectura de Soul Knight ni una exportación del agregado original. La evidencia describe la oferta documentada al usuario. Queda abierta la existencia de un canal para integraciones autorizadas mediante acuerdo con el proveedor. [Manual oficial](https://soulknight.chillyroom.com/et/article/base/3) · [FAQ](https://soulknight.chillyroom.com/et/article/base/6) · [Soporte oficial](https://www.chillyroom.com/en/support)

El backend directo necesita consentimiento de la cuenta en una superficie aprobada, una identidad de propietario verificable y operaciones de lectura para metadatos y bytes del respaldo. Las rutas privadas identificadas en el cliente en la Fase 5 no conceden ese acceso. Si el proveedor confirma un contrato, el primer ensayo debe verificar una copia intacta de la cuenta de prueba y atribuir la respuesta a la sesión que la autorizó. [RPC y BlobSave en Fase 5](../phase5/rpc-y-blobsave.md)

## B · Cliente Android como puente

| Componente | Viabilidad y dependencia |
| --- | --- |
| Entorno por usuario | Un AVD aislado simplifica observar la interfaz y volver a una compilación conocida. La operación requiere capacidad de virtualización y compatibilidad gráfica y de ABI. Una imagen de Play Store puede ejecutar la aplicación con su aislamiento de producción. |
| Restauración oficial | Demostrada con la cuenta propia en Android 11 y el ABI de 32 bits. En el primer intento la vista previa falló y el segundo funcionó tras entrar al tutorial fuera de línea. El proveedor incluye a los emuladores en sus límites de vinculaciones. Variaciones de interfaz, versiones obligatorias o verificaciones requieren atención. [Experimento](experimentos.md) · [Límites del proveedor](https://soulknight.chillyroom.com/et/article/base/4) |
| Copia local | En el AVD que restauró, se denegaron las rutas de datos tanto antes como después del resultado. La ruta privada requiere un mecanismo que exponga la aplicación o autorice el proveedor. Un selector de archivos sirve para una exportación que el juego publique en almacenamiento compartido. Android restringe a una app auxiliar el acceso a los datos internos y a los directorios específicos de otra app. [Sondeo de archivos](archivos.md) · [Almacenamiento de Android 11](https://developer.android.com/about/versions/11/privacy/storage) · [Cambios de backup en Android 12](https://developer.android.com/about/versions/12/behavior-changes-12) |
| Transferencia y reconstrucción | Una exportación voluntaria hacia el selector del sistema o una copia que entregue soporte permitiría transferir el contenido de prueba. El módulo de Fase 5 requiere un objeto JSON o gzip del agregado. Los archivos locales por subsistema requieren su propio lector. [Reconstrucción de Fase 5](../phase5/reconstruccion.md) |
| Operación y escala | Conservar una VM por sesión aumenta el coste de CPU, RAM y disco. La interacción visual depende de idioma, versión y UI. Vinculaciones, expiración y desafíos limitan reintentos. La automatización con un helper solo puede empezar donde el cliente exponga una salida compatible y el proveedor autorice el flujo. |

## Recomendación

Priorizar el flujo web directo si ChillyRoom ofrece lectura delegada. Usar Android 11 con el ABI de 32 bits como referencia de restauración y repetir la prueba en un dispositivo ARM64 del mismo canal. Para avanzar con el puente, obtener primero una exportación que el juego o soporte pueda entregar al titular. Solo con esa salida se puede verificar la reconstrucción, y una integración reproducible requiere además autorización para el proceso completo.

# Fase 4 · Guardados de Soul Knight 8.8.0

El APK analizado declara Soul Knight 8.8.0 y contiene Unity 2022.3.62f2 con IL2CPP. El cliente conserva modelos que coinciden con los nueve tipos de archivos observados en 8.6.0. El código también contiene rutas alternativas con Rijndael, selección de serializador, migración y sincronización de un documento agregado. La investigación dispuso únicamente de guardados reales atribuidos a 8.6.0. La compatibilidad de archivos escritos por 8.8.0, incluida su restauración en el juego, sigue pendiente de prueba.

| Documento | Contenido |
| --- | --- |
| [APK](apk.md) | Huellas, firma, manifiesto, recursos, ABI y método de análisis |
| [Guardados locales](guardados-locales.md) | Mapa de componentes, estructuras, cifrado, migración y comparación con las nueve muestras |
| [Sincronización](sincronizacion.md) | Cuenta y canal, RPC y blob, compresión, controles y límites de una integración |
| [Editor y pruebas](editor-y-pruebas.md) | Riesgos de corrupción, decisiones de producto, pruebas y siguiente fase |

## Estado de partida

La Fase 3 está integrada en `main` desde `d303c7b`. El adaptador `sk-local-des-cbc` valida la envoltura y reconoce nueve esquemas por contenido. El backend proyecta campos de solo lectura y comprueba una exportación reabriéndola y comparando sus bytes con la entrada. El frontend comprueba el tamaño y SHA-256. El formato demostrativo `.skdemo` admite edición. [Análisis de Fase 3](../../phase3/FORMAT_ANALYSIS.md) · [Implementación de Fase 3](../../phase3/IMPLEMENTATION.md) · [Pruebas de Fase 3](../../phase3/TEST_RESULTS.md)

Se añadió una prueba de regresión automatizada y opcional para los nueve archivos privados de 8.6.0. Los nueve completaron inspección, validación, exportación idéntica y reimportación. Las decisiones sobre importación, edición, conversión y exportación de 8.8.0 quedan registradas en la matriz de cobertura. [Editor y pruebas](editor-y-pruebas.md)

## Evidencia

- **Comprobado con muestras** indica que se observó el resultado sobre bytes de la cuenta de prueba o mediante el editor local.
- **Confirmado en el APK** indica una declaración, recurso o llamada estática identificada en el artefacto. La evidencia describe el código distribuido y su camino base.
- **Hipótesis** indica una interpretación que requiere muestras, ejecución autorizada o documentación del proveedor. Los cuerpos parciales, las ramas por cuenta y canal y los puntos de hotfix limitan la atribución al comportamiento en ejecución.

# Fase 5.1 · Validación experimental de Soul Knight 8.8.0

**Soul Knight 8.8.0 restauró la partida de la cuenta propia mediante su interfaz oficial.** Funcionó en una imagen Google Play de Android 11 con el ABI de 32 bits incluido en el APK. La primera restauración falló al construir la vista previa. Tras abrir el tutorial local sin conexión y volver al menú, el cliente permitió confirmar la descarga y aplicar el progreso. Los dos paneles quedaron visualmente igualados. [Registro de experimentos](experimentos.md)

| Resultado | Evidencia exigida | Estado |
| --- | --- | --- |
| A · Restauración oficial | Inicio de sesión, respaldo visible y progreso restaurado en el cliente | **Verificado** en la cuenta propia. |
| B · Reconstrucción | Copia obtenida por un mecanismo permitido, resumen concordante con el juego | Bloqueado por el acceso a los archivos. |
| C · Automatización autorizada | Lectura reproducible por un mecanismo aprobado, con extracción o exportación de datos | Sin demostrar. La automatización demostrada alcanza el control supervisado de la UI. |

Las pruebas parten del commit `ccd0d2d`. Los detalles estáticos del APK y del agregado se mantienen en los informes anteriores. [Fase 4](../phase4/README.md) · [Fase 5](../phase5/README.md)

- [Registro de experimentos y evidencias](experimentos.md)
- [Laboratorio Android y reproducción](laboratorio.md)
- [Archivos y reconstrucción](archivos.md)
- [Comparación de arquitecturas y recomendación](arquitecturas.md)

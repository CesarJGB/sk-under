# Propuesta para la Fase 6.14

La Fase 6.13 deja una visualización funcional y verificada de solo lectura. La
siguiente fase debe cerrar primero las incógnitas que impiden escribir con
seguridad, sin convertir la falta de evidencia en una autorización implícita.

## Prioridades

1. **Transacción legítima de fichas de pesca.** Repetir el protocolo de captura
   en un dispositivo o emulador con acceso de lectura: obtener fichas, guardar,
   reiniciar, recuperar desde la nube y comparar antes/después. La prueba debe
   incluir un saldo positivo, la proyección local de `fishChip`, los historiales
   `fishChipStore*`, `furniture_fish_chips` y la autoridad observada. Sin esta
   evidencia, la escritura debe seguir deshabilitada.
2. **Niveles de personajes.** Probar mejoras legítimas en al menos otro
   personaje y en más de un nivel, registrar costos, topes visibles y
   persistencia. Solo entonces se podría evaluar una edición limitada con
   respaldo y validación estructural.
3. **Habilidades y skins.** Comprobar qué cambia al desbloquear una habilidad y
   al equipar una skin. No usar `skinLock` como prueba de posesión. Mantener los
   entitlements, compras y verificaciones de propiedad fuera del editor.
4. **Recursos ordinarios.** Elegir un recurso con semántica sencilla, por
   ejemplo una semilla o un material, y demostrar una transición antes/después
   con reinicio. Extender la gestión solo después de repetir la prueba.
5. **Rendimiento y ergonomía.** Medir el informe con agregados de distintos
   tamaños, revisar la paginación de listas largas y añadir filtros de recursos
   si el catálogo de nombres se incorpora en una fase posterior.
6. **Compatibilidad.** Mantener el contrato existente de gemas y respaldos;
   añadir pruebas de regresión para clientes que no envían `report`.

## Criterio de escritura

Cualquier campo nuevo debe cumplir: evidencia E3 de semántica, E4 de
persistencia, dependencias identificadas, validación de tipos y límites,
respaldo previo, restauración verificable y una prueba de regresión que
demuestre que los campos desconocidos y las compras no cambian. Mientras falte
uno de esos puntos, la interfaz debe mostrar el dato y no ofrecer un botón de
edición.
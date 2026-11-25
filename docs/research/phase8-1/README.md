# Fase 8.1 del editor móvil de SK-Under

El editor vuelve a mostrar las cantidades de la partida descargada y comparte un borrador entre Rápida y Categorías. El flujo de respaldo, preparación, confirmación y verificación se mantiene.

## Causa de los valores en cero

El rediseño de `3b7262d` dejó de pasar los valores originales a las filas de Rápida. Las filas numéricas leían el borrador recién creado, cuyo valor inicial era una cadena vacía, y mostraban el marcador literal `0`, incluso con el campo desactivado. El resumen de descarga seguía entregando las cantidades. El resumen preliminar disponible al iniciar sesión, por su parte, podía traer saldos sin el informe de desbloqueos. El editor carga ese informe mediante la descarga habitual cuando entra con una copia preliminar.

Rápida y el detalle muestran el original junto a un campo de solicitud independiente. Un cero confirmado se muestra como tal. Los valores desconocidos quedan identificados y los controles incompatibles se deshabilitan. Si el informe permite observar fichas de pesca que el escritor no puede validar, se muestra el saldo en solo lectura. Desactivar un recurso lo excluye del plan, incluso si el borrador conserva el texto escrito en su campo.

Para colecciones de cantidades heterogéneas, Rápida muestra «Cantidades distintas». El detalle muestra cada importe. Los mínimos masivos de Rápida y del detalle se combinan por elemento usando el mayor mínimo aplicable. Se respetan las cantidades superiores, las ediciones individuales explícitas y la protección del espejo de fichas `material_fish`.

## Interfaz y funciones preservadas

- El editor usa un encabezado propio con regreso a Partida, cuenta, plataforma, versión y estado de carga. El selector Rápida/Categorías ocupa una fila independiente.
- Rápida agrupa recursos, mínimos, desbloqueos y beneficios en filas compactas. «Seleccionar pendientes» actúa sobre los desbloqueos elegibles. Las colecciones muestran desbloqueados sobre el total determinable, pendientes y un icono de confirmación al completarse.
- La cuadrícula de nueve categorías conserva tres columnas en móvil desde 320 px y reutiliza sus iconos en el detalle. Las insignias indican cambios que afectan a los controles de esa categoría. Se mantienen la búsqueda, los filtros, las exclusiones y las cantidades individuales.
- La barra inferior muestra los cambios efectivos y el estado de la operación. Los botones bloquean solicitudes duplicadas mientras se prepara, sube o recarga la partida. El regreso y el historial piden confirmación antes de descartar el borrador de la partida. Un conflicto o una subida sin verificar conserva el borrador.
- El plan mantiene el SHA base, el candidato único, la confirmación explícita, el respaldo restaurable y la verificación remota. El backend, los protocolos, la serialización, los escritores y los niveles de evidencia permanecen intactos.

## Procedencia gráfica

El repositorio contiene catálogos normalizados y capturas de interfaz. La referencia SKDFE 8.8.0 documenta la extracción de sprites, pero su árbol de referencia carece de licencia de redistribución. Los nueve PNG de 16 × 16 en `frontend/public/editor-icons/` se dibujaron para esta fase sobre una cuadrícula de píxeles. Representan una gema, un casco, un rayo, una capa, un gato, un lingote, un brote, una moneda y una medalla. La interfaz los sirve localmente y reutiliza Lucide para los controles. [Procedencia de SKDFE](../../../knowledge/sources/skdfe.md)

## Pruebas

| Comprobación | Resultado local |
| --- | --- |
| TypeScript y build de Vite | Correctos |
| Backend, compilación y catálogos | 651 pruebas aprobadas y 16 omitidas |
| Pruebas históricas de experimentos | 27 aprobadas |
| Playwright Chromium | 45 aprobadas y 24 casos históricos omitidos |
| Playwright WebKit | 15 regresiones funcionales del editor aprobadas |
| Registro legado y estructura de conocimiento | Proyección idéntica y estructura válida |

Las pruebas de navegador usan partidas sintéticas con cantidades positivas, ceros reales, datos ausentes o incompatibles y colecciones completas o parciales. Comprueban el borrador compartido, el regreso con cambios, el descarte, la protección contra solicitudes duplicadas y la conservación de cantidades inactivas mediante el cuerpo exacto del plan de guardado. Se simula el espacio del teclado mediante `VisualViewport` y se comprueba el estado durante una subida sin verificación.

El manifiesto de conocimiento de la rama base ya tenía hashes desactualizados en tres archivos. La comprobación estructural pasa con `--no-manifest-check` y la proyección de los 66 campos sigue siendo idéntica.

## Capturas de Playwright

Cada celda enlaza a una captura de Chromium del tamaño indicado. Las tres vistas se revisaron en móvil, tableta y escritorio. Las comprobaciones automáticas verifican que no haya desplazamiento horizontal y que la última fila pueda verse por encima de la barra inferior.

| Ventana | Rápida | Categorías | Materiales |
| --- | --- | --- | --- |
| 320 × 568 | [Abrir](capturas/rapida-320.png) | [Abrir](capturas/categorias-320.png) | [Abrir](capturas/materiales-320.png) |
| 360 × 800 | [Abrir](capturas/rapida-360.png) | [Abrir](capturas/categorias-360.png) | [Abrir](capturas/materiales-360.png) |
| 375 × 812 | [Abrir](capturas/rapida-375.png) | [Abrir](capturas/categorias-375.png) | [Abrir](capturas/materiales-375.png) |
| 390 × 844 | [Abrir](capturas/rapida-390.png) | [Abrir](capturas/categorias-390.png) | [Abrir](capturas/materiales-390.png) |
| 430 × 932 | [Abrir](capturas/rapida-430.png) | [Abrir](capturas/categorias-430.png) | [Abrir](capturas/materiales-430.png) |
| 768 × 1024 | [Abrir](capturas/rapida-768.png) | [Abrir](capturas/categorias-768.png) | [Abrir](capturas/materiales-768.png) |
| 1280 × 800 | [Abrir](capturas/rapida-1280.png) | [Abrir](capturas/categorias-1280.png) | [Abrir](capturas/materiales-1280.png) |

- [Desbloqueos en Rápida](capturas/rapida-desbloqueos-390.png)
- [Recursos](capturas/recursos-390.png), [Personajes](capturas/personajes-390.png), [Habilidades](capturas/habilidades-390.png) y [Skins](capturas/skins-390.png)
- [Mascotas](capturas/mascotas-390.png), [Semillas](capturas/semillas-390.png), [Temporada](capturas/temporada-390.png) y [Pase de batalla](capturas/pase-390.png)

## Validación pendiente

La comprobación en dispositivo físico y con la cuenta del propietario queda pendiente. El pase de batalla conserva la evidencia experimental que tenía en la fase anterior.

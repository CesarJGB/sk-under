# SK-Under

Antes de investigar o habilitar una categoría de guardado, consulta [la investigación de guardados](docs/save-research/README.md), el [Save Knowledge Engine](knowledge/README.md) y la entrada correspondiente de [knowledge/fields/fields.json](knowledge/fields/fields.json). El archivo `docs/save-research/field-registry.json` se conserva como proyección legada de 66 campos y debe seguir coincidiendo con la generación determinista. Reutiliza las capturas y protocolos de las fases anteriores. Registra nuevas observaciones por versión, plataforma y capa. Actualiza el nivel de evidencia únicamente después del experimento que lo respalde.

Mantén partidas, credenciales y capturas de cuentas en almacenamiento privado. Para el repositorio utiliza resultados saneados y fixtures sintéticos. Los catálogos sirven para identificar elementos. Los estados de compra y las recompensas reclamadas son de solo lectura.

## Diseño y experiencia de usuario

Side es un editor Mobile First. Antes de modificar la interfaz, comprueba el resultado en tamaños móviles reales (320, 360, 375, 390 y 430 px de ancho), sin desplazamiento horizontal, con controles táctiles utilizables y sin contenido tapado por la barra inferior.

- Prioriza funcionalidad, simplicidad y densidad útil. Evita descripciones secundarias, subtítulos de relleno, explicaciones permanentes y texto que repita lo que ya comunica un control.
- No uses tarjetas grandes para operaciones simples ni tarjetas dentro de tarjetas sin necesidad. Una operación de una casilla y un valor numérico ocupa una fila compacta.
- No concentres todos los editores detallados en una única página ni crees desplazamientos verticales innecesarios. La edición rápida es la pantalla inicial; los editores detallados se abren desde una cuadrícula de categorías.
- Toda función nueva debe integrarse en su categoría y, si admite una operación masiva, en edición rápida mediante el registro declarativo común. No mantengas inventarios manuales duplicados.
- Todos los editores comparten un único borrador global asociado al perfil y a la versión base. No crees botones independientes de guardado o subida por categoría.
- Mantén la información técnica secundaria en elementos expandibles o ayudas contextuales. Muestra advertencias solo donde aporten información pertinente.
- Reutiliza componentes, patrones visuales y estilos existentes. Evita el exceso de iconos decorativos.
- Preserva accesibilidad, integridad del guardado, respaldos, confirmaciones y protección contra conflictos. No sacrifiques seguridad por compactar la interfaz.
- Antes de dar por terminado un cambio visual, revísalo con capturas de Playwright en móvil, tableta y escritorio.

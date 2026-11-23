# Editor, riesgos y pruebas

## Decisiones de cobertura

| Operación | Decisión de Fase 4 | Evidencia necesaria para ampliar cobertura |
| --- | --- | --- |
| Importar 8.6.0 | Se verificó el adaptador existente con las nueve muestras. Proyecta los campos conocidos en solo lectura | Muestras adicionales para ampliar a otros canales, cuentas y familias |
| Exportar 8.6.0 | Se verificó la copia intacta y su reimportación en el editor. La restauración en el juego sigue pendiente | Restauración desde una copia en un entorno autorizado y aislado |
| Importar y exportar 8.8.0 | Pendiente para cada familia y ruta de guardado | Archivos reales de la misma compilación, códec comprobado y exportación intacta con reimportación |
| Mostrar o editar más campos | Pendiente. Los miembros que aparecen en el APK se tratan como candidatos | Pares de muestras controladas que revelen tipo, rango, significado y dependencias entre archivos |
| Detectar versiones | Se conserva el reconocimiento por estructura y los dos marcadores internos de la Fase 3 | Evidencia de un marcador estable por archivo y contraste de muestras entre compilaciones y canales |
| Validar al guardar | Para el formato existente, la API exige envoltura, relleno, JSON y estructura válidos, y verifica igualdad y relectura al exportar | Un códec 8.8.0 probado y reglas semánticas específicas para nuevas operaciones |
| Convertir formatos y sincronizar con la nube | Pendiente | Conversión sin pérdida probada en copias desechables. Para la nube se requiere un mecanismo autorizado y documentado |

El cambio funcional se limita a una prueba de regresión para la interfaz autenticada del backend.

## Riesgos de corrupción

- Cambiar `AppVersion`, `version` o `last_play_version` sin conocer su semántica puede activar una migración o provocar una reinicialización. El número de compilación Android y el del bundle sirven para identificar el APK.
- El progreso cruza archivos y preferencias. Un cambio aislado en monedas, desbloqueos, compras, arma equipada o estadísticas puede dejar contadores, referencias o indicadores inconsistentes.
- Volver a serializar JSON puede omitir miembros desconocidos, cambiar tipos y tratamiento de mapas, o perder precisión en JavaScript. Una copia intacta conserva envoltura, orden, espacios y datos desconocidos.
- El relleno y un esquema válido pueden admitir contenido DES-CBC alterado. El SHA-256 del editor comprueba igualdad con la entrada que recibió. La autenticidad y la aceptación por el juego requieren controles adicionales.
- Los archivos con sufijos por cuenta, copias auxiliares y variantes Rijndael pueden influir en qué datos se cargan. La prioridad entre archivos, la recuperación ante un fallo de escritura y el efecto de renombrar una copia necesitan una prueba controlada.
- Aplicar un respaldo completo puede reemplazar progreso posterior e iniciar pasos de recuperación o reconciliación. Mantener copias aisladas por cuenta y capturar el estado completo permite recuperar el punto de partida.

## Resultados de pruebas

| Verificación | Resultado |
| --- | --- |
| `uv run --locked pytest -q` desde `backend/`, con las muestras privadas y el códec configurados | 99 aprobadas. Incluye nueve pruebas nuevas contra la API autenticada |
| La misma suite con la configuración habitual | 90 aprobadas y 9 omitidas de forma explícita |
| `npm ci` y `npm run build` desde `frontend/` | Instalación con lockfile, TypeScript y compilación Vite completados |
| `npm run test:browser` desde `frontend/` | 4 aprobadas en Chromium, incluidos rechazos por divergencia de tamaño, hash y bytes |
| Verificación directa del códec 8.6.0 | 9/9 descifrados a objetos JSON. El recifrado del texto exacto reprodujo los nueve originales |

[La prueba privada](../../../backend/tests/test_private_save_roundtrip.py) lee cada muestra, compara tamaño y SHA-256 en inspección y validación, descarga con la API local, exige igualdad byte por byte y vuelve a inspeccionar la descarga. Comprueba además el rechazo de una edición y relee el original para confirmar preservación. Las descargas se mantienen en memoria. El conjunto configura un token de prueba del editor y toma los parámetros del códec ya verificado en Fase 3 de un archivo privado.

Para reproducir el conjunto completo desde `backend/` con las rutas locales del VPS de investigación:

```sh
SK_PHASE4_SAMPLES_DIR='/home/cesar/sk cuentas /cuenta 1 8.6.0' \
SK_PHASE4_CIPHER_ENV_FILE='/home/cesar/.config/sk-under/phase3/cipher.env' \
uv run --locked pytest -q
```

El directorio padre `sk cuentas ` tiene un espacio final. En otra máquina se pueden indicar las rutas correspondientes. Cuando se proporciona el directorio y falta un archivo o la configuración del códec, la prueba falla. Las muestras, sus bytes, los valores del códec y los datos de cuenta quedan fuera del repositorio.

## Siguiente fase

1. Capturar dos conjuntos locales propios de Android 8.8.0, uno nuevo y otro proveniente de una actualización desde 8.6.0. Registrar paquete, versión de APK, canal y qué archivos aparecen. Incluir las variantes `.rij` si el cliente las genera y conservar cada conjunto original íntegro.
2. Repetir la captura cambiando una sola variable mediante el cliente oficial. Comparar las envolturas y el contenido de cada archivo y preferencia. Repetir con otro estado de cuenta para distinguir campos omitidos por estado de cambios de esquema.
3. Incorporar únicamente un adaptador de inspección y copia para las familias con repetición verificable. Probar archivos truncados, marcadores desconocidos, colisiones de reconocimiento y conservación de bytes, además de comparar salidas contra las muestras.
4. Antes de habilitar una edición o conversión, verificar la escritura y restauración en una copia de prueba con el mismo canal y compilación. Exigir consistencia entre archivos, preservación de miembros desconocidos y relectura del resultado mediante el cliente autorizado.

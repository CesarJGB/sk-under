# Fase 6.12 — Ingeniería inversa del guardado en la nube

Esta fase describe el agregado real de 8.8.0 y sus proyecciones locales sin
modificar la ruta de edición de gemas ya validada. El trabajo es de solo
lectura: no se añadieron controles de edición para otros recursos, no se
falsificaron compras ni recibos y no se publicaron cuentas, perfiles, capturas
ni valores privados.

## Resultado en una página

- El agregado de nube inspeccionado contiene 17 entradas superiores: 13
  secciones de estado, `maps`, dos identificadores y `serialzedVersion`. La
  correspondencia con los archivos locales se documenta en
  [inventario-archivos.md](inventario-archivos.md).
- Las fichas de pesca tienen un candidato claro de saldo, `gameData.fishChip`
  (`Int32`), pero **no se observó ningún saldo positivo ni una transacción
  legítima**. La autoridad local o remota del saldo sigue sin resolverse. No se
  confunde con `material_fish`, `cumulativeFishCount` ni con los chips de
  temporada. [fichas-de-pesca.md](fichas-de-pesca.md)
- Los 42 personajes, 105 habilidades y 802 skins del catálogo 8.8.0 se cruzan
  con `gameData`. La estructura está identificada; la semántica de los valores
  de `skinLock` y de los desbloqueos sigue siendo parcial.
  [personajes-skins-skills.md](personajes-skins-skills.md)
- Inventario, temporada, estadísticas y evolución comparten IDs de catálogo,
  pero se guardan en secciones distintas. La matriz de relaciones separa
  evidencia de hipótesis. [recursos.md](recursos.md) ·
  [dependencias.md](dependencias.md)
- El [registro de campos](../../save-research/field-registry.json) pasó de 43
  a 65 entradas, separa estructura de hipótesis y mantiene las fichas, skins,
  compras y entitlements en solo lectura.
- Se añadieron un analizador reutilizable y diez pruebas sintéticas. La suite
  completa terminó con 482 pruebas y las 33 pruebas de navegador siguieron
  aprobadas. La propuesta para 6.13 prioriza una transacción legítima de fichas
  y la validación de los estados de personaje sin habilitar escrituras nuevas.
  [propuesta-6.13.md](propuesta-6.13.md)

## Capas y método

| Capa | Muestra | Uso |
| --- | --- | --- |
| Agregado de nube | Copia auténtica de 8.8.0, 114.778 bytes | Forma que el servidor conserva y entrega. |
| Archivos locales 8.8.0 | Perfil auténtico del APK oficial, 18 archivos decodificados | Proyección local y comparación con la nube. |
| Archivos locales 8.6.0 | Nueve `.data` privados decodificados | Comparación histórica; no hay `game.data` ni preferencias. |
| Capturas Android 8.8.0.11 | Tars antes/después de acciones legítimas | Solo para cambios observados; no se publican. |
| Cliente estático | Metadata IL2CPP 8.8.0 | Nombres y firmas; no sustituye una prueba de comportamiento. |
| Catálogo | SKDFE fijado en `57b9b86335c080caca55e178c8409cb67658ccf6` | Nombres e índices; no demuestra posesión. |

Los niveles de evidencia son los del [registro de campos](../../save-research/field-registry.json):
E1 fuente comunitaria, E2 estructura propia, E3 acción controlada, E4
persistencia y consistencia. Una observación estructural no se presenta como
E3. Los valores de las capturas privadas no se copian a este repositorio.

## Herramientas

`tools/analyze_save.py` funciona sobre un agregado JSON/gzip, un archivo
`.data`/`.json` decodificado, un tar de captura o un directorio de archivos
locales. Reutiliza el decodificador y las claves del proyecto; no contiene
claves ni rutas privadas.

```bash
cd backend

# Inventario estructural sin valores
uv run --locked python ../docs/research/phase6-12/tools/analyze_save.py \
  inventory ../captura.tar --keys-env ~/.config/sk-under/phase3/cipher.env

# Comparación de dos capturas, con valores solo en la salida local
uv run --locked python ../docs/research/phase6-12/tools/analyze_save.py \
  compare ../antes.tar ../despues.tar --keys-env ~/.config/sk-under/phase3/cipher.env --values

# Fichas, personajes y rutas de una sección
uv run --locked python ../docs/research/phase6-12/tools/analyze_save.py fish ../partida.json
uv run --locked python ../docs/research/phase6-12/tools/analyze_save.py characters ../partida.json
uv run --locked python ../docs/research/phase6-12/tools/analyze_save.py fields ../partida.json --section gameData
```

La salida omite saldos, muestras y valores antes/después salvo con `--values`.
Los informes con valores son privados. La herramienta no escribe archivos ni
abre conexiones.

## Límites

No se realizó una compra de fichas de pesca ni una conversión de moneda. No se
probó una recuperación de nube con un saldo positivo de fichas. No se
verificaron las variantes regionales ni iOS. La muestra 8.6.0 no contiene
`game.data`, por lo que las rutas de nube de personajes y gemas no se pueden
trasladar sin más a esa versión.
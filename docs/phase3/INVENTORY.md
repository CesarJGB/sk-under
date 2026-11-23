# Inventario de la Fase 3

En el VPS se verificó la ruta indicada. El directorio padre tiene un espacio al final de su nombre. El conjunto contiene nueve archivos regulares con extensión `.data` y un sufijo local común. Se trabajó con copias temporales privadas de solo lectura. Los SHA-256 de los originales coincidieron con los de las copias antes y después de la verificación. La procedencia de una sola cuenta y de la versión 8.6.0 corresponde a la información facilitada con las muestras.

| Nombre base | Extensión | Bytes | Bytes al decodificar Base64 |
| --- | --- | ---: | ---: |
| `bp_data` | `.data` | 71 456 | 53 592 |
| `item_data` | `.data` | 52 172 | 39 128 |
| `misc_data` | `.data` | 748 | 560 |
| `monsrise_data` | `.data` | 556 | 416 |
| `pvp_data` | `.data` | 5 944 | 4 456 |
| `season_data` | `.data` | 69 248 | 51 936 |
| `statistic` | `.data` | 487 168 | 365 376 |
| `task` | `.data` | 25 080 | 18 808 |
| `weapon_evolution_data` | `.data` | 22 872 | 17 152 |

El inventario exacto con nombres completos y SHA-256 se conserva en `~/.config/sk-under/phase3/INVENTORY.md` con permisos `0600`. Los nombres de esta tabla identifican tipos de guardado.

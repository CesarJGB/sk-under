# Observaciones propias — fase 9.3

Comparación de solo lectura de estructuras de skins de arma y efectos de
eliminación. No se conservan credenciales, tokens, identificadores de cuenta ni
guardados completos. Los valores siguientes son recuentos y formas saneadas.

## Muestras

| Etiqueta | Plataforma | Perfil | `gameVersion` | `AppVersion` | Capa |
| --- | --- | --- | ---: | ---: | --- |
| A | Android | Avanzada | 2145 | ausente | Agregado de nube descodificado |
| B | Android | Nueva | 2155 | 80800 | Agregado de nube descodificado |
| C | iOS | Avanzada, vía editor externo | 2155 | 1531 | Documento descodificado de solo lectura |
| D | Android | Avanzada | 8.6.0 | — | Componentes locales descodificados |
| E | Android | Avanzada | 8.8.0 | 80800 | Agregado local/Nube Global |

## Skins de arma

| Observación | A | B | C | D | E |
| --- | ---: | ---: | ---: | ---: | ---: |
| Armas con registro | 1 | 2 | 180 | 167 | 0 |
| Skins registradas | 1 | 2 | 192 | 177 | 0 |
| Armas con 2 skins | 0 | 0 | 10 | 10 | 0 |
| Armas con 3 skins | 0 | 0 | 1 | 1 | 0 |
| `CurrentSkinIndex` 0 | 1 | 1 | 0 | 2 | — |
| `CurrentSkinIndex` 1 | 0 | 1 | 180 | 165 | — |

Forma del registro: `{Name, Level, CurrentSkinIndex, UnlockedSkins}`. En D,
`weapon_405` y `weapon_415` tienen `CurrentSkinIndex: 0` y
`UnlockedSkins: []`; esto demuestra que un registro puede existir sin skins
registradas, pero no aclara si 0 es “sin skin” o “skin por defecto”.

Los identificadores de D pertenecen al catálogo de 192; faltan 15. C contiene
los 192. La muestra E tiene `weapons: {}` y conserva las claves opcionales
`favorWeapons`, `lastOpenMachineHistoryStr0` y `blindBoxOpenCount0` según la
versión.

## Efectos de eliminación

| Observación | A | B | C | D | E |
| --- | --- | --- | --- | --- | --- |
| `miscData` presente | No | Sí | Sí | Sí | Sí |
| ID desbloqueados | — | 0, 1 | 0–6 | 0–10 | 0, 1 |
| Pares de escena | — | 1→1, 0→1 | 1→1, 0→3 | 1→0, 0→0 | 1→0, 0→0 |
| ID desconocidos | — | — | — | 9, 10 | — |

La forma observada es una lista de enteros para los desbloqueos y una lista de
pares `{Key, Value}` para la selección. Las claves 0 y 1 aparecen en todas las
muestras con `miscData`; no se ha demostrado su correspondencia con modos de
juego.

## Catálogos

- Skins: 192 elementos, 180 armas, 81 con una segunda skin y una con tercera.
- Efectos: 9 elementos evidenciados (0–8). Nombres disponibles para 0–3; 4–8
  conservan nombre nulo; 9–10 se excluyen por falta de nombre y recurso.

## Evidencia

- Existencia y tipo de las rutas: **E2** en muestras propias.
- Relación con los catálogos: **E2** observada.
- Semántica de `CurrentSkinIndex`, de las claves de escena y aceptación del
  cliente: **H**.
- Persistencia tras subida y reinicio: **H** hasta la prueba física.

No se elevan niveles por la presencia en catálogos ni por la comparación con
iOS.
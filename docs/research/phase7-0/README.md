# Fase 7.0 — Save Knowledge Engine

## Resumen ejecutivo

La Fase 7.0 cambia la metodología del proyecto. En lugar de investigar cada
función del editor desde cero, SK-Under dispone ahora de una base de
conocimiento propia, estructurada y consultable sobre los guardados de Soul
Knight. El resultado no añade controles de edición nuevos: construye la
infraestructura para investigar y validar muchas categorías con evidencia,
procedencia y dependencias explícitas.

El motor se apoya en tres pilares:

1. **Registro canónico de campos**: 616 registros con tipo, rutas, estructura,
   valores observados, límites, dependencias, fuentes, evidencia por aspecto,
   política de edición, preguntas abiertas y experimentos.
2. **Catálogos normalizados**: 24 familias y 4.286 elementos con identificadores
   estables, nombres en inglés/español/chino cuando existen, relaciones y
   referencias al guardado.
3. **Herramientas reutilizables**: generación determinista, búsqueda, comparación
   de versiones, validación e informes, sin autenticación ni acceso a datos
   privados.

La compatibilidad histórica se analizó entre 8.6.0, 8.7.0 y 8.8.0. Las
estructuras estables se conservan como candidatas; las diferencias se registran
sin convertir una coincidencia estructural en una confirmación semántica.

## Fuentes investigadas

| Fuente | Versión / commit | Uso | Límite |
| --- | --- | --- | --- |
| SKDFE `main` | `57b9b86335c080caca55e178c8409cb67658ccf6` (8.8.0) | Catálogos, traducciones, configuración, historia | Sin archivo de licencia; no se redistribuye contenido crudo |
| SKDFE 8.7.0 | `8cfa5d5` | Diferencias de versión | Catálogos históricos, no guardados |
| SKDFE 8.6.0 | `e088a67` | Diferencias de versión | Catálogos históricos, no guardados |
| `data.json` de SKDFE | 8.8.0 | Forma de guardado y familias observadas | Muestra externa con forma de guardado; E1, no observación propia |
| `weapon_skins.json` | 8.8.0 | Estructura de ejemplo | Generado para la wiki; no es un guardado auténtico |
| Metadata IL2CPP 8.8.0 | `docs/research/phase5-5/metadata-880-inventory.json` | 20 tipos y 691 campos declarados | Declara tipos; no demuestra uso ni semántica |
| Diff 8.6/8.8 | `docs/research/phase5-5/schema-diff-860-880.json` | Claves comunes y añadidas | Solo secciones con muestra local 8.6 |
| Registro histórico | `docs/save-research/field-registry.json` | 66 campos y evidencia acumulada | Se conserva intacto |
| Fases 6.12–6.20 | `docs/research/phase6-*` | Evidencia E2/E3/E4, dependencias y límites | Resultados saneados; los guardados siguen privados |
| Discord | `docs/save-research/community-reference.txt` | Patrones PlayerPrefs y pistas 8.5.0 | E1, sin verificación propia |
| Guardado propio 8.8.0 | Agregado de 114.778 bytes / 17 entradas | Estructura observada | No se publica contenido ni identificadores |

SKDFE tiene 149 commits, una sola rama (`main`) y ninguna etiqueta. Se
revisaron versiones anteriores y archivos eliminados (`itemlist.json`,
`weaponlist.json`, `weapons.json`, `weapon.aznoobnam`, `exportskdata.yml`).
Los archivos históricos contienen mapas antiguos de identificadores y nombres;
no se usaron para completar huecos actuales.

## Cobertura

### Archivos y clasificación

Se clasificaron 20 archivos o familias de SKDFE y 5 archivos históricos
eliminados. La clasificación completa está en
[`knowledge/evidence/skdfe-file-classification.json`](../../../knowledge/evidence/skdfe-file-classification.json).

| Clase | Ejemplos | Qué puede demostrar |
| --- | --- | --- |
| Catálogo estático | `char_code_name.json`, `pet_code_name.json`, `weapon_full.json` | Existencia e identificadores |
| Configuración exportada | `weapons.decrypted.csv`, `items.decrypted.csv`, `enemies.decrypted.csv` | Tipos, recetas, drops y campos declarados |
| Derivado | `needed_data.json`, `item.json`, `enemy.json`, `Allinfo.txt` | Agrupaciones y nombres; no posesión |
| Forma de guardado | `data.json`, `weapon_skins.json` | Estructura candidata; no guardado auténtico |
| Wiki | `wiki.html`, `Allinfo.txt` | Presentación derivada; no fuente primaria |
| Pipeline | `skdata.py`, `skdfe/*` | Cómo se generan los datos y sus límites |

### Campos

| Métrica | Antes (Fase 6.x) | Después (Fase 7.0) |
| --- | ---: | ---: |
| Campos registrados | 66 | **616** |
| Campos históricos conservados | 66 | 66 |
| Campos declarados nuevos | 0 | 550 |
| Categorías | 10 | **18** |
| E1 | 1 | 194 |
| E2 | 54 | 411 |
| E3 | 5 | 5 |
| E4 | 6 | 6 |
| H | 0 | 0 |
| Dependencias registradas | Dispersas en Markdown | **26 estructuradas** |
| Fuentes con procedencia | Parcial | **15** |

Los 550 campos nuevos proceden de metadata estática y del diff 8.6/8.8. Su
existencia y tipo son E1; 411 registros alcanzan E2 por estructura observada.
La semántica solo se eleva cuando existe evidencia controlada: 581 campos
permanecen en H, 24 en E2, 5 en E3 y 6 en E4.

Distribución por categoría: Estadísticas 169, Inventario 107, Temporada 78,
Configuración 45, Escape 39, Progreso y acceso 33, Tienda y compras 26,
Monster Rise 21, Sobre de guardado 18, Datos varios 17, Tareas 14, Fichas de
pesca 11, PvP 10, Evolución de armas 9, Pase de batalla 9, Gemas 5, Vestíbulo 4
y Preferencia interna 1.

### Catálogos

| Familia | Elementos | Con nombre EN | Observación |
| --- | ---: | ---: | --- |
| characters | 42 | 42 | Códigos, 105 habilidades, 802 skins |
| character_skills | 105 | 105 | Slots por personaje |
| character_skins | 802 | 801 | Una skin sin traducción |
| pets | 58 | 56 | `Hide` sin nombre; `Fish Chip King` sin código |
| pet_skills | 57 | 56 | Descripciones EN/ES |
| weapons | 1.081 | 963 | 995 visibles + 86 variantes + 9 anillos/transformaciones |
| weapon_skins | 192 | 192 | Índices por arma |
| materials | 343 | 154 | Unión de dos fuentes |
| seeds / plants | 47 / 47 | 47 / 47 | Semilla y planta relacionadas |
| blueprints | 265 | 4 | Muchas claves sin nombre localizado |
| enemies / bosses | 593 / 74 | 257 / 61 | Drops declarados |
| lobby | 49 | 28 | Muebles, desbloqueos, salas y jardín |
| tokens / special_items / vouchers | 19 / 29 / 136 | 1 / 8 / 0 | Vales desde muestra externa |
| jewelry / chips / mounts / followers | 15 / 18 / 4 / 6 | 0 / 18 / 4 / 6 | Sistemas complementarios |
| trophies / season_content / collectibles | 212 / 10 / 82 | 0 / 0 / 0 | Claves observadas, sin nombres |

La cobertura de nombres es deliberadamente honesta: no se inventan traducciones
para blueprints, trofeos, vales o coleccionables. El catálogo conserva la clave,
la familia y la relación; la ausencia de nombre queda explícita.

### Traducciones

`knowledge/translations/name-index.json` contiene 8.526 entradas en inglés,
español y chino simplificado. Se generan solo para elementos catalogados; no se
redistribuye `I2language.csv` completo.

### Versiones

| Familia | 8.6.0 | 8.7.0 | 8.8.0 | 8.6→8.8 |
| --- | ---: | ---: | ---: | --- |
| Personajes | 42 | 42 | 42 | Sin cambios |
| Habilidades | 103 | 104 | 105 | +2 |
| Skins de personaje | 782 | 792 | 802 | +20 |
| Mascotas | 56 | 57 | 57 | +1 |
| Armas | 982 | 989 | 995 | +13 |
| Skins de arma | 177 | 185 | 192 | +15 |
| Materiales filtrados | 130 | 130 | 130 | Sin cambios |
| Planos | 259 | 262 | 265 | +6 |
| Enemigos | 592 | 592 | 593 | +1 |

No se observaron eliminaciones en estas familias entre 8.6.0 y 8.8.0. La
estabilidad estructural no se interpreta como compatibilidad semántica.

## Relaciones documentadas

`knowledge/dependencies/dependencies.json` contiene 26 relaciones: 3
confirmadas, 17 observadas, 4 hipótesis y 2 negativas. Las más relevantes:

- `gameData.gems = gameData.lastGems + gameData.varGems` (E4); editar un solo
  término puede romper la conciliación.
- `gameData.fishChip` e `itemData.materials.material_fish` deben mantenerse
  coherentes (E4 en el alcance probado).
- `heroUnlock`, `heroSkillUnlock`, `skinLock` y `heroLevel` son proyecciones
  locales con contrapartidas XML; su persistencia posterior a un re-guardado no
  está demostrada en todos los casos.
- `petUnlock` se relaciona con el catálogo de mascotas, no con una prueba de
  posesión.
- `weaponEvolutionData.weapons` se relaciona con el catálogo de armas;
  `UnlockedSkins` y `CurrentSkinIndex` son estados distintos.
- Los planos de evolución y fusión conectan armas y materiales; los drops de
  enemigos conectan enemigos e ítems.
- `seasonData.chips` no es lo mismo que los chips de Monster Rise.
- Los derechos de compra y recibos dependen de servicios externos y permanecen
  fuera del alcance de edición.

## Contradicciones y decisiones

1. **`data.json` no es un guardado auténtico.** Se clasifica como muestra
   externa con forma de guardado, evidencia E1. No se usa para demostrar
   posesión ni persistencia.
2. **`weapon_skins.json` es una estructura generada.** Se usa para entender la
   forma, no como estado real de una cuenta.
3. **La metadata declara más campos de los observados.** 550 registros nuevos
   son E1; solo 411 alcanzan E2 por estructura observada. No se eleva su
   semántica sin experimento.
4. **Los catálogos no prueban posesión.** Un identificador en `weapons` o
   `pets` solo resuelve nombres y relaciones.
5. **Hay claves sin nombre.** `Hide`, 261 blueprints, trofeos y vales carecen de
   traducción localizada. Se conservan como `null` y se documentan.
6. **Las armas visibles y las filas de configuración no son equivalentes.**
   23 armas de `weapon_full.json` no tienen fila CSV y 86 filas CSV no están en
   el catálogo visible. El campo `config_only` las separa.
7. **La compatibilidad estructural no es semántica.** Rutas y tipos estables
   entre 8.6 y 8.8 siguen siendo candidatos, no confirmaciones.

## Limitaciones

- SKDFE no incluye licencia; solo se conservan hechos normalizados y
  procedencia, no contenido crudo.
- No se dispone de una muestra auténtica 8.6.0 de `gameData` para comparar
  todas las secciones.
- La metadata IL2CPP no confirma uso en partidas reales.
- La referencia de Discord es E1 y procede de 8.5.0.
- No se ejecutaron nuevas escrituras remotas ni pruebas con cuentas reales en
  esta fase.
- La cobertura de nombres es parcial y no equivale a cobertura funcional.
- Los campos declarados sin observación propia no tienen valores iniciales ni
  límites funcionales confirmados.

Detalle: [`knowledge/evidence/limitations.md`](../../../knowledge/evidence/limitations.md).

## Herramientas y ejemplos

```bash
python3 knowledge/tools/search_knowledge.py "Bastón Increíble" --catalog weapons
python3 knowledge/tools/search_knowledge.py --field gameData.fishChip --json
python3 knowledge/tools/compare_versions.py --family weapons --from 8.6.0 --to 8.8.0
python3 knowledge/tools/generate_report.py --family pets
python3 knowledge/tools/validate_knowledge.py --write-manifest
python3 knowledge/tools/build_catalog.py --skdfe /ruta/a/skdfe --check
```

Resultados de ejemplo:

- `weapons` 8.6.0 → 8.8.0: 982 → 995, 13 añadidas, 0 eliminadas.
- `search_knowledge.py --field gameData.fishChip` devuelve el registro, su
  política de solo lectura y sus dependencias.
- `validate_knowledge.py` resume 24 catálogos, 4.286 elementos, 616 campos, 26
  dependencias, 15 fuentes y 8.526 traducciones.

## Pruebas

Se añadieron 21 pruebas en `backend/tests/test_knowledge_*.py`:

- esquemas de catálogos, campos, dependencias, fuentes y manifiesto;
- generación determinista con una fixture sintética de SKDFE;
- normalización de identificadores;
- integridad, duplicados y referencias entre catálogos;
- proyección exacta del registro histórico de 66 campos;
- consistencia con el catálogo de personajes del backend;
- búsqueda, comparación de versiones e informes;
- fuentes existentes, niveles de evidencia y ausencia de datos sensibles;
- coherencia de snapshots y diferencias de versión.

Las 21 pruebas de conocimiento pasan. La fase también debe superar la suite
completa del backend, la compilación del frontend y las pruebas de navegador
antes de publicarse.

## Datos nuevos y datos reorganizados

- **Reorganizados**: los 66 campos históricos, sus dependencias y los
  catálogos de personajes ya usados por el backend. Se conservan sin cambios y
  se proyectan de forma determinista.
- **Nuevos**: 550 campos declarados, 24 catálogos normalizados, 8.526 entradas
  de traducción, 26 relaciones estructuradas, 3 versiones comparadas y 15
  fuentes con procedencia.
- **No nuevos**: no se añadieron controles de edición, no se modificó el
  protocolo de autenticación, descarga o subida, y no se escribió en cuentas
  reales.

## Oportunidades para la siguiente fase

El informe detallado está en [oportunidades.md](oportunidades.md). Los grupos
prioritarios son inventario, mascotas, niveles de personaje y armas. Inventario
y mascotas tienen la mejor combinación de catálogo, estructura y dependencias;
los niveles de personaje requieren una prueba de persistencia; las armas
necesitan separar nivel, forja, evolución y skins antes de editar.

La siguiente fase puede partir de esta base para diseñar experimentos
controlados, sin repetir el inventario de fuentes ni la investigación
estructural.
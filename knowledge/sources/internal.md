# Fuentes internas de SK-Under

## Registro canónico de campos

`docs/save-research/field-registry.json` contiene 66 campos investigados hasta la fase
6.20. Es la base congelada que el backend valida y que el Save Knowledge Engine proyecta
de forma determinista.

- Niveles globales: 54 E2, 6 E4, 5 E3 y 1 E1.
- Categorías: fichas de pesca (11), inventario (10), progreso y acceso (9), evolución de
  armas (8), pase de batalla (7), temporada (6), estadísticas (5), gemas (5), vestíbulo
  (4) y preferencia interna (1).
- Los 66 registros se conservan sin cambios en `knowledge/fields/fields.json` como
  `legacy_record`. `build_fields.py --check` compara la proyección con el archivo
  original byte a byte.

El registro ampliado añade campos declarados por metadata y conserva la separación entre
existencia, tipo, semántica, compatibilidad, relaciones y persistencia. No se elevaron
niveles de evidencia.

## Documentos revisados

| Documento | Aporte |
| --- | --- |
| `docs/save-research/README.md` | Resumen de fases 6.12–6.20 y políticas de solo lectura. |
| `docs/save-research/community-reference.txt` | Referencia de Discord sobre 8.5.0 y patrones de PlayerPrefs. |
| `docs/save-research/external-sources.md` | Commit de SKDFE, recuentos y condiciones de uso. |
| `docs/save-research/save-file-mapping.md` | Rutas locales/nube, inventario, estadísticas, evolución, temporada y pase. |
| `docs/save-research/cross-file-dependencies.md` | Dependencias confirmadas y pendientes entre archivos. |
| `docs/save-research/version-compatibility.md` | Versiones analizadas y límites de compatibilidad. |
| `docs/save-research/validation-results.md` | Resultados de validación de fases previas. |
| `docs/save-research/playerprefs-research.md` | Patrones de PlayerPrefs y límites de interpretación. |
| `docs/research/phase5-5/metadata-880-inventory.json` | 20 tipos y 691 campos declarados; 14 tipos de guardado seleccionados. |
| `docs/research/phase5-5/schema-diff-860-880.json` | Claves comunes y añadidas entre 8.6.0 y 8.8.0. |
| `docs/research/phase6-12/` | Inventario del agregado, personajes/skins/habilidades, recursos y evidencias. |
| `docs/research/phase6-16/` | Confirmación E4 de `fishChip` + `material_fish`. |
| `docs/research/phase6-17/` | `heroUnlock` E3. |
| `docs/research/phase6-18/` | `heroSkillUnlock` E3. |
| `docs/research/phase6-19/` | `skinLock` E3. |
| `docs/research/phase6-20/` | `cumulativeFishCount` y límites de la tarjeta de resurrección. |
| `backend/app/catalogs/characters-880.json` | Proyección backend de 42/105/802. |

## Hechos internos reutilizados

- El agregado de nube 8.8.0 observado tiene 17 entradas superiores, 13 secciones de
  estado y 114.778 bytes en la muestra documentada.
- `gameData` tiene 38 claves observadas; `itemData`, 78; `statisticData`, 160;
  `seasonData`, 67.
- `heroUnlock`, `heroLevel`, `heroSkill` y `heroSkillUnlock` cubren 42 códigos.
  `skinLock` contiene 42 listas y 802 entradas.
- `heroSkillUnlock` tiene 105 entradas: 42 con `Key` 0 verdadera, 35 con `Key` 1 falsa y
  28 con `Key` 2 falsa en la muestra.
- `petUnlock` contiene 58 booleanos.
- `gems = lastGems + varGems` se verificó en la rama de consumo de 8.8.0.
- `fishChip` y `material_fish` se editaron juntos y persistieron en Android físico.
- `heroUnlock`, `heroSkillUnlock` y `skinLock` tienen semántica E3 por modificación
  controlada; la persistencia tras volver a guardar no está cerrada en todos los casos.
- `cumulativeFishCount` se identificó estáticamente como contador de peces acumulados, no
  como saldo de fichas.
- La tarjeta de resurrección no se considera editable: coexisten un entero de PlayerPrefs,
  un objeto de catálogo y un booleano de nube cuya relación no está probada.

## Contradicciones y vacíos detectados

- `weapon_skins.json` parece un guardado, pero es una representación generada por SKDFE.
  No se usa como evidencia de posesión.
- `data.json` contiene estados avanzados plausibles, pero no se ha demostrado que proceda
  de una cuenta real. Se clasifica como E1.
- El nombre de `furniture_fish_chips` sugiere un espejo de `fishChip`; no hay evidencia.
- Los valores negativos y grandes de `skinLock` no tienen semántica confirmada.
- La relación entre `battlePassSaveData.seasonData[].Value.*` y los archivos locales
  `bp_data` está observada, pero no cerrada.
- `OriginalWeapon`, `cumulativeFishCount` y varias claves de temporada siguen necesitando
  experimentos controlados.

## Política de privacidad

Los guardados originales, recibos, identificadores de cuenta y estados de pago no se
versionan. El repositorio solo contiene resultados saneados, fixtures sintéticos y
referencias bibliográficas. Esta fase no realizó escrituras remotas.
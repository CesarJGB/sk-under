# Validación privada de archivos reales

**Se reconstruyeron los nueve archivos 8.6.0 desde el árbol JSON en Python y se compararon los bytes cifrados completos con los originales.** Cuatro coincidieron al emitir JSON compacto, cuatro con dos espacios de sangría y LF, y uno requirió conservar la sangría por línea. La prueba anterior de exportación intacta también pasó para los nueve. Los archivos corresponden a la cuenta y versión indicadas por el titular. El marcador interno de un subsistema puede tener otra numeración.

| Familia local 8.6.0 | Bytes originales | Bytes JSON UTF-8 | Miembros raíz | Campo reconocido, sin valores de cuenta | Serialización que reprodujo los bytes |
| --- | ---: | ---: | ---: | --- | --- |
| bp_data | 71456 | 53587 | 3 | seasonData | Dos espacios |
| item_data | 52172 | 39120 | 77 | materials | Dos espacios |
| misc_data | 748 | 555 | 17 | unlockedKillEffectIds | Compacta |
| monsrise_data | 556 | 412 | 18 | maxClearLevel | Compacta |
| pvp_data | 5944 | 4451 | 10 | pvpTaskData | Dos espacios |
| season_data | 69248 | 51930 | 70 | gainedCoinInSeason | Sangría original por línea |
| statistic | 487168 | 365368 | 157 | StatisticsData | Dos espacios |
| task | 25080 | 18807 | 12 | NewTaskData | Compacta |
| weapon_evolution_data | 22872 | 17149 | 4 | weapons | Compacta |

Para cada fila se recalculó SHA-256 y se verificó la pareja nombre–huella contra el inventario privado de Fase 3. El [inventario público](../../phase3/INVENTORY.md) permite comprobar los tamaños y localizar el manifiesto privado. Se verificó Base64 canónico, longitud de bloques múltiplo de ocho, padding PKCS#7, JSON y esquema de familia. La envoltura comienza directamente con Base64. `statistic` usa la variante de clave ya configurada. Ningún archivo contiene por sí solo el directorio de secciones de un agregado remoto. [Códec existente](../../../backend/app/parsers/real_save.py) · [Esquemas](../../phase3/FORMAT_ANALYSIS.md)

El ensayo reserializó **todo** el árbol conservando el orden de lectura y los campos desconocidos, cifró con el códec local y volvió a codificar en Base64. En `season_data` se generó JSON de dos espacios y se sustituyó únicamente la sangría de cada línea por la anchura de la línea original antes de cifrar. Los 69 248 bytes coincidieron. Esto demuestra una condición concreta para reproducir esa muestra intacta. Una edición que cambie el número de líneas requiere otra validación. El editor sigue exportando el original en el modo de solo lectura.

## Repetición privada

Desde `backend/`, con el entorno Python del proyecto y las tres variables apuntando a las referencias autorizadas del operador. Elegir únicamente los nueve archivos de esa cuenta. El informe emite familias, conteos y coincidencias. El original solo se abre para lectura.

```bash
PYTHONPATH=. uv run --locked python ../docs/research/phase5-3/check-local-reference.py \
  --cipher-env "$SK_PHASE4_CIPHER_ENV_FILE" --inventory "$PRIVATE_INVENTORY" \
  "$SK_PHASE4_SAMPLES_DIR"/*_111_.data
uv run --locked pytest -q tests/test_private_save_roundtrip.py
```

En 8.8.0 se localizaron el APK, sus ELF, metadatos IL2CPP, el AVD de 5.2 y su diagnóstico de arranque. Se verificaron los SHA-256 de ambas bibliotecas extraídas frente a las entradas del APK. La procedencia y los puntos de inspección se documentan en el [estudio del agente](fetch-comparison.md). No apareció una exportación propia de Data, del agregado ni de subsistemas 8.8.0 entre los artefactos de laboratorio accesibles. El [sondeo tras restaurar](../phase5-experimental/archivos.md) había obtenido cero bytes con el mecanismo de backup del sistema. El bloqueo está antes de interpretar la primera copia remota. Faltan bytes autorizados y la revisión correspondiente para compararla con el cliente.

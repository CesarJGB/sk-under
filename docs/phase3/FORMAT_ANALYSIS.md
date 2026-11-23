# Análisis técnico de los archivos .data

Los nueve archivos siguen la secuencia Base64 estándar canónico → DES-CBC → relleno PKCS#7 de bloque de 8 bytes → objeto JSON UTF-8. Ocho comparten la clave general y `statistic` requiere la variante estadística. Se verificó el mismo IV en ambos casos. La prueba decisiva fue obtener nueve objetos coherentes y recuperar los nueve archivos originales, byte por byte, al repetir el proceso en orden inverso sobre el texto descifrado exacto. La implementación usa PyCryptodome para la primitiva histórica. [Referencia de DES](https://www.pycryptodome.org/src/cipher/des) · [Utilidades de relleno](https://www.pycryptodome.org/src/util/util#module-Crypto.Util.Padding)

## Envoltura y análisis binario

- Los nueve archivos son ASCII sin saltos de línea. Decodificarlos y recodificarlos como Base64 estándar reproduce la envoltura exacta.
- Los tamaños binarios son múltiplos de 8. Cuatro archivos dejan residuo 8 al dividir el tamaño binario por 16. No se repitieron bloques alineados de 8 bytes dentro de un archivo o entre archivos de este conjunto.
- Se buscaron encabezados GZIP, ZIP, XZ, Zstandard, BZIP2 y SQLite, y BOM UTF-8. Ninguno coincidió al inicio del binario decodificado. La prueba de zlib tampoco produjo un flujo completo. El descifrado entrega directamente JSON, sin una capa de compresión entre el cifrado y la serialización.
- CRC32 y Adler-32 del resto del binario no coincidieron con valores contiguos de 4 bytes al inicio o final, en ambos órdenes de bytes. El recifrado exacto explica el binario completo sin un tráiler exterior independiente. El análisis deja abiertos controles semánticos internos y verificaciones del cliente.
- La forma Base64 y el tamaño de bloques sirven para descartar entradas. El contenido descifrado aporta el reconocimiento. La entropía y la ausencia de repeticiones, por sí solas, también serían compatibles con otros formatos.

| Tipo | Entropía Base64 | Entropía binaria | Bytes JSON |
| --- | ---: | ---: | ---: |
| `bp_data` | 5,9994 | 7,9964 | 53 587 |
| `item_data` | 5,9994 | 7,9948 | 39 120 |
| `misc_data` | 5,9139 | 7,6001 | 555 |
| `monsrise_data` | 5,9009 | 7,5157 | 412 |
| `pvp_data` | 5,9945 | 7,9603 | 4 451 |
| `season_data` | 5,9992 | 7,9969 | 51 930 |
| `statistic` | 5,9999 | 7,9996 | 365 368 |
| `task` | 5,9992 | 7,9913 | 18 807 |
| `weapon_evolution_data` | 5,9985 | 7,9887 | 17 149 |

La entropía se calculó por símbolo usando las frecuencias de cada archivo. La cifra binaria de las muestras más cortas refleja también el tamaño de la muestra.

## Estructura y versiones

Los nueve documentos son objetos JSON diferenciables por sus claves y tipos. Hay mapas con claves dinámicas, listas de registros, listas con pares `Key` y `Value`, y campos que contienen texto con su propia estructura potencial. Se conservan los valores anidados y las colecciones desconocidas sin interpretarlos. Los nombres sugieren vínculos entre objetos, armas, logros, tareas y recursos, pero el conjunto de una sola captura no establece integridad referencial ni permite reconstruir un guardado global.

`item_data.AppVersion` contiene el entero `80300`, pese a que la muestra se atribuye a 8.6.0. `monsrise_data.version` contiene `1`. Estos valores se tratan como marcadores internos de las estructuras observadas. Los otros siete tipos carecen de un marcador de versión fiable establecido. El tipo se identifica por contenido, sin usar nombre, sufijo, tamaño específico ni hash de la muestra.

## Alcance de la integridad

El motor verifica relleno, UTF-8, sintaxis JSON, unicidad de claves, esquema suficiente para reconocer el tipo y marcadores internos donde existen. Para una exportación, exige igualdad byte por byte con la entrada y vuelve a identificar y leer el resultado. El SHA-256 permite comparar copias. DES-CBC carece de autenticación intrínseca, por lo que una alteración que preserve el relleno y una estructura admitida podría superar el reconocimiento. La aceptación de una modificación dentro del juego permanece sin verificar.

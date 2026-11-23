# Referencia real 8.8.0

> **Actualización Fase 5.6 (2026-11-23):** esta fase obtuvo una referencia
> local auténtica 8.8.0, decodificó `game.data` y confirmó gzip en el cuerpo de
> `ZipHelper.Decompress`. El agregado de nube y la aceptación por el cliente
> siguen pendientes. Véase [Fase 5.6](../phase5-6/README.md).


**No se obtuvo una muestra real de 8.8.0.** El entorno contiene el APK oficial
8.8.0 y nueve `.data` de 8.6.0; no hay un `CloudSaveGameData` de 8.8.0, ni un
RPC real, ni una exportación de cuenta. El fixture
`cloud-save-880-sintetico.json` es sintético y así se etiqueta.

## 1. Búsqueda realizada

| Fuente | Resultado |
| --- | --- |
| APK 8.8.0 | `54bb332b…`; no contiene un archivo de partida. |
| `assets/bin/Data/Managed/Metadata/global-metadata.dat` | Metadata, no partida. |
| Nueve `.data` del entorno | 8.6.0; caches por subsistema. |
| Directorio privado de la app | No accesible sin el cliente/dispositivo. |
| Capturas de red | Solo contadores; sin cuerpo RPC. |
| Fixture 8.8.0 | Sintético; declarado. |

No se encontró una muestra auténtica. No se inventan capturas, hashes ni
respuestas del proveedor.

## 2. Archivo exacto que hace falta

Se necesita **una** de estas entradas:

1. un `CloudSaveGameData` de 8.8.0 en JSON UTF-8, crudo o gzip, producido por
   una restauración/exportación oficial del titular;
2. un sobre RPC 8.8.0 completo (`00 00 00 80` + cuerpo) con el texto/estructura
   que el cliente obtuvo;
3. una copia entregada por soporte, en el formato que el proveedor pueda dar.

No sirve como referencia 8.8.0:

- un `.data` local de 8.6.0;
- el fixture sintético;
- el `global-metadata.dat`;
- un archivo editado por nosotros.

## 3. Procedimiento de incorporación

1. **No** subir la muestra al repositorio.
2. Guardarla fuera del checkout, con permisos restringidos.
3. Registrar procedencia: cuenta (privada), canal, versión, fecha, método
   oficial usado y si hubo restauración.
4. Calcular tamaño y SHA-256 **antes** de abrirla.
5. Ejecutar el informe estructural:

   ```bash
   cd backend
   PYTHONPATH=. uv run --locked python ../docs/research/phase5-5/tools/reference_report.py \
     /ruta/privada/muestra --rpc-gzip
   ```

6. Verificar que el SHA-256 y el tamaño del informe coinciden con los
   declarados.
7. Comparar `serialzedVersion`, secciones presentes/nulas/ausentes y campos
   desconocidos con [`metadata-880-inventory.json`](metadata-880-inventory.json).
8. Conservar el original sin modificar; trabajar solo sobre copias.
9. Documentar la comparación sin publicar identidad, valores ni huellas de la
   cuenta.

## 4. Criterios de aceptación

Una muestra se considerará referencia 8.8.0 si:

- su procedencia es el titular o una función oficial;
- el SHA-256 y el tamaño se registran;
- el formato se detecta como JSON, gzip o RPC y el parseo termina;
- la raíz contiene `serialzedVersion`, identidad y `gameData`;
- las secciones se clasifican como presentes/nulas/ausentes;
- el original se conserva intacto.

No se considerará aceptada por el cliente solo por parsear. Eso exige una
prueba de restauración autorizada en el cliente oficial.

## 5. Estado actual

| Elemento | Estado |
| --- | --- |
| APK 8.8.0 identificado | Sí |
| Metadata 8.8.0 descifrada e inventariada | Sí |
| Agregado real 8.8.0 | **No** |
| RPC real 8.8.0 | **No** |
| Compatibilidad 8.8.0 declarada | **No** |

La herramienta de validación está lista; la muestra sigue pendiente.

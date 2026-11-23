# Laboratorio de edición y validación

**Resultado: el laboratorio modifica una copia sintética, conserva campos
desconocidos, respeta tipos y números grandes, reabre el resultado y emite un
informe semántico y binario.** No escribe el original y no envía nada a un
servicio remoto.

## 1. Garantías

| Garantía | Implementación |
| --- | --- |
| No sobrescribir el original | El laboratorio recibe bytes y nunca abre una ruta de entrada en escritura. |
| Copia de seguridad | La CLI crea `.bak` si el destino existe y se usa `--force`. |
| Campos desconocidos | Se conservan tal cual; solo se editan secciones reconocidas. |
| Tipos | `bool`/`int`/`float`/`str`/`None`/lista/objeto se comparan antes de asignar. |
| Precisión numérica | Los enteros se serializan como enteros Python; no se convierten a `float`. |
| Cambios ajenos | El informe compara hojas y rechaza rutas no solicitadas. |
| Reapertura | El resultado se vuelve a parsear y se compara con el documento de trabajo. |
| Sin red | El módulo no importa sockets ni clientes HTTP. |

## 2. API

`backend/app/cloud/lab.py`:

```python
from app.cloud.lab import SaveLab

lab = SaveLab.open(payload)          # JSON o gzip
lab.set("gameData.gems", 10)         # ruta existente y tipo compatible
report = lab.report()                # no escribe nada
print(report.output_data)            # bytes de la copia
print(report.as_dict())              # cambios, diff binario, hashes
```

`SaveLab.set` rechaza:

- rutas inexistentes;
- índices fuera de rango;
- secciones superiores desconocidas;
- cambios de tipo (incluido `int` → `bool`).

`SaveLab.report` devuelve:

- `changes`: ruta, valor anterior y nuevo;
- `binary`: tamaños, primer byte distinto, prefijo/sufijo común, bytes
  cambiados y SHA-256;
- `unknown_fields_preserved`;
- `roundtrip`;
- `output_size`, `output_sha256`.

## 3. CLI

Desde `backend/`:

```bash
PYTHONPATH=. uv run --locked python ../docs/research/phase5-5/tools/save_lab.py \
  --input /ruta/copia.json \
  --set gameData.gems=10 \
  --set 'itemData.materials={"1":5}' \
  --output /ruta/copia.edit.json \
  --report /ruta/informe.json
```

- Si el destino existe, exige `--force` y crea `destino.bak`.
- `--dry-run` calcula el informe sin escribir.
- `--encoding same|json|gzip` elige la salida.
- La entrada nunca se modifica.

## 4. Pruebas

`backend/tests/test_save_lab.py` cubre:

- edición de un campo y conservación de los demás;
- campos desconocidos y entero `9007199254740993`;
- rechazo de tipos y de rutas;
- entrada/salida gzip;
- copia sin cambios que devuelve los bytes originales;
- entrada vacía, JSON truncado y raíz incompleta;
- escritura sin sobrescritura y con `--force`;
- diff binario;
- rutas con listas.

Comando:

```bash
cd backend
uv run --locked pytest -q tests/test_save_lab.py
```

## 5. Límites

- El serializador usa JSON compacto; el diff binario incluye el cambio de
  formato, no solo el valor editado. El diff **semántico** es el que decide si
  se tocó un campo ajeno.
- No se ha probado la aceptación por Soul Knight.
- No se editan campos nuevos que no existan; el laboratorio no inventa claves.
- No se editan arrays completos si no se conoce su contrato; solo valores
  existentes.
- No se ejecuta `FixData` ni se simula la migración 8.6.0 → 8.8.0.

## 6. Próximo paso

Con una referencia 8.8.0 real:

1. ejecutar el laboratorio sobre una copia;
2. comparar el informe con el original;
3. restaurar la copia editada en el cliente oficial, con autorización;
4. verificar que el juego la acepta y que no cambian campos ajenos;
5. solo entonces evaluar escritura en producción.

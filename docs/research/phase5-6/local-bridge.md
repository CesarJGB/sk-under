# Puente local Linux sin emulador permanente

**Resultado:** el puente local funciona en Linux con archivos que el titular ya
posee. No abre sockets, no usa sesiones del juego y no necesita un emulador
encendido. El emulador solo se usó para adquirir la referencia 8.8.0; el
procesamiento posterior es independiente de Android.

## 1. Arquitectura

```text
dispositivo del titular
        │  exportación/copia autorizada (archivo local)
        ▼
SaveAcquisitionProvider  →  SaveDecoder  →  SaveValidator
                                             │
                                             ├── SaveEditor (laboratorio)
                                             └── SaveExporter
```

Las interfaces están en `backend/app/bridge.py`:

| Interfaz | Implementación local | Responsabilidad |
| --- | --- | --- |
| `SaveAcquisitionProvider` | `LocalFileProvider` | Leer un archivo regular, con límite y sin seguir enlaces |
| `SaveDecoder` | `LocalSectionDecoder` | Detectar Base64+DES+CBC+JSON, XOR de `game.data` o JSON plano |
| `SaveValidator` | `LocalSectionValidator` | Verificar tamaño, SHA-256 y esquema/versión |
| `SaveEditor` | `LocalSectionEditor` | Aplicar cambios explícitos sobre una copia en memoria |
| `SaveExporter` | `LocalFileExporter` | Escribir una copia nueva sin tocar el original |

`LocalBridge` compone las cinco interfaces. Un proveedor autorizado futuro
(una exportación oficial, una carpeta sincronizada por el titular o un
dispositivo propio) puede implementar `SaveAcquisitionProvider` sin reescribir
el decodificador, el validador, el editor ni el exportador.

## 2. Uso

El puente usa las mismas claves locales que el adaptador de la Fase 3:

```bash
cd backend
uv run --locked python -m app.bridge \
  --env-file /ruta/privada/cipher.env \
  inspect --directory /ruta/a/files
```

Salida: JSON con nombre, tamaño, SHA-256, estado, tipo, versión y nombres de las
claves de nivel superior. **No imprime valores de la partida ni el contenido
JSON.**

Archivo individual:

```bash
uv run --locked python -m app.bridge \
  --env-file /ruta/privada/cipher.env \
  inspect --file /ruta/a/item_data_<perfil>.data
```

Copia intacta (el original no se modifica):

```bash
uv run --locked python -m app.bridge \
  --env-file /ruta/privada/cipher.env \
  export /ruta/a/item_data_<perfil>.data \
  --output /ruta/segura/copia.data
```

Edición de laboratorio:

```bash
uv run --locked python -m app.bridge \
  --env-file /ruta/privada/cipher.env \
  edit /ruta/a/item_data_<perfil>.data \
  --output /ruta/segura/editada.data \
  --set cumulativeFishCount=123
```

El valor se interpreta como JSON cuando es posible; si no, como texto. La ruta
debe existir y el tipo debe coincidir con el valor original. Los marcadores
`AppVersion`, `version`, `gameVersion`, `ChillyUid`, `cloudSaveId` y
`platformId` están protegidos.

## 3. Entradas aceptadas

| Entrada | Detección | Estado |
| --- | --- | --- |
| `*.data` Base64 + DES-CBC + JSON | Códec de la Fase 3 y esquemas 8.6.0/8.8.0 | `decoded` |
| `game.data` XOR JSON | Capa XOR de 15 bytes + `AboGameData` | `decoded` |
| `sandbox_config*.data`, `sandbox_maps*.data` | JSON plano y nombre esperado | `plain_json` |
| Archivo desconocido | Sin esquema | `unknown` u `opaque` |
| Archivo vacío, enorme, FIFO, directorio o enlace | Rechazado antes de leer | Error tipado |

El puente no clasifica un archivo solo por su nombre: el nombre solo desempata
un esquema ya validado por sus claves. Un `game.data` aleatorio no se interpreta
como partida.

## 4. Seguridad y privacidad

- Sin red: no hay `requests`, sockets, URLs ni llamadas al proveedor.
- Sin credenciales: no lee tokens, contraseñas, cuentas ni sesiones.
- Sin escritura en el original: la exportación escribe un destino nuevo.
- Sin sobrescritura por defecto: si el destino existe, falla; `--overwrite` es
  explícito.
- Archivos regulares: `os.O_NOFOLLOW` y `O_NONBLOCK`; se rechazan enlaces,
  FIFOs y directorios.
- Límites: 8 MiB por archivo, 64 archivos y 32 MiB por directorio.
- Permisos: la salida se crea con modo `0600`.
- La copia privada de la muestra 8.8.0 y su inventario viven fuera de Git.

No se implementó extracción de contraseñas, reutilización de tokens,
suplantación de sesiones, acceso a cuentas ajenas ni elusión de controles.

## 5. Qué no hace

- No descarga una partida de la nube.
- No inicia sesión ni usa el cliente oficial.
- No sube una copia al servidor.
- No confirma que el juego acepte una copia editada.
- No reconstruye el sobre `CloudSaveGameData` (faltan `serialzedVersion`,
  `cloudSaveId` y `platformId` en el perfil local).

## 6. Pruebas

`backend/tests/test_local_bridge.py` cubre:

- 8.8.0 `item_data` con enteros grandes y campos desconocidos;
- `game.data` XOR con edición y roundtrip;
- secciones nuevas `setting`, `mall_reload`, `escape_season` y `bp_data`;
- versiones 80300/80800/0 y rechazo de 80700;
- archivos vacíos, corruptos, desconocidos, FIFO, directorio y excesivos;
- exportación sin sobrescritura, permisos y preservación del original;
- resumen de directorio sin valores.

Comando: `cd backend && uv run --locked pytest -q tests/test_local_bridge.py`.

## 7. Integración con el backend web

El adaptador `sk-local-des-cbc` ahora reconoce doce estructuras JSON locales
(nueve de 8.6.0 y tres nuevas de 8.8.0) y `sk-local-game-xor` reconoce
`game.data`. Las rutas HTTP existentes `/files/inspect`, `/files/validate` y
`/files/export` siguen siendo de solo lectura para estos formatos: inspeccionan,
verifican y devuelven una copia intacta. La edición real no se habilitó en
producción.

El puente CLI es la vía de laboratorio para editar; el frontend puede importar
y verificar una copia local 8.8.0 sin cambios de contrato. No se añadieron
dependencias de producción ni llamadas externas.

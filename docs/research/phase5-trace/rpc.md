# Contratos administrados de la ruta RPC

Los tipos se resolvieron desde los índices IL2CPP enlazados con el ELF. La firma del callback determina qué recibe el consumidor en memoria. Las claves del mensaje, la representación en red y el significado de los enteros requieren evidencia adicional. [Método de verificación](blobsave.md)

| Método de LoginApi | Entrada y resultado | Dependencia comprobada |
| --- | --- | --- |
| `CheckSaveMac` | Callback `(Err, Exception) → void` | Consulta uid, plataforma y dato de dispositivo antes de `CallRpc`. La respuesta entra en el agente, cuya sobrecarga de `onCheckSaveMac` tiene ramas hacia consulta de tiempo y descarga. |
| `GetSaveTimeInfo` | Callback `(Err, long, int, int) → void` | Delega en `CallRpc`. El nombre sugiere tiempo de guardado. Las unidades, el orden semántico y los dos enteros quedan abiertos. |
| `DnloadSave` | Éxito `Action<string>`, fallo `Action<Err,Exception>`, retorno void | `<ForceFetchData>d__125.MoveNext +0x2e8` llama al método. El agente recibe el texto en `onLoadGameRpcSuccess` y contempla serializador y canal. La tarea externa de `ForceFetchData()` devuelve `(bool, Err)`. |
| `UploadSave` | `byte[] data, string extra, Callback(Err)`, retorno void | Inicia una operación asíncrona. Firma comprobada sin ejercer escrituras. |

## Discriminador de cuatro bytes

En la ruta base de `LoginApi._Decompress` (VA `0x0636cefc`), +0x84 a +0x9c comprueban longitud mínima de cuatro y leen `BitConverter.ToUInt32(bytes, 0)`. En +0xa0 a +0xc0, el valor `0x80000000` conduce a `ZipHelper.Decompress(bytes, 4, length-4)`. La segunda comparación (+0xe8 a +0xf0) reconoce `0xffffffff` y su rama retorna nulo (+0x150). Para menos de cuatro bytes o un primer entero distinto de ambos, el camino común conserva el array original para envolverlo. La entrada nula tiene una rama independiente. El prefijo comprimido en este ABI little-endian se representa con los bytes `00 00 00 80`.

Esta lectura explica por qué detectar gzip en el byte cero sería insuficiente como decodificador RPC. La llamada comprobada procede del RPC genérico. El cuerpo de `ZipHelper.Decompress` no quedó resuelto y el formato del bloque interior sigue abierto. El significado de aplicación del marcador que devuelve nulo tampoco quedó demostrado. La [tabla de BlobSave](blobsave.md) documenta otra representación de éxito y error.

En el ABI armeabi-v7a del AVD, la misma operación `0x06009e07` comienza en VA `0x0350a86c`. Se comprobó el umbral de cuatro bytes en `0x0350a910`, la comparación con `0x80000000` en `0x0350a928`, la resta de cuatro en `0x0350a93c`, la llamada al método `0x06002663` (ZipHelper.Decompress) en `0x0350a944` y la comparación equivalente a -1 en `0x0350a960`. Esto corrobora el discriminador en las dos arquitecturas del APK.

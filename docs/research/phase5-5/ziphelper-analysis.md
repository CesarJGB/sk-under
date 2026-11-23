# `ZipHelper`: tipos, firmas y llamada

**Resultado: la clase y la llamada están confirmadas; el cuerpo no es legible
estáticamente.** El APK 8.8.0 incluye varias clases `ZipHelper`. La que usa el
RPC es la del espacio global (typeDef 1070), no las de `ChillyRoom.Utils`,
`System.IO.Compression` o `SharpZipLib`.

## 1. Tipos homónimos

| typeDef | Nombre | Campos | Métodos | Papel |
| ---: | --- | ---: | ---: | --- |
| 1070 | `ZipHelper` | 0 | 5 | Destino de `LoginApi._Decompress`. |
| 15046 | `ChillyRoom.Utils.ZipHelper` | 1 | 5 | Utilidad propia, no llamada por esta ruta. |
| 43104 | `ZipHelper` | 0 | 5 | Copia/duplicado en otro ensamblado. |
| 42930 | `ICSharpCode.SharpZipLib.Zip.ZipHelperStream` | 24 | 24 | Stream de SharpZipLib. |
| 43393 | `System.IO.Compression.ZipHelper` | 8 | 8 | Utilidades internas de .NET. |

La metadata también registra `System.IO.Compression.dll`,
`ICSharpCode.SharpZipLib.dll` y cadenas como `"gzip"`, `"gzip, deflate"` y
`"Corrupted gzip header"`. Esas presencias no demuestran por sí solas qué
algoritmo usa el método global.

## 2. Métodos del typeDef 1070

| Token | Nombre | Retorno | Params | Flags |
| --- | --- | --- | ---: | --- |
| `0x06002660` | `GZipCompressString` | `string` | 1 | estático |
| `0x06002661` | `GZipDecompressString` | `string` | 1 | estático |
| `0x06002662` | `Compress` | `byte[]` | 3 | estático |
| `0x06002663` | `Decompress` | `byte[]` | 3 | estático |
| `0x06002664` | `.ctor` | `void` | 0 | — |

`Decompress` recibe `(byte[] data, int offset, int length)` y devuelve
`byte[]`. Es exactamente la forma que usa el RPC con `offset=4` y
`length=BodySize-4`.

## 3. Llamada desde `LoginApi`

En `LoginApi._Decompress` (token `0x06009e07`, VA `0x0636cefc`):

```text
0x0636cf80  ldr  w8, [x19, #0x18]     ; longitud del array
0x0636cf84  cmp  w8, #4
0x0636cf88  b.lt rama_comun
0x0636cf98  bl   BitConverter.ToUInt32
0x0636cf9c  mov  w8, #-0x80000000
0x0636cfa0  cmp  w0, w8
0x0636cfa4  b.ne otra_rama
0x0636cfac  mov  w1, #4
0x0636cfb8  sub  w2, w8, #4
0x0636cfbc  bl   0x077b0c0c           ; ZipHelper.Decompress
```

El destino `0x077b0c0c` coincide con el puntero del método `0x06002663` en el
arreglo de `Assembly-CSharp` (`methodPointers[9826]`). La correspondencia se
verificó con el arreglo del `Il2CppCodeGenModule` de ese ensamblado
(`methodPointerCount = 0x34038`).

En el ABI `armeabi-v7a`, la misma llamada está en `0x0350a944` y el destino es
`0x04f02eac`. Ambos ABI confirman el discriminador y la llamada, no el cuerpo.

## 4. Por qué el cuerpo no se puede leer

El puntero `0x077b0c0c` cae en una región que el empaquetador ACE protege. Los
punteros de `ByteBuffer.ReadString` (`0x077b0a40`) y
`ByteBuffer.ReadStringZipped` (`0x077b0b30`) caen en la misma región y tampoco
empiezan con un prólogo. Una decodificación XOR `0x03` produce instrucciones
válidas, pero son **etiquetas interiores** de un despachador; no son los
cuerpos de los métodos. Por eso no se puede afirmar si dentro hay
`GZipStream`, `DeflateStream` o una implementación propia.

Esta es una diferencia importante: el nombre `ZipHelper.Decompress` y la firma
`byte[] (byte[], int, int)` son evidencia de la interfaz, no del algoritmo.

## 5. Implementación candidata

El patrón público más frecuente para esa interfaz es:

```csharp
public static byte[] Decompress(byte[] data, int offset, int length)
{
    using var input = new MemoryStream(data, offset, length);
    using var gzip = new GZipStream(input, CompressionMode.Decompress);
    using var output = new MemoryStream();
    gzip.CopyTo(output);
    return output.ToArray();
}
```

La clase hermana `GZipDecompressString` refuerza la hipótesis gzip. No se copia
como verdad: el backend implementa `decode_rpc_gzip` como **candidato opt-in** y
solo acepta un cuerpo que empiece por `1f 8b`. El flujo por defecto continúa
rechazando el sobre comprimido.

## 6. Vectores y límites

Los vectores ejecutables están en
[`rpc-codec-test-vectors.md`](rpc-codec-test-vectors.md). El decodificador:

- conserva el sobre original;
- exige el marcador `00 00 00 80`;
- exige gzip `1f 8b`;
- valida CRC/ISIZE, truncamiento y bytes posteriores;
- limita el JSON a 16 MiB y la entrada a 8 MiB;
- no usa red, no escribe archivos y no se habilita en producción.

## 7. Lo que falta

Una respuesta real o una copia de memoria del código descifrado. Sin eso, la
hipótesis gzip no se eleva a confirmación y no se declara compatibilidad RPC.

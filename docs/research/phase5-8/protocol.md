# Contrato y captura de protocolo

## Procedimiento nuevo

Se extrajeron del APK 8.8.0 `assets/bin/Data/Managed/Metadata/global-metadata.dat` y `lib/arm64-v8a/libil2cpp.so`. Se ejecutó `metadata_inventory.py` de 5.5 con `--types 'BackupClient,FetchGameDataReq,GetBlobSave,NetPack,BlobSaveClient'`. El primer intento con el ELF extraído de memoria falló por ausencia de `.rela.dyn`; el ELF del APK sí funcionó. El primer intento con metadata ya descifrada también falló porque el programa la descifra: se repitió con la metadata original del APK. Salida completa en el laboratorio privado.

## Observaciones

- `BackupClient.GetBlobSaveAsync` tiene una sobrecarga de cero parámetros y otra de un parámetro. Su máquina `<GetBlobSaveAsync>d__18` tiene `cancellationToken`, `HttpClient`, `HttpRequestMessage` y `HttpResponseMessage`, sin campo de objeto de petición. Esto descarta que el llamador deba pasar un `FetchGameDataReq` a esas sobrecargas; no prueba que el cuerpo HTTP sea vacío, ni qué verbo se usa.
- `FetchGameDataAsync` tiene sobrecargas de uno y dos parámetros; `FetchGameDataReq` declara `EventType` y `DateTimeUtcOffsetOfMinutes`. El `POST {}` observado no demuestra que los campos opcionales tengan siempre esos valores.
- Hay dos tipos distintos: `NetPack` global expone `MsgId` de tipo `ushort`, mientras `ChillyRoom.RPC.NetPack` expone `OpCode` de tipo `ushort`; ambos declaran `ReqIdx` (`uint`), `Type` (`byte`), `BodySize` (`uint`) y constantes de índices y tamaño. No se han recuperado aquí sus valores, ni probado que se usen en la descarga legacy. No deben identificarse ambos tipos solo por su nombre.
- `BlobSaveClient` tiene `DownloadAsync` de cero o un parámetro y métodos de serialización JSON y detección gzip. Las firmas no prueban que la respuesta del servicio sea gzip.

Como prueba acotada de la hipótesis GET sin cuerpo, con la sesión legítima, el host y los encabezados completos de la lectura conocida, `GET /Backup/GetBlobSave` devolvió **404, cero bytes**. Esto no prueba el contrato alternativo. El prototipo `GatewayCloudSaveProvider` usa GET y su ruta de éxito sigue sin verificar; no debe presentarse como funcional. No se efectuaron sondeos masivos.

## Captura y límites

Se inició `adb shell tcpdump -i any -s 0 -w /data/local/tmp/sk58.pcap` con `adb root` en el AVD de laboratorio. El archivo se trata como privado. El transporte de red cifrado no proporciona por sí solo `NetPack` en claro; no se afirma haber capturado uno. Se instaló Frida 17.27.4 en un entorno temporal y se inició `frida-server` x86_64 en Android. El attach al proceso funcionó; `Process.arch` informó `x64` y se enumeró `libndk_translation.so`. `/proc/<pid>/maps` confirmó `lib/arm64/libil2cpp.so`, pero no se enumeraba como módulo nativo de Frida: el APK ejecuta ARM64 mediante traducción, de modo que esta comprobación no identificó una dirección de función ARM que se pueda interceptar directamente. No se obtuvo un NetPack en claro.

**Hipótesis descartada:** que GET con los encabezados de la sesión baste para recuperar la copia. **Aún sin resolver:** verbo y cuerpo concretos, respuesta, cabecera binaria y relación de NetPack con la operación. **Siguiente experimento:** instrumentar localmente las funciones de serialización en el cliente autorizado y comparar los bytes antes del cifrado con el evento de descarga oficial; no adivinar peticiones.

La primera captura de red se cerró con 4.870 paquetes, cero perdidos según tcpdump, y se guardó en privado. Un inventario con Scapy contó 3.132 paquetes TCP con carga; 2.728 usaban el puerto 443 y entre ellos se detectaron comienzos de registros TLS. La captura también contiene tráfico HTTP y del propio laboratorio; el puerto o una firma aislada no atribuyen un paquete a una operación del juego. Se inició otra captura para las operaciones posteriores. Ningún paquete se presenta como NetPack auténtico sin atribución y decodificación.

## Tramas binarias auténticas observadas

En la segunda captura privada, Scapy identificó dos envíos TCP al puerto 9377 a las 19:05:12 y 19:05:28 UTC, antes de las operaciones manuales de nube. Al concatenar en orden los payloads enviados, se observaron dos cabeceras de ocho bytes: `02 03 00 01 00 00 0b 2a` y `02 03 00 02 00 00 03 16`; los últimos cuatro bytes interpretados en big-endian coinciden respectivamente con 2.858 y 790 bytes de cuerpo. Ambos cuerpos empiezan con gzip y se descomprimieron a 13.703 y 1.285 bytes de contenido binario no JSON. Los dos acuses observados son de nueve bytes y cada uno declara un byte de cuerpo bajo la misma interpretación. Se guardaron tramas y cuerpos descomprimidos en el laboratorio privado.

Esto es evidencia de un **encuadre binario real**, no de que sea `ChillyRoom.RPC.NetPack` ni de que corresponda a la copia de nube. No se ha resuelto la identidad de la conexión. No contiene las cadenas buscadas `GetBlobSave`, `FetchGameData` ni `cloudSaveId`; su ausencia no prueba que no se relacione con ellas. El parser `inspect_rpc_frame` clasifica las cabeceras como `passthrough`; ese parser inspecciona el discriminador de respuesta RPC, no este encuadre completo. El tráfico capturado en el puerto local 27042 incluye la propia instrumentación Frida y no se debe atribuir al servidor del juego. La adquisición de un NetPack de guardado sigue pendiente.

# Análisis estático del APK

## Artefacto y verificación

| Dato | Resultado |
| --- | --- |
| Archivo de entrada | `soul-knight-8-8-0.apk` |
| Tamaño | 818 758 969 bytes |
| SHA-256 | `54bb332be9444596501ec99f745f21adfa55265feea3a15331c735009b517f34` |
| Contenedor | ZIP con 6 892 entradas. Lectura y CRC correctos en todo el archivo |
| Firma | `apksigner verify --verbose --print-certs` verificó el esquema v2 y un firmante |
| SHA-256 del certificado público | `e2bb0d8f9d7c76e5256ed29e9cd0b026f8aad3cc5e5dfde1da6df141ea6aabf2` |
| Aplicación | `com.ChillyRoom.DungeonShooter` |
| Versión Android del paquete | `versionName=8.8.0`, `versionCode=1080800` |
| Versión del bundle | `version=8.8.0`, `bundleVersionCode=80800` en `assets/bundleVersionData.txt` |
| Android SDK | Mínimo 24, objetivo 36, compilación 36 |
| Motor | Unity 2022.3.62f2, IL2CPP, build Release con stripping |
| ABI | `arm64-v8a` (ELF64 AArch64) y `armeabi-v7a` (ELF32 ARM), 20 bibliotecas por ABI |

La firma valida el artefacto frente al certificado incluido. La identidad del firmante queda pendiente de cotejo con un certificado o APK obtenido de un canal oficial de referencia. El número de compilación Android, el del bundle y los marcadores del contenido guardado pertenecen a dominios diferentes. [Documentación de apksigner](https://developer.android.com/tools/apksigner)

## Manifiesto y recursos

- La aplicación registrada es `com.chillyroomsdk.sdkbridge.BasePlayerApplication`. El lanzador declarado es `com.chillyroomsdk.sdkbridge.BasePlayerActivity`, que extiende `UnityPlayerActivity`.
- El manifiesto contiene `INTERNET`, `ACCESS_NETWORK_STATE`, `allowBackup=false` y una configuración de seguridad de red referenciada desde `@xml/xiaomi_network_security_config`. La configuración permite tráfico sin cifrar. El transporte observado de cada servicio requiere evidencia aparte.
- Hay seis DEX principales y `assets/audience_network.dex`. Los DEX principales incluyen el puente ChillyRoom, integración con Google Play y bibliotecas de terceros. JADX confirmó que `com.chillyroomsdk.util.SaveUtil.SaveImage` guarda imágenes mediante MediaStore.
- `META-INF/com.android.games.engine.build_fingerprint` declara Unity e IL2CPP. El encabezado UnityFS de `assets/bin/Data/data.unity3d` y el de los bundles `login.ab` y `localization.ab` muestran la misma versión del motor. Se contabilizaron 2 473 pares `.ab` / `.manifest` en `assets/AssetBundles/`.
- `assets/bin/Data/ScriptingAssemblies.json` enumera, entre otros, `Assembly-CSharp.dll`, `Assembly-CSharp-firstpass.dll`, `Newtonsoft.Json.dll`, `ICSharpCode.SharpZipLib.dll` y `ChillyRoom.IM.dll`. La lógica principal del estudio se vinculó con `Assembly-CSharp.dll` en IL2CPP.
- `libunity.so` contiene el motor y `libil2cpp.so` el código nativo generado. También aparecen `libmain.so`, `libxlua.so`, `libgilzoide-sqlite-net.so`, `libunitydatachannel.so`, `libnative-lib.so`, `libnms.so`, `libanogs.so` y `libanort.so`. `readelf` muestra una dependencia directa de `libil2cpp.so` sobre `libanort.so`. La presencia de Lua y SQLite por sí sola no establece el formato de los guardados.

## Procedimiento y límites

Se leyó el ZIP con Python y se comprobó el SHA-256. Se usaron apksigner del paquete de Android Build Tools 31.0.2, Apktool 3.0.3 para el manifiesto y los recursos, y JADX 1.5.6 para cinco clases seleccionadas de `classes2.dex`. Las herramientas Java se ejecutaron en un contenedor sin red, con el APK montado en solo lectura. El APK, sus bibliotecas y sus scripts se trataron como datos durante todo el análisis. [Apktool 3.0.3](https://github.com/iBotPeaches/Apktool/releases/tag/v3.0.3) · [JADX 1.5.6](https://github.com/skylot/jadx/releases/tag/v1.5.6)

```sh
sha256sum soul-knight-8-8-0.apk
apksigner verify --verbose --print-certs soul-knight-8-8-0.apk
apktool d --no-src -o decoded soul-knight-8-8-0.apk
unzip -p soul-knight-8-8-0.apk classes2.dex > classes2.dex
jadx --no-res --single-class com.chillyroomsdk.sdkbridge.account.BaseAccountAgent classes2.dex
readelf -h -d libil2cpp.so
```

El `global-metadata.dat` de 55 013 528 bytes usa un encabezado y tramos transformados. Se interpretaron tablas en memoria mediante lectura estructural, contrastada con los tamaños, rangos, identificadores de metadatos y pertenencia de métodos a cada tipo. Se validaron 193 imágenes, 46 649 tipos, 380 122 métodos, 351 540 campos y 350 248 parámetros. Se cotejaron los registros de tipo de 88 bytes, de método de 36 bytes y de imagen de 40 bytes con una referencia de estructuras IL2CPP. [Estructuras de metadatos de Il2CppDumper](https://github.com/Perfare/Il2CppDumper/blob/master/Il2CppDumper/Il2Cpp/MetadataClass.cs)

Para comprobar llamadas seleccionadas, se enlazó cada identificador de método con la tabla de punteros de su módulo en el ELF AArch64 usando relocaciones de `.rela.dyn`. Se disensamblaron los tramos legibles de la sección ejecutable `il2cpp` mediante Capstone 5.0.9 y pyelftools 0.33. Algunas entradas tienen cuerpos parciales y los punteros directos no cubren todas las instancias genéricas. Los informes indican cuándo se conoce un símbolo y cuándo se ha seguido una llamada. Las referencias hexadecimales incluyen identificadores IL2CPP y, donde se especifica, direcciones virtuales del ELF de este APK.

Los recursos descompilados, los archivos del APK, los valores de configuración privada y las muestras se conservaron fuera de Git.

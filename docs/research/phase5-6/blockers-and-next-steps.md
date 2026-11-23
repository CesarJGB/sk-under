# Bloqueos y próximos pasos

## 1. Bloqueos actuales

| Bloqueo | Consecuencia | Evidencia | Qué falta exactamente |
| --- | --- | --- | --- |
| Sin `CloudSaveGameData` de nube | No se declara compatibilidad remota | El perfil local no contiene `serialzedVersion`, `cloudSaveId` ni `platformId` | Una descarga autorizada de una cuenta propia o una respuesta RPC real |
| Sin respuesta RPC real | No se confirma el `NetPack` ni el `Body` | gzip confirmado en `ZipHelper.Decompress`; el sobre no se ejercitó | Cuerpo comprimido + JSON/estructura que el cliente aplicó |
| Sin prueba de cliente | No se declara que una copia editada sea aceptada | Roundtrip de laboratorio | Restaurar una copia editada en el cliente oficial y observar el resultado |
| `FixData` no decompilado | No se conoce la migración 8.6.0 → 8.8.0 | Firmas identificadas; cuerpos protegidos | Cuerpo de `NewCloudSaveAgent.FixData`/`RGSaveManager.FixData` o una prueba de restauración |
| Checksum/MAC del proveedor | No se puede garantizar que una copia modificada pase la validación del servidor | No observado | Contrato del proveedor o una respuesta/copia real que lo incluya |
| Código de `game.data` | Resuelto localmente (XOR) | 41 claves, roundtrip exacto | Nada para el perfil local; sí falta su relación con la envoltura de nube |

No se intentó eludir autenticación, anti-cheat, TLS pinning ni controles del
proveedor. No se extrajeron datos de otras cuentas.

## 2. Las tres cosas que faltan para la integración remota

1. **Una copia de nube autorizada del titular.** El formato esperado es el JSON
   `CloudSaveGameData` con las 18 claves (o el cuerpo RPC que lo contiene), no
   los archivos locales por sección.
2. **El contrato de transporte.** Confirmar el `NetPack` (cabecera, `Body`,
   `BodySize`) y si el `Body` es JSON directo, una cadena con longitud
   prefijada o un buffer con tags.
3. **Una prueba de restauración.** Restaurar en el cliente oficial una copia
   no-op y, después, una copia con un cambio controlado; verificar que el juego
   la acepta y que los campos ajenos no cambian.

## 3. Qué se puede hacer sin cuenta

- Procesar en Linux los archivos locales que el titular ya tiene.
- Verificar el códec, el esquema y el roundtrip.
- Comparar 8.6.0 y 8.8.0.
- Preparar el importador y el puente para recibir una muestra de nube.
- Documentar el bloqueo sin inventar valores de envoltura.

## 4. Experimentos para la Fase 5.7

Ordenados por valor esperado:

1. **Obtener una copia de nube propia y autorizada.** Que el titular descargue
   su progreso en el cliente oficial y lo exporte por una vía permitida, o que
   el proveedor entregue el archivo. Medir tamaño, SHA-256, `serialzedVersion`,
   `cloudSaveId` y `platformId`. Es el experimento que más desbloquea.
2. **Capturar un `NetPack` real de la propia sesión.** Si se autoriza, observar
   la respuesta del servidor en el cliente propio (sin eludir TLS pinning ni
   anti-cheat) y comparar el `Body` con el JSON. Confirmaría o descartaría la
   hipótesis de `Body` JSON.
3. **Probar la aceptación de una copia no-op y de una copia editada.** Primero
   una copia intacta 8.8.0; después un cambio de un solo campo permitido. Es la
   única forma de elevar el roundtrip de laboratorio a compatibilidad de
   cliente.
4. **Leer `FixData` en una copia de memoria ya descifrada.** La Fase 5.6 ya
   demostró que el código se puede leer en runtime; el siguiente paso es
   localizar el cuerpo de `NewCloudSaveAgent.FixData` y documentar qué campos
   corrige. No requiere red.
5. **Construir un agregado local de laboratorio sin envoltura.** Útil para
   probar el validador de las 18 secciones, pero debe etiquetarse como
   sintético: no sustituye a una muestra de nube y no se publica como
   compatible.

## 5. Criterios para no repetir errores

- No declarar “compatible” solo porque los nombres de campo coinciden.
- No declarar “gzip” solo por el nombre del método; la Fase 5.6 ya lo confirmó
  en el cuerpo, pero una respuesta real sigue siendo necesaria para el flujo.
- No confundir un `.data` local con el agregado de nube.
- No publicar partidas, huellas, IDs de cuenta ni credenciales.
- No añadir campos nuevos con valores arbitrarios para “completar” un esquema.
- No habilitar edición real en producción sin prueba de cliente.

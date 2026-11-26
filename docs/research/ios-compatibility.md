# Compatibilidad preliminar con iOS — fase 9.2

## Estado

No se implementa soporte iOS en producción. Esta fase solo investiga la
estructura del guardado y separa tres problemas que no deben confundirse:

1. **Formato**: interpretar y serializar las secciones del juego.
2. **Autenticación y descarga**: obtener el guardado de la cuenta iOS.
3. **Sincronización**: volver a subir un candidato y verificar que el cliente lo
   acepta.

La muestra disponible demuestra parte del primer punto. No demuestra los otros
dos.

## Origen de la muestra

El guardado iOS se obtuvo mediante el editor externo CRDE, en modo de solo
lectura, usando su endpoint de visualización con la sesión autorizada. El
documento llegó ya descodificado como JSON. No se dispone de un guardado nativo
de iOS ni de su sobre de autenticación.

La cuenta de juego es de canal iOS, versión 8.8.1. El editor conserva
`platformId` y `maps` dentro de `_crde_misc`, no en el nivel superior.

## Formato observado

### Secciones

C contiene `battlePassSaveData`, `escapeSeasonData`, `gameData`, `itemData`,
`mallReloadData`, `miscData`, `monsterRiseData`, `pvpData`, `seasonData`,
`settingData`, `statisticData`, `taskData` y `weaponEvolutionData`, además de
`_crde_misc`.

Son las mismas secciones de juego que B, con otra versión de `itemData`
(`AppVersion` 1531 frente a 80800) y otro progreso. A usa `gameVersion` 2145 y
un esquema más antiguo.

### Sobre de nube

A y B incluyen `cloudSaveId`, `platformId`, `serialzedVersion` y `maps`. C no
los incluye en el nivel superior; CRDE los conserva en `_crde_misc`. Esto puede
significar una de dos cosas y no se ha demostrado cuál:

- que el guardado nativo iOS use otro sobre; o
- que el editor externo los separe al exportar y los reintegre al sincronizar.

No se debe concluir que iOS no usa `serialzedVersion` basándose solo en esta
respuesta.

### Tipos y codificaciones

- `itemData.blueprints` usa enteros: 24 valores `1` y 174 valores `2`. Confirma
  la escala `1 = Got`, `2 = Researched` ya deducida en la fase 9.1.
- `gameData.currentRoomDecorate` es entero 0; en A (Android antigua) era texto.
  La diferencia ya existía entre dos cuentas Android, así que no es específica
  de iOS.
- `gameData.heroLevel` tiene 42 entradas y `Knight` en 8.
- `petUnlock` tiene 58 entradas.
- Las claves de objetos, planos, personajes y mascotas coinciden con Android.
- `StartTime` se conserva como `__CRDE_LARGE_INT64__<valor>`, una representación
  del editor para enteros de 64 bits. No es un tipo del guardado original.

## Qué se puede reutilizar

| Componente | Reutilización | Motivo |
| --- | --- | --- |
| Lectura de secciones JSON | Directa | Mismas secciones y claves |
| Catálogos de personajes, mascotas, planos y vestíbulo | Directa | Identificadores compartidos |
| Escritores de `heroLevel`, `blueprints`, `petUnlock` | Adaptación menor | Ya soportan texto/entero; falta validar el sobre |
| Escritor de decoraciones | Adaptación menor | Requiere `event2Count` y `blueprints`; ya previsto |
| Validación de tipos y reversión byte a byte | Directa | Opera sobre el documento descodificado |
| Borrador global, respaldos y cambios pendientes | Conceptual | Dependen del perfil y del SHA de origen |
| Autenticación de SK-Under | No reutilizable | Es específica de la nube Android |
| Descarga y sincronización | No reutilizable | No se investigó el canal iOS |
| Verificación remota posterior | No disponible | Sin canal iOS autorizado |

## Qué necesita adaptación

- **Sobre de nube**: identificar el formato nativo iOS y si exige
  `serialzedVersion`, `maps`, `cloudSaveId` o `platformId`.
- **Integridad**: comprobar si el guardado iOS usa la misma serialización
  canónica y los mismos hashes que Android.
- **Codificación de planes**: el escritor ya detecta texto o entero, pero debe
  validarse con una cuenta iOS real.
- **Metadatos del editor**: `_crde_misc` no debe formar parte del candidato ni
  trasladarse a otra cuenta.
- **Autenticación**: no se dispone de un mecanismo propio para iOS. No se debe
  usar el token de CRDE en SK-Under.
- **Sincronización**: no se ha probado ninguna subida iOS. No se implementa.

## Propuesta para una fase iOS

1. Obtener un guardado nativo iOS y su sobre real, con autorización del
   propietario.
2. Comparar el sobre con A/B: campos obligatorios, codificación, compresión,
   hashes y versión.
3. Implementar un adaptador de lectura que normalice el sobre sin tocar las
   secciones de juego.
4. Reutilizar los escritores existentes sobre el documento normalizado.
5. Añadir validación de integridad y reversión byte a byte para el sobre iOS.
6. Diseñar autenticación y descarga propias solo si existe un mecanismo
   autorizado; no reutilizar tokens de terceros.
7. Probar en una copia aislada y después en el dispositivo, con respaldo.
8. No habilitar escritura iOS en producción hasta completar la validación.

## Riesgos

- Un sobre incorrecto puede invalidar el guardado aunque las secciones de juego
  sean correctas.
- Copiar `platformId`, `cloudSaveId` o metadatos de CRDE entre cuentas puede
  mezclar identidades.
- `currentSkinDatas` y `currentRoomDecorate` no tienen mapa de selección
  demostrado; no deben editarse.
- La ausencia de `serialzedVersion` en la respuesta de CRDE no prueba que el
  cliente iOS lo omita.
- La validación en Android no se extrapola a iOS.

## Conclusión

El formato de las secciones de juego es compatible a nivel de lectura y los
escritores actuales pueden reutilizarse con un adaptador. La autenticación, la
descarga y la sincronización iOS no están resueltas y no deben declararse
compatibles. La compatibilidad de escritura iOS queda para una fase dedicada.
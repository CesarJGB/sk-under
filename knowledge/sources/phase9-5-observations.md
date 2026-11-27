# Observaciones propias — fase 9.5

Fecha: 2026-11-26

## Muestras

- iOS avanzada C: 995 contadores de armas, valores de 10 a 82, mediana 46.
  Todos por encima de los umbrales observados; no se usan como tabla de
  requisitos.
- Android avanzada A y nueva B: contadores dispares, incluidos ceros.
- Guardado local 8.6 avanzado: 9999 para todas las claves de arma.
- APK 8.8.0 y metadata descifrada para localizar `UIForge`.

## Confirmación del propietario

En Android 8.8.0.13:

- Editar `statisticData.object2ObtainTime` registra el arma y el juego reconoce
  el contador nuevo.
- La fase 9.4 solo escribía 1 y por eso el arma aparecía registrada pero seguía
  bloqueada para fabricar.
- Una arma morada muestra 1/6; una blanca 1/2, verde 1/3, azul 1/4 y naranja
  1/6.
- `weapon_337` (Subfusil UZI Romántico) muestra 1/2, aunque el catálogo de
  prefab lo marca como nivel 3.

## Desensamblado

`UIForge.IsUnlockedByObtainTime` compara el contador con
`UnlockCountDict[nivel]`; la ausencia de clave cae en 8.
`GetWeaponLevel` intenta `TbWeapons.DataMap`, luego `WeaponInfo` y luego el
prefab. El bundle Luban que contiene `TbWeapons` sigue cifrado.

## Límites

- Los umbrales de los objetivos de fusión distintos de `weapon_337` no están
  confirmados.
- No se observó ninguna estructura de desbloqueo permanente alternativa a
  `object2ObtainTime` en las muestras.
- La operación masiva de forja aún no se ha validado en dispositivo.
- No se atribuye a CRDE ninguna implementación interna; solo se observó su
  acción de interfaz «Unlock all weapons in forge table».
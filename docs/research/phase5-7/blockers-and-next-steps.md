# Bloqueos y próximos pasos

## 1. Bloqueos actuales

| Bloqueo | Consecuencia | Evidencia | Qué falta exactamente |
| --- | --- | --- | --- |
| Cuenta de laboratorio sin progreso | `FetchGameData` devuelve un agregado vacío; no hay comparación útil | Respuesta de 600 bytes con colecciones vacías; [lectura](authentic-cloud-read.md) | Una cuenta con progreso, o crear progreso y confirmar que el agregado deja de estar vacío |
| `GetBlobSave` devuelve `500` | No se obtiene el wrapper nuevo | `500` con token y con varias variantes de cuerpo | El cuerpo/cabeceras exactos que espera el servicio, o un contrato oficial |
| `BlobSave/Download` devuelve `404` | La ruta legacy no existe en el host actual | `404`; host legacy `503` | Confirmar el host/ruta reales |
| Sin `CloudSaveGameData` | No hay `serialzedVersion`/`cloudSaveId`/`platformId` | [comparación](cloud-local-comparison.md) | Una respuesta auténtica del wrapper nuevo |
| Login de Google Play roto en el APK | No se puede usar la vía Play Games | `NoClassDefFoundError: PendingIntentCompat`; GMS 20.18.17 < 21.30.00; [estabilización](emulator-stabilization.md) | GMS actualizado y una cuenta Google autorizada, o un APK que no tenga el fallo |
| Primer arranque en frío cae | Hay que relanzar una vez | `SIGSEGV` en `IL2CPP Threadpool`; [estabilización](emulator-stabilization.md) | Entorno ARM nativo o un arranque que no dependa de la traducción |
| Auto-login con sesión obsoleta se atasca | La restauración no-op no llega al menú | `LoginInit`/100 %; [aceptación](modification-acceptance.md) | Iniciar sesión de nuevo o limpiar la sesión antes de la prueba |
| Aceptación visible no demostrada | No se puede afirmar que una edición se use | `game.data.gems=424242` se conserva, pero el HUD mostró 1.000 | Un ciclo post-tutorial con guardado/recarga y un campo visible |
| `CheckSaveMac`/MAC no resuelto | No se sabe si una copia editada pasará | Nombre del método; sin respuesta | Cuerpo del método o prueba de aceptación |
| `FixData` no decompilado | No se conoce la migración | [FixData](fixdata-analysis.md) | Cuerpo del método o prueba 8.6.0 → 8.8.0 |
| Límite de vinculaciones | Cada login de cuenta en emulador cuesta una | Documentación oficial: 5/90 días y 24 h | Reservar una vinculación para una prueba definitiva |

## 2. Orden recomendado

1. **Conservar el AVD estable.** API 30 `google_apis` x86_64, KVM, 4 vCPU,
   4 GiB, `swiftshader_indirect`, ABI `arm64-v8a`. No cambiar de imagen sin
   necesidad. El primer arranque en frío requiere un segundo intento.
2. **Crear progreso en la cuenta.** Completar el tutorial y guardar de forma
   normal. Verificar que `FetchGameData` deja de devolver colecciones vacías y
   que el agregado tiene datos comparables.
3. **Resolver `GetBlobSave`.** Obtener el cuerpo exacto que espera el servicio
   desde el cliente estable o desde un contrato oficial. Probar solo lectura
   con el token actual y etiquetar el resultado como verificado solo si hay
   `200` con un wrapper reconocible.
4. **Aceptación visible post-tutorial.** Editar un campo visible de bajo
   impacto, restaurar con el hotfix permitido y la nube bloqueada, y observar el
   HUD y el archivo tras un guardado/recarga. Separar `gems`, `lastGems` y
   `varGems`.
5. **Restauración no-op con sesión fresca.** Repetir la copia intacta de 5.6
   sin restaurar el token obsoleto, iniciar sesión de nuevo y comprobar que el
   cliente conserva el progreso y no lo repara.
6. **Proveedor Linux.** Añadir un proveedor de solo lectura para
   `FetchGameData` (agregado legacy) con pruebas sintéticas, y otro para
   `CloudSaveGameData` solo cuando el contrato de `GetBlobSave` esté verificado.
   No presentar el agregado legacy como la partida nueva.
7. **FixData y MAC.** Leer los cuerpos en runtime con el cliente estable o
   probar la restauración 8.6.0. No implementar una migración especulativa.
8. **Escritura.** Solo después de 3–7, con copia remota, autorización explícita
   y procedimiento de recuperación.

## 3. Qué no hacer

- No adivinar el cuerpo de `AccountLogin` con la cuenta real.
- No desactivar TLS, pinning, anti-cheat ni controles del proveedor.
- No parchear el cliente para saltar el pago, el consentimiento o la
  integridad.
- No presentar un fixture local ni el agregado legacy como una descarga de
  `CloudSaveGameData`.
- No declarar aceptación por generar un archivo que el cliente no abrió o cuyo
  valor no se observó.
- No publicar credenciales, tokens, IDs, `cloudSaveId`, `platformId` ni hashes
  de la partida.

## 4. Criterio de salida de la fase

La fase solo se puede cerrar como éxito si existe una de estas dos evidencias,
con el mismo cliente y la misma cuenta:

- una restauración no-op aceptada y persistente, más una modificación de un
  campo aceptada y visible; o
- una descarga auténtica de `CloudSaveGameData` no vacío y una comparación
  reproducible con la partida local.

Todo lo demás es progreso parcial y debe etiquetarse como tal.

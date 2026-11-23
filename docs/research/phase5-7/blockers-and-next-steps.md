# Bloqueos y próximos pasos

## 1. Bloqueos actuales

| Bloqueo | Consecuencia | Evidencia | Qué falta exactamente |
| --- | --- | --- | --- |
| Cliente inestable en el AVD | No hay menú, no hay restauración, no hay captura | `SIGSEGV` en `libndk_translation` y en `libil2cpp`; [validación](official-client-validation.md) | Un dispositivo ARM estable o un build oficial que arranque |
| Sin token de juego | El gateway rechaza la lectura | `10001` sin token; `10015` con la sesión web; [adquisición](cloud-save-acquisition.md) | Un token emitido por el login oficial |
| Cuerpo de `AccountLogin` desconocido | No se puede reproducir el login en Linux | Firma `(string, string, callback, exp)`; `/UserAuth/Login` devuelve `10000` | El cuerpo/cabeceras exactos, observados en una sesión real |
| Esquema de éxito de la descarga desconocido | El proveedor HTTP no se puede validar | No hay respuesta con `CloudSaveGameData` | Una respuesta auténtica de `/Backup/GetBlobSave` o `/BlobSave/Download` |
| Sin `CloudSaveGameData` | No hay comparación ni `cloudSaveId`/`platformId` | [comparación](cloud-local-comparison.md) | La copia de nube |
| `CheckSaveMac`/MAC no resuelto | No se sabe si una copia editada pasará | Nombre del método; sin respuesta | Cuerpo del método o prueba de aceptación |
| `FixData` no decompilado | No se conoce la migración | [FixData](fixdata-analysis.md) | Cuerpo del método o prueba 8.6.0 → 8.8.0 |
| Límite de vinculaciones | Cada login de cuenta en emulador cuesta una | Documentación oficial: 5/90 días y 24 h | Reservar una vinculación para una prueba definitiva |

## 2. Orden recomendado

1. **Estabilizar el cliente.** Probar el APK oficial 8.8.0 en un dispositivo
   ARM físico o en un build que no dependa del pago Xiaomi. No usar el emulador
   inestable para una vinculación de cuenta.
2. **Reservar una vinculación.** Iniciar sesión una sola vez, con la cuenta de
   laboratorio, en el dispositivo estable. Registrar la versión, el perfil y el
   estado de sincronización.
3. **Restauración no-op.** Copiar la partida local auténtica, restaurarla,
   comprobar que el juego la acepta y que persiste tras reiniciar. Este es el
   mínimo de la fase.
4. **Modificación controlada.** Cambiar un solo campo escalar de bajo impacto,
   restaurar y observar si el cliente lo muestra y lo conserva.
5. **Descarga de nube.** Abrir el panel oficial, descargar el guardado y
   conservar el JSON/`Data` auténtico. Comparar con el local.
6. **Token de juego.** Con la sesión estable, capturar la petición
   `AccountLogin`/`AccessToken` en los límites de serialización, sin eludir TLS
   ni pinning. Usar el token solo en el proceso Linux autorizado.
7. **Validar el proveedor HTTP.** Confirmar ruta, cuerpo y esquema con la
   respuesta real. Etiquetar el resultado como lectura verificada solo entonces.
8. **FixData y MAC.** Leer los cuerpos en runtime con el cliente estable o
   probar la restauración 8.6.0. No implementar una migración especulativa.
9. **Escritura.** Solo después de 3–8, con copia remota y procedimiento de
   recuperación.

## 3. Qué no hacer

- No adivinar el cuerpo de `AccountLogin` con la cuenta real.
- No desactivar TLS, pinning, anti-cheat ni controles del proveedor.
- No parchear el cliente para saltar el pago, el consentimiento o la
  integridad.
- No presentar un fixture local como una descarga.
- No declarar aceptación por generar un archivo que el cliente no abrió.
- No publicar credenciales, tokens, IDs, `cloudSaveId`, `platformId` ni hashes
  de la partida.

## 4. Criterio de salida de la fase

La fase solo se puede cerrar como éxito si existe una de estas dos evidencias,
con el mismo cliente y la misma cuenta:

- una restauración no-op aceptada y persistente, más una modificación de un
  campo aceptada; o
- una descarga auténtica de `CloudSaveGameData` y una comparación reproducible
  con la partida local.

Todo lo demás es progreso parcial y debe etiquetarse como tal.

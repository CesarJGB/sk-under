# Validación de escritura en la nube

**Estado: NO IMPLEMENTADA.** No se realizó ninguna escritura remota. No hay
código de subida, no se ejecutó una prueba de subida y no se simuló un éxito.

## 1. Hipótesis

Si una copia modificada se acepta localmente y el cliente puede subirla, el
servidor debería devolver la nueva revisión y una descarga posterior debería
conservar la modificación. Antes de escribir hay que demostrar la lectura, la
serialización y la restauración local.

## 2. Por qué no se ejecutó

| Requisito previo | Estado | Consecuencia |
| --- | --- | --- |
| Descarga auténtica de la cuenta | Parcial: `FetchGameData` 200, agregado legacy vacío | No hay una revisión base no vacía que modificar |
| Token de juego válido | Sí, token de sesión del cliente (solo lectura) | Hay una sesión autorizada desde Linux, pero no se usó para escribir |
| Restauración no-op aceptada por el cliente | No concluyente | El cliente carga hasta login y el auto-login obsoleto se atasca |
| Modificación controlada aceptada localmente | No demostrada visiblemente | El archivo se conserva, pero el HUD no mostró el valor modificado |
| Contrato de `CheckSaveMac`/MAC | No | Una subida podría ser rechazada o marcar la cuenta |
| Comportamiento ante conflictos | No | No se sabe qué revisión gana ni cómo se recupera |
| Límite de vinculaciones | 5 por 90 días, 24 h entre ellas | Cada intento puede consumir una vinculación |

La regla de la fase es explícita: no se declara compatibilidad por generar un
archivo válido; hace falta que el cliente lo acepte y lo use. Sin ese paso, una
subida sería un experimento destructivo sobre la única copia de la cuenta.

## 3. Qué no se hizo

- No se llamó a `/BlobSave/Upload`, `/Backup/...` ni a ningún endpoint de
  escritura.
- No se creó un proveedor de escritura.
- No se reutilizó la sesión web para intentar una subida.
- No se modificó el cliente para habilitar una escritura.
- No se restauró una copia de la nube en el AVD.

## 4. Condiciones para habilitarla

1. Una descarga auténtica y una copia local del mismo estado.
2. Una restauración no-op observada en el cliente oficial, con persistencia
   tras cerrar y reabrir.
3. Una modificación de un solo campo, aceptada y persistente en el cliente.
4. El contrato de integridad (`CheckSaveMac`/MAC) resuelto o una prueba de que
   el servidor no lo exige.
5. Una copia de seguridad remota y local verificada.
6. Confirmación explícita del titular antes de la primera escritura.
7. Un procedimiento de recuperación probado, no solo documentado.

## 5. Riesgos

- Consumir una de las cinco vinculaciones de dispositivo.
- Sobrescribir la copia remota original sin una restauración viable.
- Activar controles de integridad o anti-cheat del proveedor.
- Interpretar un `200` como aceptación cuando el servidor solo guardó una
  revisión que el cliente luego rechaza.
- Publicar por accidente un token, un `cloudSaveId` o un guardado.

## 6. Conclusión

La escritura remota queda **fuera de alcance** en esta fase. No es un fallo de
implementación: es la decisión correcta mientras la lectura, la aceptación
local y el contrato de integridad no estén demostrados.

# Guía de validación con cuentas reales

**Objetivo:** comprobar el flujo autónomo de extremo a extremo con cuentas propias, sin que el administrador introduzca `distro_id` ni `unique_id`. **Estado actual:** la cuenta de laboratorio completó el flujo; las tres cuentas facilitadas fueron rechazadas por credenciales.

## 1. Antes de empezar

1. Verifica que puedes iniciar sesión en `https://accounts.chillyroom.com/login` con el correo y la contraseña. Si el portal rechaza la contraseña, el gateway también la rechazará; no es un problema de `distro_id`.
2. Si la cuenta se creó con Google Play y no tiene contraseña de ChillyRoom, el acceso por correo y contraseña no es posible. Usa el método que permita el proveedor; no intentes recuperar ni cambiar la contraseña desde SK-Under.
3. No ejecutes reintentos repetidos si ves `10001`, `429`, `100509` o un captcha. Detente y revisa.
4. Mantén `SK_NATIVE_WRITE_ENABLED=false` durante la validación inicial. La descarga y la preparación de un respaldo no escriben en la nube.

## 2. Matriz de cuentas

| Cuenta | Correo | Resultado de la Fase 6.9 | Qué falta |
| --- | --- | --- | --- |
| 1 | Correo privado del propietario | Gateway `10001`; portal rechaza credenciales. | Confirmar contraseña o método de acceso. |
| 2 | Correo privado del propietario | Gateway `10001`; portal rechaza credenciales. | Confirmar contraseña o método de acceso. |
| 3 | Correo privado del propietario | Gateway `10001`; portal rechaza credenciales. | Confirmar contraseña o método de acceso. |
| Laboratorio | Cuenta privada del propietario | Flujo autónomo completo; 114.779 bytes y 99.999 gemas. | Ninguno para solo lectura. |

No se publican contraseñas, tokens, correos completos, UIDs, `player.id`, `distro_id`, `unique_id` ni partidas. Los hashes de los correos están en [evidence.json](evidence.json).

## 3. Procedimiento por cuenta

1. Abre `/partida` en HTTPS.
2. Selecciona **Android Global**, introduce el correo y la contraseña.
3. Si el portal pide captcha o verificación, complétalo en el portal oficial y vuelve a intentarlo manualmente. SK-Under no resuelve desafíos.
4. Observa el resultado:
   - **Sesión activa + gemas**: el jugador correcto se encontró y la partida se descargó.
   - **`native_no_cloud_save`**: el jugador no tiene partida en la nube; no se creó ni se sobrescribió nada.
   - **`native_device_binding_throttled`**: ChillyRoom limita la vinculación de un dispositivo nuevo. Conserva el par y espera el plazo indicado; no regeneres identificadores.
   - **`native_portal_rejected` / `native_credentials_rejected`**: las credenciales no son aceptadas. No reintentes en masa.
5. Descarga la partida y verifica las gemas y el SHA-256 mostrados.
6. Prepara una edición (por ejemplo, gemas +1). No confirmes si la escritura está deshabilitada. Comprueba que se crea un respaldo y que el listado lo muestra.
7. Cierra sesión; verifica que la sesión queda inactiva.
8. Inicia sesión de nuevo. Debe reutilizar el mismo perfil, no consultar el portal y descargar la misma partida.
9. Repite con una segunda cuenta en un navegador/perfil distinto. Comprueba que no puede ver la partida, los respaldos ni la sesión de la primera. No se probó con las tres cuentas por el rechazo de credenciales.

## 4. Consulta directa del portal (diagnóstico)

El backend usa el portal oficial. Para diagnosticar credenciales sin pasar por el juego:

```bash
cd backend
uv run --locked python - <<'PY'
from app.native.portal import PortalClient
from app.native.errors import NativeError
try:
    p = PortalClient().profile('<correo>', '<contraseña>')
    print('ok', len(p.soulknight_players()))
except NativeError as exc:
    print(type(exc).__name__, exc.code)
PY
```

No ejecutes este bloque en masa. Si devuelve `native_portal_rejected`, la contraseña no es válida para el portal; el gateway dará `10001`.

## 5. Qué observar en los datos

- El navegador no debe recibir token, correo, `distro_id`, `unique_id`, `cloudSaveId`, `platformId` ni `player.id`.
- El almacén `native.sqlite3` no debe contener esos valores en claro; los perfiles y sesiones están cifrados.
- Los respaldos deben empezar por `SKB1` y no contener `"gems"` en claro.
- Los logs no deben contener la contraseña, el correo ni el token. Los errores solo muestran códigos estables.
- Tras reiniciar el contenedor, la cookie debe seguir activa (si no caducó) y los respaldos deben conservarse.

## 6. Si una cuenta falla

1. Comprueba el correo y la contraseña en el portal oficial.
2. Si el portal funciona pero el gateway da `10001`, revisa si la cuenta es solo Google Play o si el correo de la cuenta es distinto.
3. Si el portal devuelve `native_portal_identity_mismatch` o el jugador no coincide, no fuerces el perfil: conserva la evidencia y repórtalo.
4. Si aparece `100509`, espera el plazo; no generes un `unique_id` nuevo para saltarlo.
5. No cambies la contraseña, no des de baja la cuenta ni ejecutes migraciones destructivas para “probar”.

## 7. Criterio de aceptación

Una cuenta se considera validada cuando:

- inicia sesión solo con distribución, correo y contraseña;
- el backend resuelve el jugador y el par de instalación sin intervención del administrador;
- descarga una partida válida y muestra las gemas;
- prepara una edición y un respaldo cifrado;
- cierra y vuelve a iniciar sesión sin perder el perfil;
- no puede acceder a datos de otra cuenta.

La Fase 6.9 cumple ese criterio con la cuenta de laboratorio. Para las tres cuentas facilitadas falta la autenticación; no se puede validar el resto sin credenciales aceptadas por el proveedor.

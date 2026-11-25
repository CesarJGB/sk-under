# Dashboard multicuenta y navegación contextual

Esta iteración convierte la portada en un **dashboard de cuentas** y separa la navegación por cuenta sin cambiar el protocolo de guardado ni el editor existente.

## Flujo de interfaz

- `/` muestra el dashboard: cuentas vinculadas, estado de sesión y tarjeta **Añadir cuenta**. No descarga partidas ni muestra estadísticas.
- `/cuentas/nueva` reutiliza el formulario de acceso de ChillyRoom (distribución, correo, contraseña, perfil opcional, errores y aprovisionamiento automático).
- `/cuentas/:accountId/partida` y `/cuentas/:accountId/editor` conservan las categorías del editor (`/editor/categoria/:categoria`). El selector de cuenta solo elige una cuenta; la autorización siempre se valida en el servidor.
- El encabezado interno comparte hamburguesa, marca y un cajón con la cuenta actual, Partida, Editor y Volver al inicio. El dashboard no tiene cajón.
- Las rutas antiguas `/partida` y `/editor` siguen funcionando: sin cuentas llevan a añadir una, con una sola cuenta redirigen a su contexto y con varias vuelven al dashboard.
- `sk-under.hide-email` centraliza la ocultación visual del correo en dashboard, tarjetas, cajón, Partida y Editor. Con varias cuentas ocultas se usan identificadores no sensibles («Cuenta 1», «Cuenta 2»). Solo se persiste el booleano.

## Sesiones multicuenta

La cookie HttpOnly existente sigue agrupando el navegador. El servidor crea una sesión autorizada independiente por cuenta y una asociación interna con un selector opaco de 32 caracteres hexadecimales. Las operaciones envían `X-SK-Account`; el backend comprueba que el selector pertenece a la cookie del navegador antes de resolver la sesión, el perfil y los respaldos.

- Añadir una cuenta no revoca las demás.
- Desvincular una cuenta revoca solo su sesión y su asociación; no elimina el perfil persistente ni los respaldos históricos.
- Cada cuenta conserva su caducidad, límites de escritura, descarga y borrador en memoria.
- Una cookie de sesión única anterior se migra a una asociación de navegador al primer uso, sin invalidarla.
- El estado descargado se reutiliza entre Partida y Editor dentro del mismo navegador; una recarga completa lo vuelve a pedir. No se guardan correos, contraseñas, tokens ni partidas en `localStorage`.

## Validación

- `backend/tests/test_native_accounts.py` cubre alta simultánea, aislamiento entre navegadores, cierre selectivo, migración de sesión única y reautenticación.
- Las suites existentes de tienda, API, login automático, editor y navegador se mantuvieron verdes.
- La validación de navegador usa proveedores simulados: no se subieron ni restauraron partidas en cuentas reales de ChillyRoom.

## Despliegue

El cambio es compatible con las rutas y cookies anteriores. Conviene desplegar primero el backend (nuevos `/accounts` y validación del selector) y después el frontend. Las sesiones existentes siguen siendo válidas; no es necesario borrar la base SQLite ni los perfiles cifrados.
# Fase 6.5 · Autenticación de ChillyRoom

**El acceso autónomo desde `/partida` sigue bloqueado.** ChillyRoom autentica a la cuenta de laboratorio en su portal web. La sesión que obtiene el navegador sirve para administrar esa cuenta en el portal. Al abrir SK Under en el mismo navegador, la API sigue devolviendo cero cuentas y ninguna sesión activa. Hace falta un intercambio que ChillyRoom autorice para SK Under y que conceda acceso a la partida de la identidad autenticada.

Investigación realizada el 23 de noviembre de 2026 a partir de `c0714a0`. Los resultados reproducibles están en [evidence.json](evidence.json). La emisión de una sesión nueva en el juego y su aceptación en BlobSave quedaron registradas en la [Fase 6.4](../phase6-4/authentication.md).

## Producción desde un navegador limpio

Un contexto nuevo de Chromium, con cero cookies, abrió directamente `https://sk.underdive.space/partida`. Pages respondió `200`. La API de Coolify respondió `200` en `/api/v1/health` y en `GET /api/v1/cloud/accounts`. El almacén estaba listo y el formulario mostraba el acceso por contraseña deshabilitado, con cero cuentas y sin opción de descargar una partida.

Desde esa página, un `POST /api/v1/cloud/accounts/login` con el origen real y un cuerpo JSON vacío devolvió `503 cloud_login_unavailable` y `Cache-Control: no-store`. El navegador siguió sin cookie de SK Under. La comprobación utilizó cero credenciales y cero tickets.

## Vías de autorización investigadas

| Vía | Observación |
| --- | --- |
| Portal oficial de cuentas | El control **Login** del sitio oficial abre `accounts.chillyroom.com/login` con `redirectTo` apuntando a la raíz del propio portal. La cuenta de laboratorio obtuvo `200` y abrió **Account Management**. La pantalla ofreció cambiar la contraseña, vincular correo y gestionar la baja de la cuenta. El recorrido observado terminó dentro del portal, sin consentimiento para SK Under ni opción de descargar la partida. [Soporte oficial](https://www.chillyroom.com/en/support/58) · [Portal de cuentas](https://accounts.chillyroom.com/login) |
| Portal y SK Under en el mismo navegador | Tras el acceso válido al portal se abrió `/partida` en otra pestaña del mismo contexto. La API de SK Under respondió `200` con `session_active=false`, cero cuentas y ninguna cookie propia. Es el límite observado del flujo público del portal, incluida su redirección de vuelta. |
| Descubrimiento de OAuth y OpenID Connect | Los dos documentos estándar devolvieron `404` en el sitio corporativo, el sitio de Soul Knight y su gateway. En el dominio del portal ambos devolvieron `200 text/html` con el mismo documento HTML que su raíz. La revisión de fuentes oficiales en inglés y chino tampoco localizó registro de aplicaciones, emisor publicado, callback autorizado o permisos de guardado para terceros. |
| Vinculación y verificaciones oficiales | El manual documenta confirmación de correo para alta y restablecimiento, vinculación de compras y la descarga `Retrieve Progress` dentro del juego. Las reglas de guardado indican que la identidad de ChillyRoom y la de Google pueden corresponder a partidas distintas incluso si usan el mismo correo. El correo por sí solo carece de valor como prueba de titularidad de la partida. [Manual de Android](https://soulknight.chillyroom.com/et/article/base/3) · [Límites de guardado](https://soulknight.chillyroom.com/et/article/base/4) · [FAQ oficial](https://soulknight.chillyroom.com/et/article/base/6) |

La cuenta de laboratorio, con una contraseña incorrecta, recibió `400` y quedó en la pantalla de acceso del portal sin iniciar sesión. Un correo generado en el dominio reservado `example.invalid` recibió `400` y el mensaje `Account does not exist.`. Cada prueba comenzó en un contexto independiente y usó el formulario oficial. Las contraseñas, cookies, tokens, correos e identificadores de cuenta quedaron fuera de la evidencia.

## Qué falta para implementar el acceso

La evidencia confirma autenticación web de la cuenta y, por separado, una descarga real con la sesión del juego ya configurada en el laboratorio de Coolify (`200`, 114 778 bytes y 1 002 gemas). No se verificó ningún mecanismo autorizado para convertir la autenticación web en permiso de lectura del guardado. Los resultados de descubrimiento se limitan a los dominios y rutas comprobados. Un acceso para socios puede existir y requiere confirmación del proveedor.

Para completar la integración, ChillyRoom tendría que confirmar un flujo autorizado que devuelva a SK Under una autorización verificable y limitada al titular, o documentar un intercambio permitido para terceros. El contrato debe especificar cómo registrar la aplicación, acreditar el consentimiento, completar los desafíos en el proveedor y obtener un identificador estable junto con un permiso aceptado por BlobSave o por la API de guardado que ChillyRoom indique. También se necesitan sus reglas de caducidad, renovación y revocación. El canal público para consultar esta posibilidad figura en el [soporte oficial](https://www.chillyroom.com/en/support/58).

Cuando haya un contrato verificable, la prueba de aceptación debe partir de `/partida` en un navegador limpio. SK Under debe verificar la autorización y la correspondencia con el titular antes de emitir su cookie. El backend debe cifrar la sesión, limitar los intentos y permitir que el usuario complete cualquier desafío en ChillyRoom sin guardar su contraseña. Para comprobar aislamiento se necesitan dos cuentas autorizadas con partidas independientes.

## Regresión del acceso con vinculación privada

En producción se reutilizó la sesión de juego ya emitida para vincular la cuenta de laboratorio en modo de solo lectura. Chromium descargó su partida desde `/partida` antes y durante el despliegue de `919c4ca`. Con el contenedor nuevo saludable se repitió la descarga. La cookie y el SHA-256 de la partida coincidieron.

En otra prueba con esa revisión, el cierre de sesión desde Pages devolvió `204`, eliminó la cookie y dejó su repetición con `401 cloud_browser_required`. Un nuevo ticket reconectó la misma cuenta y permitió descargar la misma partida. El ticket fijó una vigencia local de 40 segundos para probar la caducidad de forma controlada. Después del plazo, SK Under marcó la cuenta como desconectada y su API devolvió `409 cloud_session_expired`. La caducidad y la renovación en el proveedor quedan pendientes.

## Estado de las pruebas

| Caso | Evidencia real | Regresión automatizada |
| --- | --- | --- |
| Acceso válido | Portal oficial con la cuenta de laboratorio. En SK Under el acceso autónomo devolvió `503`. | El formulario y la ruta siguen bloqueados. |
| Contraseña incorrecta | `400` en el portal oficial para la cuenta de laboratorio. | SK Under no envía credenciales al proveedor. |
| Cuenta inexistente | `400` en el portal oficial para una dirección generada en `example.invalid`. | Sin intercambio directo en SK Under. |
| Descarga del titular | Partida real leída en Coolify con una sesión de laboratorio ya emitida. | Pruebas de identidad y descarga con fixtures. |
| Cierre y revocación de la cookie | Cierre desde Pages y `401` al reutilizar la cookie del recorrido vinculado. | Revocación, repetición y conservación del historial. |
| Nuevo acceso después del cierre | Descarga de la misma partida tras la reconexión por ticket. El acceso autónomo sigue pendiente. | Reconexión de la cuenta vinculada con otro ticket. |
| Aislamiento de dos cuentas | Disponible una sola identidad autorizada con partida validada. | Dos identidades simuladas y rechazo de lecturas cruzadas. |
| Persistencia tras recrear el contenedor | Descarga con la misma cookie durante el despliegue de `919c4ca`. En la [Fase 6.4](../phase6-4/evidence.json) también se verificó el historial tras recrear. | Reapertura del mismo almacén con las mismas credenciales de cifrado. |
| Caducidad | `409` tras vencer la vigencia local controlada de la sesión vinculada. Falta la caducidad real del proveedor y su renovación. | Caducidad local y rechazo remoto simulado. |

Regresión local con las dependencias bloqueadas del repositorio. Backend compilado y `340` pruebas aprobadas, con `16` omitidas que requieren muestras privadas. El build de TypeScript y Vite pasó. Pasaron `14` pruebas de Chromium y `4` pruebas de cuentas en WebKit. Las suites de cuentas usan fixtures o respuestas interceptadas.

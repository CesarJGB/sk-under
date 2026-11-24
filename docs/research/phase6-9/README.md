# Fase 6.9 · Autenticación autónoma y validación real

**Rama:** `feature/phase6-9-autonomous-auth` · **Base:** `9163668` (Fase 6.8) · **Estado:** flujo autónomo real completado con la cuenta de laboratorio; validación con las tres cuentas facilitadas bloqueada por rechazo de credenciales.

La Fase 6.9 resuelve la limitación central de la Fase 6.8: el usuario ya no necesita que el administrador aprovisione `x-distro-id` ni `x-unique-id`. El backend consulta el portal oficial de cuentas, recupera el distro del jugador de Soul Knight, genera un código de instalación nuevo, lo cifra y lo conserva, autentica en el gateway y descarga la partida. En la prueba real, ese flujo funcionó de extremo a extremo con la cuenta de laboratorio: portal → login → descarga de **114.779 bytes** con **99.999 gemas** → edición preparada → respaldo cifrado → reinicio del proceso → sesión persistente → descarga → cierre de sesión → nuevo acceso.

## 1. Resultado frente a los niveles de éxito

| Nivel | Estado | Evidencia |
| --- | --- | --- |
| Mínimo | **Cumplido** | Investigación reproducible de los identificadores, pruebas reales con la cuenta de laboratorio y delimitación precisa de los requisitos del proveedor. |
| Principal | **Cumplido** | Autenticación real con una cuenta nueva desde el flujo web, sin aprovisionamiento manual, y descarga válida de su partida. |
| Avanzado | **Parcial** | Una cuenta real con sesiones independientes, reinicio del proceso y persistencia. Las tres cuentas no se pudieron validar porque la contraseña facilitada es rechazada por el gateway y por el portal. |
| Completo | **Pendiente** | Falta la validación real de las tres cuentas y la confirmación de autorización del proveedor para uso de terceros. |

El criterio fundamental de aceptación se cumple para la cuenta validada: un usuario nuevo no necesita que el administrador introduzca identificadores. El backend los resuelve y los conserva. La limitación restante para las otras cuentas es externa: las credenciales entregadas no autentican.

## 2. Qué se descubrió (resumen)

La investigación completa está en [identifiers.md](identifiers.md) y la cronología en [experiments.md](experiments.md).

- **`x-distro-id` no es una credencial de cuenta ni un UUID arbitrario sin consecuencias.** El gateway acepta UUID v4, pero el valor selecciona un **jugador**. Un UUID nuevo crea un jugador vacío; para acceder a la partida existente hay que usar el distro que corresponde a ese jugador. El portal oficial expone `registerDistroId` y `lastLoginDistroId` por jugador. El `lastLoginDistroId` de la cuenta de laboratorio funcionó para el login y para BlobSave.
- **`x-unique-id` es el código de instalación.** La forma observada es `xiaomioutseas_` + 16 dígitos hexadecimales. BlobSave lo exige y lo vincula al dispositivo. Un valor nuevo puede fallar con `100509` (límite de vinculación de dispositivos) o funcionar si el jugador ya está resuelto y la cuenta admite la vinculación. El backend lo genera una vez, lo cifra y lo reutiliza.
- **`100504` significa que el jugador no tiene partida en la nube.** Es la señal que permitió descartar jugadores vacíos y elegir el jugador correcto.
- **El portal oficial es la pieza que faltaba.** No expone la partida, pero sí la lista de jugadores y sus distros. Es una consulta de solo lectura autenticada con las mismas credenciales. El cliente usa la sesión efímera del portal y la descarta; no guarda cookies, tokens ni contraseñas.
- **`cloudSaveId` (`GPV2_<uid>`) y `platformId` (`GP`)** identifican la copia, no la instalación. No son `x-distro-id` ni `x-unique-id` y no se usaron para sustituirlos.
- **`ChillyUid`** sigue siendo un campo local de `SettingData`; no se usó como credencial ni como identificador de instalación.

## 3. Flujo autónomo implementado

1. El usuario selecciona **Android Global**, correo y contraseña.
2. El backend reserva un intento de forma atómica y consulta el portal oficial.
3. El portal devuelve los jugadores de Soul Knight con `registerDistroId` y `lastLoginDistroId`.
4. El backend genera un `distro_id` de respaldo y un `unique_id` nuevo, y prueba los jugadores del portal con el mismo par:
   - `100504`: el jugador no tiene partida; se prueba el siguiente.
   - `100509`: el jugador existe pero el proveedor limita la vinculación; se selecciona y se guarda la espera.
   - `200`: se descarga y se fija la identidad de guardado.
5. Se crea un perfil cifrado por cuenta, ligado al hash del correo, al subject de identidad y al subject de guardado. El par de instalación queda cifrado con AES-SIV y se reutiliza en todos los accesos posteriores.
6. Se emite una cookie de sesión aislada. El navegador nunca recibe token, correo, `distro_id`, `unique_id`, `cloudSaveId` ni `platformId`.
7. Si no hay jugadores en el portal (cuenta nueva), se genera una instalación nueva y se informa si aún no existe partida en la nube.
8. Si el portal rechaza las credenciales o pide un desafío, no se inventa un jugador ni se simula una sesión: se devuelve un error estable.

La consulta al portal ocurre una sola vez por cuenta; los accesos posteriores usan el perfil guardado y no vuelven a llamar al portal. Dos primeras solicitudes concurrentes de la misma cuenta se serializan para no duplicar la vinculación. Si ya existe un perfil de la Fase 6.8 vinculado al mismo subject, se reutiliza en lugar de crear otro; si su par guardado es obsoleto, se actualiza solo después de verificar la misma identidad y se descarga la partida con el par nuevo.

## 4. Pruebas reales

### 4.1 Flujo autónomo completo (cuenta de laboratorio)

Ejecución real desde Linux, sin emulador, el 24 de noviembre de 2026. Los valores completos saneados están en [evidence.json](evidence.json).

| Comprobación | Resultado |
| --- | --- |
| Portal oficial | `200`; una sola consulta; dos jugadores de Soul Knight visibles. |
| Selección del jugador | El primer jugador devolvió `100504` (sin partida); el segundo, el jugador de laboratorio, devolvió la partida. |
| Identidad | `player.id` del gateway coincidió con el `pid` del portal. |
| Login | `200`, sesión nueva; `auto_identity=true`. |
| Descarga | `114.779` bytes, `99.999` gemas, SHA-256 `ace7c58b3c7776ce26afe4f18a362d819b804984b7ca37b3e4aab2bc5d82cfb1`. |
| Edición preparada | `99.999 → 100.000`; solo cambió `gameData.gems`; no se subió. |
| Respaldo | 1 respaldo; `original.json`, `candidate.json`, `record.json` y `events.jsonl` empiezan por `SKB1`; ninguno contiene `"gems"` en claro. |
| Reinicio | Proceso nuevo con el mismo almacén y clave; la cookie siguió activa y la descarga volvió a dar `99.999` gemas. |
| Cierre de sesión | `204`; la sesión local quedó inactiva. |
| Nuevo acceso | `200`; misma partida; no se consultó el portal de nuevo; un solo perfil. |

### 4.2 Flujo con perfil administrativo (control)

También se ejecutó el flujo con un perfil administrativo que contiene el par original de la instalación de laboratorio, para comparar con la Fase 6.8. La descarga fue el mismo SHA-256 y el mismo tamaño; el respaldo quedó cifrado; el cierre de sesión devolvió `204`, la cookie se revocó y un login nuevo descargó la misma partida.

### 4.3 Matriz de las tres cuentas facilitadas

Se probó el portal oficial una vez por cuenta y el gateway una vez por cuenta con la contraseña indicada. **Las tres fueron rechazadas.**

| Cuenta | Correo (SHA-256) | Gateway | Portal | Resultado |
| --- | --- | --- | --- | --- |
| 1 | `a8ba83b9f73f…` | `400` / `10001` | credenciales rechazadas | No se pudo continuar. |
| 2 | `ed92b9fffd9f…` | `400` / `10001` | credenciales rechazadas | No se pudo continuar. |
| 3 | `83954491d749…` | `400` / `10001` | credenciales rechazadas | No se pudo continuar. |

No se hicieron reintentos ni fuerza bruta. El gateway devuelve `10001` para “cuenta o contraseña incorrecta”. El portal devuelve el mismo rechazo para la misma contraseña. Esto descarta que el problema sea el `distro_id` o el `unique_id`: las credenciales no son aceptadas antes de llegar a esa etapa. La validación multicuenta real queda pendiente de que el propietario confirme las contraseñas o el método de acceso de esas cuentas (por ejemplo, si están vinculadas solo a Google Play y no tienen contraseña de ChillyRoom). No se solicitan ni se almacenan credenciales nuevas en el repositorio.

## 5. Identificadores: respuesta a las preguntas de la fase

| Pregunta | Respuesta respaldada |
| --- | --- |
| ¿`x-distro-id` pertenece a una distribución? | Es un UUID de contexto de jugador/instalación. No es una constante de versión: un UUID nuevo crea un jugador vacío. |
| ¿Cambia entre cuentas? | Sí. Cada jugador tiene su propio distro; el portal lo expone por jugador. |
| ¿Depende de la instalación, versión o plataforma? | Depende del jugador y de la instalación. El portal muestra `registerDistroId` y `lastLoginDistroId`; ambos pueden ser iguales o distintos. El alcance validado es Android Global 8.8.0. |
| ¿Hay una configuración pública o un mecanismo autorizado para obtenerlo? | Sí: el portal oficial autenticado devuelve los distros de los jugadores. No se usó un canal privado ni se eludió ningún control. |
| ¿Puede administrarse automáticamente? | Sí, consultando el portal una vez y guardando el distro cifrado. |
| ¿`x-unique-id` es de instalación, dispositivo o sesión? | De instalación/dispositivo. No es una sesión: el login funciona sin él, pero BlobSave lo exige y lo vincula. |
| ¿Tiene relación verificable con la identidad de la cuenta? | La tiene con el jugador y el dispositivo; no es el `uid` ni el `player.id`. El backend lo asocia al perfil y verifica el subject de guardado en cada descarga. |
| ¿Existe generación/registro legítimo? | El cliente lo genera; el servidor lo registra/vincula. El backend genera uno nuevo con el formato observado y respeta el límite `100509` si aparece. |
| ¿Necesita persistir? | Sí. Regenerarlo en cada acceso puede consumir vinculaciones y romper la continuidad. Se guarda cifrado y se reutiliza. |
| ¿Una cuenta puede acceder desde distintas instalaciones legítimas? | Sí, con el límite del proveedor. El portal permite localizar el jugador; un dispositivo nuevo puede vincularse, sujeto a la frecuencia que impone ChillyRoom. |

El detalle, incluida la corrección de la hipótesis de la Fase 6.7 sobre el UUID aleatorio, está en [identifiers.md](identifiers.md).

## 6. Cambios de backend

- `backend/app/native/portal.py`: cliente del portal Redwood, autenticación con cookies efímeras, CSRF y consulta GraphQL `Profile`. Extrae `pid`, `registerDistroId` y `lastLoginDistroId`; valida el correo devuelto; no guarda nada.
- `backend/app/native/identity.py`: generación del UUID v4 y del código `xiaomioutseas_<16 hex>`, con validación estricta.
- `backend/app/native/store.py`: migración de la tabla de perfiles; `email_hash`, `auto_generated`, `binding_wait_until`, `last_save_error`; búsqueda por hash de correo; reserva atómica de intentos; limpieza de sesiones/perfiles.
- `backend/app/native/service.py`: descubrimiento de jugador, selección por `100504`/`100509`, reutilización del perfil, bloqueo de descubrimiento concurrente, sesiones y respaldos cifrados.
- `backend/app/cloud/provider.py` y `modern.py`: errores tipados `100504`, `100505` y `100509`, con `Retry-After` y sin conservar el cuerpo remoto.
- `backend/app/cloud/backup_store.py`: cifrado AES-SIV de respaldos y migración de respaldos antiguos.
- `backend/app/net.py`: IP real solo desde proxies confiables.
- `backend/app/security_headers.py`: CSP de API, HSTS en producción HTTPS y cabeceras de seguridad.
- `backend/app/main.py`, `settings.py`: nuevas variables y middleware.
- `backend/app/native/maintenance.py`: `migrate-backups`, `cleanup` y listado administrativo saneado.

## 7. Cambios de frontend

- El formulario de `/partida` ya no pide `distro_id`, `unique_id` ni selección de perfil en el flujo normal. Solo distribución, correo y contraseña.
- Se muestra el estado de identidad generada, la espera de vinculación (`100509`), la ausencia de partida (`100504`), el desafío del portal y los errores de credenciales sin filtrar secretos.
- La CSP se inyecta en el HTML con el origen exacto de `VITE_API_BASE_URL`; `_headers` añade cabeceras de seguridad.
- La vía administrativa de `/partida` permanece oculta salvo para perfiles migrados sin instalación; el flujo por enlace de la Fase 6.3 sigue en `/partida/vinculadas`.

## 8. Pruebas automatizadas

- **Backend:** 440 pruebas aprobadas, 16 omitidas por requerir muestras privadas. Incluyen portal, identidad, selección de jugador, `100504`, `100509`, aislamiento de dos cuentas, reserva atómica concurrente, migración de esquema, cifrado de respaldos, CSP, proxies confiables y redacción de secretos.
- **Frontend:** TypeScript y Vite compilan; 25 pruebas Playwright en Chromium (11 del acceso nativo), incluidas ausencia de identificadores manuales, espera de vinculación, ausencia de partida, desafío del portal, aislamiento visual y solo lectura.
- Las pruebas no abren red: el portal, el cliente de autenticación y el proveedor se inyectan.

Reproducción:

```bash
cd backend
uv sync --locked
uv run --locked pytest -q

cd ../frontend
npm ci
npm run build
npx playwright install chromium
npm run test:browser
```

## 9. Limitaciones restantes

1. **Credenciales de las tres cuentas:** la contraseña facilitada es rechazada por el gateway y el portal. Sin credenciales válidas no se puede completar la validación multicuenta. No se intentó fuerza bruta ni recuperación de contraseña.
2. **Autorización del proveedor:** el portal es una interfaz oficial y la consulta es de solo lectura, pero no hay confirmación de ChillyRoom para el uso de terceros ni un contrato de integración. El servicio debe permanecer privado.
3. **Límite de dispositivos:** la página oficial documenta 5 vinculaciones por cuenta cada 90 días y al menos 24 horas entre vinculaciones. El backend respeta `100509`, conserva el par y no reintenta; no lo evita.
4. **Desafíos del portal:** captchas, 2FA o bloqueos no se resuelven automáticamente. El usuario debe completarlos en el portal; el backend devuelve un error estable.
5. **Múltiples jugadores:** si una cuenta tiene varios, el backend prueba hasta 8 y elige el que devuelve partida o la primera espera de vinculación. No hay una etiqueta de jugador en el portal para mostrar una elección humana.
6. **Una sola réplica:** SQLite y el bloqueo de descubrimiento son de proceso; un despliegue con varios workers necesita un almacén compartido.
7. **Escritura real:** sigue deshabilitada por defecto y no se probó una subida en esta fase. Las pruebas reales fueron de solo lectura y de preparación de respaldo.
8. **CSP dinámica:** el `connect-src` exacto se fija al compilar con `VITE_API_BASE_URL`; si se cambia el dominio de la API hay que recompilar o ajustar la CSP del proxy.

## 10. Riesgos de seguridad

El detalle está en [security.md](security.md). Los principales:

- La contraseña se comparte con el portal oficial; un compromiso del proceso mientras atiende un login podría exponerla. No se persiste ni se registra.
- El portal puede imponer captchas o límites; automatizarlo sin autorización expresa del proveedor es un riesgo de cumplimiento.
- El `distro_id` y el `unique_id` son identificadores sensibles; se cifran con AES-SIV y nunca se devuelven al navegador.
- Los respaldos contienen progreso real; ahora se cifran en reposo con una clave derivada o explícita.
- El cierre de sesión local no revoca el token en ChillyRoom.
- Un XSS podría actuar como el usuario mientras la cookie esté activa; la CSP y la ausencia de tokens en JavaScript reducen el impacto.

## 11. Preparación para Coolify

La imagen y el runbook están preparados: un worker, un volumen `/var/lib/sk-under`, HTTPS, `SK_NATIVE_ORIGIN` exacto, `SK_NATIVE_STORE_KEY`/`SK_NATIVE_BACKUP_KEY`, `SK_NATIVE_TRUSTED_PROXIES` para el proxy y `SK_NATIVE_AUTO_IDENTITY=true`. No se desplegó ni se modificó Coolify desde esta sesión. Los pasos están en [deployment.md](deployment.md).

## 12. Commits publicados

Rama `feature/phase6-9-autonomous-auth`, publicada en `origin`:

| Commit | Contenido |
| --- | --- |
| `d8d40d5` | Backend: portal, identidad autónoma, selección de jugador, `100504`/`100509`, migración del almacén, respaldos cifrados, CSP, IP de proxy y límite atómico. |
| `3027d73` | Frontend: formulario sin identificadores manuales, estados de vinculación/partida/desafío y CSP. |
| `b39d9e9` | Documentación, evidencia saneada, runbook de Coolify y guía de pruebas. |
| `f421e1c` | Registro de los commits publicados de la rama. |
| `9c6606e` | Reutilización de perfiles vinculados de la Fase 6.8 y pruebas de migración. |

No se hizo merge a `main` ni se desplegó públicamente.

## Documentos de la fase

- [Identificadores](identifiers.md)
- [Experimentos](experiments.md)
- [Seguridad](security.md)
- [Despliegue en Coolify](deployment.md)
- [Guía de pruebas manuales](manual-testing.md)
- [Evidencia saneada](evidence.json)

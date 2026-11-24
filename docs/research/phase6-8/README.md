# Fase 6.8 · Integración web de autenticación nativa

**Rama:** `feature/phase6-8-web-native-auth` · **Base:** `25219a2` (Fase 6.7) · **Estado:** implementado y probado con transporte simulado; la prueba real con la cuenta de laboratorio y la validación multicuenta real quedan pendientes del propietario.

Esta fase convierte el cliente experimental de la Fase 6.7 en una aplicación web privada: formulario de acceso con distribución, correo y contraseña; verificación de identidad; sesión aislada por cuenta; perfiles de instalación cifrados; descarga, edición, respaldo, confirmación y verificación de gemas con los componentes existentes.

No se reconstruyó nada de las fases anteriores. Se reutilizan `ModernCloudSaveProvider`, `BlobSaveUploader`, `CloudLabService`, `LabBackupStore`, el editor de gemas, las validaciones de integridad y el flujo de cuentas vinculadas (que sigue disponible en `/partida/vinculadas`).

## 1. ¿Qué componentes se integraron?

| Componente | Ubicación | Origen |
| --- | --- | --- |
| Cliente de autenticación nativa | `backend/app/native/client.py` | contrato de la Fase 6.7, con transporte inyectable |
| Registro de distribuciones | `backend/app/native/distributions.py` | nuevo, seis distribuciones; solo GP habilitada |
| Almacén cifrado de perfiles y sesiones | `backend/app/native/store.py` | AES-SIV y SQLite, patrón del almacén de la Fase 6.3 |
| Servicio de sesión y editor | `backend/app/native/service.py` | nuevo orquestador; reutiliza el laboratorio de gemas |
| API privada | `backend/app/api/native.py` | rutas `/api/v1/cloud/native/*` |
| CLI de aprovisionamiento | `backend/app/native/provision.py` | nuevo; sin red y sin eco |
| Configuración | `backend/app/settings.py` | `SK_NATIVE_*` |
| Formulario y editor | `frontend/src/pages/NativeAuthPage.tsx` | nuevo; estética y clases existentes |
| Cliente HTTP del frontend | `frontend/src/api.ts` | `nativeAuth` |
| Pruebas | `backend/tests/test_native_*.py`, `frontend/tests/native-auth.spec.ts` | nuevas |
| Despliegue | `backend/Dockerfile`, `.env.example`, `docs/research/phase6-8/deployment.md` | directorios persistentes y runbook |

La API no usa una sesión global. Cada cookie resuelve un perfil y un subject propios; no hay `account_id` en las URL. El token del proveedor nunca llega al navegador.

## 2. ¿Qué se descubrió sobre los identificadores?

El análisis completo, con niveles de evidencia, está en [identifiers.md](identifiers.md). Resumen:

- **`x-distro-id`**: cabecera obligatoria del login observado. El gateway rechaza su ausencia (`502/10003`) y un UUID aleatorio (`400/10003`). No es el identificador de cuenta, no sustituye a la contraseña y no se demostró que sea compartido por versión ni único por instalación. Es un identificador de contexto validado; el backend lo guarda cifrado en un perfil.
- **`x-unique-id`**: identificador de instalación. No es necesario para el login, pero BlobSave lo exige y rechaza uno nuevo. No se demostró que sea igual a `ChillyUid`, `platformId` o `x-distro-id`.
- **`platformId` / `cloudSaveId`**: campos del agregado `CloudSaveGameData`; identifican el guardado. El backend deriva de ambos un subject HMAC y lo fija en la primera descarga.
- **`ChillyUid`**: campo local de `SettingData` en `setting_*.data`, protegido por el puente. No hay evidencia de que sea `x-unique-id`, de que autentique o de que se pueda copiar entre cuentas.
- **`player.id`, `session.uid`, `user.id`**: identidad de cuenta/jugador en la respuesta de login. `session.uid == user.id` se exige; `player.id` es un valor distinto y se usa junto al correo para derivar el subject.
- **Token de sesión**: credencial opaca de ~7 días, distinta en cada login; se cifra con AES-SIV y se asocia a la sesión web. No es un identificador de cuenta.
- **`_crde_misc.platformId`**: no aparece en el formato original ni en el repositorio. Es compatible con metadata añadida por una herramienta externa. **No se asume equivalente** a `CloudSaveGameData.platformId` ni a `x-distro-id`; no se usa para identidad.

La hipótesis del propietario queda así: la parte “identificador compartido por versión” es posible pero no está demostrada; la separación entre identidad de autenticación, instalación, guardado y sesión sí es consistente con toda la evidencia.

## 3. ¿Qué funcionalidades web están realmente disponibles?

Con `SK_NATIVE_AUTH_ENABLED=true`, un origen HTTPS autorizado, `SK_NATIVE_STORE_KEY` y un perfil Android Global aprovisionado:

- Formulario de acceso con selector de las seis distribuciones (solo Android Global habilitada), correo, contraseña, mostrar/ocultar, indicador de proceso y errores comprensibles.
- Login nativo contra el gateway, verificación de identidad y creación de sesión aislada.
- Estado de identidad verificada, caducidades y cierre de sesión.
- Estado de instalación pendiente y formulario para completar el identificador de instalación de la propia cuenta.
- Descarga de la partida, lectura de gemas, preparación determinista, respaldo privado, validación, confirmación explícita, subida y verificación posterior.
- Listado de respaldos, verificación de la nube y restauración.
- Solo lectura por defecto; la escritura requiere `SK_NATIVE_WRITE_ENABLED=true`, permiso del perfil y confirmación.
- El flujo anterior por enlace privado sigue en `/partida/vinculadas`.

Las demás distribuciones aparecen deshabilitadas y no se usan para autenticar. iOS no se presenta como funcional.

## 4. ¿Qué pruebas reales se realizaron?

**Ninguna petición real nueva en esta fase.** El entorno de esta sesión no contenía credenciales de ChillyRoom, un `distro_id`/`unique_id` aprovisionado ni acceso al despliegue de Coolify. No se solicitó ni se almacenó la contraseña del propietario. No se hicieron reintentos ni pruebas de carga contra el proveedor.

La última validación real del contrato sigue siendo la Fase 6.7: login Linux, identidad, descarga de 114.779 bytes y comparación de SHA-256 con el emulador detenido ([evidence.json](../phase6-7/evidence.json)). La Fase 6.8 reutiliza ese contrato, pero **no repite esa ejecución**.

La validación multicuenta real tampoco se realizó. La infraestructura y las pruebas simuladas están listas; el propietario debe ejecutar la [guía de pruebas manuales](manual-testing.md).

## 5. ¿Qué pruebas fueron simuladas?

- **Backend:** 380 pruebas aprobadas y 16 omitidas por requerir muestras privadas. De ellas, 40 son nuevas de la Fase 6.8:
  - cliente nativo (11): cabeceras, cuerpo, gzip, límites, `10003`, `429`, red, identidad contradictoria, `repr` sin secretos;
  - almacén (7): cifrado, binding de identidad, caducidad, inactividad, revocación, identidad de guardado, rate limit;
  - API (19): configuración, cookie, login, errores, aislamiento de dos cuentas, instalación pendiente, expiración, reinicio, escritura y concurrencia, origen, tamaños, perfiles, diagnóstico, servicio deshabilitado, cookie Secure y rechazo de BlobSave;
  - aprovisionamiento (3).
- **Frontend:** TypeScript y Vite compilan; 22 pruebas Playwright en Chromium, 8 nuevas del acceso nativo: seis distribuciones, mostrar/ocultar, errores, flujo completo, instalación pendiente, caducidad, servicio no disponible, selección de perfil y solo lectura.
- Los proveedores de nube y el cliente de autenticación se inyectan en las pruebas; no se abre red.

## 6. ¿Qué necesita hacer el propietario para probar sus cuentas?

1. Desplegar la rama `feature/phase6-8-web-native-auth` en Coolify con el volumen `/var/lib/sk-under` y HTTPS; configurar `SK_NATIVE_ORIGIN`, `SK_ALLOWED_ORIGINS`, `SK_NATIVE_STORE_KEY` y `SK_NATIVE_AUTH_ENABLED=true`. El paso a paso está en [deployment.md](deployment.md).
2. Aprovisionar un perfil por cuenta con sus propios `distro_id` y `unique_id`, desde variables de entorno o con `python -m app.native.provision`. No reutilizar el perfil de una cuenta para otra.
3. Iniciar sesión desde `/partida` con la cuenta de laboratorio, comprobar identidad y descarga, y ejecutar el flujo de solo lectura.
4. Si autoriza la escritura, activar `SK_NATIVE_WRITE_ENABLED=true` y `--allow-write` solo para el perfil de prueba; confirmar, verificar y restaurar.
5. Probar dos cuentas en navegadores o perfiles separados y completar la tabla de resultados de la guía manual. Hasta entonces, la validación multicuenta real no está completada.

## 7. ¿Qué obstáculos siguen pendientes?

- **Credenciales y aprovisionamiento reales:** no están en el repositorio ni en esta sesión. Sin ellos no se puede ejecutar el login real.
- **Despliegue:** el runbook está preparado, pero no se creó ni modificó ningún recurso de Coolify desde esta sesión.
- **Autorización del proveedor:** el uso de terceros y el aprovisionamiento oficial de `distro_id`/`unique_id` siguen sin confirmación de ChillyRoom. El backend no los genera ni los elude.
- **Renovación:** no se observó un endpoint de renovación aceptado; la sesión dura ~7 días y luego exige login.
- **iOS y distribuciones regionales:** fuera de alcance; no validadas.
- **Una sola réplica:** SQLite y el rate limit en proceso requieren un worker mientras no se migre a un almacén compartido.
- **Escritura real:** sigue limitada al entorno autorizado y apagada por defecto.

## 8. ¿Está preparado el servicio para permanecer activo en Coolify?

Sí, a nivel de imagen y configuración:

- `Dockerfile` crea `/var/lib/sk-under/{accounts,backups,native,native-backups}` con UID/GID `10001` y modo `0700`.
- Healthcheck de imagen contra `/api/v1/health`.
- `SK_NATIVE_AUTH_ENABLED`/`SK_NATIVE_WRITE_ENABLED` apagados por defecto.
- Sesiones y perfiles persisten en SQLite dentro del volumen; la clave externa permite reabrir el almacén tras recrear el contenedor.
- Runbook con política `unless-stopped`, un worker, un volumen, variables, respaldo, rotación y verificación.

No se verificó el despliegue real. Esa comprobación corresponde al propietario.

## 9. ¿Qué riesgos o limitaciones existen?

- El token del proveedor está en memoria y cifrado en reposo, pero un compromiso del proceso o del volumen con la clave permite usarlo mientras siga vigente.
- El logout local no revoca el token en ChillyRoom; el proveedor puede conservarlo hasta su caducidad.
- Los respaldos contienen progreso real de la cuenta. Se crean con modo `0600`, pero no tienen cifrado adicional.
- Sin 2FA, captcha ni renovación; el backend respeta `429` y no reintenta.
- El rate limit se aplica por IP vista por el servidor (detrás de un proxy puede ser la del proxy) y por correo; con una sola réplica.
- El aprovisionamiento sigue siendo manual: el propietario debe obtener sus identificadores por un canal autorizado.
- La autorización de ChillyRoom para el uso de terceros y el mecanismo oficial de aprovisionamiento siguen pendientes.
- Un XSS en el frontend podría actuar como el usuario mientras la sesión esté activa; el frontend no guarda tokens en JavaScript y el backend no expone el token, lo que reduce el impacto.
- El `distro_id`/`unique_id` no son secretos de sesión, pero son privados; se cifran y no se muestran.

El detalle está en [security.md](security.md).

## 10. ¿Cuál es el commit publicado?

Commit de implementación y documentación: _se completa al publicar la rama_. La rama es `feature/phase6-8-web-native-auth`; no se hace merge a `main`.

## Niveles alcanzados

| Nivel | Estado | Evidencia o límite |
| --- | --- | --- |
| Mínimo | **Cumplido** | Cliente de autenticación integrado, formulario, registro de distribuciones y pruebas automatizadas. |
| Principal | **Cumplido con transporte simulado; real pendiente** | Flujo web completo, identidad, proveedor existente y editor funcionan con pruebas inyectadas; falta repetirlo con la cuenta real. |
| Avanzado | **Preparado, no desplegado** | Servicio Linux independiente del emulador, Dockerfile, volumen, runbook y recuperación; no se verificó Coolify desde esta sesión. |
| Completo | **Pendiente del propietario** | Validación multicuenta real y confirmación de aislamiento con dos cuentas. |

## Documentos de la fase

- [Arquitectura](architecture.md)
- [Identificadores](identifiers.md)
- [Seguridad](security.md)
- [Despliegue en Coolify](deployment.md)
- [Guía de pruebas manuales](manual-testing.md)
- [Evidencia saneada](evidence.json)

## Reproducción de las pruebas

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

No se requieren credenciales ni red para estas pruebas. Las pruebas que necesitan muestras privadas se omiten automáticamente.

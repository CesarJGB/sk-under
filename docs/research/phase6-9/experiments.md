# Experimentos de la Fase 6.9

**Periodo:** 24 de noviembre de 2026, desde Linux, sin emulador activo. **Método:** hipótesis → evidencia → prueba controlada → análisis → nueva hipótesis. Las credenciales y los identificadores crudos se mantuvieron fuera de Git; los resúmenes usan hashes.

## 1. Línea base

Se revisaron la Fase 6.7 (cliente Linux, login real y descarga) y la Fase 6.8 (perfil de instalación, sesión web, almacén cifrado). La Fase 6.8 exigía un `distro_id` y un `unique_id` aprovisionados por el administrador. La pregunta era si esa exigencia se podía eliminar sin eludir controles.

La cuenta de laboratorio seguía disponible en un almacén privado. Las tres cuentas del propietario se probaron por primera vez en esta fase.

## 2. Experimentos de identificadores

### 2.1 Login con el par original

| Elemento | Resultado |
| --- | --- |
| Login del laboratorio con su distro y su unique originales | `200`, sesión nueva. |
| Descarga con `ModernCloudSaveProvider` | `200`, 114.779 bytes, 99.999 gemas, SHA-256 `ace7c58b…`. |
| Repetición de la descarga | Mismo SHA-256 y tamaño. |

Conclusión: el contrato de la Fase 6.7 sigue vigente y la descarga real es reproducible.

### 2.2 Login con un UUID v4 nuevo

| Elemento | Resultado |
| --- | --- |
| Distro UUID v4 nuevo, sin unique | `200`; `player.id` distinto del original. |
| Descarga con ese jugador | `400` / `100504` (sin partida). |
| Distro nuevo + unique original | `200` de login; `100504` de BlobSave. |

Conclusión: un UUID nuevo no es rechazado por formato; crea/selecciona otro jugador. La hipótesis de la Fase 6.7 («UUID aleatorio rechazado») no se reproduce de forma general. El distro debe corresponder al jugador que tiene la partida.

### 2.3 Unique nuevo con el jugador original

| Elemento | Resultado |
| --- | --- |
| Distro original + unique nuevo | `200` de login; BlobSave `400` / `100509`. |
| Respuesta de `100509` | `bindDeviceWaitSeconds=81970`, `timeWait=81970` (≈22,8 h). |
| Reintento inmediato | No se hizo; se respetó el límite. |

Conclusión: el servidor vincula dispositivos nuevos y aplica una espera. El par debe conservarse; regenerar el unique en cada acceso no es aceptable.

### 2.4 Formato del unique

El unique del laboratorio es `xiaomioutseas_` + 16 hex. Se generó uno con el mismo formato y se probó con el jugador correcto en el flujo final; funcionó. Un valor no hexadecimal o con otro sufijo no se usó para eludir nada: el backend valida el formato y documenta el prefijo observado.

## 3. El portal oficial

### 3.1 Hipótesis

Si el portal oficial ya autentica la cuenta, podría exponer el distro del jugador que el cliente guarda localmente. La Fase 5.7 había visto que el portal mostraba «un UUID de registro y otro de último login», pero no se había usado para el gateway.

### 3.2 Prueba con navegador y HTTP directo

Se localizó la consulta GraphQL `Profile` en el bundle público del portal. La respuesta incluye:

```text
accountInfo { userId email }
gamesInfo { players { pid gameId gameName registerDistroId lastLoginDistroId } }
```

Se reprodujo el flujo Redwood con HTTP directo:

1. `POST /.redwood/functions/auth` con la cuenta y la contraseña.
2. `POST /.redwood/functions/api/csrf-refresh`.
3. `POST /.redwood/functions/graphql` con `Authorization: Bearer <sesión>`, `auth-provider: chillyRoomAuth`, `x-csrf-token` y `Apollo-Require-Preflight`.

La respuesta fue `200` y devolvió dos jugadores de Soul Knight. No se guardaron cookies ni tokens: la sesión se descartó al terminar.

### 3.3 Comparación con el gateway

| Jugador del portal | `pid` coincide con `player.id` | Distro del portal | Resultado |
| --- | --- | --- | --- |
| 1 | No (jugador creado por una prueba anterior) | `627b…` | `100504` (sin partida). |
| 2 | Sí (jugador del laboratorio) | `5b05…` | Login `200` y descarga `200` con el unique original. |

El `lastLoginDistroId` del jugador 2 no era el UUID local `1591…` de la instalación de laboratorio, pero ambos distros seleccionaron el mismo jugador y sirvieron la misma partida. Conclusión: el portal es una fuente válida de un distro del jugador.

## 4. Flujo autónomo completo

### 4.1 Diseño de la prueba

Se creó un almacén nuevo, sin perfil previo, con `SK_NATIVE_AUTO_IDENTITY=true` y `SK_NATIVE_PORTAL_ENABLED=true`. Se usó la cuenta de laboratorio y el cliente/proveedor reales. El backend:

1. Consultó el portal una vez.
2. Generó un unique nuevo.
3. Probó el jugador 1: `100504`, sin partida.
4. Probó el jugador 2: `200`, partida.
5. Creó el perfil cifrado y la sesión.

### 4.2 Resultados

| Comprobación | Resultado |
| --- | --- |
| Portal | 1 llamada; dos jugadores. |
| Login | `200`; `auto_identity=true`; perfil ligado al jugador 2. |
| Descarga | 114.779 bytes; 99.999 gemas; SHA-256 `ace7c58b…`. |
| Edición preparada | 99.999 → 100.000; solo cambió `gameData.gems`; no se confirmó. |
| Respaldo | 1; archivos `SKB1`; sin `"gems"` en claro. |
| Reinicio | Proceso nuevo, mismo almacén/clave; cookie activa; descarga 99.999 gemas; 1 respaldo. |
| Logout | `204`; sesión inactiva. |
| Re-login | `200`; 99.999 gemas; no se consultó el portal; 1 perfil. |

El flujo completo se ejecutó en **3,4 s** la primera vez (portal + dos jugadores + descargas) y **0,7 s** el re-login, sin portal.

### 4.3 Observación sobre `100509`

En el experimento 2.3, el jugador original con un unique nuevo devolvió `100509`. En el flujo 4, el jugador del portal con un unique nuevo descargó correctamente. La diferencia observada es el distro usado (uuid local frente a `lastLoginDistroId` del portal) y el momento de la cuenta. No se aisló la causa exacta; **[H]** el servidor puede tratar de forma distinta una instalación antigua y una vinculación nueva sobre el jugador actual. El backend mantiene el manejo de `100509` y no depende de que no aparezca.

## 5. Cuentas facilitadas

| Cuenta | Gateway con la contraseña indicada | Portal con la misma contraseña | Reintentos |
| --- | --- | --- | --- |
| 1 | `400` / `10001` | rechazo de credenciales | 1 |
| 2 | `400` / `10001` | rechazo de credenciales | 1 |
| 3 | `400` / `10001` | rechazo de credenciales | 1 |

No se hizo fuerza bruta, recuperación de contraseña ni cambios de cuenta. El rechazo ocurre antes de usar `distro_id` o `unique_id`. La conclusión es que la contraseña facilitada no es aceptada o que esas cuentas no tienen acceso por contraseña de ChillyRoom (por ejemplo, solo Google Play). Es un requisito externo, no un fallo del flujo autónomo.

## 6. Pruebas de seguridad añadidas

- Reserva atómica de intentos con 10 solicitudes concurrentes y límite 3: exactamente 3 aceptadas y 7 bloqueadas.
- Migración de un almacén de la Fase 6.8 sin reescribir los valores cifrados.
- Respaldo cifrado: `SKB1`, sin `"gems"` ni `cloudSaveId`; clave incorrecta rechazada; migración de respaldos antiguos.
- CSP de API y frontend; HSTS en producción HTTPS; cabeceras `nosniff`, `DENY`, `no-referrer`, `Permissions-Policy`.
- `X-Forwarded-For` ignorado desde un socket no confiable; cadena resuelta desde la derecha con proxies confiables.
- Errores de portal/proveedor sin cuerpo remoto, contraseña ni identificadores.

## 7. Reproducción

Las pruebas automatizadas no tocan red:

```bash
cd backend && uv run --locked pytest -q
cd ../frontend && npm run build && npm run test:browser
```

Las pruebas reales requieren credenciales válidas y están descritas en [manual-testing.md](manual-testing.md). No se deben ejecutar en masa ni reintentar `100509`, `429` o un desafío.

# Despliegue privado en Coolify (Fase 6.9)

**Estado:** preparado y probado localmente; no se creó ni modificó ningún recurso de Coolify desde esta sesión. **Objetivo:** una instancia privada, un worker, un volumen persistente y HTTPS.

## 1. Requisitos

- Código de la Fase 6.9 publicado en la rama de despliegue.
- Backend con la imagen `backend/Dockerfile`; frontend con `VITE_API_BASE_URL` apuntando al origen HTTPS exacto de la API.
- Dominio privado, por ejemplo `sk.example.com`, con TLS terminado en el proxy de Coolify.
- Volumen persistente montado en `/var/lib/sk-under`.
- Salida HTTPS a `accounts.chillyroom.com`, `api-gateway.soulknight.chillyroom.com` y `save.soulknight.chillyroom.com`.

## 2. Variables del backend

```dotenv
SK_ENV=production
SK_ALLOWED_ORIGINS=["https://sk.example.com"]
SK_NATIVE_AUTH_ENABLED=true
SK_NATIVE_ORIGIN=https://sk.example.com
SK_NATIVE_STORE_KEY=<64 hex: openssl rand -hex 32>
# Opcional; si falta se deriva de la clave anterior.
# SK_NATIVE_BACKUP_KEY=<64 hex: openssl rand -hex 32>
SK_NATIVE_AUTO_IDENTITY=true
SK_NATIVE_AUTO_ALLOW_WRITE=false
SK_NATIVE_PORTAL_ENABLED=true
SK_NATIVE_WRITE_ENABLED=false
SK_NATIVE_STORE_DIR=/var/lib/sk-under/native
SK_NATIVE_BACKUP_DIR=/var/lib/sk-under/native-backups
# Red exacta del proxy de Coolify/Traefik. No uses 0.0.0.0/0.
SK_NATIVE_TRUSTED_PROXIES=172.16.0.0/12
SK_NATIVE_LOGIN_ATTEMPTS=5
SK_NATIVE_LOGIN_WINDOW_SECONDS=900
SK_NATIVE_IDLE_SECONDS=1800
SK_NATIVE_ABSOLUTE_SECONDS=604800
```

No configures `SK_NATIVE_DISTRO_ID` ni `SK_NATIVE_UNIQUE_ID` para el flujo normal. Son solo para una migración administrativa de una instalación concreta.

`SK_NATIVE_STORE_KEY` y `SK_NATIVE_BACKUP_KEY` deben conservarse fuera de la imagen y del repositorio. Si se pierden, no se pueden descifrar perfiles ni respaldos. Si se rotan, hay que migrar antes.

## 3. Frontend

El frontend es estático. Al compilar:

```bash
cd frontend
VITE_API_BASE_URL=https://api.sk.example.com npm run build
```

La CSP del HTML se genera con `connect-src 'self' https://api.sk.example.com`. Si el frontend y la API comparten origen, `VITE_API_BASE_URL` puede ser el mismo origen. Si cambia el dominio, recompila. `_headers` añade una CSP base y cabeceras; el proxy puede reforzarla. Para la sesión nativa, frontend y API deben usar HTTPS y pertenecer al mismo sitio, por ejemplo `sk.example.com` y `api.sk.example.com`: la cookie es `SameSite=Strict`. Una vista previa `*.pages.dev` frente a una API en otro dominio es cross-site y no permite ese flujo. El CORS del backend debe permitir el origen exacto del frontend con credenciales. Consulta los detalles en [despliegue de la Fase 6.8](../phase6-8/deployment.md).

## 4. Volumen y permisos

La imagen crea:

```text
/var/lib/sk-under/native          0700
/var/lib/sk-under/native-backups  0700
/var/lib/sk-under/accounts        0700
/var/lib/sk-under/backups         0700
```

Monta un volumen persistente en `/var/lib/sk-under`. La imagen usa UID/GID `10001`; el volumen debe permitir la escritura de ese usuario. No montes el repositorio ni un directorio compartido con otros servicios.

## 5. Proxy y IP real

Coolify/Traefik añade `X-Forwarded-For`. El backend solo lo interpreta si la IP del socket está en `SK_NATIVE_TRUSTED_PROXIES`. Ajusta el CIDR a la red real del proxy; si no lo conoces, deja la variable vacía y el limitador usará la IP del proxy (menos preciso, pero no falsificable por el cliente).

Comprueba que el proxy envía `X-Forwarded-Proto: https` para que el backend añada HSTS. No actives HSTS si el servicio se sirve por HTTP.

## 6. Persistencia y reinicio

1. Inicia sesión una vez y comprueba que `/api/v1/cloud/native/config` devuelve `auto_identity=true` y `portal_enabled=true`.
2. Descarga la partida y prepara una edición; se crea un respaldo cifrado.
3. Recrea el contenedor/instancia desde Coolify.
4. Con la misma cookie, `GET /api/v1/cloud/native/session` debe seguir activo; `GET /save` y `GET /backups` deben responder. Si la cookie caducó, inicia sesión de nuevo: el perfil y el par se reutilizan y no se consulta el portal.
5. El cierre de sesión (`POST /logout`) debe devolver `204` y la cookie debe quedar inactiva.

La prueba local de la Fase 6.9 hizo exactamente esto con un proceso nuevo y el mismo almacén: sesión activa, descarga correcta y un respaldo conservado.

## 7. Migración de respaldos de la Fase 6.8

Si el volumen contiene respaldos nativos en claro de la Fase 6.8:

```bash
docker exec -it <contenedor> python -m app.native.maintenance migrate-backups
```

El comando cifra `original.json`, `candidate.json`, `record.json`, `confirmation.json` y las líneas de `events.jsonl` con la clave actual y reemplaza cada archivo de forma atómica. No cambia los bytes de la partida. Haz una copia del volumen antes de ejecutarlo.

## 8. Diagnóstico

- `GET /api/v1/cloud/native/diagnostics` (cookie o Bearer administrativo existente) muestra conteos, eventos saneados, distribuciones y caducidades. No muestra correos, tokens ni identificadores.
- Un `100509` se presenta como `native_device_binding_throttled` con `Retry-After`; no se reintenta.
- Un `100504` se presenta como `native_no_cloud_save`; no se crea ni se sobrescribe nada.
- Un desafío del portal se presenta como `native_portal_challenge_required`; el usuario debe completarlo en el portal.

## 9. Límites de despliegue

- Un solo worker. SQLite, el rate limit y el bloqueo de descubrimiento son de proceso.
- No se probó el despliegue real en Coolify desde esta sesión.
- No se habilitó ni se probó escritura real durante la validación de esta fase.
- La autorización de ChillyRoom para uso de terceros sigue pendiente; mantén el servicio privado.

## 10. Checklist

- [ ] Commit de despliegue publicado y CI verificado.
- [ ] `SK_NATIVE_STORE_KEY` y `SK_NATIVE_BACKUP_KEY` fuera del repositorio, respaldadas.
- [ ] `SK_ALLOWED_ORIGINS` y `SK_NATIVE_ORIGIN` exactos, con HTTPS.
- [ ] `SK_NATIVE_TRUSTED_PROXIES` con la red del proxy.
- [ ] Volumen `/var/lib/sk-under` persistente y propiedad de `10001`.
- [ ] Frontend recompilado con `VITE_API_BASE_URL` correcto.
- [ ] `SK_NATIVE_WRITE_ENABLED=false`.
- [ ] Prueba de login, descarga, respaldo, reinicio y logout.
- [ ] Migración de respaldos antiguos, si existen.
- [ ] Revisión de que no se publican credenciales, tokens ni partidas.

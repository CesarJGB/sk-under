# Implementación de la Fase 3

- `backend/app/parsers/real_save.py` valida la envoltura, prueba las dos variantes DES y describe los marcadores estructurales por tipo. El reconocimiento devuelve el documento ya leído. Un sobre ambiguo, incompatible o inválido se rechaza.
- `backend/app/formats/real_save.py` registra las nueve estructuras bajo una familia de formato. El adaptador devuelve la proyección de campos admitidos después del reconocimiento. `backend/app/serializers/real_save.py` prepara la descarga con los bytes recibidos, preservando toda la envoltura original.
- El motor rechaza cambios a los campos de lectura y exige la igualdad exacta antes de reabrir una exportación real. Las rutas conservan la autenticación, límites, CORS, respuestas sin caché y errores sin fragmentos del archivo. El servidor no escribe los guardados en disco.
- La interfaz consulta la API para ofrecer `.data` y muestra las categorías reconocidas. Antes de descargar, compara el tamaño y el SHA-256 de la validación con la inspección, y verifica el SHA-256 de la respuesta binaria mediante Web Crypto. La aplicación de producción se sirve por HTTPS y las pruebas pueden usar loopback. `.skdemo` conserva la edición.

## Habilitar en una instancia privada

Por omisión se anuncia solamente `.skdemo`. Configura `SK_SAVE_GENERAL_KEY_HEX`, `SK_SAVE_STATISTICS_KEY_HEX` y `SK_SAVE_IV_HEX` juntos en el backend. Cada variable requiere los 16 dígitos hexadecimales del parámetro de 8 bytes. Los literales verificados corresponden a las llamadas de descifrado general y estadístico y al IV en la referencia citada. [Origen de los parámetros](SHOULXING_COMPARISON.md)

En el VPS de investigación, los parámetros ya verificados están en `~/.config/sk-under/phase3/cipher.env`, con permisos `0600`, fuera del checkout. El archivo solo contiene la configuración del códec. La instancia de prueba necesita también su configuración habitual de acceso y CORS. Por ejemplo, desde `backend/` con un `.env` de desarrollo ya preparado para loopback:

```sh
uv sync --locked
uv run --env-file "$HOME/.config/sk-under/phase3/cipher.env" uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8017 --no-proxy-headers --no-access-log
```

Los parámetros de cifrado y el token de acceso se administran en el backend. Para activar `.data` en Coolify, configura las tres variables del códec como secretos de runtime en la aplicación del backend y verifica que `/api/v1/formats` publique `read_only` después del despliegue.

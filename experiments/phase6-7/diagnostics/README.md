# Diagnóstico de autenticación

Estas herramientas son para pruebas autorizadas sobre una instalación propia.
No desactivan TLS, no eluden la validación de certificados y no automatizan
ataques de credenciales.

## Escáner de memoria

`scan_memory.py` usa Frida para buscar cadenas en regiones `rw-` del proceso.
Sirve para localizar literales de rutas, cabeceras o cuerpos durante un login
controlado. Los resultados pueden contener correo, tokens o identificadores:
guárdalos en una ruta privada, no los publiques y bórralos al terminar.

```bash
python3 experiments/phase6-7/diagnostics/scan_memory.py \
  --device 10.0.0.2:27044 --process 'Soul Knight' \
  --pattern loginType --pattern /UserAuth/Login \
  --out /tmp/scan.json
```

Requiere un `frida-server` compatible con la arquitectura del proceso. En el
AVD x86_64 con cliente ARM64 traducido, el agente x86_64 puede leer memoria,
pero no interceptar código ARM64; el escáner solo lee.

## Registro del cliente oficial

`adb logcat` expone estados como `[UserAuthClient] received response: OK` y
`Root Cert:false ... CheckCertHashTrusted`. No imprime el cuerpo. Es útil para
correlacionar tiempos y resultados, no para extraer credenciales.

## Límites

- No usar contra cuentas de terceros.
- No repetir intentos ante `10003`, `429` o desafíos.
- No interpretar un `502` como contraseña incorrecta.
- La validación estricta del certificado impide un proxy de inspección; no se
  intentó eludirla.

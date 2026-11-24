# Cliente Linux de autenticación nativa (Fase 6.7)

`native_auth.py` implementa el contrato de login observado y probado con la
cuenta de laboratorio. `native_auth_cli.py` es la interfaz de línea de
comandos. `test_native_auth.py` contiene pruebas simuladas; no usa red ni
credenciales reales.

La cabecera `x-distro-id` es obligatoria. El cuerpo es JSON plano; el gateway
rechaza gzip. La cabecera `x-unique-id` no es necesaria para el login, pero
BlobSave sí exige el identificador de instalación válido.

```bash
# Solo autenticación y resumen de identidad
backend/.venv/bin/python experiments/phase6-7/native_auth_cli.py \
  --distro-id "$SK_NATIVE_DISTRO_ID"

# Autenticación + descarga a un archivo privado
backend/.venv/bin/python experiments/phase6-7/native_auth_cli.py \
  --distro-id "$SK_NATIVE_DISTRO_ID" \
  --unique-id "$SK_NATIVE_UNIQUE_ID" \
  --download "$HOME/.local/share/sk-under/partida.json" \
  --json
```

La contraseña se solicita sin eco. Para automatización controlada se puede
usar `--password-stdin`; no se acepta por argumento. El token solo se escribe
si se pasa `--session-file`, con modo `0600`.

No ejecutes reintentos ante `10003` o `429`: el proveedor aplica control de
frecuencia. Los identificadores y las credenciales de laboratorio no se
incluyen en este repositorio.

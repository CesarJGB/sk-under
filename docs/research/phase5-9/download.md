# Descarga independiente

## Experimentos nuevos

1. **Hipótesis:** el host visto al abrir el panel sirve BlobSave. **Herramientas:** tcpdump, muestreo `/proc`, análisis IL2CPP y `urllib` con TLS normal. Con Android apagado se envió el POST identificado usando sesión SDK y distribución. **Resultado:** HTTP 400, gzip, error `100505` (parámetro de código de dispositivo incorrecto). **Interpretación:** el host respondió como servicio de guardados, pero la solicitud carecía de identidad de instalación válida. **Siguiente acción:** investigar `RefreshUniqueId`.
2. **Hipótesis:** el valor requerido se deriva del canal y Android ID de la instalación. **Procedimiento:** se leyó en el AVD propio el identificador de la aplicación y se usó el canal observado; no se desactivaron TLS, autenticación ni controles. Tras apagar Android se añadió `x-unique-id`. **Resultado:** 200 gzip con `data` textual que reconstruye 17 claves y 1.000 gemas. **Siguiente acción:** repetir y comparar.
3. **Reproducibilidad:** una segunda solicitud manual, una mediante `ModernCloudSaveProvider` y otra mediante la CLI devolvieron exactamente el mismo agregado, con Android detenido. Los cuatro agregados pesan 114.778 bytes y comparten SHA-256 `eeef81390418a60cf6f4da25932ab93c0ee22bc418eeb60bf595f28f13f6f97c`. Las solicitudes manuales fueron dos, además de las dos del proveedor/CLI. No se contaron los errores como éxito.

La referencia de memoria de 5.8 tiene los mismos identificadores de copia/plataforma y las mismas 17 claves. Once secciones superiores coinciden por completo; otras seis difieren. Con `game.data` restaurado en la nueva prueba, coinciden 36 de 38 campos comunes, incluidas las 1.000 gemas. Las discrepancias no se atribuyen automáticamente a corrupción; el cliente puede haber actualizado o transformado estado entre momentos.

## Uso experimental

Desde `backend`, con `SK_CLOUD_SESSION_TOKEN`, `SK_CLOUD_UNIQUE_ID` y `SK_CLOUD_DISTRO_ID` aportados por el titular en un entorno privado:

```sh
uv run --locked python -m app.cloud.modern /ruta/privada/copia.json
```

El destino debe ser nuevo; se crea con permisos 0600. No se automatizan login ni extracción de identificadores. El proveedor usa HTTPS con verificación estándar, rechaza redirecciones, limita tamaños y valida respuesta y agregado. Las variables de sesión caducan; el éxito se probó con una cuenta, canal e instalación, no con todas las versiones o plataformas. La copia y la sesión de laboratorio permanecen fuera del repositorio.

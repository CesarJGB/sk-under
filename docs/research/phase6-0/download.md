# Descarga Linux

**Confirmado mediante ejecución:** con la sesión legítima existente y Android detenido (sin dispositivos en `adb devices`), dos solicitudes del proveedor produjeron sendos agregados de 114.778 bytes, 17 claves superiores y SHA-256 `eeef81390418a60cf6f4da25932ab93c0ee22bc418eeb60bf595f28f13f6f97c`. Coinciden byte a byte con la huella de 5.9. El hash es local, no una firma del servidor. Solo se comprobó una cuenta.

Las dos copias nuevas se guardaron en un directorio privado con modo 0400; esto previene sobrescrituras accidentales, pero no las hace inmutables frente al propietario. Existen además copias previas independientes. No se imprimieron credenciales ni contenido de la partida.

**Pruebas sintéticas:** errores HTTP 401/403, identificadores malformados, gzip corrupto o truncado, datos inválidos, límites y respuesta HTTP incompleta. La fase 5.9 también registró un 400 real por identificador incorrecto; no se repitió. No se provocó una caducidad real ni se afirma conocer su código HTTP. Se mapearon excepciones de lectura HTTP incompleta a error de protocolo y se suprimieron detalles de excepciones de transporte.

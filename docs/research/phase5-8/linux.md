# Lectura desde Linux

## Experimento

Con la sesión legítima guardada en el laboratorio privado, se probó primero `POST /Backup/FetchGameData` con `{}` y Bearer en el host `LegacyGateway` de la sesión: el balanceador devolvió **503 HTML**. La misma petición en el gateway documentado, sin `x-distro-id`, devolvió **400 / 10015**. No son pruebas de que la cuenta carezca de progreso ni de que el token haya caducado.

A continuación se recuperó `LastLoginHostWithDistroId` de las preferencias respaldadas, aplicando URL-decode, base64-decode y separando host e identificador. Con el host resultante, el token `LegacyGateway`, `POST {}` y los encabezados de 5.7, el nuevo `LegacyGatewayReader.read()` obtuvo **200** y un agregado legacy auténtico. `heroData`, `petData`, `plantPotData`, `heroRoomData` y `gameItemData` tienen cero entradas. Los bytes de respuesta están en `~/.config/sk-under/phase5-8/`, junto con las capturas y registros privados. La falta de `x-distro-id` es una diferencia verificable entre las solicitudes, pero los resultados no prueban por sí solos que sea la única causa de 10015.

## Implementación y límites

`backend/app/cloud/legacy.py` implementa esa lectura de solo lectura, HTTPS, límites de tamaño, clasificación de errores y validación de cinco campos observados. El resultado es un `LegacyAggregate`, separado del importador `CloudSaveGameData`: cuenta colecciones sin publicar su contenido y declara `progress=unknown`, incluso cuando estén vacías o tengan entradas. Una colección no vacía no es por sí sola prueba de una partida recuperable. Los encabezados de idioma/versión reproducen esta sesión concreta, no constituyen un contrato universal. El token y el identificador no aparecen en `repr`.

**Resultado de esta primera lectura:** el lector reprodujo una respuesta auténtica con la sesión del cliente. En ese momento seguían pendientes una copia no vacía, la comparación con `.data` y la respuesta de `GetBlobSave`. La sección siguiente registra los experimentos posteriores.

## Repetición después de la subida, con Android apagado

Tras el guardado y la recuperación oficiales se apagó el emulador con `adb emu kill` y `docker wait` confirmó que el contenedor estaba `exited`. Con la sesión legítima del laboratorio se repitieron lecturas ya fundamentadas: `POST /Backup/FetchGameData` devolvió **200** y las cinco colecciones principales siguieron vacías; `POST /Backup/GetBlobSave` con `{}` devolvió **500** y cero bytes; `GET /BlobSave/Download` devolvió **404** y cero bytes. La existencia de una fila no vacía en la interfaz oficial descarta usar el agregado legacy vacío como prueba de ausencia de progreso en la copia moderna. El contrato moderno aún no está identificado: una respuesta 500 no explica por sí sola si falla el cuerpo, el método, la ruta o algún requisito del servicio.

El proveedor experimental de copia moderna ahora exige que el payload pase el parser de `CloudSaveGameData`; un `200` con un `data` arbitrario produce `CloudProviderProtocolError`. Eso valida estructura, no autenticidad ni progreso. Se añadió una prueba de regresión para el falso positivo.

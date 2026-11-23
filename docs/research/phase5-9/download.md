# Descarga Linux

En esta fase no se hizo una nueva petición remota: la evidencia disponible no identifica un contrato moderno que merezca reproducirse. En 5.8, con el contenedor Android detenido, la lectura `POST /Backup/FetchGameData` devolvió 200 con colecciones legacy vacías; `POST /Backup/GetBlobSave` devolvió 500 y `GET /BlobSave/Download` 404. Esos resultados no identifican el protocolo moderno ni demuestran ausencia de partida. Los detalles de sesión y resultados anteriores están en [5.8/linux.md](../phase5-8/linux.md).

El JSON privado de 110.049 bytes proviene de memoria del proceso oficial tras la recuperación. El parser local reconstruye sus 17 claves y la prueba privada confirma que `gameData.gems` coincide con el archivo restaurado; el registro anterior comparó otros 38 campos, con 29 valores coincidentes. No se comprobó el origen de red del JSON, su integridad de transporte, ni una descarga independiente o repetible. No hay una copia descargada desde Linux que pueda contrastarse con la referencia.

El proveedor experimental existente y sus pruebas son infraestructura hipotética, no una implementación demostrada del protocolo. No se implementó otra ruta de red al no existir un contrato verificable. El bloqueo concreto es la falta de correlación entre solicitud, respuesta, sesión y agregado moderno.

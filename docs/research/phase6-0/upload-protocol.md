# Protocolo de subida

**Confirmado mediante análisis estático previo:** `UploadAsync` construye POST `/BlobSave/Upload`, serializa con Json.NET, comprime y usa `ByteArrayContent` con `application/json` y `gzip`. La rama inspeccionada añade `x-request-token` cuando un callback devuelve un entero positivo. Véase [5.9](../phase5-9/upload.md).

**Análisis estático adicional:** se volvió a inventariar la metadata del APK 8.8.0: `BlobSaveClient` contiene tanto `GetRequestToken` como `ResetRequestToken` y sus accesores, además de `CreateSerializerSettings`; `JsonPayload` tiene una propiedad `Data` textual. La existencia de estos miembros no demuestra cuándo se invocan, su implementación activa, el nombre serializado ni el significado o ciclo de vida del token. Los parches IFix pueden alterar las ramas base.

**Inferido:** el candidato local JSON con `data` textual y gzip es compatible con la forma de la respuesta observada y los tipos estáticos. No hay captura del cuerpo oficial de subida ni prueba de que la configuración Json.NET genere bytes equivalentes. Tampoco se conoce el procesamiento efectivo de respuesta ni los requisitos de persistencia.

**Pendiente:** observar una subida oficial autorizada en un entorno de investigación, identificar el callback y su reinicio, serialización, cabeceras y respuesta, respetando TLS e integridad; comparar la solicitud resultante antes de cualquier escritura Linux. No se observó una nueva subida oficial en esta fase.

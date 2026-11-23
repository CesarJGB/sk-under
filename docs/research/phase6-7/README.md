# Fase 6.7 · Autenticación nativa experimental

**Estado: trabajo parcial.** No se ha obtenido ni verificado una sesión nativa. El cliente conserva un contrato hipotético y no es apto para producción. Las pruebas de éxito descritas aquí son simulaciones locales, no demuestran una autorización real. La infraestructura de producción no se ha modificado.

## Entorno y alcance

El APK local tiene SHA-256 `54bb332be9444596501ec99f745f21adfa55265feea3a15331c735009b517f34`, idéntico al de [Fase 5.5](../phase5-5/real-880-reference.md); el paquete instalado en el AVD informa `versionName=8.8.0` y `versionCode=1080800`. La identidad binaria de la instalación no se ha verificado independientemente mediante un hash del APK instalado. Se cerró y volvió a iniciar la sesión manualmente en la cuenta del laboratorio como prueba de referencia. No se extrajo la sesión para el cliente Linux. El AVD solo sirve de referencia; el experimento Python de Linux no llama a Android ni lee sesiones existentes.

## Matriz de investigación

| Hipótesis y evidencia previa | Experimento | Resultado e interpretación | Incertidumbre y alternativa |
| --- | --- | --- | --- |
| `loginType=3` y nombres del DTO describen la petición | Auditoría de metadata y código de [6.6](../phase6-6/reapertura.md); prueba de serialización local | El enum y los campos tienen respaldo estático, el JSON generado tiene esa forma. No se observó en esta fase la petición oficial. | Cifrado o transformación de contraseña, campos opcionales y cabeceras siguen sin confirmar; observar el contrato autorizado sin alterar TLS. |
| `502/10003` identifica una causa | Búsqueda pública; arranque oficial y dos pruebas Linux con credenciales de laboratorio: petición de 6.6 y variante con cabeceras de juego/version/plataforma de BlobSave, sin identificadores ni Bearer | Cliente oficial: la sesión automática informó `OK` a las 22:56:49 UTC; tras cerrar sesión en la interfaz, un inicio manual de correo y contraseña informó `OK` a las 22:59:39 UTC, registró éxito de Email y volvió al título. Linux: 502 en ambas; la segunda devolvió 10003. Las cabeceras probadas por sí solas no resuelven la hipótesis y se desconoce el significado del código. | El login oficial funcionó en esa ventana, pero el contenido, endpoint efectivo y tratamiento de la solicitud aún no se observaron. No se descarta indisponibilidad parcial, configuración o incompatibilidad de versión. Evitar reintentos sin evidencia nueva. |
| Respuesta `session`/`user` y correspondencia de IDs prueban titularidad | Revisión de metadata 8.8.0: `SessionInfoLite` declara `Uid`, `Token`, `Expire` y `UserProfile` declara `Id`, `Email`; simulación local de coincidencia y discrepancia | Las comprobaciones filtran estructuras contradictorias, pero sus nombres JSON, unidades y relación semántica en una respuesta real siguen sin demostrarse. Se eliminó el indicador categórico `identity_verified`. | Confirmar respuesta real y relación estable, preferiblemente con una interfaz de identidad documentada. |
| El SDK permite ejecutarse de forma independiente en Linux | Revisión de [arquitectura del SDK](../phase5/autenticacion.md) y búsqueda pública por nombres de tipos | `AccountSdk` y `UserAuthClient` aparecen en metadata de una imagen Unity/IL2CPP; `HttpClient` y DTOs no son por sí mismos dependencias Android. No se localizó SDK independiente para esta operación. La instrumentación previa de Frida detectó ARM64 traducido, no un módulo ARM interceptable por Frida x86-64. | No se demuestra inexistencia; investigar distribución y licencia oficial, inicialización, adaptadores de plataforma y observación autorizada en un entorno ARM compatible. |
| Compresión, errores y redirecciones del cliente son robustos | Servidor local con éxito sintético, gzip, bomba gzip, gzip corrupto, longitud inválida, codificación desconocida, HTTP 502, desafío, identidad contradictoria y 302 | 11 pruebas pasan; límite comprimido y descomprimido, no se retransmiten credenciales en redirecciones y no se muestran cuerpos de error. | Los casos son simulados y no definen el protocolo del servicio. |
| El proveedor Linux y el uploader conservan sus garantías | Pruebas existentes de `test_cloud_modern`, `test_cloud_blob_upload`, `test_cloud_save` | 59 pasan, 1 omitida; validan pruebas existentes, no una partida descargada con una sesión nueva. | Para validación real se necesita una sesión nativa verificada y autorización de la operación. |

## Distribuciones

El [manual Android](https://soulknight.chillyroom.com/et/article/base/3) indica que desde 5.5.3 se migraron guardados a servidores de ChillyRoom y que no se transfieren entre Android y iOS. Las [FAQ oficiales](https://soulknight.chillyroom.com/et/article/base/6) indican que sus sistemas de cuentas y estructuras de datos difieren. Google y ChillyRoom pueden representar cuentas distintas incluso con el mismo correo. La variante es por tanto una entrada significativa para identificar origen y formato; estas fuentes no documentan cómo parametrizar el gateway para cada distribución ni autorizan extrapolar el contrato del canal de laboratorio. Solo se investiga Android Global 8.8.0. La [limitación oficial de dispositivos](https://soulknight.chillyroom.com/et/article/base/4) se debe respetar; el emulador y transferencias pueden consumir cupos.

## Ejecución

```sh
python3 -m unittest discover -s experiments/phase6-7 -v
backend/.venv/bin/python -m pytest -q backend/tests/test_cloud_modern.py backend/tests/test_cloud_blob_upload.py backend/tests/test_cloud_save.py
backend/.venv/bin/python experiments/phase6-7/native_login.py
# Alternativa experimental: cabeceras de contexto observadas en BlobSave
backend/.venv/bin/python experiments/phase6-7/native_login.py --save-context
```

Ambas variantes son interactivas y cada ejecución hace una solicitud real. `--save-context` no es una cabecera de login validada; usa la plataforma de la distribución Android investigada, sin identificadores de dispositivo. El comando envía credenciales reales al endpoint hipotético sin reintentos y solo después de un aparente éxito solicita identificadores y trata de descargar. No invocarlo como prueba de credenciales de terceros. El diseño no persiste contraseñas o tokens ni imprime cuerpos; Python no garantiza borrado seguro de memoria. TLS se comprueba normalmente, las redirecciones se rechazan, y los desafíos o contratos desconocidos detienen el proceso. La comparación local de identidad es provisional y una descarga estructuralmente válida no demuestra por sí sola la propiedad de la partida.

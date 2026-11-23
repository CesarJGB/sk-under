# Opciones autorizadas de exportación

## 1. Lo que ofrece hoy el proveedor

| Opción | ¿Autorizada? | ¿Entrega un archivo? | ¿Reproducible? |
| --- | --- | --- | --- |
| Nube del juego (`Upload Progress`) | Sí, dentro del cliente | No; guarda una revisión en el servidor | Manual, por cuenta |
| Nube del juego (`Retrieve Progress`) | Sí, dentro del cliente | No; aplica la revisión al dispositivo | Manual, por cuenta |
| Copia de seguridad del sistema operativo | Depende del SO y del titular | Puede incluir `.data` locales, no el agregado | Parcial, fuera del juego |
| Soporte de ChillyRoom | Sí, asistido | No hay formato público; puede recuperar una copia de su sistema | Humano, caso por caso |
| API para terceros | No localizada | — | — |

El manual indica que el soporte puede recuperar copias de su sistema. La FAQ
dice que la **única** forma soportada de respaldar es la nube manual. No se
encontró un botón de exportación ni una URL de descarga para el titular.

## 2. Petición viable al proveedor

Una solicitud de acceso delegado debería pedir, por escrito:

1. método de autenticación y consentimiento del titular;
2. ámbito de lectura (solo metadatos, solo guardado propio, o ambos);
3. formato exacto de la revisión (JSON, gzip, RPC, `NetPack`);
4. versión de esquema y política de migración (`FixData`);
5. límites, cuotas, caducidad y revocación;
6. tratamiento de datos personales y retención;
7. entorno de pruebas y credenciales de sandbox;
8. compromiso de no usar endpoints privados ni tokens del cliente.

Sin esa respuesta, el transporte remoto del backend debe seguir deshabilitado.

## 3. Petición viable al soporte (para una muestra propia)

El titular puede solicitar una copia de su propio respaldo, indicando:

- cuenta y canal de instalación;
- versión 8.8.0;
- que la copia es para verificación de interoperabilidad de su propio editor;
- que no se publicará ni se compartirá;
- que se acepta recibirla en el formato que el soporte pueda entregar.

No se debe pedir al soporte que realice cambios, que comparta datos de terceros
ni que eluda las limitaciones de vinculación.

## 4. Opciones descartadas

| Opción | Motivo |
| --- | --- |
| `adb backup` del directorio privado | En 5.1 devolvió cero bytes; no es una exportación del agregado. |
| Extraer tokens del cliente | No autorizado; riesgo de seguridad y de cuenta. |
| Llamar a `api-gateway.soulknight.chillyroom.com` | No hay contrato público; prohibido por las reglas de la fase. |
| Automatizar el login | Elusión de controles; no se hace. |
| Root/Magisk para leer memoria | No es una vía de exportación autorizada; no se usa. |
| Replicar el cliente Android en Linux | No resuelve la autorización; solo mueve el problema. |

## 5. Conclusión

No existe hoy una exportación **de archivo** autorizada y reproducible. La
opción más cercana es una copia asistida por soporte o una delegación publicada
por ChillyRoom. Mientras falte, el flujo correcto es importar una copia local
que el titular ya posea y mantener el transporte remoto apagado.

# Adquisición legítima de respaldos

**Resultado: no se localizó una exportación de archivo ni una API pública de
lectura.** La única vía oficial documentada es la nube del juego, operada desde
el cliente, con carga y descarga manuales. El soporte puede recuperar copias de
su sistema, pero no publica un contrato machine-readable ni una delegación para
terceros.

## 1. Funciones oficiales

| Función | ¿Existe? | Evidencia | Límite |
| --- | --- | --- | --- |
| Guardar en la nube | Sí, manual | Manual de Android: `Upload Progress`. | Requiere cuenta y conexión; no es automático. |
| Recuperar desde la nube | Sí, manual | Manual de Android: `Retrieve Progress`; FAQ: `Download Progress`. | Sustituye el progreso local; consume vinculación. |
| Exportar un archivo | No documentado | Manual, FAQ y soporte no describen un archivo exportable. | No hay botón, ruta ni formato público. |
| Transferir a otro dispositivo | Solo misma plataforma y cuenta | FAQ: no Android↔iOS. | 5 vinculaciones/90 días, 24 h entre ellas. |
| Recuperación por soporte | Sí, asistida | Manual: “customer service representatives can retrieve backups”. | Proceso humano; no es API ni exportación automática. |
| API para terceros | No localizada | Sin contrato público de identidad/lectura. | No se debe usar un endpoint privado. |

Fuentes: [manual de Android](https://soulknight.chillyroom.com/et/article/base/3),
[limitaciones](https://soulknight.chillyroom.com/et/article/base/4),
[FAQ](https://soulknight.chillyroom.com/et/article/base/6).

## 2. Persistencia local después de una recuperación

La restauración oficial aplica el agregado al almacenamiento del cliente. En
8.6.0 se observaron nueve archivos `*.data` en el directorio privado de la
app, cifrados en Base64 + DES-CBC con claves locales. Esos archivos son
**caches por subsistema**, no el agregado `CloudSaveGameData`. En 8.8.0 el
cliente sigue usando `PlayerPrefs` y modelos de sección; no se encontró una
exportación legible.

Lo que se puede obtener por mecanismos normales:

- una copia de los `.data` locales solo si el sistema operativo permite al
  titular acceder al directorio privado (por ejemplo, copia de seguridad del
  dispositivo o un dispositivo con acceso autorizado);
- ningún archivo `CloudSaveGameData` completo desde la nube;
- ningún token, cookie o endpoint reutilizable.

No se eludió el aislamiento de Android ni las protecciones del juego.

## 3. Separación de responsabilidades

| Operación | ¿Cliente oficial? | Entrada | Salida | ¿Linux? |
| --- | --- | --- | --- | --- |
| Iniciar sesión | Sí | Cuenta del titular | Sesión | No sin contrato autorizado. |
| Subir/descargar nube | Sí | Agregado + cuenta | Revisión aplicada | No. |
| Restaurar en el juego | Sí | Revisión | `PlayerPrefs`/`.data` | No. |
| Producir un archivo del agregado | No documentado | — | — | Bloqueado. |
| Validar un archivo suministrado | No | JSON/gzip/RPC | Informe | **Sí** (backend). |
| Editar y reconstruir una copia | No | JSON/gzip | Copia + informe | **Sí** (laboratorio). |
| Comparar campos 8.6.0/8.8.0 | No | Archivos locales | Diff | **Sí**. |

## 4. Requisito externo que falta

Para obtener una referencia 8.8.0 sin emulador hace falta **una de estas dos**:

1. una **exportación del titular** producida por una función oficial (no
   existe hoy), o
2. una **interfaz delegada/documentada por ChillyRoom** con consentimiento,
   identidad, ámbito de lectura y formato.

Mientras no exista, el transporte remoto permanece deshabilitado y el flujo
útil es la importación local de una copia que el titular ya tenga.

## 5. Lo que no se hace

- No se automatiza el login.
- No se reutilizan tokens extraídos del cliente.
- No se llaman endpoints privados.
- No se hace ingeniería inversa del servidor.
- No se suben partidas al repositorio.
- No se declara que una copia editada sea aceptada por el juego.

## 6. Conclusión

La dependencia de Android no se elimina para **adquirir** el respaldo. Sí se
reduce para **procesarlo**: validación, esquema, edición y comparación ya
funcionan en Linux con un archivo suministrado. La vía autorizada reproducible
sigue siendo una exportación oficial o una delegación del proveedor; hoy no hay
ninguna de las dos.

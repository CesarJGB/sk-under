# Fase 5.9: descarga moderna desde Linux

**Resultado de la continuación:** se repitió la recuperación oficial y, después de apagar Android, Linux descargó cuatro veces la copia moderna de la cuenta de laboratorio. Las cuatro lecturas obtuvieron el mismo agregado JSON de 114.778 bytes, con 17 claves de nivel superior y `gameData.gems=1000`. Una lectura usó el proveedor experimental y otra su CLI. La escritura desde Linux sigue sin demostrarse ni habilitarse.

| Evidencia | Estado | Alcance |
| --- | --- | --- |
| 5.8: subida y recuperación oficial | Confirmado mediante cliente oficial | La copia en memoria no se atribuyó a respuesta de red |
| Primera ejecución 5.9: captura antigua | Bloqueado | No identificó la solicitud moderna |
| Continuación: recuperación oficial | Confirmado mediante cliente oficial | Panel con 1.000 gemas, aplicación de preferencias y cambios en archivos |
| Continuación: solicitud moderna | Confirmado desde Linux | POST a host de guardados, sesión y dispositivo de laboratorio; respuesta gzip con `data` textual |
| Continuación: copia y reproducción | Confirmado desde Linux con Android apagado | Cuatro lecturas iguales; identificadores coinciden con muestra 5.8; 36/38 campos comunes de `gameData` coinciden con el archivo local restaurado |
| Elección de ruta y parámetros del cliente | Inferido del código y correlacionado con tráfico | El cuerpo TLS oficial no fue capturado; la sesión puede variar por versión/canal |
| Subida Linux y aceptación por juego | No demostrado | Hay un candidato serializado solo localmente; no se transmitió |

El proveedor es optativo, de solo lectura y no modifica el comportamiento predeterminado. Ver [protocolo](protocol.md), [descarga y uso](download.md), [subida](upload.md), [comparación](roundtrip.md) y [evidencia y pruebas](evidence.md).

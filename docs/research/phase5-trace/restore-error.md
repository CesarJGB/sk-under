# El fallo al construir la vista previa

En 5.1 pasaron **451 ms** entre el marcador de captura local y la excepción en el reloj del invitado. El panel seguía abierto y faltaba la confirmación. El segundo intento alcanzó esa confirmación tras entrar en el tutorial sin conexión, abrir el cofre, salir y reconectar. Cambiaron simultáneamente el estado local, la conectividad y el tiempo transcurrido. [Registro original](../phase5-experimental/experimentos.md)

| Pregunta | Evidencia nueva en AArch64 |
| --- | --- |
| ¿Qué resume la vista? | `CreateExtraData(CloudSaveGameData)` usa estadísticas y el contador de peces. Su modelo contiene ocho enteros, una colección de héroes `List<int>`, cuatro colecciones `List<string>` (skins, habilidades, mascotas, plantas) y un booleano de tarjeta. |
| ¿Qué recibe el formateador? | En `GetExceptRMBPayDescribe` (VA `0x063682a4`), la rama base crea opciones, activa `intersectWithRestoreRole` y copia cinco referencias de colección y un booleano. En +0xec transfiere el control a `GetExtraDescribe(ExtraDescribeOptions) → string`. Copiar una referencia preserva un posible nulo. |
| ¿Qué más interviene? | El cuerpo base de `GetExtraDescribe` (`0x06367cf0`) crea un StringBuilder, consulta localización, `HeroSkillInfo.RMB_Skill`, el separador de idioma y recorta el texto. Estos son otros insumos del formateo. |

Una colección ausente es una hipótesis comprobable. La traza carece del argumento nulo, del valor de las opciones y de la rama exacta. Tampoco distingue un origen local de uno remoto. Se desconoce la condición mínima. El único conjunto suficiente observado fue la secuencia concreta de 5.1. En 5.2 la ejecución nueva llegó hasta la interfaz previa al login, sin reproducir la excepción.

El ensayo discriminante necesita la misma cuenta, versión, idioma y respaldo, sobre un dispositivo de prueba ya vinculado. Comparar la vista previa antes y después de entrar y salir del tutorial sin abrir el cofre, manteniendo igual la conectividad. Si sigue fallando, repetir después del cofre. Registrar únicamente tipo de excepción, nombre de parámetro si se expone y marcos del formateador. Detenerse en la confirmación basta para probar la vista previa.

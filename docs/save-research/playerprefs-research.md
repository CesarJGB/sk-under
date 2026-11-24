# PlayerPrefs de Android Global

El paquete Android de laboratorio es `com.ChillyRoom.DungeonShooter`. Bajo `shared_prefs/`, el XML de Unity se llama `com.ChillyRoom.DungeonShooter.v2.playerprefs.xml`. En las capturas reales 8.8.0 se pudo leer como `<map>` con entradas `<int name="…" value="…"/>` y `<string name="…">…</string>`. Una sola captura de la fase 6.11 contiene simultáneamente dos prefijos numéricos. Ambos tienen sus propias tablas de héroes, mascotas y skins. El prefijo sirve como ámbito local de perfil. Su correspondencia exacta con todos los identificadores de cuenta, instalación y nube sigue abierta.

| Clave tras el prefijo | Observaciones de Android 8.8.0 / 8.8.0.11 | Eje de comparación |
| --- | --- | --- |
| `gems`, `last_gems`, `var_gems`, `cumulative_gems`, `cumulative_consume_gems` | `int`. Recompensa, gasto, guardado, reinicio y recuperación comprueban funciones distintas. | En `game.data` se escriben como `gems`, `lastGems`, `varGems`, `cumulativeGems`, `cumulativeConsumeGems`. En nube están en `gameData`. |
| `c<ID>_unlock`, `p<ID>_unlock` | `string` con `True`/`False` antes de recuperar y `true`/`false` también observados tras recuperar. Por perfil hay 42 y 58 claves. | `heroUnlock` y `petUnlock` usan bool JSON con el código como clave. Un valor local puede describir acceso o progresión. La procedencia comercial requiere comprobación independiente. |
| `c<ID>_level` | `int`. La mejora aislada `c0_level` de 0 a 1 y el guardado posterior demuestran la correspondencia del Caballero. | `gameData.heroLevel.Knight` y `heroLevel.Knight` en `game.data`. |
| `c<ID>_skin<N>` | `int` con valores negativos, cero y positivos. Se encontraron 802 claves por perfil y 802 coincidencias de ID localizado. | `skinLock` y `currentSkinDatas` son candidatos distintos para estado y selección. Queda por comprobar la conversión por valor. |
| `c_<código>_skill_<N>_unlock` | `int`. 105 claves aparecieron en el par de capturas tras recuperar un invitado. Ejemplo `c_Alchemist_skill_0_unlock`. | `heroSkillUnlock` / `heroSkill` y `Character<ID>_skill_<N>_name`. El índice del héroe se obtiene del código estable del catálogo. Los valores y transiciones específicas siguen pendientes. |
| `reborn_card` | `int` por perfil, observado tras recuperar. | `gameData.rebornCard` y `game.data.rebornCard` son bool. Queda por contrastar qué representa el entero frente a la bandera remota y qué fuente decide el derecho. |
| `OpenRijTest_Id` | Referencia de Discord. Ausente en las capturas XML inspeccionadas. | Función, tipo y contraparte remota pendientes. |
| `furniture_*` / `room_*` | `int` por perfil. Comprar el cofre creó `furniture_chest=1` en el XML antes de guardar. | Correlación parcial respecto a progresión del vestíbulo. Queda por aislar qué campos de `game.data`, `statistic` e inventario persisten la misma acción. |

Las 42 claves `heroUnlock` encajan por código con `char_code_name.json`. `p0` coincide con el código `Cat` y el nombre de catálogo `Chilly`. El guardado contiene 57 códigos de ese catálogo y un código adicional, `FishChipKing`. Esta diferencia importa al listar una partida mediante una tabla de traducciones. [Códigos de héroes](https://github.com/aznoobnam/skdfe/blob/57b9b86335c080caca55e178c8409cb67658ccf6/char_code_name.json) · [Códigos de mascotas](https://github.com/aznoobnam/skdfe/blob/57b9b86335c080caca55e178c8409cb67658ccf6/pet_code_name.json)

## Escritura local y recuperación

- Preferencias globales de idioma y resolución aparecieron sin prefijo. Son ajustes del cliente y no se observó su contraparte en el agregado examinado. El mismo XML también puede incluir cachés de sesión. Se conserva en almacenamiento privado.
- Las capturas de tutorial, mejora y compra enseñan preferencias más recientes que `game.data` hasta que se ejecuta el guardado normal. El HUD sigue el estado inmediato de la sesión. [Gemas en tres capas](../research/phase6-11/README.md)
- Con la recuperación oficial se observa `CoverPlayerPref` y la reconstrucción de claves de gemas, habilidades, mobiliario y `reborn_card` en el perfil activo. El segundo perfil continúa presente. Para habilidades, mobiliario y tarjeta queda por aislar la ruta fuente exacta de cada valor.
- Se inspeccionó XML de las capturas previas y se contrastó con el agregado. Las integraciones futuras deben tratar las preferencias como una proyección local que se puede leer con un parser XML, identificar explícitamente el perfil y conservar las grafías/tipos. Las compras y recompensas reclamadas se consultan como estados protegidos.

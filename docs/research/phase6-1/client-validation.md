# Validación con el cliente oficial 8.8.0

## Entorno

- AVD de laboratorio API 30, x86_64 con `libil2cpp` ARM64 por traducción, 4 CPU y 4 GiB.
- Cliente `com.ChillyRoom.DungeonShooter` 8.8.0 (`versionCode=1080800`).
- Sesión ChillyRoom conservada del perfil de laboratorio; login automático confirmado en el arranque.
- Red habilitada, sin bloqueo de IPv4/IPv6 y sin interceptación TLS.

No se usó Frida ni escaneo de memoria. La observación se hizo con capturas de pantalla, `adb logcat` y la extracción posterior de `files/` mediante `adb exec-out tar` con `adbd` en modo root.

## Secuencia observada

1. El cliente arrancó y llegó al menú con «Login succeeded».
2. El icono de nube abrió el panel. La primera captura mostró «Cloud save not found» mientras se cargaba.
3. Tras unos segundos, la fila superior (nube) mostró **1001** gemas y contador 5; la fila inferior (local) seguía en **1000**.
4. Se pulsó **Retrieve Progress** y se confirmó la advertencia de que la descarga sobrescribe el guardado local.
5. El panel volvió a mostrarse con **1001** en ambas filas.
6. El registro incluyó `CloudSaveGameData:CoverPlayerPref()` y `CloudSaveRunner:AutoDnloadAsync`.
7. Se cerró el panel, se pulsó **NEW GAME** y el hall abrió mostrando **1001** en el contador de gemas.

Capturas privadas:

| Archivo | Descripción |
| --- | --- |
| `game-cloudpanel2.png` | Fila de nube con `1001`, fila local con `1000` |
| `game-after-retrieve.png` | Ambas filas con `1001` tras recuperar |
| `game-select2.png` | Hall abierto con `1001` visible |

## Comprobación del archivo local

Después de la recuperación se extrajo el perfil del AVD y se decodificó `files/game.data` (XOR JSON, `AboGameData`):

| Campo | Valor |
| --- | --- |
| Tamaño | `25.496` bytes |
| Claves | `41` |
| `gems` | `1001` |

Esto confirma que el cliente no solo mostró el valor en el panel: aplicó la copia de nube al perfil local y lo escribió en `game.data`.

## Qué demuestra y qué no

**Demuestra:**

- El cliente oficial descarga y muestra el agregado subido desde Linux.
- La modificación de `game_data.gems` es interpretada por el cliente y aplicada al perfil.
- El juego puede abrir el hall con la copia recuperada.
- La sesión del cliente y la sesión usada desde Linux representan la misma cuenta de laboratorio.

**No demuestra:**

- Que el servidor valide reglas de progreso o anti-cheat para otros campos.
- Que una modificación arbitraria o de gran escala sea aceptada.
- Que el cliente no use cachés intermedias para otros datos; la comprobación se apoya en el panel, `game.data` y el hall de esta ejecución.
- Que el mismo resultado se repita en otra versión, región o canal.

## Trazabilidad

El log privado `retrieval-logcat.txt` conserva las líneas de `CoverPlayerPref`, `AutoDnloadAsync` y carga del hall. Las capturas y el perfil extraído permanecen bajo `~/.config/sk-under/phase6-1/`, fuera del repositorio. El emulador se detuvo después de la comprobación para liberar CPU.

# Aceptación de archivos y modificación controlada

**Estado: ACEPTACIÓN ESTRUCTURAL PARCIAL; ACEPTACIÓN VISIBLE NO DEMOSTRADA.**
El cliente cargó el perfil restaurado y el `game.data` modificado sin error de
integridad y sin borrar el archivo. No se observó el valor modificado en el
HUD y no se completó un ciclo limpio de guardado/recarga posterior al tutorial.
No se declara que el juego acepte la modificación.

## 1. Restauración no-op del perfil 5.6

Se restauró el perfil completo de 5.6 (`pre-restart-data.tar`: `files/` y
`shared_prefs/`, identidad de invitado de 5.6) sobre el AVD limpio, preservando
propietario y contexto SELinux. El cliente:

- cargó `LoadInitBundles`, la escena de login y `LoginInit:Start`;
- **no** emitió `SIGSEGV`;
- se quedó en el splash al 100 % / `LoginInit`, sin llegar al menú.

El bloqueo se atribuye al auto-login con el token y el host de la sesión de 5.6,
no a los bytes del perfil: la misma instalación con login manual fresco llega
al menú. No se observó aceptación, reparación ni rechazo del contenido.

## 2. Modificación de `game.data.gems`

Se usó la cuenta del titular recién logueada (no la sesión de 5.6) para evitar
el auto-login obsoleto. El perfil estaba en el menú principal/tutorial.

| Paso | Resultado |
| --- | --- |
| Archivo original | `game.data`, 25.460 bytes, 41 claves, `gems=0` |
| Edición | `gems=424242`, resto de claves intactas |
| Archivo modificado | 25.465 bytes; relectura con 41 claves y `gems=424242` |
| Copia de seguridad | Original conservado en el laboratorio privado |
| Despliegue | `game.data` en `/data/data/.../files/`, propietario `10167`, modo `600`, `restorecon` |
| Carga | El cliente cargó la cuenta del titular, el tutorial y el hall; sin error de integridad |
| Persistencia en ejecución | El archivo siguió con 25.465 bytes y `gems=424242`; el cliente no lo reescribió |
| HUD | El tutorial mostró `GEM×1000` y el hall mostró 1.000; **no** 424.242 |
| Recarga limpia | Bloqueada por el requisito de hotfix al bloquear la nube; no se completó |

La recompensa del tutorial explica la diferencia: el cliente otorgó 1.000 gemas
en memoria y el HUD mostró ese valor. El archivo modificado no se rechazó ni se
borró, pero tampoco se observó que su valor se usara en la interfaz. No se puede
distinguir “el cliente lo leyó y el tutorial lo sobrescribió en memoria” de “el
cliente lo ignoró y conservó el archivo hasta el próximo guardado” con la
evidencia disponible.

## 3. Qué se probó y qué no

**Probado:**

- El cliente acepta estructuralmente el `game.data` modificado: no hay error de
  integridad, no lo borra y lo mantiene mientras corre.
- El formato XOR de 8.8.0 conserva las 41 claves y el roundtrip es exacto.
- El cliente puede cargar un perfil restaurado hasta la escena de login sin el
  `SIGSEGV` de la primera tanda.
- La cuenta del titular se puede loguear por email en este AVD y llega al
  tutorial/hall.

**No probado:**

- Que el valor modificado se muestre en el HUD en un ciclo limpio.
- Que el cliente guarde el valor modificado en `game.data` o en la nube.
- Que una copia reconstruida por SK-Under pase `FixData`/`CheckSaveMac` y sea
  aceptada como partida.
- Que la modificación se pueda subir y recuperar.

## 4. Reversión

Al terminar, se restauró `game.data` desde la copia original y se verificó el
hash original. Se eliminaron las reglas `iptables` de bloqueo y se desactivó el
modo avión. No se ejecutó ninguna escritura remota y no se dejó el emulador
encendido.

## 5. Próximo experimento

1. Completar el tutorial y forzar un guardado normal (entrar y salir de una
   partida o usar el menú de pausa) para que el cliente escriba su estado.
2. Con el tutorial ya cerrado, editar `gems` y `lastGems` a un valor
   distintivo, restaurar y relanzar con el hotfix permitido pero la nube
   bloqueada.
3. Observar el HUD y volver a extraer `game.data`: si el valor persiste y se
   muestra, hay aceptación visible; si el cliente lo repara, registrar el valor
   de reparación.
4. Repetir con un campo visible de bajo impacto (por ejemplo, un héroe
   desbloqueado) para separar la semántica de `gems`/`lastGems` de la
   aceptación del archivo.
5. Solo después de la aceptación local, evaluar una escritura remota con copia
   de seguridad y autorización explícita.

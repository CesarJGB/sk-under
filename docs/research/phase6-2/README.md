# Fase 6.2: primer editor web funcional de gemas

**Resultado:** la página **Partida** descarga la copia auténtica de laboratorio, muestra `gameData.gems`, prepara una copia determinista que solo cambia ese campo, crea un respaldo privado, valida el resultado y expone una confirmación administrativa para subirla y verificarla. La escritura sigue deshabilitada por defecto y no puede activarse desde el navegador.

La nube de laboratorio ya contenía `gameData.gems=1001` al comenzar esta fase. Por esa razón **no se realizó una nueva escritura remota**: se verificó la lectura auténtica, una preparación sin cambios y una preparación local con `1002`. La preparación con `1002` no se confirmó. La evidencia de una subida real y de la aceptación por el cliente oficial 8.8.0 sigue siendo la de la [Fase 6.1](../phase6-1/README.md).

## Qué se implementó

| Capa | Resultado |
| --- | --- |
| Edición | `backend/app/cloud/gems_editor.py`: lectura, validación y modificación exclusiva de `gameData.gems` con serialización canónica. |
| Respaldos | `backend/app/cloud/backup_store.py`: original y candidato en un directorio privado, registro sin secretos y diario de eventos. |
| Servicio | `backend/app/cloud/lab_service.py`: preparar, confirmar, verificar y restaurar; la persistencia solo se declara tras una descarga posterior. |
| API | `backend/app/api/cloud_lab.py`: siete rutas `/api/v1/cloud/lab/*`; confirmar y restaurar exigen `X-SK-Cloud-Admin`. |
| Configuración | `SK_CLOUD_*` en `backend/app/settings.py`; escritura deshabilitada por defecto y credenciales solo en el servidor. |
| Frontend | `frontend/src/pages/LabEditorPage.tsx`: sección **Partida** con estado, gemas actuales, campo numérico, vista previa, respaldo, validación, confirmación, subida y restauración. |
| Pruebas | Pruebas unitarias, de API y Playwright; no contactan ChillyRoom. |

## Flujo real disponible

1. **Cargar partida**: `GET /api/v1/cloud/lab/save` descarga la copia auténtica y devuelve solo gemas, tamaño, SHA-256 y versión.
2. **Preparar**: `POST /api/v1/cloud/lab/prepare` vuelve a descargar, exige la serialización canónica, cambia solo `gameData.gems`, crea el respaldo y devuelve la vista previa.
3. **Confirmar**: `POST /api/v1/cloud/lab/confirm` comprueba que la nube sigue igual que al preparar, sube el candidato, vuelve a descargar y solo reporta `persisted=true` si el SHA-256 coincide. Exige `X-SK-Cloud-Admin` y la frase `SUBIR`.
4. **Verificar**: `POST /api/v1/cloud/lab/verify` compara la nube con el original y el candidato del respaldo.
5. **Restaurar**: `POST /api/v1/cloud/lab/restore` reenvía el original solo si la nube contiene exactamente el candidato confirmado. Exige `X-SK-Cloud-Admin` y la frase `RESTAURAR`.

Una preparación con el mismo valor produce `changed=false`; la confirmación remota se rechaza con `cloud_no_changes`. Esto permite validar el editor sin escribir cuando la cuenta ya tiene el valor de prueba.

## Resultado de la comprobación real

| Comprobación | Resultado |
| --- | --- |
| Estado del laboratorio | `read_only`: lectura disponible, escritura deshabilitada, autorización administrativa configurada. |
| Copia auténtica | `modern-cloud`, 114.778 bytes, `gems=1001`, `serialzed_version=1`. |
| SHA-256 remoto | `3f4b7617b04da3f1bd3b1b01197c46cf99d6ebd2a048c733d1738657239f492a` |
| Preparación sin cambios | `changed=false`, candidato idéntico al original, respaldo creado. |
| Preparación con `1002` | `changed=true`, 114.778 bytes, un byte distinto, SHA-256 candidato `d0e019c816921f0d…`; respaldo creado. |
| Conservación semántica | Al restaurar `gems=1001` en el candidato, el documento es idéntico al original; solo cambia `gameData.gems`. |
| Interfaz real | Playwright cargó la copia auténtica, mostró `1,001`, preparó `1002`, mostró `1001 → 1002`, mantuvo la confirmación deshabilitada y no registró errores de consola. |
| Escritura remota nueva | **No ejecutada**: la nube ya tenía `1001` y no había una modificación pendiente que justificara otra escritura. |
| Cliente oficial | **No reejecutado** en esta fase: no había emulador ni dispositivo disponible (`adb devices` vacío). La aceptación por 8.8.0 está documentada en la Fase 6.1. |

## Nivel de éxito declarado

- **Éxito mínimo:** conseguido. La web carga una partida, muestra sus gemas, acepta un valor y genera un agregado válido.
- **Éxito principal:** conseguido. La interfaz está conectada al backend, crea respaldos, valida que solo cambia `gameData.gems` y permite preparar la operación real.
- **Éxito avanzado:** no se repitió en esta fase una subida nueva porque la nube ya estaba en `1001`; la Fase 6.1 ya demostró subida auténtica, persistencia y recuperación por el cliente. El flujo web de confirmación y verificación está implementado y cubierto por pruebas, pero la combinación «confirmación web real + cliente oficial» no se ejecutó en esta fase.

## Archivos

- [Implementación](implementation.md): módulos, contratos, configuración y pruebas.
- [Seguridad](security.md): autorización, secretos, respaldos y límites.
- [Verificación](verification.md): comandos, resultados reales y estado de CI.

## Límites

- Solo se edita `gameData.gems`; pescados, materiales, personajes, armas y desbloqueos permanecen intactos y no tienen todavía editor.
- La serialización canónica reproduce la copia real de 8.8.0. Otra versión o cuenta con un formato distinto se rechaza en lugar de reformatearse.
- El rango `0..2147483647` es una cota conservadora; no se verificó la aceptación del servicio para valores grandes.
- La restauración depende de que la nube siga conteniendo el candidato exacto del respaldo; si cambió por otra vía, se detiene.
- La sesión de nube es un secreto de alta sensibilidad y debe obtenerse fuera de banda. No se implementó login ni multiusuario.
- No hay firma ni hash publicado por el servidor: la persistencia se comprueba comparando localmente lo enviado y lo descargado.

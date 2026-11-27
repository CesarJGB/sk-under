# Fase 9.4 — Descubrimiento, forja y progresión de armas

Fecha: 2026-11-26

## Objetivo

Investigar las estructuras que gobiernan el descubrimiento de armas, la
disponibilidad de la mesa de forja, los planos, las armas mitológicas y la
evolución, e implementar únicamente lo que tuviera evidencia suficiente. La
fase también promueve a E3 las skins de arma y los efectos de eliminación ya
validados físicamente por el propietario.

Toda la investigación de muestras y CRDE fue de solo lectura. No se subió ningún
candidato a una cuenta remota.

## Muestras y método

Se reutilizaron las muestras autorizadas de fases anteriores:

- Android Global avanzada A (`gameVersion` 2145).
- Android Global nueva B (`gameVersion` 2155, `AppVersion` 80800).
- iOS avanzada C, obtenida mediante visualización RAW autorizada de CRDE
  (canal iOS, 8.8.1).
- Android 8.6 local D y muestras 8.8.0 del repositorio.
- Catálogo de conocimiento 8.8.0 y catálogos locales de armas, planos, skins,
  materiales y mitológicas.

No se asumió que los identificadores o tipos de iOS fueran directamente
compatibles con Android Global. Las diferencias de codificación se documentan y
los escritores conservan la forma existente.

## Estructuras descubiertas

### Descubrimiento y contadores

`statisticData.object2ObtainTime` es un mapa de identificador de objeto a entero.
Incluye armas, anillos, enemigos y jefes, por lo que no es exclusivo de armas ni
una cantidad de inventario. Los valores observados incluyen cero, valores
pequeños y valores altos; la muestra 8.6 avanzada usa 9999 para todas sus claves
de arma. Por eso un valor positivo se interpreta como descubrimiento o registro
de obtención, sin afirmar que sea una fecha Unix ni una cantidad.

Evidencia: E2. El nombre de metadatos `ObtainWeaponTimes` y las referencias
`IsWeaponForgeUnlockByObtainTimes` apoyan la relación con forja, pero la regla
exacta del cliente no está confirmada.

### Cola de forja

`itemData.forgeWeapons` es una lista de cuatro posiciones con identificadores o
`null`. No es un desbloqueo permanente: las muestras pueden tener armas en la
cola con contador cero y viceversa. SK-Under la muestra en solo lectura y nunca
la escribe como sustituto del descubrimiento.

Evidencia: E2 para estructura; semántica permanente descartada.

### Evolución y posesión cosmética

`weaponEvolutionData.weapons.<arma>` contiene
`{Name, Level, CurrentSkinIndex, UnlockedSkins}`. La existencia del registro no
concede el arma base. El propietario confirmó que las skins pueden estar
disponibles aunque algunas armas sigan bloqueadas. `Level` y
`CurrentSkinIndex` no se modifican.

Evidencia: E3 para disponibilidad de skins; H para la semántica de
`CurrentSkinIndex`, `Level` y la posesión base.

### Colección y handbook

`statisticData.handbookWeaponCollectionTrackedLevels` es un mapa de arma a
entero. La muestra 8.6 avanzada tiene 518 entradas con valor 3; A no lo tiene y
B/C lo tienen vacío. Parece seguimiento de colección, no descubrimiento
universal. Se deja en solo lectura.

Evidencia: E2/H. No se implementa escritor.

### Planos

`itemData.blueprints` usa texto (`Got`/`Researched`) en muestras Android 8.6 y
enteros (`1`/`2`) en Android 8.8 e iOS 8.8.1. La propiedad e investigación de
planos es independiente del descubrimiento del arma. El editor existente ya
soporta ambas codificaciones, conserva alias y claves desconocidas y no rebaja
estados.

Evidencia: E2 para la escritura; no se modificó en esta fase.

### Armas mitológicas

`itemData.mythicWeapons` es una lista de `{id, level}`. Los identificadores
observados corresponden a `weapon_mythic_00..27` y las muestras tienen listas
vacías, parciales o completas. Todos los niveles observados son 3, pero no se ha
demostrado que 3 sea el máximo ni que la lista conceda la posesión funcional.
No se implementa escritura en 9.4.

Evidencia: E1/E2; requiere investigación en 9.5.

### Otras rutas

- `itemData.itemUnlock` contiene desbloqueos de vestíbulo y vehículos, no armas.
- `fusionWeaponPathUnlock` y `forgeWeaponMaterialPayments` suelen estar vacíos.
- `weapon2PurpleFramePassTime` está vacío en las muestras.
- `_AllMythicWeaponIds` solo aparece como nombre de metadatos, no como campo de
  guardado observado.

## Sistemas independientes y coordinados

| Sistema | Ruta | ¿Independiente? | Cambio en 9.4 |
| --- | --- | --- | --- |
| Descubrimiento | `statisticData.object2ObtainTime` | Sí | Sí, solo cero/ausente → 1 |
| Cola de forja | `itemData.forgeWeapons` | Sí, transitoria | No |
| Skin/evolución | `weaponEvolutionData.weapons` | Sí, cosmético | No se altera |
| Colección | `handbookWeaponCollectionTrackedLevels` | Probable | No |
| Planos | `itemData.blueprints` | Sí | No se altera |
| Mitológicas | `itemData.mythicWeapons` | Probable, requiere posesión | No |
| Marco morado | `weapon2PurpleFramePassTime` | Desconocido | No |

El descubrimiento y la skin son independientes. El descubrimiento y la forja
probablemente comparten el contador, pero la regla exacta debe validarse. Los
planos y las mitológicas no se deducen del contador.

## Implementación

### Catálogo

- `knowledge/tools/build_backend_weapons.py` proyecta el catálogo 8.8.0:
  995 armas no config-only y 494 forjables.
- `backend/app/catalogs/weapons.py` valida esquema, versión, recuento,
  identificadores y tipos.
- `backend/app/catalogs/weapons-880.json` es la proyección empaquetada.

### Editor de progresión

`backend/app/cloud/weapon_progression_editor.py`:

- Lee `statisticData.object2ObtainTime` y presenta 995 armas con nombre, tipo,
  nivel, forjabilidad, contador actual, propuesta, estado de forja y presencia en
  la cola.
- Conserva todos los contadores desconocidos y de otros objetos.
- Solo eleva un contador ausente o en cero a `1`; nunca reduce ni maximiza.
- Crea únicamente `statisticData.object2ObtainTime` cuando falta.
- No escribe `itemData.forgeWeapons`, `weaponEvolutionData`, `mythicWeapons` ni
  `blueprints`.
- Verifica reproducción exacta, estabilidad de serialización y restauración
  byte a byte del subárbol original para demostrar que no cambió nada ajeno.
- Es idempotente y expone `require_weapon_progression_write_compatibility`.

### Integración

La categoría `weapon_progression` se añadió al editor unificado antes de las
skins de arma. Está conectada en modelos Pydantic, API nativa, servicio de
sesión, servicio de laboratorio y almacén de respaldos. La UI añade una sección
de descubrimiento y forja dentro de la categoría **Armas**, con búsqueda,
filtros, selección individual, selección masiva, valores actuales/propuestos,
estado de forja y avisos E2. Las skins y los efectos conservan su lógica y ahora
muestran E3.

### Verificación en producción

La implementación se publicó el 2026-11-26 mediante GitHub Actions, Cloudflare
Pages y Coolify:

- `34ac692` añadió el catálogo de 995 armas, el editor de progresión, la UI y
  las pruebas. CI `45910094969` terminó correctamente.
- `c44f58e` corrigió la lectura de contadores ajenos al catálogo, incluida la
  clave vacía presente en la partida Android avanzada. CI `45910474911`
  terminó correctamente y Coolify desplegó el commit.
- `907beb1` corrigió el valor propuesto mostrado para un arma pendiente con
  contador `0`. CI `45911296127` terminó correctamente y el frontend quedó
  publicado.

La API de producción confirmó `commit` igual al último despliegue y el login de
una cuenta Android Global devolvió `weapon_progression` con 995 armas, 463
descubiertas y 404 con forja habilitada. Un `prepare-unified` real, sin
confirmación ni subida, seleccionó `weapon_135x`:

- único campo afectado: `statisticData.object2ObtainTime.weapon_135x`;
- valor propuesto: `1`;
- una categoría: `Descubrimiento de armas`;
- respaldo restaurable creado;
- ninguna escritura remota.

La UI de producción repitió el flujo con la fila `One Punch`, mostró
`Actual: sin registrar → Propuesto: 1`, abrió la revisión y dejó el candidato
sin confirmar. El SHA remoto no se modificó.

## Evidencia y validación

- Skins de arma y efectos de eliminación: **E3** por validación física del
  propietario en Android el 2026-11-26.
- Descubrimiento/forja: **E2 experimental**. La escritura es estructuralmente
  válida y conserva datos, pero el cliente aún no ha confirmado que el arma
  aparezca desbloqueada ni que la mesa de forja la acepte.
- `object2ObtainTime`: E2 para existencia, tipo, semántica probable y relaciones;
  persistencia H hasta la prueba física.
- Planos y mitológicas: sin cambios de escritura.

## Limitaciones y cuestiones abiertas

- No se ha demostrado que un contador positivo sea condición suficiente para la
  forja; pueden intervenir nivel, planos, materiales o derechos de servidor.
- No se conoce el valor máximo legítimo por arma; por eso no se maximiza.
- La cola de forja no es un desbloqueo permanente.
- No se ha validado la creación de contadores en una cuenta nueva.
- No se ha validado el comportamiento del cliente al abrir la mesa de forja con
  un contador añadido.
- Las mitológicas, sus niveles y la evolución requieren una investigación
  específica y coordinada.
- iOS no se usa para trasplantar identificadores ni para afirmar compatibilidad
  de escritura.

## Checklist de validación física Android

1. Elegir un arma forjable bloqueada y anotar su contador actual.
2. Preparar solo esa arma, revisar que el único campo afectado sea
   `statisticData.object2ObtainTime.<id>` y confirmar que el valor propuesto es 1.
3. Guardar, descargar de nuevo y comprobar que el contador persiste y que no se
   modificaron otros contadores.
4. Reiniciar el cliente y comprobar si el arma aparece descubierta o disponible
   en la colección.
5. Abrir la mesa de forja y comprobar si el arma aparece como forjable.
6. Repetir con un arma no forjable y confirmar que no se promete forja.
7. Probar una selección múltiple y verificar que no se alteran skins, cola ni
   planos.
8. Ejecutar rollback exacto y confirmar que el SHA vuelve al original.
9. Registrar plataforma, versión, arma, contador previo, resultado visual y
   cualquier corrección automática del cliente.

## Continuación en la fase 9.5

La [Fase 9.5](phase9-5-weapon-forge-unlock.md) resolvió la pregunta principal:
la forja no se habilita con cualquier contador positivo, sino al alcanzar el
umbral del nivel del arma. Se añadió una operación separada para desbloquear la
forja, se documentaron los umbrales estándar y la excepción de fusión
`weapon_337`, y se marcaron como pendientes los requisitos que todavía no tienen
evidencia suficiente.

Siguen abiertas las preguntas sobre `itemData.mythicWeapons`, la semántica de
`Level`/`CurrentSkinIndex` en evolución, los marcos de enemigos, monturas,
trofeos y monedas iniciales. No se implementa migración de cuentas ni edición
RAW arbitraria sin un diseño de seguridad y derechos de servidor.
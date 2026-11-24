# Referencia comunitaria de Discord

## Estado de la fuente

La referencia procede de un TXT privado aportado por el propietario del proyecto. El
archivo no se versiona y no se reproduce aquí. Su contenido se resume como pistas de
investigación, no como verdad verificada.

- Versión dominante: 8.5.0.
- Nivel de evidencia: E1.
- No se copian identificadores de cuenta, recibos ni valores privados.
- Una coincidencia con 8.8.0 es un candidato de investigación, no una confirmación.

## Aportes reutilizados

- Patrones de PlayerPrefs:
  - `{perfil}_c<ID>_unlock`
  - `{perfil}_p<ID>_unlock`
  - `{perfil}_c<ID>_skin<ID>`
  - `{perfil}_c_<código>_skill_<N>_unlock`
  - `{perfil}_unlock`
  - `{perfil}_gems`, `{perfil}_last_gems`, `{perfil}_var_gems`
  - `{perfil}_cumulative_gems`, `{perfil}_cumulative_consume_gems`
  - `{perfil}_reborn_card`
  - `{perfil}_furniture_fish_chips`
  - `{perfil}_furniture_chest`
  - `OpenRijTest_Id`
- Nombres de estadísticas como `achieve_record`, `object2ObtainTime`,
  `object2PassLevel` y `object2PassTime`.
- Estructuras de inventario, evolución de armas, temporadas y pase de batalla.
- Advertencias sobre diferencias entre archivos locales y agregados de nube.

## Límites

- La fuente no permite afirmar comportamiento en 8.8.0.
- Los patrones de PlayerPrefs no demuestran que el valor sea autoritativo frente a la nube.
- Los valores de `skinLock` negativos o grandes requieren experimentos propios.
- La tarjeta de resurrección sigue sin una representación autoritativa identificada.
- No se usa esta fuente para editar ni para declarar compatibilidad.
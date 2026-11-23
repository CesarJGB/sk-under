# Dependencia del cliente oficial

**Resumen:** Android sigue siendo necesario para **autenticar y transferir**
desde la nube; no para validar, comparar, editar o reconstruir una copia que ya
esté en disco. La frontera es la fuente de la revisión, no el procesamiento.

## 1. Matriz operación → dependencia

| Operación | Dependencia | Entrada | Salida | Evidencia | ¿Independiente en Linux? |
| --- | --- | --- | --- | --- | --- |
| Login Google/ChillyRoom | Cliente + servicio | Credenciales del titular | Sesión | Manual oficial. | No. |
| Subir progreso | Cliente + servicio | `CloudSaveGameData` local | Revisión remota | Manual oficial. | No. |
| Descargar progreso | Cliente + servicio | Cuenta + revisión | Agregado aplicado | Manual/FAQ. | No. |
| Restaurar en el juego | Cliente | Revisión | `PlayerPrefs`/`.data` | Flujo observado en 5.1. | No. |
| Obtener un archivo del agregado | Nadie lo documenta | — | — | Manual/FAQ/soporte. | **Bloqueado**. |
| Verificar tamaño/SHA-256 | Backend | Bytes | Informe | `cloud/validator.py`. | Sí. |
| Detectar JSON/gzip/RPC | Backend | Bytes | Formato | `cloud/decoder.py`. | Sí. |
| Descomprimir RPC gzip candidato | Backend, opt-in | Sobre + cuerpo | Agregado | Pruebas sintéticas. | Sí, no confirmado con muestra real. |
| Reconstruir el agregado | Backend | JSON/gzip | Modelo | `cloud_save.py`. | Sí. |
| Detectar secciones nulas/ausentes | Backend | Agregado | Informe | `cloud/preview.py`. | Sí. |
| Editar y serializar una copia | Laboratorio | JSON/gzip | Copia + diff | `cloud/lab.py`. | Sí. |
| Comparar 8.6.0/8.8.0 | Herramientas | Metadata + `.data` | Diff | `schema-diff-860-880.json`. | Sí. |
| Validar aceptación por el juego | Cliente oficial | Copia editada | Confirmación | No ejecutado. | No. |

## 2. Frontera de autorización

```text
Titular ──cuenta──> Cliente oficial ──nube──> Servicio
                         │
                         └── restauración local (PlayerPrefs/.data)
                                      │
                                      ▼
                             Copia suministrada
                                      │
                                      ▼
                         Backend Linux (sin red)
```

El backend no sustituye la autenticación ni la restauración. Un consentimiento
para iniciar sesión en el juego no documenta una delegación a un servicio
externo.

## 3. Qué se puede mover a Linux

- Validación de integridad y formato.
- Detección de versión por estructura (no por confianza en un campo).
- Reconstrucción y conservación de campos desconocidos.
- Edición no destructiva y comparación semántica/binaria.
- Informes de diferencias y pruebas de regresión.

## 4. Qué no se puede mover sin el proveedor

- La sesión y la identidad de la cuenta.
- La autorización de lectura de la nube.
- La obtención de una revisión concreta.
- La confirmación de que el cliente acepta una copia editada.
- La restauración de compras o la migración de cuenta.

## 5. Riesgos

| Riesgo | Impacto | Mitigación actual |
| --- | --- | --- |
| Uso de endpoints privados | Legal/técnico | Transporte remoto deshabilitado. |
| Reutilización de tokens | Seguridad | No se almacenan ni se extraen. |
| Vinculaciones | Pérdida de cupo | No se automatiza login. |
| Datos privados en Git | Privacidad | `.gitignore`, CI de higiene, muestras fuera del repo. |
| Edición no aceptada | Corrupción | Laboratorio local; no se declara compatibilidad. |
| Códec RPC no confirmado | Falso positivo | Opt-in, firma gzip y errores tipados. |

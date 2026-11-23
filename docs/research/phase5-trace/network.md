# Observabilidad por UID y por ventana

El control de esta fase compara la actividad de todo el invitado con conexiones TCP del UID de Soul Knight. Las [70 muestras](muestras-red.txt) conservan epoch, número de sockets TCP establecidos con puerto remoto 443, número de destinos distintos y bytes acumulados RX/TX de wlan0. El sondeo toma una instantánea aproximadamente cada cinco segundos. La primera y la segunda ejecución usan el mismo UID.

| Ventana UTC | Medición | Alcance |
| --- | --- | --- |
| 04:00:37–04:00:42, juego cerrado | +1 094 bytes RX, +929 TX, cero sockets del UID | Demuestra tráfico de fondo con la aplicación cerrada. |
| 04:00:42–04:01:19, arranque | +434 698 bytes RX, +134 583 TX, de cero a once sockets | El conteo corresponde al juego. Los bytes incluyen todo el Wi-Fi virtual. |
| 04:05:32–04:05:37 | Cinco sockets a cinco destinos en ambas muestras; dos nombres SNI del proveedor | Coincidieron IP de destino del ClientHello y socket del UID en el mismo segundo de epoch entero para el gateway, y con un segundo de diferencia para dc. |
| 04:06:04–04:06:25, apertura del formulario | +439 998 bytes RX y +63 284 TX. Cuatro sockets en ambos extremos | La apertura de la vista precedió a una autenticación. El contador no identifica mensajes ni permite medir una subida de partida. |
| Envío de login, panel y restauración | Sin muestra nueva de estas tres ventanas | Los dominios de autenticación y almacenamiento y los volúmenes de una lectura siguen sin identificar. |

El SNI se leyó de los ClientHello iniciales de TLS sobre TCP/IPv4 en el espacio de red exclusivo del AVD. Se proyectaron únicamente hora, destino y nombre anunciado en memoria. No se guardaron paquetes ni se abrieron sesiones TLS. El emulador traduce conexiones del invitado. La comparación por IP y tiempo admite destinos compartidos, y el nombre anunciado tampoco demuestra qué operación HTTP siguió. El muestreo puede perder conexiones breves, reuso de TLS, QUIC, ClientHello fragmentados y nombres cifrados. El filtro de nombres DNS UDP del ensayo no produjo una atribución utilizable.

## Repetir con un dispositivo de laboratorio

En el AVD de [Fase 5.1](../phase5-experimental/laboratorio.md), instalar primero el paquete y ejecutar desde esta carpeta. La primera orden funciona con los permisos ordinarios de ADB. Abrir el juego en otra terminal durante el sondeo.

```sh
adb -s emulator-5554 shell sh -s 70 5 < muestra-red.sh
adb -s emulator-5554 shell date -u +%s
```

El script resuelve el UID por nombre de paquete y filtra la salida de `ss -nte`. En esta imagen ss recurrió a procfs al denegarse el socket netlink. Los contadores de interfaz proceden de `/proc/net/dev`; los de sysfs estaban restringidos. En otro dispositivo verificar primero que la shell puede ver las filas del UID. Un conteo cero con visibilidad restringida no constituye una medición negativa.

Para obtener SNI en el espacio de red aislado se usó esta proyección, limitada a ClientHello iniciales. Cruzar temporalmente el destino con el peer remoto de `ss -nte` en el invitado, muestreado aproximadamente cada dos segundos y filtrado por el UID de la app. Conservar en el informe solo la coincidencia y el dominio público verificado. Usar logcat del PID con `-v epoch` proyectando únicamente hora y marcador de método, y marcar cada acción de UI con epoch del host.

```sh
timeout 186 tcpdump -U -i eth0 -s 1600 -w - \
  'ip and tcp dst port 443 and tcp[((tcp[12] & 0xf0) >> 2):1] = 22 and tcp[((tcp[12] & 0xf0) >> 2)+5:1] = 1' |
  tshark -n -r - -Y tls.handshake.extensions_server_name -T fields \
    -e frame.time_epoch -e ip.dst -e tls.handshake.extensions_server_name -l
```

Las dos conexiones previas al formulario corresponden a nombres diferentes. Aún no se puede asignarles funciones diferenciadas de autenticación, telemetría o almacenamiento.

Como control posterior se tomaron tres lecturas de la hora Android entre dos lecturas del host. En las tres, el invitado quedó entre 0,72 y 1,00 segundos por detrás de los límites medidos en el host (redondeados). Los emparejamientos SNI/socket anteriores usan epoch sin ajuste y resolución entera para el socket. Su precisión es del orden de segundos.

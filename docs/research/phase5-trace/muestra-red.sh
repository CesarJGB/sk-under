#!/system/bin/sh
# Ejecutar mediante adb shell sh. Solo stdout agregado del invitado.
set -eu
package=com.ChillyRoom.DungeonShooter
app_uid=$(cmd package list packages -U "$package" | awk -v pkg="package:$package" '$1 == pkg {sub(/^uid:/,"",$2); print $2}')
case "$app_uid" in ""|*[!0-9]*) exit 1 ;; esac
printf '%s\n' 'epoch sockets_tcp443_uid destinos_tcp443_uid wlan_rx_bytes wlan_tx_bytes'
for _ in $(seq 1 "${1:-12}"); do
    stamp=$(date +%s)
    # En API 30 ss puede recurrir a procfs cuando netlink devuelve EACCES.
    sockets=$(ss -nte 2>/dev/null)
    counts=$(printf '%s\n' "$sockets" | awk -v uid="uid:$app_uid" '
        $1 == "ESTAB" && $5 ~ /:443$/ {
            for (i=6; i<=NF; i++) if ($i == uid) {n++; peers[$5]=1; break}
        }
        END {for (p in peers) d++; print n+0,d+0}')
    bytes=$(awk '$1 == "wlan0:" {print $2,$10; found=1} END {if (!found) exit 1}' /proc/net/dev)
    printf '%s %s %s\n' "$stamp" "$counts" "$bytes"
    sleep "${2:-5}"
done

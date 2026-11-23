#!/system/bin/sh
# Ejecutar en el invitado. Un proceso por marca, sin acciones sobre el juego.
set -eu
package=com.ChillyRoom.DungeonShooter
if [ "${1:-}" = events ]; then
    pid=$(pidof "$package") || exit 1
    logcat -d --pid="$pid" -v threadtime -v monotonic 2>/dev/null | awk '
       $1 ~ /^[0-9]+[.][0-9]+$/ {
           if (match($0, /JNI_OnLoad|InitSDK|LoginOptions|OnLoginResultAction|NewCloudSaveAgent[.:]+ForceFetchData|NewCloudSaveAgent[.:]+FetchData|ParseJsonToCloudSaveGameData|CreateFromPlayerPref|GetExtraDescribe|CoverPlayerPref|ArgumentNullException/))
               print $1,substr($0,RSTART,RLENGTH)
       }'
    exit
fi
case "${1:-}" in
    control|launch|login|idle|panel|summary|retrieve|dialog|cancel|confirm|applied|login-screen) ;;
    *) exit 2 ;;
esac
read -r start _ < /proc/uptime
pid=$(pidof "$package" || true)
app_uid=$(cmd package list packages -U "$package" |
    awk -v p="package:$package" '$1 == p && $2 ~ /^uid:[0-9]+$/ {print substr($2,5)}')
sockets=ND
if [ -n "$app_uid" ] && rows=$(ss -nte 2>/dev/null); then
    sockets=$(printf '%s\n' "$rows" | awk -v uid="uid:$app_uid" '
      $1 == "ESTAB" && $5 ~ /:443$/ {
          for (i=6;i<=NF;i++) if ($i == uid) n++
      }
      END {print n+0}')
fi
net=$(awk '$1=="wlan0:" {print $2, $10; seen=1} END {if (!seen) print "ND ND"}' /proc/net/dev)
localfile=/sdcard/Android/data/$package/files/game.data
file=$(stat -c '%s,%Y' "$localfile" 2>/dev/null || echo ND)
read -r end _ < /proc/uptime
printf '%s %s %s %s %s %s %s\n' "$1" "$start" "$end" "${pid:-ND}" "$sockets" "$net" "$file"

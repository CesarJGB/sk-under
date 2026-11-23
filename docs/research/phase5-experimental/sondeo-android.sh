#!/usr/bin/env bash
set -euo pipefail

serial=${1:?Uso: bash sondeo-android.sh SERIAL [RUTA_A_ADB]}
adb=${2:-adb}
package=com.ChillyRoom.DungeonShooter

device() {
    "$adb" -s "$serial" "$@" </dev/null
}

if [[ $(device get-state) != device ]]; then
    printf '%s\n' 'El dispositivo Android no está conectado.' >&2
    exit 1
fi

for property in sys.boot_completed ro.build.version.sdk ro.build.type ro.product.cpu.abilist ro.dalvik.vm.native.bridge; do
    printf '%s=%s\n' "$property" "$(device shell getprop "$property" | tr -d '\r')"
done
printf 'SELinux=%s\n' "$(device shell getenforce | tr -d '\r')"

installed=$(device shell pm list packages "$package" | tr -d '\r')
if [[ $installed != "package:$package" ]]; then
    printf '%s\n' 'Soul Knight no está instalado en el dispositivo seleccionado.' >&2
    exit 1
fi

device shell dumpsys package "$package" |
    awk '/^[[:space:]]+(versionName|versionCode|primaryCpuAbi)=/ {sub(/\r$/, ""); print}'

if result=$(device shell run-as "$package" id 2>&1); then
    printf '%s\n' 'run-as=permitido'
elif [[ $result == *'not debuggable'* ]]; then
    printf '%s\n' 'run-as=paquete no depurable'
else
    printf '%s\n' 'run-as=no disponible'
fi

for path in "/data/user/0/$package/files" "/sdcard/Android/data/$package/files" "/sdcard/Android/media/$package"; do
    if result=$(device shell ls -d "$path" 2>&1); then
        state=visible
    elif [[ $result == *'Permission denied'* ]]; then
        state=denegado
    elif [[ $result == *'No such file or directory'* ]]; then
        state=ausente
    else
        state=indeterminado
    fi
    printf '%s=%s\n' "$path" "$state"
done

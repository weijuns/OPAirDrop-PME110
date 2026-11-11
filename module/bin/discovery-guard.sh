#!/system/bin/sh
# Explicit native test session only. No boot installation, reboot, driver changes,
# global freezer changes, or fabricated peers. Keep an existing app alive by
# starting its existing service only after observing cached/frozen/missing state.
MODDIR=${0%/bin/*}
. "$MODDIR/bin/common.sh"
BASE=/data/adb/opairshare_pme110
mkdir -p "$BASE"
chmod 0700 "$BASE"
SELF=$MODDIR/bin/discovery-guard.sh
LOCK=$BASE/discovery-guard.lock
LOG=$BASE/discovery-guard.log
APP=com.google.android.mosey
EXPECTED_FFI=ec8f58c686046788bacb628793c83c28f7659e524cf23afaf5511bf32af5447a

owner_pid() {
    guard_pid=$(cat "$LOCK/pid" 2>/dev/null)
    case "$guard_pid" in ''|*[!0-9]*) return 1 ;; esac
    [ -r "/proc/$guard_pid/cmdline" ] || return 1
    tr '\000' ' ' < "/proc/$guard_pid/cmdline" |
        grep -Fq "$SELF run" || return 1
    echo "$guard_pid"
}

case "${1:-status}" in
    status)
        if active=$(owner_pid); then echo "guard=$active"; else echo 'guard=none'; fi
        echo "enabled=$(getprop debug.opairshare.nativenet)"
        tail -n 12 "$LOG" 2>/dev/null
        exit 0
        ;;
    stop)
        if active=$(owner_pid); then kill -TERM "$active"; echo "guard stop requested: $active";
        else echo 'guard=none'; fi
        exit 0
        ;;
    start)
        [ "$(id -u)" = 0 ] || { echo 'root required'; exit 1; }
        [ "$(getprop debug.opairshare.nativenet)" = 1 ] || { echo 'native test session is off'; exit 1; }
        if active=$(owner_pid); then echo "guard=$active (already running)"; exit 0; fi
        setsid /system/bin/sh "$SELF" run </dev/null >>"$LOG" 2>&1 &
        exit 0
        ;;
    run) ;;
    *) echo 'usage: mtk-discovery-guard.sh start|stop|status'; exit 2 ;;
esac

[ "$(id -u)" = 0 ] || exit 1
if ! mkdir "$LOCK" 2>/dev/null; then
    if owner_pid >/dev/null; then exit 0; fi
    # Give a concurrently starting owner time to write its pid before reclaiming.
    sleep 1
    if owner_pid >/dev/null; then exit 0; fi
    rm -f "$LOCK/pid"
    rmdir "$LOCK" 2>/dev/null || exit 1
    mkdir "$LOCK" 2>/dev/null || exit 1
fi
echo $$ > "$LOCK/pid"
cleanup() {
    if [ "$(cat "$LOCK/pid" 2>/dev/null)" = "$$" ]; then
        rm -f "$LOCK/pid"; rmdir "$LOCK" 2>/dev/null
    fi
}
trap 'exit 0' TERM INT HUP
trap cleanup EXIT
# Children must not remain in adbd's cgroup when USB changes.
# Root is already the current group on this phone; this is scoped to our process.
echo $$ > /sys/fs/cgroup/cgroup.procs || { echo 'cannot detach adbd cgroup'; exit 1; }
echo "$(date '+%F %T') guard started pid=$$"
last_app=
last_server=
while [ "$(getprop debug.opairshare.nativenet)" = 1 ] && [ ! -e "$MODDIR/disable" ] && [ ! -e "$MODDIR/remove" ]; do
    if [ ! -d /sys/class/ieee80211/wonder ]; then
        echo "$(date '+%F %T') wonder binding missing; stopping without loading modules"
        exit 1
    fi
    server_pid=$(pidof mosey_server | awk '{print $1}')
    if [ -z "$server_pid" ]; then
        actual_ffi=$(sha256sum /data/moapp/lib64/libmosey_daemon_ffi.so 2>/dev/null | awk '{print $1}')
        if [ "$actual_ffi" != "$EXPECTED_FFI" ]; then
            echo "$(date '+%F %T') unexpected FFI; stopping"; exit 1
        fi
        echo "$(date '+%F %T') daemon missing; starting"
        env -u LD_PRELOAD /data/moapp/mosey_server >>$BASE/mtk_wonder_server.log 2>&1 </dev/null &
        sleep 2
        server_pid=$(pidof mosey_server | awk '{print $1}')
    fi
    app_pid=$(pidof "$APP" | awk '{print $1}')
    adj=0
    frozen=0
    if [ -n "$app_pid" ]; then
        adj=$(cat "/proc/$app_pid/oom_score_adj" 2>/dev/null)
        case "$adj" in ''|*[!0-9-]*) adj=0 ;; esac
        group=$(awk -F: '$1 == 0 {print $3}' "/proc/$app_pid/cgroup" 2>/dev/null)
        if [ -n "$group" ]; then
            frozen=$(awk '$1 == "frozen" {print $2}' "/sys/fs/cgroup$group/cgroup.events" 2>/dev/null)
        fi
    fi
    reason=
    if [ -z "$app_pid" ]; then reason=missing;
    elif [ "$frozen" = 1 ]; then reason=frozen;
    elif [ "$adj" -ge 900 ]; then reason=cached;
    elif [ "$server_pid" != "$last_server" ]; then reason=daemon_changed; fi
    if [ -n "$reason" ]; then
        echo "$(date '+%F %T') restore reason=$reason app=$app_pid adj=$adj frozen=$frozen daemon=$server_pid"
        # DURATION is milliseconds. A short admission window, not a permanent exemption.
        run_framework /system/bin/cmd deviceidle tempwhitelist -u 0 -d 20000 "$APP"
        run_framework /system/bin/am startservice --user 0 -n "$APP/.ExternalSharingService"
    fi
    if [ "$app_pid" != "$last_app" ] || [ "$server_pid" != "$last_server" ]; then
        echo "$(date '+%F %T') processes app=$app_pid daemon=$server_pid"
    fi
    last_app=$app_pid
    last_server=$server_pid
    sleep 3
done
echo "$(date '+%F %T') native test flag off; guard stopped"

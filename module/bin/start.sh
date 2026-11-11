#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
MODDIR=${0%/bin/*}
. "$MODDIR/bin/common.sh"
enabled && compatible || exit 1
check_hash /data/moapp/mosey_server "$DAEMON_SHA" || exit 1
check_hash /data/moapp/lib64/libmosey_daemon_ffi.so "$FFI_SHA" || exit 1
if [ -d /sys/module/mtk_wonder_bind ]; then
    [ "$(cat /sys/module/mtk_wonder_bind/parameters/activate)" = Y ] || exit 1
else
    insmod "$MODDIR/kernel/mtk_wonder_bind.ko" provider_node=/soc/pinctrl/eint0default wonder_node=/soc/pinctrl/camdefault activate=1 || exit 1
fi
[ -d /sys/class/ieee80211/wonder ] || exit 1
if ! pidof mosey_server >/dev/null; then
    env -u LD_PRELOAD /data/moapp/mosey_server >> "$STATE/server.log" 2>&1 </dev/null &
fi
# Install the owned companion after boot. Never kill existing host processes.
sh "$MODDIR/bin/install-oshare.sh" "$MODDIR" boot || exit 1
setprop debug.opairshare.autodiscovery 1
setprop debug.opairshare.nativenet 1
setprop debug.opairshare.receiveonly 0
setprop debug.opairshare.receive.ready 1
cmd deviceidle tempwhitelist -u 0 -d 20000 com.google.android.mosey
am startservice --user 0 -n com.google.android.mosey/.ExternalSharingService
sh "$MODDIR/bin/discovery-guard.sh" start

#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
MODDIR=${0%/*}
. "$MODDIR/bin/common.sh"
exec >> "$STATE/boot.log" 2>&1
enabled && compatible || { echo 'Unsupported or disabled; no driver changes'; exit 1; }
n=0
while [ "$(getprop sys.boot_completed)" != 1 ]; do
    n=$((n+1)); [ "$n" -le 90 ] || exit 1; sleep 2
done
sh "$MODDIR/bin/start.sh" || exit 1

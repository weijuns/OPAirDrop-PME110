#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
MODDIR=${MODDIR:-/data/adb/modules/opairshare_pme110}
STATE=${STATE:-/data/adb/opairshare_pme110}
EXPECTED_KERNEL=6.12.69-android16-6-g242e1a07f878-ab15865446-4k
DAEMON_SHA=c56a69c00500d3bf91063560e2452b4d6e216ff63b659831b3cae2f01e75d827
FFI_SHA=ec8f58c686046788bacb628793c83c28f7659e524cf23afaf5511bf32af5447a
mkdir -p "$STATE"
chmod 0700 "$STATE"
check_hash() { [ "$(sha256sum "$1" 2>/dev/null | awk '{print $1}')" = "$2" ]; }
compatible() {
    [ "$(getprop ro.product.model)" = PME110 ] &&
    [ "$(getprop ro.board.platform)" = mt6993 ] &&
    [ "$(uname -r)" = "$EXPECTED_KERNEL" ]
}
enabled() { [ ! -e "$MODDIR/disable" ] && [ ! -e "$MODDIR/remove" ]; }
# Android shellCommand transfers stdout/stderr FDs to system_server. Private
# module log files cannot be passed through Binder; capture via a pipe first.
run_framework() {
    framework_output=$("$@" 2>&1)
    framework_status=$?
    [ -z "$framework_output" ] || printf '%s\n' "$framework_output"
    return "$framework_status"
}

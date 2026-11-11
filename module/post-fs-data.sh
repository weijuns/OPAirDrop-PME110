#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
MODDIR=${0%/*}
. "$MODDIR/bin/common.sh"
enabled && compatible || exit 1
exec >> "$STATE/boot.log" 2>&1
echo "$(date) post-fs-data"
sh "$MODDIR/bin/cleanup-retired.sh" || echo 'Retired cache cleanup deferred.'
check_hash "$MODDIR/runtime/mosey_server" "$DAEMON_SHA" || exit 1
check_hash "$MODDIR/runtime/lib64/libmosey_daemon_ffi.so" "$FFI_SHA" || exit 1
# The stock daemon has an absolute /data/moapp library path. Never replace
# files while an existing daemon is using them.
if ! pidof mosey_server >/dev/null; then
    mkdir -p /data/moapp/lib64
    cp "$MODDIR/runtime/mosey_server" /data/moapp/mosey_server || exit 1
    cp "$MODDIR/runtime/lib64/libmosey_daemon_ffi.so" /data/moapp/lib64/ || exit 1
    chmod 0755 /data/moapp/mosey_server
    chmod 0644 /data/moapp/lib64/libmosey_daemon_ffi.so
fi
sh "$MODDIR/bin/gms.sh" mount "$MODDIR" || exit 1
# Refresh the service-manifest cache using the same existing mechanism.
touch /apex/apex-info-list.xml

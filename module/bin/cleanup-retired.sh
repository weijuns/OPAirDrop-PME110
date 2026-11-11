#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# A live migration may leave old bind-mount roots that the kernel will not
# unlink. They are no longer modules and are reclaimed after their last boot.
set -eu
MODDIR=${0%/bin/*}
. "$MODDIR/bin/common.sh"
CACHE="$STATE/retired-mounts"
[ -d "$CACHE" ] || exit 0
[ ! -L "$CACHE" ] || exit 1
MOUNTS=${OPAIR_RETIRED_MOUNTINFO:-/proc/1/mountinfo}
[ -r "$MOUNTS" ] || exit 1
# mountinfo roots on the /data filesystem are relative to that mount, so both
# /data/adb/... and /adb/... representations must be treated as references.
if grep -F -e "$CACHE/" -e "${CACHE#/data}/" "$MOUNTS" >/dev/null; then
    echo 'Retired files are still referenced by this boot; cleanup deferred.'
    exit 0
fi
if ! rm -rf "$CACHE" 2> "$STATE/retired-cleanup.log"; then
    echo 'Retired cache remains busy; cleanup deferred. See retired-cleanup.log.'
    exit 0
fi
rm -f "$STATE/retired-cleanup.log"
echo 'Retired mount cache removed.'

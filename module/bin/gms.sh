#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# Reimplementation of the feature filtering used by fei-ke's Unlock CN GMS.
set -eu
ACTION=${1:?prepare or mount}
BASE=${2:?module path}
case "$ACTION" in
prepare)
    mkdir -p "$BASE/gms"
    while IFS= read -r path; do
        [ -f "$path" ] || continue
        mkdir -p "$BASE/gms${path%/*}"
        awk -f "$BASE/bin/gms-filter.awk" "$path" > "$BASE/gms$path"
    done < "$BASE/bin/gms-paths.txt"
    ;;
mount)
    while IFS= read -r path; do
        [ -f "$BASE/gms$path" ] && [ -f "$path" ] || continue
        cmp -s "$BASE/gms$path" "$path" && continue
        mount -o ro,bind "$BASE/gms$path" "$path"
    done < "$BASE/bin/gms-paths.txt"
    ;;
*) exit 2;;
esac

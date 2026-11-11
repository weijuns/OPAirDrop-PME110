#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
MODDIR=${0%/bin/*}
. "$MODDIR/bin/common.sh"
json() {
    awk 'BEGIN {printf "{"; for(i=1;i<ARGC;i+=2){if(i>1)printf ",";q(ARGV[i]);printf ":";q(ARGV[i+1])}print "}";exit}
    function q(s,j,c){printf "\"";for(j=1;j<=length(s);j++){c=substr(s,j,1);if(c=="\\")printf "\\\\";else if(c=="\"")printf "\\\"";else if(c=="\n")printf "\\n";else if(c=="\r")printf "\\r";else if(c=="\t")printf "\\t";else if(c~/[[:cntrl:]]/)printf "?";else printf "%s",c}printf "\""}' "$@"
}
read_setting() { value=$(settings get global "$1"); [ "$value" = null ] && value=; printf '%s' "$value"; }
decode() {
    [ -n "$1" ] || return 0
    # Hex is used throughout the command boundary; never evaluate user input.
    esc=$(printf '%s' "$1" | sed 's/../\\x&/g')
    /data/adb/ksu/bin/busybox printf '%b' "$esc"
}
app_state() {
    if pidof "$1" >/dev/null; then echo running
    elif pm path "$1" 2>/dev/null | grep -q '^package:'; then echo idle
    else echo not_installed; fi
}
status() {
    custom=$(decode "$(read_setting opairshare_airdrop_name_hex)")
    default=$(getprop ro.vendor.oplus.market.enname)
    [ -n "$default" ] || default=$(getprop ro.product.model)
    directory=$(decode "$(read_setting opairshare_receive_directory_hex)")
    mode=$(read_setting opairshare_share_mode)
    case "$mode" in quickshare|oshare|both) ;; *) mode=both;; esac
    active=$(getprop debug.opairshare.share_mode)
    case "$active" in quickshare|oshare|both) ;; *) active=both;; esac
    awdl=idle; pidof mosey_server >/dev/null && awdl=running
    ready=off
    service check com.google.android.moseyservice.IMoseyService/default 2>/dev/null | grep -q ': found$' && ready=on
    session=off; ip link show mosey0 2>/dev/null | grep -q '<[^>]*UP' && session=on
    callback=off; pidof com.google.android.mosey >/dev/null && callback=on
    version=$(sed -n 's/^version=//p' "$MODDIR/module.prop")
    json coexist on scope auto profile fast autostart on version "$version" \
        share_mode "$mode" share_mode_active "$active" \
        airdrop_name "${custom:-$default}" airdrop_name_default "$default" airdrop_name_custom "$custom" \
        receive_directory "$directory" ready "$ready" editable on session "$session" \
        frequency '' channel '' network '' radio '' matcher '' pending '' phy '' mcs '' nss '' batch '' collect '' \
        callback "$callback" awdl "$awdl" quickshare "$(app_state com.google.android.mosey)" oshare "$(app_state com.coloros.oshare)"
}
write_hex() {
    case "$2" in *[!0-9a-fA-F]*|'') exit 2;; esac
    [ $(( ${#2} % 2 )) -eq 0 ] && [ "${#2}" -le 1024 ] || exit 2
    settings put global "$1" "$2" || exit 1
    status
}
logs() {
    for f in "$STATE/boot.log" "$STATE/server.log" "$STATE/discovery-guard.log" "$STATE/oshare-install.log"; do
        [ -f "$f" ] || continue
        echo "=== ${f##*/} ==="; tail -n 100 "$f"
    done
}
case "${1:-status}" in
    status) status;;
    name-set) write_hex opairshare_airdrop_name_hex "${2:-}";;
    name-reset) settings delete global opairshare_airdrop_name_hex >/dev/null; status;;
    receive-directory-set) write_hex opairshare_receive_directory_hex "${2:-}";;
    receive-directory-reset) settings delete global opairshare_receive_directory_hex >/dev/null; status;;
    share-mode)
        case "${2:-}" in quickshare|oshare|both) ;; *) exit 2;; esac
        settings put global opairshare_share_mode "$2" || exit 1
        status;;
    history) printf '{"recorder":"off","live":{},"history":[]}\n';;
    logs) logs;;
    export-logs)
        out=/sdcard/Download/OPAirShare/opairdrop-pme110-$(date +%Y%m%d-%H%M%S).log
        mkdir -p /sdcard/Download/OPAirShare || exit 1
        { sh "$MODDIR/bin/doctor.sh"; logs; } > "$out" || exit 1
        json path "$out";;
    *) exit 2;;
esac

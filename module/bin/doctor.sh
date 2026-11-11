#!/system/bin/sh
# Read-only: usable before/after staging without changing the working session.
MODDIR=${0%/bin/*}
. "$MODDIR/bin/common.sh"
echo "Model: $(getprop ro.product.model)"
echo "Kernel: $(uname -r)"
echo "Boot ID: $(cat /proc/sys/kernel/random/boot_id)"
echo "SELinux: $(getenforce)"
echo "Daemon: $(pidof mosey_server)"
echo "Mosey: $(pidof com.google.android.mosey)"
echo "OShare: $(pidof com.coloros.oshare)"
echo "Wonder: $(cat /sys/module/mtk_wonder_bind/parameters/activate 2>/dev/null)"
echo "Native session: $(getprop debug.opairshare.nativenet)"
service check com.google.android.moseyservice.IMoseyService/default
pm path com.tlsu.oshareairdrop
pm path com.google.android.mosey
ip link show mosey0
echo "Backup: $(cat "$STATE/latest-backup" 2>/dev/null)"

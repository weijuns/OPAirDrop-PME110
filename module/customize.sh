#!/system/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
ui_print "- OPAirDrop PME110 1.1.0 · weijuns"
ui_print "- 感谢 TimelessU / Weverses、34306、fei-ke"
[ "$BOOTMODE" = true ] || abort "请在已启动的 Android 中通过 KernelSU 安装"
MODDIR=$MODPATH
. "$MODPATH/bin/common.sh"
compatible || abort "仅支持已验证的 PME110 / MT6993 精确内核"
(cd "$MODPATH" && sha256sum -c SHA256SUMS >/dev/null) || abort "安装包校验失败"
/system/bin/pm path com.google.android.mosey >/dev/null 2>&1 || abort "缺少已初始化的 Mosey；请先按 README 准备设备"
/system/bin/pm path com.tlsu.oshareairdrop >/dev/null 2>&1 || abort "此版本为现有可用环境的合并升级包，需要已启用的 OShare 桥接"
package_info=$(/system/bin/dumpsys package com.google.android.mosey 2>/dev/null)
printf '%s\n' "$package_info" | grep -q 'versionCode=27391 ' || abort "需要已验证的 Mosey 27391"
[ -f /data/adb/lspd/config/modules_config.db ] || abort "需要已初始化的 LSPosed"
# Vendor APKs and the native service stay on the owner's device. The public ZIP
# contains our source-built bridge/driver, and imports verified local inputs.
OLD=/data/adb/modules/mosey_pme110
if [ -d "$OLD/product/priv-app/MoseyApp" ]; then SYS=$OLD/product
elif [ -d "$OLD/system/product/priv-app/MoseyApp" ]; then SYS=$OLD/system/product
elif [ -d /data/adb/modules/opairshare_pme110/product/priv-app/MoseyApp ]; then SYS=/data/adb/modules/opairshare_pme110/product
elif [ -d /data/adb/modules/opairshare_pme110/system/product/priv-app/MoseyApp ]; then SYS=/data/adb/modules/opairshare_pme110/system/product
else abort "找不到旧 Mosey 系统层；未更改原模块"; fi
for relative in etc/permissions/privapp-permissions-mosey-vivo.xml etc/permissions/mosey-hiddenapi-vivo.xml etc/vintf/manifest/manifest_mosey.xml; do
    [ -s "$SYS/$relative" ] || abort "系统层配置缺失：$relative"
done
check_hash "$SYS/priv-app/MoseyApp/base.apk" ac3b59b776570aa673aed462bd7dbb08cc1486adea5f5f884f848230ddf6a4be || abort "Mosey 系统 APK 与已验证版本不符"
for part in base.apk split_config.arm64_v8a.apk split_config.en.apk split_config.xxhdpi.apk; do
    [ -f "$SYS/priv-app/MoseyApp/$part" ] || abort "Mosey 分包不完整：$part"
done
check_hash "$SYS/priv-app/MoseyApp/split_config.arm64_v8a.apk" cd2213488b5fa107966755c3dfcb435c85a06d94549c7965a83d5bca5932b49c || abort "arm64 分包校验失败"
check_hash "$SYS/priv-app/MoseyApp/split_config.en.apk" 1170711ad580850869de8e52934b2331abb3ab6fd08dceb84ac986c0daf93b5f || abort "语言分包校验失败"
check_hash "$SYS/priv-app/MoseyApp/split_config.xxhdpi.apk" a1a1f058353547ec199888124e58bbc1821a0634076effe82937a6c06a59babd || abort "资源分包校验失败"
check_hash /data/moapp/mosey_server "$DAEMON_SHA" || abort "缺少已验证的 MTK 原厂服务；不会回退到旧 vivo 服务"
check_hash /data/moapp/lib64/libmosey_daemon_ffi.so "$FFI_SHA" || abort "MTK FFI 校验失败"
BACKUP=$(cat "$STATE/latest-backup" 2>/dev/null)
case "$BACKUP" in "$STATE"/backups/*) ;; *) BACKUP=;; esac
if [ -z "$BACKUP" ] || [ ! -f "$BACKUP/bridge.apk" ]; then
    BACKUP="$STATE/backups/$(date +%Y%m%d-%H%M%S)-$$"
    mkdir -p "$BACKUP"
    chmod 0700 "$BACKUP"
    for id in com.fei_ke.unlockcngms mosey_pme110 mosey_stack_pme110; do
        if [ -d "/data/adb/modules/$id" ]; then
            cp -a "/data/adb/modules/$id" "$BACKUP/" || abort "备份失败：$id"
        fi
    done
    current_bridge=$(/system/bin/pm path com.tlsu.oshareairdrop | sed -n 's/^package://p' | head -n 1)
    cp "$current_bridge" "$BACKUP/bridge.apk" || abort "桥接备份失败"
fi
# Also clean the exact stale link if upgrading a previously staged prototype.
for generated in "$MODPATH/product/product" "$MODPATH/system/product/product"; do
    if [ -L "$generated" ]; then
        [ "$(readlink "$generated")" = ./system/product ] || abort "发现未识别的嵌套分区链接"
        rm "$generated" || abort "无法清理旧的嵌套分区链接"
    fi
done
mkdir -p "$MODPATH/system/product" "$MODPATH/runtime/lib64"
# Metamodules leave partition links in old trees; import only owned files,
# never recursively copy that generated layout into a new partition.
for relative in etc/permissions/privapp-permissions-mosey-vivo.xml etc/permissions/mosey-hiddenapi-vivo.xml etc/vintf/manifest/manifest_mosey.xml priv-app/MoseyApp/base.apk priv-app/MoseyApp/split_config.arm64_v8a.apk priv-app/MoseyApp/split_config.en.apk priv-app/MoseyApp/split_config.xxhdpi.apk; do
    mkdir -p "$MODPATH/system/product/${relative%/*}"
    cp "$SYS/$relative" "$MODPATH/system/product/$relative" || abort "导入系统层失败：$relative"
done
cp /data/moapp/mosey_server "$MODPATH/runtime/mosey_server" || abort "导入原厂服务失败"
cp /data/moapp/lib64/libmosey_daemon_ffi.so "$MODPATH/runtime/lib64/" || abort "导入 FFI 失败"
# Preserve GMS policy by regenerating copies of known configuration files only.
sh "$MODPATH/bin/gms.sh" prepare "$MODPATH" || abort "GMS 配置准备失败"
set_perm_recursive "$MODPATH" 0 0 0755 0644
for f in "$MODPATH"/*.sh "$MODPATH"/bin/*.sh "$MODPATH/runtime/mosey_server"; do
    set_perm "$f" 0 0 0755
done
CFG=/data/adb/hybrid-mount/config.toml
if [ -f "$CFG" ] && ! grep -q '^\[rules.opairshare_pme110\]' "$CFG"; then
    cp "$CFG" "$BACKUP/hybrid-mount-config.toml" || abort "挂载配置备份失败"
    printf '\n[rules.opairshare_pme110]\ndefault_mode = "magic"\n' >> "$CFG" || abort "挂载配置写入失败"
fi
printf '%s\n' "$BACKUP" > "$STATE/latest-backup"
# The old stack's uninstaller kills every mosey_server, including the new stock
# daemon. Preserve it in the backup and retire that obsolete cleanup hook first.
legacy_uninstall=/data/adb/modules/mosey_stack_pme110/uninstall.sh
if [ -f "$legacy_uninstall" ]; then
    mv "$legacy_uninstall" "$legacy_uninstall.pre-unify" || abort "无法停用旧版全局服务清理脚本"
fi
# Existing mounts and processes remain intact for this boot. KernelSU retires
# only these three replaced modules on the next boot; dependencies stay enabled.
for id in com.fei_ke.unlockcngms mosey_pme110 mosey_stack_pme110; do
    if [ -d "/data/adb/modules/$id" ]; then
        touch "/data/adb/modules/$id/disable" "/data/adb/modules/$id/remove"
    fi
done
ui_print "- 已备份旧模块：$BACKUP"
ui_print "- 合并包已暂存；当前运行会话继续使用已验证配置"
ui_print "- 不会自动重启。临时 root 会随重启失效，先保留本次会话"

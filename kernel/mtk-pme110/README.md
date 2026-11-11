# PME110 原厂 Wonder 运行时绑定

`mtk_wonder_bind.c` 采用 GPL-2.0-only；参考 AirDropVivoCN 的内存属性与平台设备绑定思路，
使用本机已有的原厂 MTK provider 和 Wonder 驱动，不替换 WLAN 驱动。

此目录保留实际编译源码、脚本、精确内核导出的头文件、链接脚本及 CRC 来源记录。
只适用于主 README 列出的精确内核，不可把此 CRC 表用于其他内核。

```sh
python3 -m venv .venv
.venv/bin/pip install pyelftools capstone
mkdir -p headers
tar -xf kheaders.tar.xz -C headers
.venv/bin/python build_module.py --headers headers --linker-script module.lds.S \
  --lld "$ANDROID_HOME/build-tools/37.0.0/lld-bin/lld" --recorded-crcs import-crcs.json
cp build/mtk_wonder_bind.ko ../../module/kernel/
```

需要支持 AArch64 / KCFI 的 Clang。原实测产物 SHA256 为
`081a0f4d1019e2f6aa297a5a7aaec7f54f5e54e3e45971fcd2386ff9be676590`。
更换编译器可能得到不同二进制，应记录工具链身份；构建成功不等于硬件兼容。
默认 `activate=false` 仅检查，服务在精确兼容检查后才以 `activate=1` 绑定。
本分支没有卸载活跃驱动的入口。

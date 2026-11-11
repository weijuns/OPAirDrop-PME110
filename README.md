# OPAirDrop PME110

作者 / PME110 适配维护：**[weijuns](https://github.com/weijuns)**

为 OPPO PME110 / MT6993 整理的一体化 AirDrop 模块，连接系统互传与 Mac。
本项目基于 **TimelessU / Weverses 的 [OPAirDrop](https://github.com/Weverses/OPAirDrop)**，
保留上游 Git 历史、许可证及原作者声明。感谢原作者提供的桥接、收发界面和 WebUI。

## 一个互传模块

KernelSU 中统一显示 **OPAirDrop PME110**，模块 ID 为 `opairshare_pme110`。
它接管以下三个模块的互传相关功能：

| 旧模块 | 合并后的功能 |
| --- | --- |
| Unlock CN GMS (`com.fei_ke.unlockcngms`) | 国行 GMS feature 配置过滤 |
| vivo Mosey PME110 (`mosey_pme110`) | Mosey 系统应用层、权限与 VINTF |
| Mosey Stack PME110 (`mosey_stack_pme110`) | 原厂 MTK 服务、生命周期、设置及 WebUI |

同时随包管理 OShare / Mosey 的 LSPosed 桥接 APK、精确内核的 Wonder 绑定模块和发现保活脚本。
桥接仍会在 LSPosed 列表显示，这是框架的工作方式，不需要另行下载维护。
**Zygisk、LSPosed 和系统挂载工具仍是依赖，不属于这三个合并对象。**

## 当前验证范围

- PME110、MT6993、Android 17。
- 精确内核：`6.12.69-android16-6-g242e1a07f878-ab15865446-4k`。
- 当前生效的 Mosey：`27391` / `1.0.927074190`。
- 用户已在原运行会话确认 Mac → 手机、手机 → Mac 均可传输。
- 合并版复用该会话的 MTK 原厂 daemon / FFI、Wonder 绑定源码及 v7 收发修复。
- 新安装器、构建和界面另行验证；**重新开机后的完整启动和长期稳定性尚待实机验证**。
- 速度记录尚未接入，界面明确显示不可用，不编造统计。

这是特定设备现有环境的 **迁移版**，不是通用 MTK 模块或全新设备的一键安装器。
它不包含 root 提权工具；临时 root 在重启后会消失，安装器不会重启设备。

## 安装与升级

1. 保留当前已能互传的环境，确认 Mosey 27391、LSPosed 桥接及两个作用域已启用。
2. 在 KernelSU 安装 Releases 的 `OPAirDrop-PME110-v1.1.0-migration.zip`。
3. 安装器检查精确设备和内核、包内 SHA256、系统分包及原厂服务哈希，再从本机导入。
4. 三个旧模块与桥接 APK 备份到 `/data/adb/opairshare_pme110/backups/`，路径记录在 `latest-backup`。
5. 完成后旧模块标记为停用并待移除，在下一次启动由 KernelSU 完成替换。
   当前会话的挂载、原厂服务和已加载驱动继续保留，不会被安装器中断。

**使用临时 root 时不要为这次安装立即重启。** 新模块的系统挂载和自动服务需要在后续具备
root 与模块加载条件的启动中生效。重新获取临时 root 属于你的 root 环境，不由本项目处理。
在新模块完成接管前，不能把安装成功等同于冷启动验证完成。

发布包不携带厂商 Mosey APK、daemon 或 FFI，安装时从自己的已有环境导入并校验。
缺少输入时停止安装并保留旧模块，不下载替代文件。

若要取消尚未生效的迁移，先在管理器移除新模块，并恢复三个旧模块的启用状态、取消待移除。
旧 Stack 的全局杀服务卸载脚本已改名为 `uninstall.sh.pre-unify`，原文件也完整保存在备份中。
不要在当前收发时执行这个旧卸载脚本；它会误杀新的原厂服务。需要恢复时以备份为准，
不要卸载活跃的 Wonder / WLAN 驱动。

## 设置与关于

从支持 KernelSU WebUI 的管理器打开模块，可查看服务、设置名称及接收位置、读取或导出日志。
关于页显示 **作者：weijuns**，下面列出原作者致谢与来源。
设置通过桥接实际读取的 `Settings.Global` 保存，不再使用早期原型的独立文本文件。

Mac 的接收提示由 macOS 呈现。实测曾遇到状态栏软件影响提示，关闭该软件后接收弹窗恢复；
不应据此更换手机驱动。

## 构建

源码包含完整桥接 Java 工程、WebUI、安装脚本和 MTK 绑定源码，私钥与设备输入不入库。
需要 JDK 21、Android SDK Platform 36 / Build Tools 37.0.0、Node.js 与 npm。

```sh
cd webui
npm ci
npm run check
npm run build
cd ..
cp -R webui/dist/. module/webroot/

# 指向自己的私钥和密码文件，切勿提交私钥。
export OPAIR_KEYSTORE=/absolute/private/release.p12
export OPAIR_PASSWORD_FILE=/absolute/private/release.password
export OPAIR_LINEAGE="$PWD/tools/pme110/signing-lineage.bin"
python3 tools/pme110/build.py bridge

# 按 kernel/mtk-pme110/README.md 构建精确内核绑定并复制到 module/kernel/。
python3 tests/pme110/test_migration.py
python3 tools/pme110/build.py package
```

依赖版本和 SHA256 固定在 `tools/pme110/build.py`。桥接从源码编译，不再替换已有 APK 的 DEX。
发布版使用 weijuns 的独立签名，公开证书链允许从早期实验签名升级；证书链不包含私钥。
其他维护者需要自己的签名，并清除 `OPAIR_LINEAGE` 或提供自己的合法轮换链；本仓库的证书链
只适用于 weijuns 的发布私钥。没有匹配的签名或合法轮换链时，不能直接覆盖本项目 APK。

旧 Qualcomm 代码和说明作为上游参考保留，不进入 PME110 迁移包。
原说明见 [UPSTREAM-README.md](docs/UPSTREAM-README.md)，本分支以本页及 `tools/pme110/` 为准。

## 致谢与许可

- **TimelessU / Weverses — [OPAirDrop](https://github.com/Weverses/OPAirDrop)**：原项目、OShare 桥接、接收界面和 WebUI。
- **34306 — [AirDropVivoCN](https://github.com/34306/AirDropVivoCN)**：早期研究、部署及 Wonder 运行时绑定思路。
- **fei-ke — [Unlock CN GMS](https://github.com/fei-ke/unlock-cn-gms)**：国行 GMS 解锁方案；本分支沿用 OPAirDrop 的 feature 过滤实现并注明来源。
- **thelok1s / mosey-extended、FeelLiao / mosey-bada** 及其他上游研究者：部署和服务接入参考。
- **libxposed / LSPosed、LuckyPray / DexKit、Vue、miuix-vue、KernelSU**：运行及构建依赖。

用户态适配和脚本按 GPL-3.0-only；内核绑定按 GPL-2.0-only；其他文件保留原许可。
厂商组件不因本项目开源而变为 GPL。详见 [LICENSE](LICENSE)、[LICENSING.md](LICENSING.md)、
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本项目与 Apple、Google、OPPO / Oplus 无官方隶属或背书关系。

# 商米v2（MT6739）工具箱

面向 **SUNMI V2 / MT6739WA / Android 7.1.1** 的一体化维修工具：改 SN、改条码、绕过激活、临时 root。
双击即用，客户机不需要安装 Python、不需要配环境变量。

```
============================================================
  商米v2 MT6739 工具
  [1-3] 改 SN / 条码  需要设备【关机】插 USB
  [4-6] 激活 / root    需要设备【开机】且 ADB 可用
  [7]   环境自检       随时可用
============================================================
  [1] 改 SN
  [2] 改条码
  [3] 查看当前 SN / 条码
  [4] 绕过激活 / 退出体验模式
  [5] 恢复激活向导（回滚）
  [6] 打开 root shell（重启前有效）
  [7] 检测当前环境
  [0] 退出
```

## 功能

| 功能 | 设备状态 | 说明 |
|---|---|---|
| 改 SN | **关机**插 USB | 写 proinfo 分区头的 SN 字段 |
| 改条码 | **关机**插 USB | 同一条记录里的条码字段 |
| 查看 SN / 条码 | **关机**插 USB | 只读，不写入 |
| 绕过激活 | **开机** + ADB | 自动 `mtk-su` 提权后禁用 `com.sunmi.welcome` |
| 恢复激活向导 | **开机** + ADB | 回滚上一步 |
| 打开 root shell | **开机** + ADB | 自动提权，得到 `#: ` 提示符的交互终端 |
| 环境自检 | 随时 | 一次性检查驱动、依赖、adb、设备与提权状态 |

## 快速开始

1. 解压到**纯英文无空格**的路径，例如 `D:\sunmi_tool\`
2. 首次使用：双击 `drivers\install_driver.bat`，UAC 点「是」（每台电脑一次）
3. 双击 `商米工具.bat`，按菜单选

也可以直接用命令行：

```bat
改SN.bat VB0123456789
改条码.bat 1T17N36G4F029QB
```

支持的子命令：

```
python main.py sn [SN]      改 SN
python main.py barcode [条码]  改条码
python main.py show          查看当前 SN / 条码
python main.py shell         打开 root shell
python main.py activate      绕过激活
python main.py restore       恢复激活向导
python main.py check         环境自检
```

## 环境要求

| 项 | 要求 |
|---|---|
| 系统 | Windows 10 / 11 x64 |
| Python | **不需要**，已内置 Python 3.12 |
| 驱动 | 内置 `usbvcom.inf` / `usbvcom_brom.inf`，一键安装 |
| 权限 | 首次装驱动需要管理员 |

## 目录结构

```
main.py              入口（菜单 + 子命令）
modules\
  common.py          日志与错误
  mtk.py             MTK 串口会话：发现端口 / 握手 / 4 KB 读写
  identity.py        proinfo 记录编解码（SN + 条码）
  adbkit.py          adb 封装（随包 adb + 固定 adbkey）
  rootkit.py         mtk-su 提权 + root shell
  activation.py      绕过激活 / 回滚
  envcheck.py        环境自检
python\              内置 Python 3.12
mtkclient\           mtkclient 2.1.4（已打补丁）
drivers\             MTK 驱动（首次装一次）
tools\
  mtk-su             提权二进制（CVE-2020-0069，32 位 ARM）
  adbkey(.pub)       固定 ADB 密钥，换电脑不用重新授权
  platform-tools\    adb.exe
work\                运行时临时文件（4 KB）
```

## 技术原理

### 1. SN / 条码在哪

在 emmc 的 **proinfo 分区**（flash 偏移 `0xEA00000`，长度 3 MB）**开头 64 字节**：

| 偏移 | 长度 | 字段 |
|---|---|---|
| `0x00` | 25 | 条码（左对齐，空格填充） |
| `0x19` | 29 | **SN** |
| `0x36` | 9 | 尾部标志 `11  1 11` |
| `0x3F` | 1 | NUL |
| `0x40` | 8 | 必须全零 |
| `0x142` | 1 | 必须为零 |

所以本工具**只读 4 KB、只改这 64 字节、只写回 4 KB**，不 dump 也不重写整个 3 MB 分区。
代码里有安全闸：64 字节之外（除两处清零段）任何字节发生变化就直接中止。

### 2. 为什么走串口而不是 libusb

MTK 下载模式的设备在 Windows 上会枚举成 `PreLoader USB VCOM Port`（`usbser`）。
`mtkclient` 默认走 libusb，而 libusb 打不开绑在 `usbser` 上的设备，于是"设备明明插着，工具却一直等"。

本工具改为主动发现 MTK 串口并以 `serialportname=COMx` 建立会话，走 mtkclient 的 `SerialClass`，
既不需要 Zadig/WinUSB，也不影响 SP Flash Tool。

### 3. 为什么 `adb root` 不可用

固件是 **user 构建**（`ro.debuggable=0`），adbd 在编译期就固定了必须以 shell 身份运行：

```
$ adb root
adbd cannot run as root in production builds
```

要真让 `adb shell` 本身是 root，只能改 system/boot，会破坏 Android Verified Boot → 无限重启。

因此工具提供等价形态：用 `mtk-su` 提权后 exec 一个交互式 sh，PS1 通过 `ENV` 文件覆盖为 `#: `：

```sh
export ENV=/data/local/tmp/rootenv
exec /system/bin/sh -i
```

```
#: id
uid=0(root) gid=0(root) groups=0(root) context=u:r:shell:s0
```

root 只在本次开机内有效，重启失效；但用它写入的配置（userdata）永久保留。

### 4. 绕过激活做了什么

```sh
settings put global device_provisioned 1
settings put secure user_setup_complete 1
pm disable com.sunmi.welcome
am force-stop com.sunmi.welcome
```

四条都写 userdata，不碰 boot，所以重启后依然有效，且零变砖风险。

## 常见问题

**一直「等待设备…」**

- 手机没真关机。长按电源 15 秒，确认屏幕全黑再插线
- 用了纯充电线，换数据线
- 驱动没装，跑 `drivers\install_driver.bat`
- 换主板后置 USB 2.0 口试试

**改 SN 报「读取失败 / 连接失败」**

- 关掉 SP Flash Tool 等占用设备的程序
- 设备可能停在 DA 模式，拔线断电重来

**Preloader 显示成 WinUSB 而没有 COM 口**

- 说明被 Zadig / libwdi 抢了驱动
- 菜单 `[7]` 环境自检会标出来
- 处理：`pnputil /delete-driver oemXX.inf /uninstall /force` 删掉 `mt65xx_preloader.inf`，
  再重插设备让它回落到 `usbvcom.inf`

**绕过激活提示「提权失败」**

- 该固件可能已修复 CVE-2020-0069，`mtk-su` 不适用
- 工具会打印原始输出，便于判断

**校验失败**

- 设备仍在会话中、未断电，直接重跑即可，不会写坏

## 免责声明

本项目仅供**合法维修**使用：恢复主板维修后丢失的原机 SN、批量部署自有设备、修复被激活向导卡住的机器。

- 修改 SN 会让设备脱离商米云 / MDM 管理
- IMEI 属受监管电信标识，请勿用于伪造
- 刷机有风险，请自行评估并做好备份

## 致谢

- [mtkclient](https://github.com/bkerler/mtkclient) —— MTK 下载模式协议实现
- [mtk-su](https://github.com/offensive-security/exploitdb) —— CVE-2020-0069 提权
- Android platform-tools

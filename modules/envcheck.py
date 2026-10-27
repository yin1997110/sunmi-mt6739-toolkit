# -*- coding: utf-8 -*-
"""环境自检：PC 侧工具链 + 设备侧状态，一次看清哪里不对。"""
import os
import platform
import subprocess
import sys

from . import adbkit, rootkit
from .common import ToolError, log, raw

OK = "[ OK ]"
NO = "[FAIL]"
WARN = "[WARN]"

DRIVERSTORE = r"C:\Windows\System32\DriverStore\FileRepository"


def _line(tag, text, extra=""):
    raw("  %s %s%s" % (tag, text, ("  " + extra) if extra else ""))


def _check_python():
    v = platform.python_version()
    bits = platform.architecture()[0]
    tag = OK if bits == "64bit" else WARN
    _line(tag, "Python %s (%s)" % (v, bits))


def _check_adb():
    try:
        p = adbkit.adb_path()
    except ToolError as e:
        _line(NO, "adb 未找到", str(e))
        return None
    try:
        out = adbkit.run(["version"], timeout=20).stdout or ""
        ver = out.splitlines()[0].strip() if out else "(无输出)"
        _line(OK, "adb", "%s  ←  %s" % (ver, p))
        return p
    except Exception as e:
        _line(NO, "adb 无法运行", str(e))
        return None


def _check_mtkclient():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for p in (os.path.join(root, "mtkclient"), root):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        import mtkclient
        path = getattr(mtkclient, "__file__", "?")
        _line(OK, "mtkclient", path)
    except Exception as e:
        _line(NO, "mtkclient 导入失败", str(e))


def _check_deps():
    missing = []
    for mod in ("serial", "usb", "Crypto"):
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)
    if missing:
        _line(NO, "Python 依赖缺失", ", ".join(missing))
    else:
        import serial
        _line(OK, "串口/USB 依赖", "pyserial %s + pyusb + pycryptodome" % getattr(serial, "VERSION", "?"))


def _check_drivers():
    if not os.path.isdir(DRIVERSTORE):
        _line(WARN, "读不到驱动库目录", DRIVERSTORE)
        return
    try:
        names = os.listdir(DRIVERSTORE)
    except Exception as e:
        _line(WARN, "驱动库目录不可读", str(e))
        return

    vcom = [n for n in names if n.lower().startswith("usbvcom")]
    zadig = [n for n in names if n.lower().startswith("mt65xx_preloader")]

    if vcom:
        _line(OK, "MediaTek VCOM 驱动已安装", ", ".join(sorted(vcom)))
    else:
        _line(NO, "未安装 MediaTek VCOM 驱动", "双击 drivers\\install_driver.bat")

    if zadig:
        _line(WARN, "发现 Zadig/libwdi 的 WinUSB 驱动", ", ".join(sorted(zadig)))
        raw("         它会把 Preloader 抢成 WinUSB，导致没有 COM 口")
        raw("         修法见 README「驱动冲突」一节")


def _check_ports():
    try:
        from serial.tools import list_ports
    except Exception:
        _line(WARN, "pyserial 不可用，跳过串口枚举")
        return
    ports = sorted(list_ports.comports(), key=lambda x: x.device)
    if not ports:
        _line(WARN, "当前没有串口", "设备需关机后插入 USB 才会出现")
        return
    for p in ports:
        mtk = "0E8D" in (p.hwid or "").upper() or "MEDIATEK" in (p.description or "").upper() \
              or "PRELOADER" in (p.description or "").upper()
        _line(OK if mtk else WARN, p.device,
              "%s  [%s]%s" % (p.description or "?", p.hwid or "?", "  ← MTK 下载模式" if mtk else ""))


def _device_block():
    raw("")
    raw("设备状态（未连接则跳过）")
    try:
        serial = adbkit.ensure_device()
    except ToolError as e:
        _line(WARN, "没有可用的 adb 设备", "改 SN/条码 不需要 adb，可忽略")
        return None

    _line(OK, "序列号", serial)

    def prop(k):
        try:
            return adbkit.shell(serial, "getprop %s" % k, timeout=15).strip()
        except Exception:
            return "?"

    model = prop("ro.product.model")
    rel = prop("ro.build.version.release")
    build_type = prop("ro.build.type")
    debuggable = prop("ro.debuggable")
    _line(OK, "型号 / 系统", "%s / Android %s" % (model, rel))
    _line(OK if debuggable == "1" else WARN, "构建类型", "%s (ro.debuggable=%s)" % (build_type, debuggable))
    if debuggable != "1":
        raw("         这是 user 构建，adb root 不可用；用菜单 [6] 的 root shell 代替")

    # 能否提权
    try:
        if rootkit.is_root(serial):
            _line(OK, "root", "已具备（uid=0）")
        else:
            mtk_su = os.path.join(adbkit.ROOT, "tools", "mtk-su")
            if not os.path.isfile(mtk_su):
                _line(NO, "root", "缺少 tools\\mtk-su")
            else:
                adbkit.push(serial, mtk_su, rootkit.REMOTE_SU)
                adbkit.shell(serial, "chmod 700 %s" % rootkit.REMOTE_SU)
                out = adbkit.shell(serial, "echo 'id' | %s" % rootkit.REMOTE_SU, timeout=30)
                if "uid=0" in out:
                    _line(OK, "root", "mtk-su 可用（临时 root）")
                else:
                    _line(NO, "root", "mtk-su 提权失败，固件可能已修复 CVE-2020-0069")
    except Exception as e:
        _line(WARN, "root 检测失败", str(e))

    # 激活状态
    try:
        disabled = adbkit.shell(serial, "pm list packages -d", timeout=30)
        home = adbkit.shell(
            serial,
            "cmd package resolve-activity -a android.intent.action.MAIN "
            "-c android.intent.category.HOME", timeout=30)
        if "com.sunmi.welcome" in disabled:
            _line(OK, "激活向导", "已禁用")
        else:
            _line(WARN, "激活向导", "仍启用（未绕过激活）")
        name_lines = [l.strip() for l in home.splitlines() if "name=" in l]
        disp = name_lines[-1] if name_lines else (home.strip() or "?")
        if "com.woyou.launcher" in home or "launcher3" in home:
            _line(OK, "默认桌面", disp)
        else:
            _line(WARN, "默认桌面", disp + "（可能还停在欢迎页）")
    except Exception as e:
        _line(WARN, "激活状态检测失败", str(e))
    return serial


def cmd_check(args):
    raw("")
    raw("=" * 66)
    raw("  环境自检")
    raw("=" * 66)
    raw("")
    raw("PC 环境")
    _check_python()
    _check_adb()
    _check_mtkclient()
    _check_deps()
    _check_drivers()
    raw("")
    raw("串口")
    _check_ports()
    _device_block()
    raw("")
    raw("=" * 66)
    raw("  自检结束。上面有 [FAIL] 的项需要先解决，[WARN] 一般不影响使用。")
    raw("=" * 66)
    return 0

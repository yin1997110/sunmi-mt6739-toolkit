# -*- coding: utf-8 -*-
"""绕过激活 / 退出体验模式（SUNMI V2）。

原理：用 mtk-su 临时提权，然后
  1) settings put global device_provisioned 1   标记设备已配置
  2) settings put secure user_setup_complete 1  标记开机向导已完成
  3) pm disable com.sunmi.welcome               禁用激活/体验应用
  4) am force-stop com.sunmi.welcome            结束进程
这些写的是 userdata，不动 boot 分区，所以重启后依然有效，且零变砖风险。
"""
from . import adbkit, rootkit
from .common import ToolError, log

WELCOME_PKG = "com.sunmi.welcome"

STEPS = [
    "settings put global device_provisioned 1",
    "settings put secure user_setup_complete 1",
    "pm disable %s" % WELCOME_PKG,
    "am force-stop %s" % WELCOME_PKG,
]


def verify(serial):
    home = adbkit.shell(
        serial,
        "cmd package resolve-activity -a android.intent.action.MAIN "
        "-c android.intent.category.HOME", timeout=30)
    disabled = adbkit.shell(serial, "pm list packages -d", timeout=30)
    ok_home = ("com.woyou.launcher" in home) or ("launcher3" in home)
    ok_disabled = WELCOME_PKG in disabled
    return ok_home, ok_disabled, home.strip()


def cmd_activate(args):
    serial = adbkit.ensure_device()
    log("设备序列号: %s" % serial)

    rootkit.ensure_root(serial)
    log("执行：退出体验 / 激活模式…")
    out = rootkit.run_as_root(serial, STEPS)
    if "__ROOT_DONE__" not in out:
        raise ToolError("命令执行不完整，原始输出：\n%s" % out.strip())

    ok_home, ok_disabled, home = verify(serial)
    log("默认桌面: %s" % (home or "(读不到)"))
    if ok_home and ok_disabled:
        log("成功：已退出体验/激活模式，重启后依然有效")
        return 0
    if ok_disabled:
        log("部分成功：%s 已禁用，但默认桌面不是预期值" % WELCOME_PKG)
        return 0
    raise ToolError("未确认成功：%s 仍在启用列表中，请检查上方输出" % WELCOME_PKG)


def cmd_restore(args):
    serial = adbkit.ensure_device()
    log("设备序列号: %s" % serial)
    rootkit.ensure_root(serial)
    log("恢复激活向导…")
    out = rootkit.run_as_root(serial, ["pm enable %s" % WELCOME_PKG])
    if "__ROOT_DONE__" not in out:
        raise ToolError("命令执行不完整，原始输出：\n%s" % out.strip())
    log("已重新启用 %s（下次开机/回到桌面时可能再次出现激活向导）" % WELCOME_PKG)
    return 0

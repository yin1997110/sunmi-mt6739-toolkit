# -*- coding: utf-8 -*-
"""商米 V2 工具 —— 模块化入口。

    python main.py                 # 交互菜单
    python main.py sn VB0123456789 # 改 SN
    python main.py barcode 1T17... # 改条码
    python main.py show            # 读当前 SN / 条码
    python main.py root            # 临时 root
    python main.py activate        # 绕过激活 / 退出体验模式
    python main.py restore         # 恢复激活向导
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(ROOT, "mtkclient"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from modules import activation, adbkit, envcheck, identity, mtk, rootkit  # noqa: E402
from modules.common import ToolError, ask, log, raw  # noqa: E402


def _ns(**kw):
    d = dict(port=None, timeout=120, connect_timeout=25, no_reset=False,
             sn=None, barcode=None)
    d.update(kw)
    return argparse.Namespace(**d)


def _need_device(args, what):
    """写 SN/条码 需要设备关机进 preloader。"""
    raw("")
    log("这一步要先把手机【完全关机】（长按电源 15 秒，确认屏幕全黑）")
    log("然后插上 USB，不要按任何键")
    log("准备 %s" % what)
    s = ask("关机并准备好后按回车开始（Ctrl+C 取消）…")
    return s


# ---------------------------------------------------------------- 菜单项
def m_change_sn(args):
    sn = args.sn
    if not sn:
        sn = ask("请输入新的 SN（13 位，VB0 开头）: ").strip()
    identity.validate_sn(sn)
    _need_device(args, "写入 SN: %s" % sn)
    return identity.cmd_write(args, sn=sn)


def m_change_barcode(args):
    bar = args.barcode
    if not bar:
        bar = ask("请输入新的条码（17 位）: ").strip()
    identity.validate_barcode(bar)
    _need_device(args, "写入条码: %s" % bar)
    return identity.cmd_write(args, barcode=bar)


def m_show(args):
    _need_device(args, "读取当前 SN / 条码（只读，不写入）")
    return identity.cmd_show(args)


def m_activate(args):
    raw("")
    log("这一步需要手机【已开机并进入系统】，ADB 可用")
    return activation.cmd_activate(args)


def m_restore(args):
    raw("")
    log("这一步需要手机【已开机并进入系统】，ADB 可用")
    return activation.cmd_restore(args)


def m_shell(args):
    raw("")
    log("这一步需要手机【已开机并进入系统】，ADB 可用")
    serial = adbkit.ensure_device()
    log("设备序列号: %s" % serial)
    if not rootkit.is_root(serial):
        rootkit.ensure_root(serial)
    return rootkit.interactive_shell(serial)


def m_check(args):
    return envcheck.cmd_check(args)


MENU = [
    ("1", "改 SN", m_change_sn),
    ("2", "改条码", m_change_barcode),
    ("3", "查看当前 SN / 条码", m_show),
    ("4", "绕过激活 / 退出体验模式", m_activate),
    ("5", "恢复激活向导（回滚）", m_restore),
    ("6", "打开 root shell（重启前有效）", m_shell),
    ("7", "检测当前环境", m_check),
]


def menu():
    raw("")
    raw("=" * 60)
    raw("  商米v2 MT6739 工具")
    raw("  [1-3] 改 SN / 条码  需要设备【关机】插 USB")
    raw("  [4-6] 激活 / root    需要设备【开机】且 ADB 可用")
    raw("  [7]   环境自检       随时可用")
    raw("=" * 60)
    for k, name, _ in MENU:
        raw("  [%s] %s" % (k, name))
    raw("  [0] 退出")
    raw("")
    while True:
        c = ask("请选择: ").strip()
        if c in ("0", "q", ""):
            return 0
        hit = [m for m in MENU if m[0] == c]
        if not hit:
            raw("无效选项")
            continue
        try:
            hit[0][2](_ns())
        except ToolError as e:
            raw("")
            raw("[错误] %s" % e)
        except KeyboardInterrupt:
            raw("")
            raw("已取消")
        raw("")
        ask("按回车返回菜单…")


def build_parser():
    p = argparse.ArgumentParser(
        prog="商米v2 MT6739 工具",
        description="商米v2 MT6739：改 SN / 改条码 / 绕过激活 / root shell / 环境自检")
    sub = p.add_subparsers(dest="cmd")

    def common(sp):
        sp.add_argument("--port", help="直接指定串口，如 COM3")
        sp.add_argument("--timeout", type=int, default=120, help="等待设备插入的秒数")
        sp.add_argument("--connect-timeout", type=int, default=25, help="握手阶段秒数上限")
        sp.add_argument("--no-reset", action="store_true", help="写完后不重启设备")

    sp = sub.add_parser("sn", help="改 SN")
    sp.add_argument("sn", nargs="?")
    common(sp)

    sp = sub.add_parser("barcode", help="改条码")
    sp.add_argument("barcode", nargs="?")
    common(sp)

    sp = sub.add_parser("show", help="查看当前 SN / 条码")
    common(sp)

    for name, h in (("shell", "打开 root shell（自动提权）"),
                    ("activate", "绕过激活"), ("restore", "恢复激活向导"),
                    ("check", "环境自检")):
        sub.add_parser(name, help=h)

    return p


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        return menu()

    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "sn":
            return m_change_sn(args)
        if args.cmd == "barcode":
            return m_change_barcode(args)
        if args.cmd == "show":
            return m_show(args)
        if args.cmd == "shell":
            return m_shell(args)
        if args.cmd == "activate":
            return m_activate(args)
        if args.cmd == "restore":
            return m_restore(args)
        if args.cmd == "check":
            return m_check(args)
        return menu()
    except ToolError as e:
        raw("")
        raw("[错误] %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())

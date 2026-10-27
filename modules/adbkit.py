# -*- coding: utf-8 -*-
"""ADB 封装：找 adb、跑命令、取设备。

优先用随包的 tools\\platform-tools\\adb.exe，其次用 PATH 里的 adb。
若 tools\\adbkey 存在，则通过 ADB_VENDOR_KEYS 使用这套固定密钥，
避免每台设备都要在屏幕上点一次「允许 USB 调试」。
"""
import os
import shutil
import subprocess

from .common import ToolError, log

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")


def find_adb():
    bundled = os.path.join(TOOLS, "platform-tools", "adb.exe")
    if os.path.isfile(bundled):
        return bundled
    found = shutil.which("adb")
    if found:
        return found
    for c in (os.path.join(ROOT, "adb.exe"),
              r"C:\Users\Dragon\Documents\工具\platform-tools-latest-windows\platform-tools\adb.exe"):
        if os.path.isfile(c):
            return c
    raise ToolError("找不到 adb.exe：随包 tools\\platform-tools\\ 下没有，PATH 里也没有")


def _env():
    env = os.environ.copy()
    key = os.path.join(TOOLS, "adbkey")
    if os.path.isfile(key):
        env["ADB_VENDOR_KEYS"] = key
    return env


def env():
    """给需要继承环境的调用方用。"""
    return _env()


ADB = None


def adb_path():
    global ADB
    if ADB is None:
        ADB = find_adb()
    return ADB


def run(args, timeout=60, serial=None):
    cmd = [adb_path()]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout, env=_env(),
                              # 必须断开 stdin：adb 会把本地 stdin 转发给设备端，
                              # 否则会悄悄吃掉调用方的管道数据（例如 root shell 的输入）
                              stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise ToolError("adb 命令超时（%s 秒）：%s" % (timeout, " ".join(args)))


def devices():
    """返回处于 device 状态的序列号列表。"""
    r = run(["devices"])
    out = []
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            out.append(parts[0])
    return out


def ensure_device(timeout=5):
    """要求恰好一台已授权设备，返回其序列号。"""
    r = run(["start-server"], timeout=30)
    ds = devices()
    if not ds:
        raw = run(["devices"]).stdout or ""
        hint = ""
        if "unauthorized" in raw:
            hint = "\n  设备显示 unauthorized：请在手机屏幕上点「允许 USB 调试」。"
        elif "offline" in raw:
            hint = "\n  设备显示 offline：拔掉 USB 重插，或执行 adb kill-server 后重试。"
        raise ToolError("没有处于 device 状态的设备。请确认：\n"
                        "  1) 手机已开机并进入系统/桌面\n"
                        "  2) USB 线是数据线，且已连接\n"
                        "  3) 已开启 USB 调试%s" % hint)
    if len(ds) > 1:
        log("检测到多台设备：%s，使用第一台 %s" % (", ".join(ds), ds[0]))
    return ds[0]


def shell(serial, cmd, timeout=60):
    r = run(["shell", cmd], timeout=timeout, serial=serial)
    return (r.stdout or "") + (r.stderr or "")


def push(serial, local, remote, timeout=120):
    if not os.path.isfile(local):
        raise ToolError("要推送的文件不存在：%s" % local)
    r = run(["push", local, remote], timeout=timeout, serial=serial)
    txt = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        raise ToolError("adb push 失败：%s" % txt.strip())
    return txt

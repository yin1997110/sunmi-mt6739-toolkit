# -*- coding: utf-8 -*-
"""临时 root：CVE-2020-0069 (mtk-su)。

重要：mtk-su 必须用管道喂命令，直接执行会等 stdin 卡死：
    echo '命令' | /data/local/tmp/mtk-su
"""
import os

from . import adbkit
from .common import ToolError, log

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MTK_SU = os.path.join(ROOT, "tools", "mtk-su")
REMOTE_SU = "/data/local/tmp/mtk-su"
ROOTENV = "/data/local/tmp/rootenv"
ROOTSH = "/data/local/tmp/rootsh.sh"


def is_root(serial):
    try:
        out = adbkit.shell(serial, "id", timeout=15)
    except Exception:
        return False
    return "uid=0" in out


def root_id(serial):
    """在 mtk-su 会话内取身份。注意：普通 adb shell 永远是 uid=2000。"""
    try:
        return adbkit.shell(serial, "echo 'id' | %s" % REMOTE_SU, timeout=30).strip()
    except Exception as e:
        return "(获取失败: %s)" % e


def ensure_root(serial):
    """确保有 root。返回 'already' 或 'mtk-su'。"""
    if is_root(serial):
        log("设备已经是 root（adb 直接以 uid=0 运行）")
        return "already"

    if not os.path.isfile(MTK_SU):
        raise ToolError("找不到提权程序：%s" % MTK_SU)

    log("推送提权程序 mtk-su…")
    adbkit.push(serial, MTK_SU, REMOTE_SU)
    adbkit.shell(serial, "chmod 700 %s" % REMOTE_SU)

    log("尝试提权（mtk-su / CVE-2020-0069）…")
    out = adbkit.shell(serial, "echo 'id' | %s" % REMOTE_SU, timeout=30)
    if "uid=0" not in out:
        raise ToolError(
            "提权失败。可能原因：\n"
            "  1) 该固件内核已修复 CVE-2020-0069（mtk-su 不适用）\n"
            "  2) 设备的 seccomp/SELinux 拦截\n"
            "原始输出：%s" % (out.strip() or "(空)"))
    log("提权成功（临时 root）")
    return "mtk-su"


def run_as_root(serial, commands, timeout=60):
    """以 root 身份顺序执行命令列表，返回输出。"""
    if not commands:
        return ""
    script = "; ".join(commands) + "; echo __ROOT_DONE__"
    out = adbkit.shell(serial, "echo '%s' | %s" % (script, REMOTE_SU), timeout=timeout)
    return out


def interactive_shell(serial):
    """开一个带 `#: ` 提示符的常驻 root shell。

    mtk-su 支持 -c <cmd>，且它是 execvp("/system/bin/sh", ...) 的实现，
    所以可以让它 exec 一个交互式 sh；PS1 通过 ENV 文件覆盖（mksh 启动时读）。
    """
    import subprocess
    import tempfile

    def _tmp(name, text):
        p = os.path.join(tempfile.gettempdir(), name)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return p

    adbkit.push(serial, _tmp("sunmi_rootenv", "PS1='#: '\n"), ROOTENV)
    adbkit.push(serial, _tmp("sunmi_rootsh.sh",
                             "#!/system/bin/sh\nexport ENV=%s\nexec /system/bin/sh -i\n" % ROOTENV),
                ROOTSH)
    adbkit.shell(serial, "chmod 644 %s; chmod 755 %s" % (ROOTENV, ROOTSH))

    print("")
    print("已进入 root shell —— 本次开机内一直有效，重启后失效")
    print("  提示符 #: 表示当前是 root；输入 exit 或按 Ctrl+D 退出")
    print("")
    cmd = [adbkit.adb_path(), "-s", serial, "shell", "-t",
           "%s -c %s" % (REMOTE_SU, ROOTSH)]
    try:
        rc = subprocess.call(cmd, env=adbkit.env())
    finally:
        print("")
    return rc

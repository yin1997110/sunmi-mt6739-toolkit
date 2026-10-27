# -*- coding: utf-8 -*-
"""通用：日志与错误。"""
import sys
import time


class ToolError(Exception):
    """可预期的失败，main 会打印成一行中文提示而不是堆栈。"""


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def warn(msg):
    print("[%s] 注意：%s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def raw(msg):
    print(msg, flush=True)


def ask(prompt):
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print("")
        return ""


def ask_yes(prompt, default=True):
    s = ask("%s [%s]: " % (prompt, "Y/n" if default else "y/N")).strip().lower()
    if not s:
        return default
    return s in ("y", "yes", "是", "1")

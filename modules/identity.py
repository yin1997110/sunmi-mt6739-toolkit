# -*- coding: utf-8 -*-
"""身份记录：proinfo 头 64 字节里的 SN 与条码。

布局：
    0x00..0x18   25 字节  条码（左对齐空格填充）
    0x19..0x35   29 字节  SN
    0x36..0x3E    9 字节  尾部标志 "11  1 11"
    0x3F          1 字节  NUL
    0x40..0x47    8 字节  必须全零
    0x142         1 字节  必须为零

策略：只读 4 KB、只改这 64 字节、只写回 4 KB，其余字节一个不动。
"""
import os
import re

from . import mtk
from .common import ToolError, log, warn

PART_OFF = 0xEA00000
BLOCK = 0x1000
REC_LEN = 64
BAR_OFF, BAR_W = 0x00, 25
SN_OFF, SN_W = 0x19, 29
TAIL_OFF, TAIL_W = 0x36, 9
ZERO_AT = ((0x40, 8), (0x142, 1))
DEF_TAIL = "11  1 11"
LK_FALLBACK = "0123456789ABCDEF"


# ---------------------------------------------------------------- 编解码
def decode_fields(block):
    rec = bytes(block[:REC_LEN])
    if len(rec) < REC_LEN:
        rec = rec + b"\x00" * (REC_LEN - len(rec))
    barcode = rec[BAR_OFF:BAR_OFF + BAR_W].decode("ascii", "replace").rstrip(" \x00")
    sn = rec[SN_OFF:SN_OFF + SN_W].decode("ascii", "replace").rstrip(" \x00")
    tail = rec[TAIL_OFF:TAIL_OFF + TAIL_W].decode("ascii", "replace").rstrip(" \x00")
    return {"barcode": barcode, "sn": sn, "tail": tail}


def validate_sn(sn):
    if not sn:
        raise ToolError("SN 不能为空")
    if not re.fullmatch(r"[!-~]{1,29}", sn):
        raise ToolError("SN %r 不合法：只能是 1~29 个可打印、非空格的 ASCII 字符" % sn)
    if sn == LK_FALLBACK:
        raise ToolError("这正是 LK 的兜底占位值，写进去等于没写")
    if len(sn) != 13:
        warn("SN 长度 %d，该型号出厂是 13 位" % len(sn))
    if not sn.startswith("VB0"):
        warn('SN 不是 "VB0" 开头，与出厂样式不同')


def validate_barcode(bar):
    if not bar:
        raise ToolError("条码不能为空")
    if not re.fullmatch(r"[!-~]{1,25}", bar):
        raise ToolError("条码 %r 不合法：只能是 1~25 个可打印、非空格的 ASCII 字符" % bar)
    if len(bar) != 17:
        warn("条码长度 %d，该型号出厂是 17 位" % len(bar))


def rebuild(block, sn=None, barcode=None):
    """返回 (新 4 KB 块, 旧字段 dict)。sn/barcode 为 None 表示保持原值。"""
    old = decode_fields(block)
    new_bar = old["barcode"] if barcode is None else barcode
    new_sn = old["sn"] if sn is None else sn
    if not new_bar:
        raise ToolError("设备上读不到条码，不能凭空造记录（proinfo 可能已被写坏）")
    tail = old["tail"] or DEF_TAIL

    rec = (new_bar.encode("ascii").ljust(BAR_W, b" ")
           + new_sn.encode("ascii").ljust(SN_W, b" ")
           + tail.encode("ascii").ljust(TAIL_W, b" ")
           + b"\x00")
    if len(rec) != REC_LEN:
        raise ToolError("内部错误：记录长度为 %d，应为 %d" % (len(rec), REC_LEN))

    out = bytearray(block)
    out[0:REC_LEN] = rec
    for off, ln in ZERO_AT:
        out[off:off + ln] = b"\x00" * ln

    # 安全闸：64 字节之外（除两处清零段）任何字节都不许变
    for i in range(REC_LEN, len(block)):
        if block[i] != out[i] and not any(o <= i < o + l for o, l in ZERO_AT):
            raise ToolError("内部错误：补丁试图改动 0x%X，已中止" % i)
    return bytes(out), old


# ---------------------------------------------------------------- 高层操作
def _open(args):
    port = args.port or mtk.wait_port(args.timeout)
    if not port:
        raise ToolError(
            "等了 %d 秒没有发现 MTK 设备。\n"
            "  1) 手机是否真的关机了（长按电源 15 秒）\n"
            "  2) 是否用了数据线（不是纯充电线）\n"
            "  3) 驱动是否装了：双击 drivers\\install_driver.bat" % args.timeout)
    log("发现设备端口 %s，开始握手…" % port)
    m, da = mtk.connect(port, args.connect_timeout)
    chip = ""
    try:
        chip = str(m.config.chipname or "")
    except Exception:
        pass
    log("设备已连接%s —— 现在不要拔线" % ("（%s）" % chip if chip else ""))
    return m, da


def cmd_show(args):
    m, da = _open(args)
    try:
        before = mtk.read_block(da, PART_OFF, os.path.join(mtk.WORK, "block_before.bin"), BLOCK)
        info = decode_fields(before)
        log("当前条码: %s" % (info["barcode"] or "(空)"))
        log("当前 SN  : %s" % (info["sn"] or "(空)"))
        if not args.no_reset:
            mtk.reset(m)
        return 0
    finally:
        mtk.close(m)


def cmd_write(args, sn=None, barcode=None):
    m, da = _open(args)
    try:
        before = mtk.read_block(da, PART_OFF, os.path.join(mtk.WORK, "block_before.bin"), BLOCK)
        info = decode_fields(before)
        log("当前条码: %s" % (info["barcode"] or "(空)"))
        log("当前 SN  : %s" % (info["sn"] or "(空)"))

        after, old = rebuild(before, sn=sn, barcode=barcode)
        if after == before:
            log("目标值与设备现有值完全一致，无需写入")
            if not args.no_reset:
                mtk.reset(m)
            return 0

        path = os.path.join(mtk.WORK, "block_after.bin")
        with open(path, "wb") as f:
            f.write(after)

        log("写入 proinfo 头 4 KB…")
        mtk.write_block(da, PART_OFF, path, BLOCK)

        log("回读校验…")
        back = mtk.read_block(da, PART_OFF, os.path.join(mtk.WORK, "block_readback.bin"), REC_LEN)
        got = decode_fields(back)
        expect_bar = barcode if barcode is not None else old["barcode"]
        expect_sn = sn if sn is not None else old["sn"]
        if got["barcode"] != expect_bar or got["sn"] != expect_sn:
            raise ToolError("校验失败：回读条码=%r SN=%r，期望条码=%r SN=%r\n"
                            "  设备仍在会话中，请勿断电，可重跑本工具"
                            % (got["barcode"], got["sn"], expect_bar, expect_sn))
        log("校验通过：条码 %s / SN %s" % (got["barcode"], got["sn"]))

        if not args.no_reset:
            mtk.reset(m)
        log("完成。")
        return 0
    finally:
        mtk.close(m)

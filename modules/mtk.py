# -*- coding: utf-8 -*-
"""MTK 下载模式会话：串口发现 → 握手 → 按偏移读写。

只用 4 KB 块操作 proinfo 头，不 dump 3 MB。
"""
import os
import time

from .common import ToolError, log

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "work")

# 串口发现
MTK_VID = "0E8D"


def find_port():
    """返回 MediaTek 下载模式对应的串口名（如 COM3），没有则 None。"""
    try:
        from serial.tools import list_ports
    except Exception:
        return None
    for info in list_ports.comports():
        hwid = (getattr(info, "hwid", "") or "").upper()
        desc = (getattr(info, "description", "") or "").upper()
        if MTK_VID in hwid or "PRELOADER" in desc or "MEDIATEK" in desc or "MTK" in desc:
            return info.device
    return None


def wait_port(timeout):
    t0 = time.time()
    last = 0.0
    while time.time() - t0 < timeout:
        p = find_port()
        if p:
            return p
        now = time.time()
        if now - last >= 5:
            last = now
            log("等待设备… 请把【已关机】的手机插上 USB（不按任何键）")
        time.sleep(0.3)
    return None


def connect(port, connect_timeout=25):
    """返回 (mtk, da)。失败抛 ToolError。"""
    import logging

    from mtkclient.config.mtk_config import MtkConfig
    from mtkclient.Library.mtk_class import Mtk
    from mtkclient.Library.DA.mtk_da_handler import DaHandler

    os.makedirs(WORK, exist_ok=True)
    os.environ.setdefault("SUNMI_MTK_WAIT_SEC", str(connect_timeout))

    cfg = MtkConfig(loglevel=logging.INFO, gui=None, guiprogress=None)
    cfg.loader = None
    mtk = Mtk(config=cfg, loglevel=logging.INFO, serialportname=port)
    da = DaHandler(mtk, logging.INFO)
    try:
        r = da.connect(mtk, directory=WORK)
    except Exception as e:
        raise ToolError("握手失败：%s" % e)
    if r is None:
        raise ToolError("握手失败：设备没有在 preloader/BROM 应答")
    try:
        r = da.configure_da(r)
    except Exception as e:
        raise ToolError("DA 配置失败：%s" % e)
    if r is None or getattr(r.config, "target_config", None) is None:
        raise ToolError("DA 配置未完成（target_config 为空）")
    return r, da


def read_block(da, offset, path, length):
    if os.path.exists(path):
        os.remove(path)
    try:
        ok = da.da_ro(start=offset, length=length, filename=path, parttype="user", display=False)
    except Exception as e:
        raise ToolError("读取失败：%s" % e)
    if not ok or not os.path.exists(path):
        raise ToolError("读取失败：设备未返回数据")
    with open(path, "rb") as f:
        data = f.read()
    if len(data) != length:
        raise ToolError("读回 %d 字节，期望 %d" % (len(data), length))
    return data


def write_block(da, offset, path, length):
    try:
        ok = da.da_wo(start=offset, length=length, filename=path, parttype="user")
    except Exception as e:
        raise ToolError("写入失败：%s\n  设备仍在会话中，请勿断电，可重跑本工具" % e)
    if not ok:
        raise ToolError("写入失败（DA 返回错误）。设备仍在会话中，请勿断电，可重跑本工具")


def reset(mtk):
    try:
        mtk.daloader.shutdown(bootmode=0)
        log("已发送重启命令，设备将进入系统")
    except Exception as e:
        log("重启命令异常：%s（设备可能已自行重启，不影响写入结果）" % e)


def close(mtk):
    try:
        if mtk is not None:
            mtk.port.close()
    except Exception:
        pass

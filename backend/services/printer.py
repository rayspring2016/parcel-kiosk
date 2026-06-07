"""
打印服务 — 用 fpdf2 生成 PDF 标签，通过 CUPS lp 命令发送到打印机。

本地 Mac：  PRINTER_HOST=localhost，使用本机 CUPS
NAS Docker：PRINTER_HOST=192.168.3.146（打印机 IP），lp -h 直连网络打印机
"""
import os
import subprocess
import tempfile
from typing import Optional

from fpdf import FPDF
from config import PRINTER_NAME, PRINTER_HOST


# ── 字体自动探测 ─────────────────────────────────────────────────
def _find_cjk_font() -> str:
    candidates = [
        os.getenv("FONT_PATH", ""),
        "/System/Library/Fonts/STHeiti Medium.ttc",                        # macOS
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",          # Debian
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",          # Ubuntu
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",               # Arch
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    raise FileNotFoundError(
        "找不到中文字体，请安装 fonts-noto-cjk 或设置 FONT_PATH 环境变量"
    )


_FONT_PATH: Optional[str] = None


def _font() -> str:
    global _FONT_PATH
    if _FONT_PATH is None:
        _FONT_PATH = _find_cjk_font()
    return _FONT_PATH


# ── PDF 生成 ─────────────────────────────────────────────────────
def _build_pdf(code: str, courier: str, arrived_at: str,
               unclaimed: bool = False) -> bytes:
    """生成 150×80mm 标签 PDF：大字编号居中，底部小字信息。"""
    pdf = FPDF(unit="mm", format=(150, 80))
    pdf.set_margins(0, 0, 0)
    pdf.set_auto_page_break(False)
    pdf.add_page()
    pdf.add_font("CJK", fname=_font())

    # 待认领：顶部红色条
    if unclaimed:
        pdf.set_fill_color(185, 28, 28)
        pdf.rect(0, 0, 150, 8, "F")
        pdf.set_font("CJK", size=7)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(0, 1)
        pdf.cell(150, 6, text="待 认 领  UNCLAIMED", align="C")

    top_y = 10 if unclaimed else 5

    # 到件时间（左上）/ 快递公司（右上）
    pdf.set_font("CJK", size=9)
    pdf.set_text_color(100, 100, 100)
    pdf.set_xy(8, top_y)
    pdf.cell(65, 6, text=arrived_at, align="L")
    pdf.set_xy(0, top_y)
    pdf.cell(142, 6, text=courier, align="R")

    # 大字编号
    pdf.set_font("CJK", size=46)
    pdf.set_text_color(20, 20, 20)
    pdf.set_xy(0, top_y + 8)
    pdf.cell(150, 34, text=code, align="C")

    # 分隔线
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.3)
    pdf.line(8, 56, 142, 56)

    # 底部小字
    pdf.set_font("CJK", size=9)
    pdf.set_text_color(80, 80, 80)
    pdf.set_xy(0, 59)
    pdf.cell(150, 6, text=f"{courier}  ·  {arrived_at}", align="C")

    return pdf.output()


# ── 发送打印 ─────────────────────────────────────────────────────
def _lp_print(pdf_bytes: bytes,
              printer: str = PRINTER_NAME,
              host: str = PRINTER_HOST) -> bool:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        tmp = f.name
    try:
        cmd = ["lp"]
        if host and host != "localhost":
            cmd += ["-h", host]
        cmd += ["-d", printer, tmp]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    finally:
        os.unlink(tmp)


# ── 服务类 ───────────────────────────────────────────────────────
class PrinterService:
    def __init__(self,
                 printer_name: str = PRINTER_NAME,
                 printer_host: str = PRINTER_HOST):
        self.printer_name = printer_name
        self.printer_host = printer_host

    def print_label(self, shelf: int, layer: int, seq: int,
                    courier: str, arrived_at: str) -> bool:
        code = f"{shelf}-{layer}-{seq:04d}"
        pdf = _build_pdf(code, courier, arrived_at, unclaimed=False)
        return _lp_print(pdf, self.printer_name, self.printer_host)

    def print_unclaimed_label(self, shelf: int, layer: int, seq: int,
                               courier: str, arrived_at: str) -> bool:
        code = f"{shelf}-{layer}-{seq:04d}"
        pdf = _build_pdf(code, courier, arrived_at, unclaimed=True)
        return _lp_print(pdf, self.printer_name, self.printer_host)


_printer_instance: Optional[PrinterService] = None


def get_printer_service() -> PrinterService:
    global _printer_instance
    if _printer_instance is None:
        _printer_instance = PrinterService()
    return _printer_instance

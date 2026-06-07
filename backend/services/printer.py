"""
打印服务 — 通过 macOS CUPS（lp 命令）向局域网打印机发送标签。
货架编号以 ASCII 大字渲染，方便快速辨认。
"""
import subprocess
import tempfile
import os
from typing import Optional
from config import PRINTER_NAME

# ASCII 大字体：每字符 3 宽，5 行高
_BIG: dict[str, list[str]] = {
    '0': ['###', '# #', '# #', '# #', '###'],
    '1': [' # ', ' # ', ' # ', ' # ', '###'],
    '2': ['###', '  #', '###', '#  ', '###'],
    '3': ['###', '  #', '###', '  #', '###'],
    '4': ['# #', '# #', '###', '  #', '  #'],
    '5': ['###', '#  ', '###', '  #', '###'],
    '6': ['###', '#  ', '###', '# #', '###'],
    '7': ['###', '  #', '  #', '  #', '  #'],
    '8': ['###', '# #', '###', '# #', '###'],
    '9': ['###', '# #', '###', '  #', '###'],
    '-': ['   ', '   ', '---', '   ', '   '],
    ' ': ['   ', '   ', '   ', '   ', '   '],
}


def _big_text(s: str, width: int = 32) -> str:
    """将字符串渲染为 5 行 ASCII 大字体，每行居中到 width。"""
    rows = [''] * 5
    for ch in s:
        char_rows = _BIG.get(ch, _BIG[' '])
        for r in range(5):
            rows[r] += char_rows[r] + ' '
    return '\n'.join(row.rstrip().center(width) for row in rows)


def _lp_print(text: str, printer: str = PRINTER_NAME) -> bool:
    """将文本写入临时文件，通过 lp 发送到 CUPS 打印机。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                    delete=False, encoding="utf-8") as f:
        f.write(text)
        tmp_path = f.name
    try:
        result = subprocess.run(
            ["lp", "-d", printer, tmp_path],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    finally:
        os.unlink(tmp_path)


def _build_label(code: str, info_lines: list, width: int = 32) -> str:
    """构建标签：大字编号 + 普通信息行。"""
    sep = "-" * width + "\n"
    big = _big_text(code, width)
    info = "".join(line.center(width) + "\n" for line in info_lines)
    return f"\n{sep}\n{big}\n\n{info}{sep}\n\n\n"


class PrinterService:
    def __init__(self, printer_name: str = PRINTER_NAME):
        self.printer_name = printer_name

    def print_label(self, shelf: int, layer: int, seq: int,
                    courier: str, arrived_at: str) -> bool:
        code = f"{shelf}-{layer}-{seq:04d}"
        label = _build_label(code, [
            f"货架 {shelf}  第 {layer} 层",
            courier,
            f"到件: {arrived_at}",
        ])
        return _lp_print(label, self.printer_name)

    def print_unclaimed_label(self, shelf: int, layer: int, seq: int,
                               courier: str, arrived_at: str) -> bool:
        code = f"{shelf}-{layer}-{seq:04d}"
        label = _build_label(code, [
            "【 待 认 领 】",
            f"货架 {shelf}  第 {layer} 层",
            courier,
            f"到件: {arrived_at}",
        ])
        return _lp_print(label, self.printer_name)


_printer_instance: Optional[PrinterService] = None


def get_printer_service() -> PrinterService:
    global _printer_instance
    if _printer_instance is None:
        _printer_instance = PrinterService()
    return _printer_instance

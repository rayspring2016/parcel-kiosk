from typing import Optional


class PrinterService:
    def __init__(self, printer=None, usb_vendor=0x04b8, usb_product=0x0202):
        if printer is not None:
            self.printer = printer
        else:
            from escpos.printer import Usb
            self.printer = Usb(usb_vendor, usb_product)

    def _print_lines(self, lines: list):
        p = self.printer
        p.set(align="center", bold=True, height=2, width=2)
        for line in lines:
            p.text(line + "\n")
        p.set(align="center", bold=False, height=1, width=1)
        p.cut()

    def print_label(self, code: str, courier: str, arrived_at: str):
        self._print_lines([courier, code, f"到件：{arrived_at}"])

    def print_unclaimed_label(self, code: str, courier: str, arrived_at: str):
        self._print_lines(["【待认领】", courier, code, f"到件：{arrived_at}"])


_printer_instance: Optional[PrinterService] = None


def get_printer_service() -> PrinterService:
    """懒加载单例：USB 打印机不支持多连接，必须全程共用同一实例"""
    global _printer_instance
    if _printer_instance is None:
        _printer_instance = PrinterService()
    return _printer_instance

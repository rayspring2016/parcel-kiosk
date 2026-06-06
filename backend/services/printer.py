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

    def print_label(self, shelf: int, layer: int, seq: int, courier: str, arrived_at: str):
        """正常标签：位置编号最大，快递公司次之"""
        code = f"{shelf}-{layer}-{seq:04d}"
        self._print_lines([code, f"货架{shelf} 第{layer}层", courier, f"到件：{arrived_at}"])

    def print_unclaimed_label(self, shelf: int, layer: int, seq: int, courier: str, arrived_at: str):
        code = f"{shelf}-{layer}-{seq:04d}"
        self._print_lines(["【待认领】", code, f"货架{shelf} 第{layer}层", courier, f"到件：{arrived_at}"])


_printer_instance: Optional[PrinterService] = None


def get_printer_service() -> PrinterService:
    global _printer_instance
    if _printer_instance is None:
        _printer_instance = PrinterService()
    return _printer_instance

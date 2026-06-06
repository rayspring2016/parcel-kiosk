from unittest.mock import MagicMock
from services.printer import PrinterService


def test_print_label_sends_content():
    mock_printer = MagicMock()
    svc = PrinterService(printer=mock_printer)
    svc.print_label(shelf=1, layer=2, seq=7, courier="顺丰", arrived_at="2026/06/06 14:32")
    assert mock_printer.text.called
    # 验证编号格式正确出现在打印内容中
    calls = [str(c) for c in mock_printer.text.call_args_list]
    assert any("1-2-0007" in c for c in calls)


def test_print_unclaimed_label():
    mock_printer = MagicMock()
    svc = PrinterService(printer=mock_printer)
    svc.print_unclaimed_label(shelf=2, layer=3, seq=12, courier="京东", arrived_at="2026/06/06 15:00")
    assert mock_printer.text.called
    calls = [str(c) for c in mock_printer.text.call_args_list]
    assert any("2-3-0012" in c for c in calls)

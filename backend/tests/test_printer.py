from unittest.mock import MagicMock
from services.printer import PrinterService


def test_print_label_sends_content():
    mock_printer = MagicMock()
    svc = PrinterService(printer=mock_printer)
    svc.print_label(slot=7, courier="顺丰", arrived_at="2026/06/06 14:32")
    assert mock_printer.text.called


def test_print_unclaimed_label():
    mock_printer = MagicMock()
    svc = PrinterService(printer=mock_printer)
    svc.print_unclaimed_label(slot=12, courier="京东", arrived_at="2026/06/06 15:00")
    assert mock_printer.text.called

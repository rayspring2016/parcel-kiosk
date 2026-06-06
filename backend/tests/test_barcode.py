from services.barcode import parse_barcode


def test_parse_json_format():
    raw = '{"name":"张三","mobile":"13800138000","courier":"YTO"}'
    result = parse_barcode(raw)
    assert result.phone == "13800138000"
    assert result.courier == "圆通"


def test_parse_sf_format():
    raw = "SF|13900139000|李四|北京市朝阳区"
    result = parse_barcode(raw)
    assert result.phone == "13900139000"
    assert result.courier == "顺丰"


def test_parse_phone_regex_fallback():
    raw = "JD0012345678|王五|13700137000|上海市"
    result = parse_barcode(raw)
    assert result.phone == "13700137000"


def test_parse_no_phone_returns_none():
    raw = "UNKNOWN_FORMAT_NO_PHONE"
    result = parse_barcode(raw)
    assert result.phone is None


def test_courier_detection_jd():
    raw = '{"mobile":"13800138000","courier":"JD"}'
    result = parse_barcode(raw)
    assert result.courier == "京东"

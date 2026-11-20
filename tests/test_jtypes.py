import pytest
from extera_toolkit.jtypes import (
    argb_to_int,
    color_from_hex,
    color_to_hex,
    to_jint,
    to_jlong,
    to_signed32,
    to_signed64,
)


def test_to_signed32():
    # 0x7FFFFFFF is max signed 32-bit positive int
    assert to_signed32(0x7FFFFFFF) == 2147483647
    # 0x80000000 becomes -2147483648
    assert to_signed32(0x80000000) == -2147483648
    # 0xFFFFFFFF becomes -1
    assert to_signed32(0xFFFFFFFF) == -1
    assert to_signed32("0xFFFFFFFF") == -1
    assert to_signed32(4294967295) == -1


def test_to_signed64():
    # 64-bit Telegram peer IDs
    topic_peer = -1001234567890
    assert to_signed64(topic_peer) == -1001234567890
    assert to_signed64("0xFFFFFFFFFFFFFFFF") == -1


def test_color_from_hex():
    # #FFFFFF -> 0xFFFFFFFF -> -1
    assert color_from_hex("#FFFFFF") == -1
    assert color_from_hex("FFFFFF") == -1
    # 3-char shorthand #FFF -> #FFFFFF -> -1
    assert color_from_hex("#FFF") == -1
    # #000000 -> 0xFF000000 -> -16777216
    assert color_from_hex("#000000") == -16777216
    # With explicit alpha: #80FFFFFF -> 0x80FFFFFF -> -2130706433
    val = color_from_hex("#80FFFFFF")
    assert val == -2130706433
    assert color_to_hex(val) == "#80FFFFFF"


def test_argb_to_int():
    white = argb_to_int(255, 255, 255, 255)
    assert white == -1
    assert color_to_hex(white) == "#FFFFFFFF"

    black = argb_to_int(255, 0, 0, 0)
    assert black == -16777216
    assert color_to_hex(black, include_alpha=False) == "#000000"

import re
from typing import Optional, Union

try:
    from java import jint, jlong
except ImportError:
    jint = None
    jlong = None

HEX_COLOR_REGEX = re.compile(r"^#?([0-9a-fA-F]{3,8})$")


def to_signed32(val: Union[int, float, str]) -> int:
    """Converts any integer or hex string to Java signed 32-bit integer (-2147483648 to 2147483647)."""
    if isinstance(val, str):
        v = val.strip()
        int_val = int(v, 16) if v.startswith(("0x", "0X")) else int(v)
    else:
        int_val = int(val)
    n = int_val & 0xFFFFFFFF
    return (n ^ 0x80000000) - 0x80000000


def to_signed64(val: Union[int, float, str]) -> int:
    """Converts 64-bit Telegram IDs (e.g. -100... or user IDs) to signed 64-bit integer."""
    if isinstance(val, str):
        v = val.strip()
        int_val = int(v, 16) if v.startswith(("0x", "0X")) else int(v)
    else:
        int_val = int(val)
    n = int_val & 0xFFFFFFFFFFFFFFFF
    return (n ^ 0x8000000000000000) - 0x8000000000000000


def to_jint(val: Union[int, float, str]):
    """Returns Chaquopy jint with signed 32-bit normalization."""
    s32 = to_signed32(val)
    if jint is not None:
        return jint(s32)
    return s32


def to_jlong(val: Union[int, float, str]):
    """Returns Chaquopy jlong with signed 64-bit normalization."""
    s64 = to_signed64(val)
    if jlong is not None:
        return jlong(s64)
    return s64


def color_from_hex(hex_str: str, default_alpha: int = 0xFF) -> int:
    """Parses #RGB, #RRGGBB, #AARRGGBB hex color into Android signed 32-bit integer."""
    clean = hex_str.strip()
    if clean.startswith("0x") or clean.startswith("0X"):
        clean = clean[2:]
    elif clean.startswith("#"):
        clean = clean[1:]

    if len(clean) == 3:  # RGB -> RRGGBB
        clean = "".join([c * 2 for c in clean])

    if len(clean) == 6:  # RRGGBB -> AARRGGBB
        argb_unsigned = (default_alpha << 24) | int(clean, 16)
    elif len(clean) == 8:  # AARRGGBB
        argb_unsigned = int(clean, 16)
    else:
        raise ValueError(f"Invalid hex color format: '{hex_str}'")

    return to_signed32(argb_unsigned)


def color_to_hex(signed_int: int, include_alpha: bool = True) -> str:
    """Converts an Android signed 32-bit color int to #AARRGGBB or #RRGGBB hex string."""
    unsigned = signed_int & 0xFFFFFFFF
    if include_alpha:
        return f"#{unsigned:08X}"
    return f"#{unsigned & 0x00FFFFFF:06X}"


def argb_to_int(a: int, r: int, g: int, b: int) -> int:
    """Constructs Android signed 32-bit color integer from ARGB components (0-255)."""
    unsigned = ((a & 0xFF) << 24) | ((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF)
    return to_signed32(unsigned)

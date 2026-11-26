"""DDS payload handling for the viewer — base64 decode + a HEADER-ONLY validity probe.

This module is deliberately **not** a DDS/DXT *decoder*. Blender's native image loader
decodes the pixels (``bpy.data.images.load``); forking a second pixel decoder into the
add-on is exactly the ecosystem-scale drift ``docs/design/blender-integration.md`` and
CLAUDE.md invariant 3 forbid. All this does is:

  * :func:`decode_payload` — base64 → raw ``.dds`` bytes (the finding-0024 pass-through:
    a shipped ``Texture`` ``<Payload>`` IS a literal complete D3D9 .dds file).
  * :func:`probe` — read the fixed 128-byte ``DDS_HEADER`` (magic + a few size/format
    fields) to assert it is a *sane* D3D9 DDS. This is the task's byte-**decidable**
    sub-anchor: the payload is byte-exact (0024), so "does it parse as a valid DDS header"
    is a true/false check, not a judgement call. Header fields only — never pixel data.

It is pure-stdlib so it runs in the headless parser tests (no ``bpy``).

Reference: Microsoft DDS_HEADER / DDS_PIXELFORMAT layout (the D3D9 on-disk header).
"""

from __future__ import annotations

import base64
import struct
from dataclasses import dataclass
from typing import Optional

DDS_MAGIC = b"DDS "          # bytes 0..3
_HEADER_SIZE = 124           # dwSize at offset 4 for a valid DDS_HEADER
_PF_SIZE = 32                # dwSize of the embedded DDS_PIXELFORMAT (offset 76)
_MIN_LEN = 128               # magic (4) + DDS_HEADER (124)

# DDS_PIXELFORMAT dwFlags bits we care about.
_DDPF_FOURCC = 0x00000004    # dwFourCC is meaningful (compressed / DX10 / etc.)
_DDPF_RGB = 0x00000040       # uncompressed RGB(A); dwRGBBitCount is meaningful

# Compressed / extended FourCCs a shipped KW texture can legitimately carry. DXT1/3/5 are
# the common cases (finding 0024); the others are accepted as "valid DDS" so the probe
# never rejects a real shipped payload it simply didn't special-case.
_KNOWN_FOURCC = {
    b"DXT1", b"DXT2", b"DXT3", b"DXT4", b"DXT5",
    b"DX10", b"ATI1", b"ATI2", b"BC4U", b"BC4S", b"BC5U", b"BC5S",
    b"RGBG", b"GRGB", b"UYVY", b"YUY2",
}
_MAX_DIM = 16384             # sane D3D texture dimension ceiling


@dataclass
class DdsInfo:
    """Result of :func:`probe`. ``valid`` is the decidable verdict; ``reason`` explains a
    failure. On success, the parsed header fields are filled for honest reporting."""

    valid: bool
    reason: str = ""
    width: int = 0
    height: int = 0
    mip_count: int = 0
    fourcc: str = ""          # 4-char code, or "" for an uncompressed payload
    uncompressed: bool = False
    bit_count: int = 0        # dwRGBBitCount, only meaningful when uncompressed


def decode_payload(payload_b64: str) -> bytes:
    """Base64-decode a ``<Payload>`` into raw ``.dds`` bytes. Raises on invalid base64
    (``binascii.Error``) — validate the result with :func:`probe`."""
    return base64.b64decode(payload_b64, validate=True)


def probe(data: bytes) -> DdsInfo:
    """Validate the fixed DDS header and return its key fields. Header-only — does not
    touch pixel/mip data, so a truncated-but-well-headed blob still reports its dims."""
    if len(data) < _MIN_LEN:
        return DdsInfo(False, f"too short ({len(data)} bytes; need >= {_MIN_LEN})")
    if data[0:4] != DDS_MAGIC:
        return DdsInfo(False, f"bad magic {data[0:4]!r} (expected {DDS_MAGIC!r})")

    # DDS_HEADER starts at offset 4. Fields read (little-endian): dwSize@4, dwHeight@12,
    # dwWidth@16, dwMipMapCount@28; DDS_PIXELFORMAT at 76: dwSize@76, dwFlags@80,
    # dwFourCC@84, dwRGBBitCount@88.
    dw_size = struct.unpack_from("<I", data, 4)[0]
    if dw_size != _HEADER_SIZE:
        return DdsInfo(False, f"dwSize={dw_size} (expected {_HEADER_SIZE})")
    height = struct.unpack_from("<I", data, 12)[0]
    width = struct.unpack_from("<I", data, 16)[0]
    mip_count = struct.unpack_from("<I", data, 28)[0]
    if not (1 <= width <= _MAX_DIM and 1 <= height <= _MAX_DIM):
        return DdsInfo(False, f"implausible dimensions {width}x{height}")

    pf_size = struct.unpack_from("<I", data, 76)[0]
    if pf_size != _PF_SIZE:
        return DdsInfo(False, f"pixelformat dwSize={pf_size} (expected {_PF_SIZE})")
    pf_flags = struct.unpack_from("<I", data, 80)[0]
    fourcc = data[84:88]
    bit_count = struct.unpack_from("<I", data, 88)[0]

    if pf_flags & _DDPF_FOURCC:
        if fourcc not in _KNOWN_FOURCC:
            return DdsInfo(False, f"unknown FourCC {fourcc!r}", width=width, height=height,
                           mip_count=mip_count)
        return DdsInfo(True, width=width, height=height, mip_count=mip_count,
                       fourcc=fourcc.decode("ascii", "replace"))
    if pf_flags & _DDPF_RGB:
        if bit_count not in (8, 16, 24, 32):
            return DdsInfo(False, f"uncompressed RGB with odd bit count {bit_count}",
                           width=width, height=height, mip_count=mip_count)
        return DdsInfo(True, width=width, height=height, mip_count=mip_count,
                       uncompressed=True, bit_count=bit_count)
    return DdsInfo(False, f"pixelformat flags 0x{pf_flags:08x} are neither FourCC nor RGB",
                   width=width, height=height, mip_count=mip_count)


def is_valid(data: bytes) -> tuple[bool, str]:
    """Convenience boolean wrapper over :func:`probe`."""
    info = probe(data)
    return info.valid, info.reason


def decode_and_probe(payload_b64: str) -> tuple[Optional[bytes], DdsInfo]:
    """Decode a payload and probe it in one step. Returns ``(bytes|None, DdsInfo)``;
    bytes is ``None`` when the base64 itself is invalid."""
    try:
        data = decode_payload(payload_b64)
    except Exception as e:  # binascii.Error and friends
        return None, DdsInfo(False, f"invalid base64: {e}")
    return data, probe(data)

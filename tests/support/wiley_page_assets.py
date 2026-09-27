"""Minimal binary/DOM scenarios for Wiley page capture contracts."""

import struct
import zlib

WEBP_1X1 = bytes.fromhex(
    "52494646220000005745425056503820160000003001009d012a010001000140262500"
    "4e8021f000fefee0000000"
)


def png_bytes(width=320, height=240):
    def chunk(kind, data):
        return (
            struct.pack("!I", len(data))
            + kind
            + data
            + struct.pack("!I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress((b"\0" + b"\x80\x40\x20" * width) * height))
        + chunk(b"IEND", b"")
    )


def formula(url):
    return {"kind": "formula", "url": url, "preview_url": url, "heading": "Equation 1"}


def figure(root, index):
    return {
        "kind": "figure",
        "dom_id": f"fig-{index}",
        "heading": f"Figure {index}",
        "url": f"{root}/full-{index}.png",
        "full_size_url": f"{root}/full-{index}.png",
        "preview_url": f"{root}/preview-{index}.png",
    }

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
PNG_PATH = ASSETS / "app-icon.png"
ICO_PATH = ASSETS / "app-icon.ico"
ICNS_PATH = ASSETS / "app-icon.icns"

GREEN_TOP = (47, 111, 79, 255)
GREEN_BOTTOM = (21, 63, 49, 255)
WHITE = (255, 254, 249, 255)


def mix(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def rounded_rect_mask(x: float, y: float, width: float, height: float, radius: float) -> bool:
    px = min(max(x, radius), width - radius)
    py = min(max(y, radius), height - radius)
    return (x - px) ** 2 + (y - py) ** 2 <= radius**2


def draw_round_line(pixels: bytearray, size: int, x: float, y1: float, y2: float, width: float) -> None:
    radius = width / 2
    min_x = max(0, math.floor(x - radius))
    max_x = min(size - 1, math.ceil(x + radius))
    min_y = max(0, math.floor(y1 - radius))
    max_y = min(size - 1, math.ceil(y2 + radius))
    for py in range(min_y, max_y + 1):
        for px in range(min_x, max_x + 1):
            dx = px + 0.5 - x
            if y1 <= py + 0.5 <= y2:
                distance = abs(dx)
            else:
                cy = y1 if py + 0.5 < y1 else y2
                dy = py + 0.5 - cy
                distance = math.hypot(dx, dy)
            edge = radius - distance
            if edge <= 0:
                continue
            alpha = min(1.0, edge)
            offset = (py * size + px) * 4
            existing_alpha = pixels[offset + 3] / 255
            out_alpha = alpha + existing_alpha * (1 - alpha)
            for channel in range(3):
                pixels[offset + channel] = round(
                    (
                        WHITE[channel] * alpha
                        + pixels[offset + channel] * existing_alpha * (1 - alpha)
                    )
                    / out_alpha
                )
            pixels[offset + 3] = round(out_alpha * 255)


def png_bytes(size: int) -> bytes:
    pixels = bytearray(size * size * 4)
    rect = size * 0.109375
    rect_size = size * 0.78125
    radius = size * 0.2109375
    shadow_center = (size / 2, size * 0.55)

    for y in range(size):
        for x in range(size):
            offset = (y * size + x) * 4
            nx = x + 0.5 - rect
            ny = y + 0.5 - rect

            sx = (x + 0.5 - shadow_center[0]) / (size * 0.44)
            sy = (y + 0.5 - shadow_center[1]) / (size * 0.42)
            shadow = max(0, 1 - (sx * sx + sy * sy))
            if shadow > 0:
                pixels[offset:offset + 4] = bytes((15, 38, 30, round(48 * shadow)))

            if not rounded_rect_mask(nx, ny, rect_size, rect_size, radius):
                continue

            t = min(1, max(0, (x + y) / (2 * size)))
            color = tuple(mix(GREEN_TOP[i], GREEN_BOTTOM[i], t) for i in range(3)) + (255,)
            pixels[offset:offset + 4] = bytes(color)

    bars = [
        (268, 478, 546),
        (348, 382, 642),
        (428, 304, 720),
        (508, 362, 662),
        (588, 320, 704),
        (668, 402, 622),
        (748, 478, 546),
    ]
    scale = size / 1024
    for x, y1, y2 in bars:
        draw_round_line(pixels, size, x * scale, y1 * scale, y2 * scale, 74 * scale)

    return encode_png(size, size, pixels)


def encode_png(width: int, height: int, rgba: bytearray) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = bytearray()
    row_bytes = width * 4
    for y in range(height):
        raw.append(0)
        start = y * row_bytes
        raw.extend(rgba[start:start + row_bytes])

    return b"\x89PNG\r\n\x1a\n" + chunk(
        b"IHDR",
        struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0),
    ) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")


def make_ico(images: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(images))
    directory = bytearray()
    data = bytearray()
    offset = 6 + 16 * len(images)
    for size, image in images:
        directory.extend(
            struct.pack(
                "<BBBBHHII",
                0 if size >= 256 else size,
                0 if size >= 256 else size,
                0,
                0,
                1,
                32,
                len(image),
                offset,
            )
        )
        data.extend(image)
        offset += len(image)
    return header + bytes(directory) + bytes(data)


def make_icns(images: list[tuple[str, bytes]]) -> bytes:
    payload = bytearray()
    for kind, image in images:
        payload.extend(kind.encode("ascii"))
        payload.extend(struct.pack(">I", len(image) + 8))
        payload.extend(image)
    return b"icns" + struct.pack(">I", len(payload) + 8) + bytes(payload)


def main() -> None:
    ASSETS.mkdir(exist_ok=True)

    pngs = {size: png_bytes(size) for size in (16, 32, 48, 64, 128, 256, 512, 1024)}
    PNG_PATH.write_bytes(pngs[1024])
    ico_images = [(size, png_bytes(size)) for size in (16, 32, 48, 64, 128, 256)]
    ICO_PATH.write_bytes(make_ico(ico_images))

    icns_images = [
        ("icp4", pngs[16]),
        ("icp5", pngs[32]),
        ("icp6", pngs[64]),
        ("ic07", pngs[128]),
        ("ic08", pngs[256]),
        ("ic09", pngs[512]),
        ("ic10", pngs[1024]),
        ("ic11", pngs[32]),
        ("ic12", pngs[64]),
        ("ic13", pngs[256]),
        ("ic14", pngs[512]),
    ]
    ICNS_PATH.write_bytes(make_icns(icns_images))


if __name__ == "__main__":
    main()

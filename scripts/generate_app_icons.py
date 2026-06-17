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
PAPER = (250, 248, 237, 255)
INK = (0, 55, 66, 255)
WAVE = (0, 108, 91, 255)
ACCENT = (255, 107, 44, 255)
OUTLINE = (0, 55, 66, 90)


def mix(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return min(max(value, minimum), maximum)


def blend_pixel(
    pixels: bytearray,
    size: int,
    x: int,
    y: int,
    color: tuple[int, int, int, int],
    coverage: float = 1.0,
) -> None:
    if not (0 <= x < size and 0 <= y < size):
        return
    alpha = coverage * color[3] / 255
    if alpha <= 0:
        return
    offset = (y * size + x) * 4
    existing_alpha = pixels[offset + 3] / 255
    out_alpha = alpha + existing_alpha * (1 - alpha)
    if out_alpha <= 0:
        return
    for channel in range(3):
        pixels[offset + channel] = round(
            (
                color[channel] * alpha
                + pixels[offset + channel] * existing_alpha * (1 - alpha)
            )
            / out_alpha
        )
    pixels[offset + 3] = round(out_alpha * 255)


def rounded_rect_coverage(
    px: float,
    py: float,
    x: float,
    y: float,
    width: float,
    height: float,
    radius: float,
) -> float:
    half_width = width / 2
    half_height = height / 2
    dx = abs(px - (x + half_width)) - (half_width - radius)
    dy = abs(py - (y + half_height)) - (half_height - radius)
    outside = math.hypot(max(dx, 0), max(dy, 0))
    inside = min(max(dx, dy), 0)
    signed_distance = outside + inside - radius
    return clamp(0.5 - signed_distance)


def fill_rounded_rect(
    pixels: bytearray,
    size: int,
    x: float,
    y: float,
    width: float,
    height: float,
    radius: float,
    color: tuple[int, int, int, int],
) -> None:
    min_x = max(0, math.floor(x - 1))
    max_x = min(size - 1, math.ceil(x + width + 1))
    min_y = max(0, math.floor(y - 1))
    max_y = min(size - 1, math.ceil(y + height + 1))
    for py in range(min_y, max_y + 1):
        for px in range(min_x, max_x + 1):
            coverage = rounded_rect_coverage(px + 0.5, py + 0.5, x, y, width, height, radius)
            if coverage:
                blend_pixel(pixels, size, px, py, color, coverage)


def fill_ellipse(
    pixels: bytearray,
    size: int,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    color: tuple[int, int, int, int],
) -> None:
    min_x = max(0, math.floor(cx - rx - 1))
    max_x = min(size - 1, math.ceil(cx + rx + 1))
    min_y = max(0, math.floor(cy - ry - 1))
    max_y = min(size - 1, math.ceil(cy + ry + 1))
    for py in range(min_y, max_y + 1):
        for px in range(min_x, max_x + 1):
            nx = (px + 0.5 - cx) / rx
            ny = (py + 0.5 - cy) / ry
            distance = math.sqrt(nx * nx + ny * ny)
            coverage = clamp((1.0 - distance) * min(rx, ry))
            if coverage:
                blend_pixel(pixels, size, px, py, color, coverage)


def draw_round_line(
    pixels: bytearray,
    size: int,
    x: float,
    y1: float,
    y2: float,
    width: float,
    color: tuple[int, int, int, int],
) -> None:
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
            blend_pixel(pixels, size, px, py, color, alpha)


def draw_horizontal_round_line(
    pixels: bytearray,
    size: int,
    x1: float,
    x2: float,
    y: float,
    width: float,
    color: tuple[int, int, int, int],
) -> None:
    radius = width / 2
    min_x = max(0, math.floor(x1 - radius))
    max_x = min(size - 1, math.ceil(x2 + radius))
    min_y = max(0, math.floor(y - radius))
    max_y = min(size - 1, math.ceil(y + radius))
    for py in range(min_y, max_y + 1):
        for px in range(min_x, max_x + 1):
            dy = py + 0.5 - y
            if x1 <= px + 0.5 <= x2:
                distance = abs(dy)
            else:
                cx = x1 if px + 0.5 < x1 else x2
                dx = px + 0.5 - cx
                distance = math.hypot(dx, dy)
            edge = radius - distance
            if edge <= 0:
                continue
            blend_pixel(pixels, size, px, py, color, min(1.0, edge))


def png_bytes(size: int) -> bytes:
    pixels = bytearray(size * size * 4)
    scale = size / 1024
    background_rect = size * 0.0625
    background_size = size * 0.875
    background_radius = size * 0.21875

    for y in range(size):
        for x in range(size):
            offset = (y * size + x) * 4

            coverage = rounded_rect_coverage(
                x + 0.5,
                y + 0.5,
                background_rect,
                background_rect,
                background_size,
                background_size,
                background_radius,
            )
            if not coverage:
                continue

            t = min(1, max(0, (x + y) / (2 * size)))
            color = tuple(mix(GREEN_TOP[i], GREEN_BOTTOM[i], t) for i in range(3)) + (255,)
            pixels[offset:offset + 4] = bytes((*color[:3], round(coverage * 255)))

    fill_rounded_rect(
        pixels,
        size,
        152 * scale,
        122 * scale,
        520 * scale,
        210 * scale,
        105 * scale,
        (255, 255, 255, 42),
    )
    fill_rounded_rect(
        pixels,
        size,
        248 * scale,
        236 * scale,
        560 * scale,
        604 * scale,
        94 * scale,
        (0, 0, 0, 36),
    )
    fill_rounded_rect(
        pixels,
        size,
        222 * scale,
        204 * scale,
        580 * scale,
        620 * scale,
        98 * scale,
        OUTLINE,
    )
    fill_rounded_rect(
        pixels,
        size,
        234 * scale,
        216 * scale,
        556 * scale,
        596 * scale,
        86 * scale,
        PAPER,
    )

    bars = [
        (320, 330, 430),
        (386, 292, 470),
        (452, 350, 430),
        (518, 272, 506),
        (584, 336, 456),
        (650, 310, 482),
        (716, 366, 434),
    ]
    for x, y1, y2 in bars:
        draw_round_line(pixels, size, x * scale, y1 * scale, y2 * scale, 30 * scale, WAVE)

    fill_ellipse(pixels, size, 325 * scale, 318 * scale, 42 * scale, 42 * scale, ACCENT)

    for y, width in ((566, 410), (646, 330), (724, 250)):
        draw_horizontal_round_line(
            pixels,
            size,
            318 * scale,
            (318 + width) * scale,
            y * scale,
            26 * scale,
            INK,
        )

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

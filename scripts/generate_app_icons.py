from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
MSIX_ASSETS = ASSETS / "msix"
PNG_PATH = ASSETS / "app-icon.png"
ICO_PATH = ASSETS / "app-icon.ico"
ICNS_PATH = ASSETS / "app-icon.icns"

GREEN_TOP = (47, 111, 79, 255)
GREEN_BOTTOM = (21, 63, 49, 255)
PAPER = (250, 248, 237, 255)
INK = (0, 55, 66, 255)
WAVE = (0, 108, 91, 255)
ACCENT = (255, 107, 44, 255)
OUTLINE = (0, 55, 66, 90)

MSIX_TILE_SIZES = {
    "StoreLogo.png": (50, 50),
    "Square44x44Logo.png": (44, 44),
    "Square71x71Logo.png": (71, 71),
    "Square150x150Logo.png": (150, 150),
    "Square310x310Logo.png": (310, 310),
    "Wide310x150Logo.png": (310, 150),
    "SplashScreen.png": (620, 300),
}


def mix(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return min(max(value, minimum), maximum)


def blend_pixel(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    color: tuple[int, int, int, int],
    coverage: float = 1.0,
) -> None:
    if not (0 <= x < width and 0 <= y < height):
        return
    alpha = coverage * color[3] / 255
    if alpha <= 0:
        return
    offset = (y * width + x) * 4
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
    return clamp(0.5 - (outside + inside - radius))


def fill_rounded_rect(
    pixels: bytearray,
    canvas_width: int,
    canvas_height: int,
    x: float,
    y: float,
    width: float,
    height: float,
    radius: float,
    color: tuple[int, int, int, int],
) -> None:
    min_x = max(0, math.floor(x - 1))
    max_x = min(canvas_width - 1, math.ceil(x + width + 1))
    min_y = max(0, math.floor(y - 1))
    max_y = min(canvas_height - 1, math.ceil(y + height + 1))
    for py in range(min_y, max_y + 1):
        for px in range(min_x, max_x + 1):
            coverage = rounded_rect_coverage(px + 0.5, py + 0.5, x, y, width, height, radius)
            if coverage:
                blend_pixel(pixels, canvas_width, canvas_height, px, py, color, coverage)


def fill_ellipse(
    pixels: bytearray,
    canvas_width: int,
    canvas_height: int,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    color: tuple[int, int, int, int],
) -> None:
    min_x = max(0, math.floor(cx - rx - 1))
    max_x = min(canvas_width - 1, math.ceil(cx + rx + 1))
    min_y = max(0, math.floor(cy - ry - 1))
    max_y = min(canvas_height - 1, math.ceil(cy + ry + 1))
    for py in range(min_y, max_y + 1):
        for px in range(min_x, max_x + 1):
            nx = (px + 0.5 - cx) / rx
            ny = (py + 0.5 - cy) / ry
            coverage = clamp((1.0 - math.hypot(nx, ny)) * min(rx, ry))
            if coverage:
                blend_pixel(pixels, canvas_width, canvas_height, px, py, color, coverage)


def draw_vertical_line(
    pixels: bytearray,
    canvas_width: int,
    canvas_height: int,
    x: float,
    y1: float,
    y2: float,
    line_width: float,
    color: tuple[int, int, int, int],
) -> None:
    radius = line_width / 2
    min_x = max(0, math.floor(x - radius))
    max_x = min(canvas_width - 1, math.ceil(x + radius))
    min_y = max(0, math.floor(y1 - radius))
    max_y = min(canvas_height - 1, math.ceil(y2 + radius))
    for py in range(min_y, max_y + 1):
        for px in range(min_x, max_x + 1):
            dx = px + 0.5 - x
            if y1 <= py + 0.5 <= y2:
                distance = abs(dx)
            else:
                cy = y1 if py + 0.5 < y1 else y2
                distance = math.hypot(dx, py + 0.5 - cy)
            coverage = clamp(radius - distance)
            if coverage:
                blend_pixel(pixels, canvas_width, canvas_height, px, py, color, coverage)


def draw_horizontal_line(
    pixels: bytearray,
    canvas_width: int,
    canvas_height: int,
    x1: float,
    x2: float,
    y: float,
    line_width: float,
    color: tuple[int, int, int, int],
) -> None:
    radius = line_width / 2
    min_x = max(0, math.floor(x1 - radius))
    max_x = min(canvas_width - 1, math.ceil(x2 + radius))
    min_y = max(0, math.floor(y - radius))
    max_y = min(canvas_height - 1, math.ceil(y + radius))
    for py in range(min_y, max_y + 1):
        for px in range(min_x, max_x + 1):
            dy = py + 0.5 - y
            if x1 <= px + 0.5 <= x2:
                distance = abs(dy)
            else:
                cx = x1 if px + 0.5 < x1 else x2
                distance = math.hypot(px + 0.5 - cx, dy)
            coverage = clamp(radius - distance)
            if coverage:
                blend_pixel(pixels, canvas_width, canvas_height, px, py, color, coverage)


def fill_gradient(
    pixels: bytearray,
    width: int,
    height: int,
    rounded: bool,
) -> None:
    inset = min(width, height) * 0.0625
    rect_width = width - 2 * inset
    rect_height = height - 2 * inset
    radius = min(width, height) * 0.21875
    for y in range(height):
        for x in range(width):
            coverage = 1.0
            if rounded:
                coverage = rounded_rect_coverage(
                    x + 0.5,
                    y + 0.5,
                    inset,
                    inset,
                    rect_width,
                    rect_height,
                    radius,
                )
            if not coverage:
                continue
            t = (x / max(1, width - 1) + y / max(1, height - 1)) / 2
            color = tuple(mix(GREEN_TOP[i], GREEN_BOTTOM[i], t) for i in range(3)) + (255,)
            blend_pixel(pixels, width, height, x, y, color, coverage)


def draw_document_mark(
    pixels: bytearray,
    canvas_width: int,
    canvas_height: int,
    origin_x: float,
    origin_y: float,
    scale: float,
) -> None:
    def x(value: float) -> float:
        return origin_x + value * scale

    def y(value: float) -> float:
        return origin_y + value * scale

    fill_rounded_rect(
        pixels, canvas_width, canvas_height, x(152), y(122), 520 * scale, 210 * scale,
        105 * scale, (255, 255, 255, 42),
    )
    fill_rounded_rect(
        pixels, canvas_width, canvas_height, x(222), y(204), 580 * scale, 620 * scale,
        98 * scale, OUTLINE,
    )
    fill_rounded_rect(
        pixels, canvas_width, canvas_height, x(234), y(216), 556 * scale, 596 * scale,
        86 * scale, PAPER,
    )

    for bar_x, y1, y2 in (
        (320, 330, 430),
        (386, 292, 470),
        (452, 350, 430),
        (518, 272, 506),
        (584, 336, 456),
        (650, 310, 482),
        (716, 366, 434),
    ):
        draw_vertical_line(
            pixels, canvas_width, canvas_height, x(bar_x), y(y1), y(y2), 30 * scale, WAVE,
        )
    fill_ellipse(
        pixels, canvas_width, canvas_height, x(325), y(318), 42 * scale, 42 * scale, ACCENT,
    )
    for line_y, line_width in ((566, 410), (646, 330), (724, 250)):
        draw_horizontal_line(
            pixels, canvas_width, canvas_height, x(318), x(318 + line_width), y(line_y),
            26 * scale, INK,
        )


def draw_compact_waveform(
    pixels: bytearray,
    canvas_width: int,
    canvas_height: int,
    origin_x: float,
    origin_y: float,
    size: float,
) -> None:
    for factor_x, y1, y2 in (
        (0.25, 0.44, 0.56),
        (0.38, 0.30, 0.70),
        (0.50, 0.20, 0.80),
        (0.62, 0.30, 0.70),
        (0.75, 0.44, 0.56),
    ):
        draw_vertical_line(
            pixels,
            canvas_width,
            canvas_height,
            origin_x + factor_x * size,
            origin_y + y1 * size,
            origin_y + y2 * size,
            size * 0.11,
            PAPER,
        )


def app_icon_png(size: int) -> bytes:
    pixels = bytearray(size * size * 4)
    fill_gradient(pixels, size, size, rounded=True)
    draw_document_mark(pixels, size, size, 0, 0, size / 1024)
    return encode_png(size, size, pixels)


def tile_png(width: int, height: int) -> bytes:
    pixels = bytearray(width * height * 4)
    fill_gradient(pixels, width, height, rounded=False)
    if min(width, height) < 100:
        size = min(width, height) * 0.78
        draw_compact_waveform(
            pixels,
            width,
            height,
            (width - size) / 2,
            (height - size) / 2,
            size,
        )
    else:
        mark_size = min(width * 0.72, height * 1.5) if width != height else min(width, height)
        draw_document_mark(
            pixels,
            width,
            height,
            (width - mark_size) / 2,
            (height - mark_size) / 2,
            mark_size / 1024,
        )
    return encode_png(width, height, pixels)


def encode_png(width: int, height: int, rgba: bytearray) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(
            ">I", len(data)
        ) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = bytearray()
    row_bytes = width * 4
    for y in range(height):
        raw.append(0)
        raw.extend(rgba[y * row_bytes:(y + 1) * row_bytes])

    return b"\x89PNG\r\n\x1a\n" + chunk(
        b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")


def make_ico(images: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(images))
    directory = bytearray()
    data = bytearray()
    offset = 6 + 16 * len(images)
    for size, image in images:
        directory.extend(
            struct.pack(
                "<BBBBHHII", 0 if size >= 256 else size, 0 if size >= 256 else size,
                0, 0, 1, 32, len(image), offset,
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
    pngs = {size: app_icon_png(size) for size in (16, 32, 48, 64, 128, 256, 512, 1024)}
    PNG_PATH.write_bytes(pngs[1024])
    ICO_PATH.write_bytes(make_ico([(size, pngs[size]) for size in (16, 32, 48, 64, 128, 256)]))
    ICNS_PATH.write_bytes(
        make_icns(
            [
                ("icp4", pngs[16]), ("icp5", pngs[32]), ("icp6", pngs[64]),
                ("ic07", pngs[128]), ("ic08", pngs[256]), ("ic09", pngs[512]),
                ("ic10", pngs[1024]), ("ic11", pngs[32]), ("ic12", pngs[64]),
                ("ic13", pngs[256]), ("ic14", pngs[512]),
            ]
        )
    )

    MSIX_ASSETS.mkdir(exist_ok=True)
    for filename, (width, height) in MSIX_TILE_SIZES.items():
        (MSIX_ASSETS / filename).write_bytes(tile_png(width, height))


if __name__ == "__main__":
    main()

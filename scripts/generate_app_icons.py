"""Derive all app icon assets from the committed master images.

Sources (committed, edit these first):
- assets/app-icon.svg   -> editable source of the full icon
- assets/brand-mark.svg -> editable source of the mark-only artwork
- assets/app-icon.png   -> 1024px render of app-icon.svg (icon master)
- assets/brand-mark.png -> 1024px render of brand-mark.svg, transparent

Outputs:
- assets/app-icon.ico   (Windows)
- assets/app-icon.icns  (macOS)
- assets/msix/*.png     (Microsoft Store tiles and splash screen)

Requires Pillow: pip install -e ".[assets]"

If the SVG sources change, re-render the two master PNGs at 1024x1024 with any
SVG renderer before running this script, e.g.:
  rsvg-convert -w 1024 -h 1024 assets/app-icon.svg -o assets/app-icon.png
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
MSIX_ASSETS = ASSETS / "msix"
ICON_MASTER = ASSETS / "app-icon.png"
MARK_MASTER = ASSETS / "brand-mark.png"
ICO_PATH = ASSETS / "app-icon.ico"
ICNS_PATH = ASSETS / "app-icon.icns"

# Brand gradient, matching assets/app-icon.svg.
GRADIENT_STOPS = (
    (0.00, (0x43, 0x38, 0xCA)),
    (0.55, (0x31, 0x2E, 0x81)),
    (1.00, (0x1E, 0x1B, 0x4B)),
)

MSIX_TILE_SIZES = {
    "StoreLogo.png": (50, 50),
    "Square44x44Logo.png": (44, 44),
    "Square71x71Logo.png": (71, 71),
    "Square150x150Logo.png": (150, 150),
    "Square310x310Logo.png": (310, 310),
    "Wide310x150Logo.png": (310, 150),
    "SplashScreen.png": (620, 300),
}


def gradient_color(t: float) -> tuple[int, int, int]:
    for (t0, c0), (t1, c1) in zip(GRADIENT_STOPS, GRADIENT_STOPS[1:]):
        if t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return tuple(round(a + (b - a) * f) for a, b in zip(c0, c1))
    return GRADIENT_STOPS[-1][1]


def gradient_background(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            t = (x / max(1, width - 1) + y / max(1, height - 1)) / 2
            pixels[x, y] = gradient_color(t)
    return image.convert("RGBA")


def resized_png_bytes(master: Image.Image, size: int) -> bytes:
    buffer = io.BytesIO()
    master.resize((size, size), Image.LANCZOS).save(buffer, "PNG")
    return buffer.getvalue()


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


def tile_png(mark: Image.Image, width: int, height: int) -> bytes:
    tile = gradient_background(width, height)
    bbox = mark.getbbox()
    cropped = mark.crop(bbox)
    scale = min(width * 0.62 / cropped.width, height * 0.62 / cropped.height)
    mark_size = (round(cropped.width * scale), round(cropped.height * scale))
    resized = cropped.resize(mark_size, Image.LANCZOS)
    tile.alpha_composite(
        resized, ((width - mark_size[0]) // 2, (height - mark_size[1]) // 2)
    )
    buffer = io.BytesIO()
    tile.save(buffer, "PNG")
    return buffer.getvalue()


def main() -> None:
    icon = Image.open(ICON_MASTER).convert("RGBA")
    if icon.size != (1024, 1024):
        raise SystemExit(f"{ICON_MASTER} must be 1024x1024, got {icon.size}")
    mark = Image.open(MARK_MASTER).convert("RGBA")

    pngs = {size: resized_png_bytes(icon, size) for size in (16, 32, 48, 64, 128, 256, 512, 1024)}
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
        (MSIX_ASSETS / filename).write_bytes(tile_png(mark, width, height))
    print(f"Wrote {ICO_PATH}, {ICNS_PATH}, and {len(MSIX_TILE_SIZES)} MSIX tiles.")


if __name__ == "__main__":
    main()

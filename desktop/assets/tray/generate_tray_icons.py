"""Generate tray icons for every recorder state (deterministic, no AI).

Run: python3 generate_tray_icons.py  (requires Pillow)

Outputs, per state (idle / recording / paused / transcribing / error):
  <state>.png            16x16 color icon (Windows / Linux)
  <state>@2x.png         32x32 color icon
  <state>Template.png    16x16 black+alpha (macOS template image)
  <state>Template@2x.png 32x32 black+alpha

Shapes differ per state so they stay distinguishable on macOS, where
template images are rendered monochrome.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).parent
SUPER = 128  # draw large, then downscale for antialiasing

COLORS = {
    "idle": (156, 163, 175, 255),  # gray
    "recording": (239, 68, 68, 255),  # red
    "paused": (245, 158, 11, 255),  # amber
    "transcribing": (59, 130, 246, 255),  # blue
    "error": (239, 68, 68, 255),  # red
}
TEMPLATE_COLOR = (0, 0, 0, 255)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGBA", (SUPER, SUPER), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image)


def draw_idle(draw: ImageDraw.ImageDraw, color: tuple) -> None:
    # Hollow ring.
    draw.ellipse((20, 20, 108, 108), outline=color, width=14)


def draw_recording(draw: ImageDraw.ImageDraw, color: tuple) -> None:
    # Filled dot.
    draw.ellipse((24, 24, 104, 104), fill=color)


def draw_paused(draw: ImageDraw.ImageDraw, color: tuple) -> None:
    # Two vertical bars.
    draw.rounded_rectangle((28, 24, 56, 104), radius=10, fill=color)
    draw.rounded_rectangle((72, 24, 100, 104), radius=10, fill=color)


def draw_transcribing(draw: ImageDraw.ImageDraw, color: tuple) -> None:
    # Three equalizer bars of differing heights.
    draw.rounded_rectangle((20, 56, 44, 108), radius=8, fill=color)
    draw.rounded_rectangle((52, 20, 76, 108), radius=8, fill=color)
    draw.rounded_rectangle((84, 40, 108, 108), radius=8, fill=color)


def draw_error(draw: ImageDraw.ImageDraw, color: tuple) -> None:
    # Filled triangle with a punched-out exclamation mark.
    draw.polygon((64, 14, 118, 110, 10, 110), fill=color)
    draw.rounded_rectangle((57, 46, 71, 82), radius=6, fill=(0, 0, 0, 0))
    draw.ellipse((57, 90, 71, 104), fill=(0, 0, 0, 0))


SHAPES = {
    "idle": draw_idle,
    "recording": draw_recording,
    "paused": draw_paused,
    "transcribing": draw_transcribing,
    "error": draw_error,
}


def render(state: str, color: tuple, suffix: str) -> None:
    image, draw = canvas()
    SHAPES[state](draw, color)
    for size, scale_suffix in ((16, ""), (32, "@2x")):
        resized = image.resize((size, size), Image.LANCZOS)
        resized.save(OUT / f"{state}{suffix}{scale_suffix}.png")


def main() -> None:
    for state, color in COLORS.items():
        render(state, color, "")
        render(state, TEMPLATE_COLOR, "Template")
    print(f"Wrote {len(COLORS) * 4} icons to {OUT}")


if __name__ == "__main__":
    main()

"""Render the macOS DMG window background (assets/dmg-background.png and @2x).

The DMG opens as a 660x460 Finder window: the app icon on the left, the
Applications folder on the right, an arrow between them and a short note
about the first launch of an unsigned build. Icon positions must match
desktop/dmg-settings.py.

Run once after changing the text, then commit both PNGs:
    python3 scripts/make_dmg_background.py [path/to/BIZUDPGothic-Bold.ttf path/to/BIZUDPGothic-Regular.ttf]
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 660, 460
APP_X, APPS_X, ICON_Y = 165, 495, 185   # icon centres, same as dmg-settings.py
NOTE_X = 200                             # START_HERE_MAC.txt sits left of the note at (110, 365)
INK, SUB, ACCENT, BG = (26, 26, 26), (110, 110, 110), (5, 87, 255), (248, 248, 248)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def render(scale: int, bold: str, regular: str) -> Image.Image:
    s = scale
    img = Image.new("RGB", (W * s, H * s), BG)
    d = ImageDraw.Draw(img)

    title = "Local Transcriber をインストール"
    lead = "左のアイコンを、右の Applications フォルダへドラッグしてください"
    f_title, f_lead, f_note = font(bold, 22 * s), font(regular, 13 * s), font(regular, 12 * s)
    d.text((W * s / 2, 42 * s), title, font=f_title, fill=INK, anchor="mm")
    d.text((W * s / 2, 74 * s), lead, font=f_lead, fill=SUB, anchor="mm")

    # Arrow between the two icons (icons are 100pt wide, so leave room)
    x0, x1, y = (APP_X + 72) * s, (APPS_X - 72) * s, ICON_Y * s
    d.line([(x0, y), (x1 - 14 * s, y)], fill=ACCENT, width=5 * s)
    d.polygon([(x1, y), (x1 - 20 * s, y - 12 * s), (x1 - 20 * s, y + 12 * s)], fill=ACCENT)

    # First launch note (the build is not notarized)
    d.line([(40 * s, 290 * s), ((W - 40) * s, 290 * s)], fill=(224, 224, 224), width=1 * s)
    notes = [
        "初めて開くときに警告が出て開けなかったら",
        "システム設定 → プライバシーとセキュリティ → 一番下までスクロール",
        "「セキュリティ」の「開く」→「このまま開く」→ Mac のパスワード",
    ]
    for i, line in enumerate(notes):
        d.text((NOTE_X * s, (338 + i * 22) * s), line, font=font(bold, 13 * s) if i == 0 else f_note,
               fill=INK if i == 0 else SUB, anchor="lm")
    return img


def main() -> None:
    bold = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / ".fonts/BIZUDPGothic-Bold.ttf")
    regular = sys.argv[2] if len(sys.argv) > 2 else str(Path.home() / ".fonts/BIZUDPGothic-Regular.ttf")
    out = ROOT / "assets"
    render(1, bold, regular).save(out / "dmg-background.png", optimize=True)
    render(2, bold, regular).save(out / "dmg-background@2x.png", optimize=True)
    print("wrote", out / "dmg-background.png", out / "dmg-background@2x.png")


if __name__ == "__main__":
    main()

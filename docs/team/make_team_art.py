"""Сборка мемной картинки команды и аватара из исходного маскота.

Запуск: python docs/team/make_team_art.py
Требуется Pillow и шрифты DejaVu из комплекта matplotlib.
Кегль подбирается автоматически под ширину, чтобы кириллица не обрезалась.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
RAW = HERE / "mascot_raw.png"
FONT_DIR = Path("/usr/local/lib/python3.11/dist-packages/matplotlib/mpl-data/fonts/ttf")
FONT_REG = FONT_DIR / "DejaVuSans.ttf"
FONT_BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"

ACCENT = (255, 176, 58)
INK = (14, 17, 22)
PAPER = (240, 244, 249)
MUTED = (147, 164, 184)
MAX_W = 0.92  # доля ширины, которую может занимать строка


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def _fit(draw: ImageDraw.ImageDraw, text: str, font_path: Path, start: int, max_width: int):
    """Подбирает максимальный кегль, при котором строка влезает в max_width."""

    size = start
    while size > 12:
        font = _font(font_path, size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
        size -= 2
    return _font(font_path, 12)


def _centered(draw: ImageDraw.ImageDraw, text: str, y: int, font, fill, width: int) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text(((width - (bbox[2] - bbox[0])) // 2, y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def crop_white(img: Image.Image, threshold: int = 245) -> Image.Image:
    """Убирает белые поля вокруг иллюстрации."""

    bg = Image.new("RGB", img.size, (255, 255, 255))
    diff = ImageChops.difference(img, bg).convert("L")
    diff = diff.point(lambda p: 255 if p > 255 - threshold else 0)
    box = diff.getbbox()
    return img.crop(box) if box else img


def build_meme(src: Path = RAW, dst: Path | None = None) -> Path:
    dst = dst or HERE / "team_meme.png"
    art = crop_white(Image.open(src).convert("RGB"))

    width = max(1024, art.size[0])
    scale = width / art.size[0]
    art = art.resize((width, int(art.size[1] * scale)), Image.LANCZOS)

    title = "ЛЕНИВЫЕ В ОРБИТЕ"
    subtitle = "команда КосмоХакатона 2026 · Красноярск × Санкт-Петербург"
    line1 = "Спешить не будем. Но успеем."
    line2 = "Стоп-код в 19:30 по МСК — мы стартуем в 19:29."

    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    max_w = int(width * MAX_W)

    f_title = _fit(probe, title, FONT_BOLD, 150, max_w)
    f_sub = _fit(probe, subtitle, FONT_REG, 44, max_w)
    f_l1 = _fit(probe, line1, FONT_BOLD, 90, max_w)
    f_l2 = _fit(probe, line2, FONT_REG, 60, max_w)

    top_h = int(f_title.size * 2.0 + f_sub.size * 2.2)
    bottom_h = int(f_l1.size * 2.0 + f_l2.size * 2.0)

    canvas = Image.new("RGB", (width, top_h + art.size[1] + bottom_h), INK)
    canvas.paste(art, (0, top_h))
    d = ImageDraw.Draw(canvas)

    y = int(f_title.size * 0.35)
    _centered(d, title, y, f_title, PAPER, width)
    bar_y = y + int(f_title.size * 1.35)
    cx = width // 2
    d.rectangle([cx - int(width * 0.12), bar_y, cx + int(width * 0.12), bar_y + 8], fill=ACCENT)
    _centered(d, subtitle, bar_y + int(f_sub.size * 0.9), f_sub, MUTED, width)

    y2 = top_h + art.size[1] + int(f_l1.size * 0.3)
    _centered(d, line1, y2, f_l1, ACCENT, width)
    _centered(d, line2, y2 + int(f_l1.size * 1.35), f_l2, PAPER, width)

    canvas.save(dst)
    return dst


def build_avatar(src: Path = RAW, dst: Path | None = None, size: int = 512) -> Path:
    """Квадратная аватарка: голова ленивца в шлеме, без текста."""

    dst = dst or HERE / "team_avatar.png"
    art = crop_white(Image.open(src).convert("RGB"))
    w, h = art.size
    box = (int(w * 0.40), int(h * 0.16), int(w * 0.98), int(h * 0.74))
    crop = art.crop(box)
    side = min(crop.size)
    cx, cy = crop.size[0] // 2, crop.size[1] // 2
    crop = crop.crop((cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2))
    crop = crop.resize((size, size), Image.LANCZOS)

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    out = Image.new("RGB", (size, size), INK)
    out.paste(crop, (0, 0), mask)
    d = ImageDraw.Draw(out)
    d.ellipse([3, 3, size - 4, size - 4], outline=ACCENT, width=12)
    out.save(dst)
    return dst


if __name__ == "__main__":
    print("мем:", build_meme())
    print("аватар:", build_avatar())

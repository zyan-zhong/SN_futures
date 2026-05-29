from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    icon_path = assets / "sn_insight_terminal.ico"
    png_path = assets / "sn_insight_terminal.png"

    size = 256
    image = Image.new("RGBA", (size, size), (10, 32, 54, 255))
    draw = ImageDraw.Draw(image)

    for y in range(size):
        blend = int(255 * y / size)
        draw.line([(0, y), (size, y)], fill=(14 + blend // 18, 57 + blend // 9, 87 + blend // 7, 255))

    draw.rounded_rectangle((22, 22, 234, 234), radius=36, outline=(240, 200, 120, 255), width=6)
    draw.rounded_rectangle((42, 42, 214, 214), radius=30, outline=(200, 230, 240, 120), width=2)

    try:
        font = ImageFont.truetype("arialbd.ttf", 108)
        small = ImageFont.truetype("arial.ttf", 24)
    except OSError:
        font = ImageFont.load_default()
        small = ImageFont.load_default()

    draw.text((56, 66), "SN", fill=(247, 225, 157, 255), font=font)
    draw.text((64, 176), "INSIGHT", fill=(220, 240, 248, 255), font=small)

    image.save(png_path)
    image.save(icon_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(icon_path)


if __name__ == "__main__":
    main()

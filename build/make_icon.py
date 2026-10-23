#!/usr/bin/env python3
"""Draw the installer icon without shipping anyone else's artwork."""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 512
SCALE = 4
OUT = Path(__file__).resolve().parent / "icon.png"


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def main() -> None:
    size = SIZE * SCALE
    image = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(image)
    top, bottom = (17, 94, 89), (9, 62, 58)
    for y in range(size):
        mix = y / (size - 1)
        draw.line(
            [(0, y), (size, y)],
            fill=tuple(round(top[i] * (1 - mix) + bottom[i] * mix) for i in range(3)),
        )

    center = size // 2
    ring = size * 0.29
    width = int(size * 0.055)
    draw.ellipse(
        (center - ring, center - ring, center + ring, center + ring),
        outline=(230, 255, 250),
        width=width,
    )

    arrow_w = int(size * 0.13)
    arrow_top = int(center - size * 0.13)
    arrow_bottom = int(center + size * 0.12)
    draw.rounded_rectangle(
        (center - arrow_w // 2, arrow_top, center + arrow_w // 2, arrow_bottom),
        radius=arrow_w // 3,
        fill=(230, 255, 250),
    )
    draw.polygon(
        [
            (center - int(size * 0.15), arrow_bottom - int(size * 0.02)),
            (center + int(size * 0.15), arrow_bottom - int(size * 0.02)),
            (center, arrow_bottom + int(size * 0.13)),
        ],
        fill=(230, 255, 250),
    )
    draw.ellipse(
        (
            center + int(size * 0.19),
            center - int(size * 0.24),
            center + int(size * 0.27),
            center - int(size * 0.16),
        ),
        fill=(255, 178, 92),
    )

    image.putalpha(rounded_mask(size, int(size * 0.21)))
    image = image.resize((SIZE, SIZE), Image.LANCZOS)
    image.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()

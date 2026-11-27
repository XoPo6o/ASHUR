"""Pixel-native controls for the Babylon Inventory UI kit."""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw

from .palette import Palette


def _rgba(palette: Palette, token: str) -> tuple[int, int, int, int]:
    return (*palette.rgb(token), 255)


def create_button(
    width: int,
    height: int,
    palette: Palette,
    *,
    variant: str = "secondary",
    pressed: bool = False,
) -> Image.Image:
    """Render a crisp button state on a logical pixel grid."""
    if width < 20 or height < 12:
        raise ValueError("Button dimensions must be at least 20x12 pixels")
    if variant not in {"primary", "secondary", "quiet"}:
        raise ValueError("variant must be primary, secondary or quiet")

    image = Image.new("RGBA", (width, height), _rgba(palette, "surface_deep"))
    draw = ImageDraw.Draw(image)
    if variant == "primary":
        fill, edge, highlight = "gold", "gold_light", "gold_light"
        shadow = "border_gold"
    elif variant == "secondary":
        fill, edge, highlight = "surface", "border_gold", "gold"
        shadow = "surface_deep"
    else:
        fill, edge, highlight = "surface_deep", "border", "muted"
        shadow = "surface"
    if pressed:
        fill, shadow = shadow, fill

    draw.rectangle((1, 1, width - 2, height - 2), fill=_rgba(palette, fill),
                   outline=_rgba(palette, edge), width=1)
    draw.line((3, 2, width - 4, 2), fill=_rgba(palette, highlight), width=1)
    draw.line((2, 3, 2, height - 4), fill=_rgba(palette, highlight), width=1)
    draw.line((3, height - 3, width - 4, height - 3),
              fill=_rgba(palette, shadow), width=1)
    draw.line((width - 3, 3, width - 3, height - 4),
              fill=_rgba(palette, shadow), width=1)
    # Small stepped end caps, deliberately restrained.
    draw.rectangle((4, 0, 6, 1), fill=_rgba(palette, edge))
    draw.rectangle((width - 7, height - 2, width - 5, height - 1),
                   fill=_rgba(palette, edge))
    return image


def create_separator(width: int, palette: Palette, *, accent: str = "gold") -> Image.Image:
    if width < 8:
        raise ValueError("Separator width must be at least 8 pixels")
    if accent not in {"gold", "teal", "muted"}:
        raise ValueError("accent must be gold, teal or muted")
    image = Image.new("RGBA", (width, 5), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.line((2, 2, width - 3, 2), fill=_rgba(palette, "border"), width=1)
    draw.rectangle((0, 1, 3, 3), fill=_rgba(palette, accent))
    draw.rectangle((width - 4, 1, width - 1, 3), fill=_rgba(palette, accent))
    return image


def export_control_set(output_dir: str | Path, palette: Palette) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    preview = Image.new("RGBA", (320, 112), _rgba(palette, "void"))
    for i, variant in enumerate(("primary", "secondary", "quiet")):
        normal = create_button(88, 24, palette, variant=variant)
        pressed = create_button(88, 24, palette, variant=variant, pressed=True)
        normal.save(output / f"button-{variant}.png", optimize=True)
        paths[variant] = output / f"button-{variant}.png"
        preview.alpha_composite(normal, (8 + i * 104, 12))
        preview.alpha_composite(pressed, (8 + i * 104, 48))
    separator = create_separator(296, palette)
    separator.save(output / "separator-gold.png", optimize=True)
    preview.alpha_composite(separator, (12, 88))
    paths["separator"] = output / "separator-gold.png"
    preview_path = output / "babylon-controls-preview.png"
    preview.save(preview_path, optimize=True)
    paths["preview"] = preview_path
    return paths

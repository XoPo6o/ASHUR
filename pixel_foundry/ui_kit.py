"""Deterministic pixel UI primitives for the Babylon Inventory visual system."""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw

from .palette import Palette


def _rgba(palette: Palette, token: str) -> tuple[int, int, int, int]:
    return (*palette.rgb(token), 255)


def create_panel_frame(
    width: int,
    height: int,
    palette: Palette,
    *,
    variant: str = "standard",
    border: int = 1,
) -> Image.Image:
    """Create a crisp 9-slice-ready Babylon Inventory panel.

    Frames use a dark steel surface, restrained antique-gold keylines,
    small stepped corner caps and a compact header rule. No smoothing,
    blur, gradients or dithering are applied.
    """
    if width < 24 or height < 20:
        raise ValueError("Panel dimensions must be at least 24x20 logical pixels")
    if border not in (1, 2):
        raise ValueError("border must be 1 or 2 logical pixels")
    if variant not in {"standard", "featured", "inset"}:
        raise ValueError("variant must be standard, featured or inset")

    fill = "surface_deep" if variant == "inset" else "surface"
    edge = {"standard": "border_gold", "featured": "gold", "inset": "border"}[variant]
    accent = {"standard": "gold", "featured": "gold_light", "inset": "teal"}[variant]
    inner = "surface_raised" if variant != "inset" else "surface"
    image = Image.new("RGBA", (width, height), _rgba(palette, fill))
    draw = ImageDraw.Draw(image)

    # Outer frame and inset keyline.
    draw.rectangle((0, 0, width - 1, height - 1), outline=_rgba(palette, edge), width=border)
    draw.rectangle((2, 2, width - 3, height - 3), outline=_rgba(palette, inner), width=1)

    # Stepped corner caps give the frame a deliberate pixel-art signature.
    for x in (3, width - 7):
        draw.rectangle((x, 1, x + 3, 2), fill=_rgba(palette, accent))
        draw.rectangle((x, height - 3, x + 3, height - 2), fill=_rgba(palette, accent))
    draw.point((1, 4), fill=_rgba(palette, accent))
    draw.point((width - 2, 4), fill=_rgba(palette, accent))

    # Compact header separator and tiny end stops.
    if variant != "inset":
        rule_y = 11
        rule_color = "border_gold" if variant == "standard" else "gold"
        draw.line((4, rule_y, width - 5, rule_y), fill=_rgba(palette, rule_color), width=1)
        draw.rectangle((4, rule_y - 1, 6, rule_y + 1), fill=_rgba(palette, accent))
        draw.rectangle((width - 7, rule_y - 1, width - 5, rule_y + 1),
                       fill=_rgba(palette, accent))

    return image


def export_panel_set(output_dir: str | Path, palette: Palette) -> dict[str, Path]:
    """Export standard, featured and inset panels plus a comparison strip."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths = {}
    for variant in ("standard", "featured", "inset"):
        path = output / f"panel-{variant}.png"
        create_panel_frame(96, 64, palette, variant=variant).save(path, optimize=True)
        paths[variant] = path

    preview = Image.new("RGBA", (3 * 104, 80), _rgba(palette, "void"))
    for index, variant in enumerate(("standard", "featured", "inset")):
        panel = create_panel_frame(96, 64, palette, variant=variant)
        preview.alpha_composite(panel, (index * 104 + 4, 8))
    preview_path = output / "babylon-ui-kit-preview.png"
    preview.save(preview_path, optimize=True)
    paths["preview"] = preview_path
    return paths

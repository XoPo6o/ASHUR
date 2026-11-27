"""Deterministic pixel UI primitives for the Babylon Inventory visual system."""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw

from .palette import Palette


def _rgb(palette: Palette, token: str) -> tuple[int, int, int, int]:
    return (*palette.rgb(token), 255)


def create_panel_frame(
    width: int,
    height: int,
    palette: Palette,
    *,
    variant: str = "standard",
    border: int = 2,
) -> Image.Image:
    """Create a crisp 9-slice-ready panel with restrained gold/steel detailing.

    The outer border and corner marks are authored on the logical pixel grid.
    No antialiasing, blur, gradients or dithering are used.
    """
    if width < 12 or height < 12:
        raise ValueError("Panel dimensions must be at least 12x12 logical pixels")
    if border not in (1, 2, 3):
        raise ValueError("border must be 1, 2 or 3 logical pixels")
    if variant not in {"standard", "featured", "inset"}:
        raise ValueError("variant must be standard, featured or inset")

    fill = "surface" if variant != "inset" else "surface_deep"
    edge = "border_gold" if variant == "featured" else "border"
    accent = "gold" if variant == "featured" else "border_gold"
    image = Image.new("RGBA", (width, height), _rgb(palette, fill))
    draw = ImageDraw.Draw(image)

    # Outer structural frame and inner keyline.
    draw.rectangle((0, 0, width - 1, height - 1), outline=_rgb(palette, edge), width=border)
    if width > 2 * border + 2 and height > 2 * border + 2:
        draw.rectangle(
            (border, border, width - border - 1, height - border - 1),
            outline=_rgb(palette, "surface_raised"),
            width=1,
        )

    # Small corner caps: restrained gold markers, not thick ornamental frames.
    cap = max(2, border + 1)
    for x in (1, width - cap - 1):
        draw.point((x, 1), fill=_rgb(palette, accent))
        draw.point((x + cap - 1, 1), fill=_rgb(palette, accent))
        draw.point((x, height - 2), fill=_rgb(palette, accent))
        draw.point((x + cap - 1, height - 2), fill=_rgb(palette, accent))

    # Header rule, intentionally subtle; inset panels omit it.
    if variant != "inset":
        rule_y = min(height - 4, border + 5)
        draw.line((border + 2, rule_y, width - border - 3, rule_y),
                  fill=_rgb(palette, "border_gold" if variant == "featured" else "border"), width=1)

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

    preview = Image.new("RGBA", (3 * 104, 80), _rgb(palette, "void"))
    for index, variant in enumerate(("standard", "featured", "inset")):
        panel = create_panel_frame(96, 64, palette, variant=variant)
        preview.alpha_composite(panel, (index * 104 + 4, 8))
    preview_path = output / "babylon-ui-kit-preview.png"
    preview.save(preview_path, optimize=True)
    paths["preview"] = preview_path
    return paths

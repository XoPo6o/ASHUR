"""Raster data widgets for the Babylon Inventory dashboard kit."""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw

from .palette import Palette
from .ui_kit import create_panel_frame


def _rgba(palette: Palette, token: str) -> tuple[int, int, int, int]:
    return (*palette.rgb(token), 255)


def draw_sparkline(
    size: tuple[int, int],
    values: list[float],
    palette: Palette,
    *,
    color: str = "gold",
    grid: bool = True,
) -> Image.Image:
    """Draw a crisp stepped sparkline on a transparent canvas."""
    width, height = size
    if width < 16 or height < 12:
        raise ValueError("Sparkline canvas must be at least 16x12 pixels")
    if len(values) < 2 or any(not isinstance(v, (int, float)) for v in values):
        raise ValueError("Sparkline requires at least two numeric values")
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    pad_x, pad_y = 3, 3
    if grid:
        for y in (height // 3, (height * 2) // 3):
            draw.line((pad_x, y, width - pad_x - 1, y),
                      fill=_rgba(palette, "surface_raised"), width=1)
    low, high = min(values), max(values)
    span = high - low or 1
    points = []
    for index, value in enumerate(values):
        x = pad_x + round(index * (width - 2 * pad_x - 1) / (len(values) - 1))
        y = height - pad_y - 1 - round((value - low) * (height - 2 * pad_y - 2) / span)
        points.append((x, y))
    # Horizontal-then-vertical segments create an intentional pixel stair-step.
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        draw.line((x1, y1, x2, y1), fill=_rgba(palette, color), width=2)
        draw.line((x2, y1, x2, y2), fill=_rgba(palette, color), width=2)
    for x, y in points:
        draw.rectangle((x, y, x + 1, y + 1), fill=_rgba(palette, color))
    return image


def draw_kpi_tile(
    width: int,
    height: int,
    palette: Palette,
    *,
    trend: str = "positive",
    values: list[float] | None = None,
) -> Image.Image:
    """Build a compact metric tile with a pixel sparkline and status marker."""
    if trend not in {"positive", "negative", "neutral"}:
        raise ValueError("trend must be positive, negative or neutral")
    panel = create_panel_frame(width, height, palette, variant="standard")
    draw = ImageDraw.Draw(panel)
    marker = {"positive": "teal", "negative": "gold", "neutral": "muted"}[trend]
    draw.rectangle((width - 12, 5, width - 7, 10), fill=_rgba(palette, marker))
    if values is not None:
        spark = draw_sparkline((width - 16, max(16, height - 24)), values, palette,
                               color="teal" if trend == "positive" else "gold" if trend == "negative" else "muted")
        panel.alpha_composite(spark, (8, 16))
    return panel


def export_dashboard_components(output_dir: str | Path, palette: Palette) -> dict[str, Path]:
    """Export a small raster component set and a composed dashboard study."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    series = [4, 5, 4.5, 6, 5.7, 7, 6.4, 8, 7.5, 9, 8.5, 10]
    for name, trend in (("positive", "positive"), ("negative", "negative"), ("neutral", "neutral")):
        tile = draw_kpi_tile(112, 64, palette, trend=trend, values=series if trend != "neutral" else series[::-1])
        path = output / f"kpi-{name}.png"
        tile.save(path, optimize=True)
        paths[name] = path

    chart = create_panel_frame(176, 88, palette, variant="featured")
    spark = draw_sparkline((156, 56), series, palette, color="gold")
    chart.alpha_composite(spark, (10, 24))
    chart_path = output / "equity-sparkline.png"
    chart.save(chart_path, optimize=True)
    paths["chart"] = chart_path

    preview = Image.new("RGBA", (320, 184), _rgba(palette, "void"))
    preview.alpha_composite(chart, (8, 8))
    for index, trend in enumerate(("positive", "negative", "neutral")):
        tile = draw_kpi_tile(96, 64, palette, trend=trend, values=series)
        preview.alpha_composite(tile, (8 + index * 104, 112))
    preview_path = output / "babylon-data-widgets-preview.png"
    preview.save(preview_path, optimize=True)
    paths["preview"] = preview_path
    return paths

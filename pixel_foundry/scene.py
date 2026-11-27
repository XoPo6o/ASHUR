"""Scene-spec loader and deterministic scene renderer."""
from __future__ import annotations
import json
from pathlib import Path
from .palette import Palette
from .renderer import PixelRenderer
from .qa import inspect_image
from .generators import expand_generator

_GENERATOR_GEOMETRY = {
    "shaft_w", "capital_h", "base_h", "arch_h", "thickness",
    "brick_w", "brick_h", "block_w", "block_h", "trunk_w", "tier_h", "inset",
}
_PRIMITIVE_GEOMETRY = {"x", "y", "w", "h", "width", "stroke", "radius", "step"}


def load_scene(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    required = ("canvas", "palette", "layers")
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"Scene is missing required keys: {', '.join(missing)}")
    return data


def _scale_operation(op: dict, factor: int) -> dict:
    """Scale authored geometry before rasterization, never by interpolating pixels."""
    scaled = dict(op)
    generator = op.get("type") in {
        "brick_wall", "stone_floor", "foliage", "stepped_ziggurat",
        "column", "archway", "market_stall", "palm_tree", "cloud_bank",
        "boulder", "water_surface", "traveler_sprite", "lamassu_sprite",
    }
    keys = _GENERATOR_GEOMETRY if generator else _PRIMITIVE_GEOMETRY
    for key in keys:
        if isinstance(scaled.get(key), (int, float)):
            scaled[key] = int(scaled[key] * factor)
    if isinstance(scaled.get("points"), list):
        scaled["points"] = [
            [int(round(value * factor)) for value in point]
            for point in scaled["points"]
        ]
    return scaled


def render_scene(scene: dict, output: str | Path | None = None, scale: int = 1) -> dict:
    canvas = scene["canvas"]
    detail_scale = int(scene.get("metadata", {}).get(
        "pixel_scale", scene.get("pixel_scale", 1)
    ))
    if detail_scale < 1:
        raise ValueError("pixel_scale must be a positive integer")
    width, height = int(canvas["width"]), int(canvas["height"])
    palette = Palette.from_data(scene["palette"])
    renderer = PixelRenderer(width * detail_scale, height * detail_scale, palette,
                             scene.get("background", "transparent"))
    expanded_layers = []
    for layer in scene["layers"]:
        expanded = dict(layer)
        operations = (_scale_operation(op, detail_scale) for op in layer.get("ops", []))
        expanded["ops"] = [
            primitive
            for op in operations
            for primitive in expand_generator(op)
        ]
        expanded_layers.append(expanded)
    image = renderer.render_layers(expanded_layers)
    report = inspect_image(image, palette)
    report["authored_canvas"] = {"width": width, "height": height}
    report["pixel_scale"] = detail_scale
    if output:
        renderer.export(output, scale=scale, indexed=scene.get("export", {}).get("indexed", True))
    return {"image": image, "qa": report, "palette": palette}

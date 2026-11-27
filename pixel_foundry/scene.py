"""Scene-spec loader and deterministic scene renderer."""
from __future__ import annotations
import json
from pathlib import Path
from .palette import Palette
from .renderer import PixelRenderer
from .qa import inspect_image

def load_scene(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    required = ("canvas", "palette", "layers")
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"Scene is missing required keys: {', '.join(missing)}")
    return data

def render_scene(scene: dict, output: str | Path | None = None, scale: int = 1) -> dict:
    canvas = scene["canvas"]
    palette = Palette.from_data(scene["palette"])
    renderer = PixelRenderer(int(canvas["width"]), int(canvas["height"]), palette,
                             scene.get("background", "transparent"))
    image = renderer.render_layers(scene["layers"])
    report = inspect_image(image, palette)
    if output:
        renderer.export(output, scale=scale, indexed=scene.get("export", {}).get("indexed", True))
    return {"image": image, "qa": report, "palette": palette}

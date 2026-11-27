"""Render controlled, visibly distinct Babylon palette directions and measure them."""
from __future__ import annotations

from copy import deepcopy
from itertools import combinations
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat

from .art_director import build_scene_spec
from .scene import render_scene


# A is the current approved reference direction. B and C are deliberately
# different art directions, not tiny hue nudges of A.
PALETTE_VARIANTS = {
    "A-reference": {
        "night": "#0B141D", "far_blue": "#101E2A", "blue_stone": "#142633",
        "sand_shadow": "#9C7746", "sand": "#D9AD62", "sand_light": "#F0D8A5",
        "gold_shadow": "#9C7746", "gold": "#D9AD62", "moon": "#E9E5D6",
        "teal": "#65CFC0", "dark": "#050A0E", "leaf_shadow": "#2D6B70",
        "leaf": "#83D59B", "leaf_light": "#E9E5D6", "water_shadow": "#2D6B70",
        "water": "#65CFC0", "water_light": "#9AB0B6", "stone": "#365564",
        "stone_dark": "#050A0E",
    },
    "B-desert-dusk": {
        "night": "#201710", "far_blue": "#34251C", "blue_stone": "#49372A",
        "sand_shadow": "#75452B", "sand": "#D28B48", "sand_light": "#F4C77A",
        "gold_shadow": "#75452B", "gold": "#E6A34F", "moon": "#F8DDA8",
        "teal": "#8F9B70", "dark": "#100C09", "leaf_shadow": "#53613A",
        "leaf": "#A5A65A", "leaf_light": "#E6D69A", "water_shadow": "#536B62",
        "water": "#8FAD91", "water_light": "#C6D0A4", "stone": "#806044",
        "stone_dark": "#100C09",
    },
    "C-moonlit-cyan": {
        "night": "#071A27", "far_blue": "#0B2B3A", "blue_stone": "#16485A",
        "sand_shadow": "#47606A", "sand": "#83A6A8", "sand_light": "#D5E6D8",
        "gold_shadow": "#47606A", "gold": "#A9C6B8", "moon": "#EAF4E5",
        "teal": "#53C9B5", "dark": "#030D15", "leaf_shadow": "#285D5B",
        "leaf": "#5B9B78", "leaf_light": "#B6D8B0", "water_shadow": "#285D72",
        "water": "#4D9DAA", "water_light": "#B2D7D8", "stone": "#427080",
        "stone_dark": "#030D15",
    },
}


def compare_images(left: Image.Image, right: Image.Image) -> dict:
    """Return objective RGB-difference diagnostics for two same-size renders."""
    a, b = left.convert("RGB"), right.convert("RGB")
    if a.size != b.size:
        raise ValueError("Palette candidates must have identical dimensions")
    diff = ImageChops.difference(a, b)
    changed = sum(1 for pixel in diff.getdata() if max(pixel) >= 8)
    total = a.width * a.height
    mean_delta = sum(ImageStat.Stat(diff).mean) / 3
    return {
        "changed_pixel_ratio": round(changed / max(1, total), 4),
        "mean_channel_delta": round(mean_delta, 2),
        "dimensions": list(a.size),
    }


def render_palette_study(art_bible: dict, output_dir: str | Path, scale: int = 4) -> dict:
    if scale < 1:
        raise ValueError("scale must be a positive integer")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    base = build_scene_spec(art_bible)
    width = int(base["canvas"]["width"]) * scale
    height = int(base["canvas"]["height"]) * scale
    gap, label_height, margin = 12, 22, 12
    board = Image.new(
        "RGB", (margin * 2 + width * 3 + gap * 2, margin * 2 + height + label_height),
        "#050A0E",
    )
    draw = ImageDraw.Draw(board)
    paths: dict[str, Path] = {}
    rendered_by_name: dict[str, Image.Image] = {}

    for index, (name, colors) in enumerate(PALETTE_VARIANTS.items()):
        scene = deepcopy(base)
        scene["palette"] = {
            "colors": colors,
            "ramps": deepcopy(art_bible["palette"].get("ramps", {})),
        }
        for key, values in scene["palette"]["ramps"].items():
            scene["palette"]["ramps"][key] = [value for value in values if value in colors]
        rendered = render_scene(scene)["image"].convert("RGB")
        if scale > 1:
            rendered = rendered.resize((width, height), Image.Resampling.NEAREST)
        rendered_by_name[name] = rendered
        x, y = margin + index * (width + gap), margin
        board.paste(rendered, (x, y))
        draw.text((x, y + height + 4), name, fill="#E9E5D6")
        path = output / f"babylon-palette-{index + 1}.png"
        rendered.save(path, optimize=True)
        paths[name] = path

    comparisons = {}
    for left, right in combinations(PALETTE_VARIANTS, 2):
        comparisons[f"{left}__vs__{right}"] = compare_images(
            rendered_by_name[left], rendered_by_name[right]
        )
    metrics_path = output / "babylon-palette-metrics.json"
    import json
    metrics_path.write_text(
        json.dumps({"comparisons": comparisons}, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["metrics"] = metrics_path

    board_path = output / "babylon-palette-comparison.png"
    board.save(board_path, optimize=True)
    paths["comparison"] = board_path
    return paths

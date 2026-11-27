"""Static pixel-art QA checks; reports diagnostics, never silently 'fixes' artwork."""
from __future__ import annotations
from collections import Counter
from PIL import Image
from .palette import Palette, validate_palette_size

def inspect_image(image: Image.Image, palette: Palette | None = None) -> dict:
    rgba = image.convert("RGBA")
    pixels = list(rgba.getdata())
    visible = [p[:3] for p in pixels if p[3] > 0]
    counts = Counter(visible)
    warnings = []
    if palette:
        warnings.extend(validate_palette_size(palette))
        allowed = {palette.rgb(k) for k in palette.colors}
        off_palette = sum(1 for p in visible if p not in allowed)
        if off_palette:
            warnings.append(f"{off_palette} visible pixels are outside the declared palette")
    # Count isolated visible pixels using 4-neighbour connectivity.
    px = rgba.load()
    isolated = 0
    for y in range(rgba.height):
        for x in range(rgba.width):
            if px[x, y][3] == 0:
                continue
            neighbors = ((x-1,y),(x+1,y),(x,y-1),(x,y+1))
            if not any(0 <= nx < rgba.width and 0 <= ny < rgba.height and px[nx,ny][3] > 0 for nx,ny in neighbors):
                isolated += 1
    if isolated:
        warnings.append(f"{isolated} isolated visible pixels; inspect for accidental noise (may be intentional stars/highlights)")
    return {
        "width": rgba.width, "height": rgba.height,
        "visible_pixels": len(visible),
        "unique_colors": len(counts),
        "transparent_pixels": len(pixels)-len(visible),
        "isolated_pixels": isolated,
        "warnings": warnings,
        "palette_usage": {f"#{r:02X}{g:02X}{b:02X}": n for (r,g,b),n in counts.most_common()},
    }

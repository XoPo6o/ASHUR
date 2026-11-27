"""Palette utilities: named ramps, nearest-color mapping and indexed PNG export."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from PIL import Image

@dataclass(frozen=True)
class Palette:
    colors: dict[str, str]

    @classmethod
    def from_data(cls, data: dict) -> "Palette":
        raw = data.get("colors", data)
        if not isinstance(raw, dict) or not raw:
            raise ValueError("Palette must contain a non-empty 'colors' mapping")
        for name, value in raw.items():
            if not isinstance(value, str) or len(value) not in (4, 7) or not value.startswith("#"):
                raise ValueError(f"Invalid color for {name}: {value!r}")
        return cls(dict(raw))

    def hex(self, name_or_hex: str) -> str:
        value = self.colors.get(name_or_hex, name_or_hex)
        if not value.startswith("#"):
            raise KeyError(f"Unknown palette color: {name_or_hex}")
        if len(value) == 4:
            value = "#" + "".join(ch * 2 for ch in value[1:])
        return value.upper()

    def rgb(self, name_or_hex: str) -> tuple[int, int, int]:
        value = self.hex(name_or_hex)
        return tuple(int(value[i:i+2], 16) for i in (1, 3, 5))

    def ordered_hex(self) -> list[str]:
        return list(dict.fromkeys(self.hex(v) for v in self.colors.values()))

    def nearest(self, rgb: tuple[int, int, int]) -> str:
        def dist(c):
            return sum((a-b) ** 2 for a, b in zip(rgb, self.rgb(c)))
        return min(self.colors, key=dist)

    def apply_indexed(self, image: Image.Image) -> Image.Image:
        """Quantize to this exact palette and return an indexed PNG-ready image."""
        rgb = image.convert("RGB")
        swatches = self.ordered_hex()
        strip = Image.new("P", (1, 1))
        flat = []
        for color in swatches:
            flat.extend(self.rgb(color))
        flat.extend([0, 0, 0] * (256-len(swatches)))
        strip.putpalette(flat[:768])
        # Pillow's palette quantizer is deterministic; dither is disabled deliberately.
        return rgb.quantize(palette=strip, dither=Image.Dither.NONE)

def validate_palette_size(palette: Palette, maximum: int = 32) -> list[str]:
    colors = palette.ordered_hex()
    if len(colors) > maximum:
        return [f"Palette has {len(colors)} unique colors (recommended maximum: {maximum})"]
    return []

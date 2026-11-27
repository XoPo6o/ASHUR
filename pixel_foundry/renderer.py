"""Low-resolution raster renderer. All geometry is authored on the logical pixel grid."""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from .palette import Palette

class PixelRenderer:
    def __init__(self, width: int, height: int, palette: Palette, background: str = "#00000000"):
        if width < 1 or height < 1:
            raise ValueError("Canvas dimensions must be positive")
        self.width, self.height, self.palette = width, height, palette
        self.image = Image.new("RGBA", (width, height), self._rgba(background))
        self.draw = ImageDraw.Draw(self.image)

    def _rgba(self, color):
        if color in (None, "transparent", "#00000000"):
            return (0, 0, 0, 0)
        return (*self.palette.rgb(color), 255)

    def _xy(self, points):
        return [(int(round(x)), int(round(y))) for x, y in points]

    def render_op(self, op: dict):
        kind = op.get("type")
        color = self._rgba(op.get("color", "#FFFFFF"))
        x, y = int(op.get("x", 0)), int(op.get("y", 0))
        w, h = int(op.get("w", 1)), int(op.get("h", 1))
        if kind == "rect":
            self.draw.rectangle((x, y, x+w-1, y+h-1), fill=color,
                                outline=self._rgba(op["outline"]) if op.get("outline") else None,
                                width=max(1, int(op.get("stroke", 1))))
        elif kind == "ellipse":
            self.draw.ellipse((x, y, x+w-1, y+h-1), fill=color,
                              outline=self._rgba(op["outline"]) if op.get("outline") else None,
                              width=max(1, int(op.get("stroke", 1))))
        elif kind == "line":
            pts = self._xy(op.get("points", []))
            if len(pts) >= 2:
                self.draw.line(pts, fill=color, width=max(1, int(op.get("width", 1))))
                if op.get("joint") == "curve":
                    r = max(0, int(op.get("width", 1))//2)
                    for px, py in pts:
                        self.draw.ellipse((px-r, py-r, px+r, py+r), fill=color)
        elif kind == "polygon":
            pts = self._xy(op.get("points", []))
            if len(pts) >= 3:
                self.draw.polygon(pts, fill=color)
                if op.get("outline"):
                    self.draw.line(pts+[pts[0]], fill=self._rgba(op["outline"]), width=1)
        elif kind == "ramp_rect":
            # Hard-edged palette bands: every transition stays on the logical pixel grid.
            ramp = self.palette.ramp(op["ramp"])
            axis = op.get("axis", "vertical")
            for index in range(max(1, w if axis == "horizontal" else h)):
                band = min(len(ramp)-1, index*len(ramp)//max(1, w if axis == "horizontal" else h))
                band_color = self._rgba(ramp[band])
                if axis == "horizontal":
                    self.draw.line((x+index,y,x+index,y+h-1), fill=band_color)
                else:
                    self.draw.line((x,y+index,x+w-1,y+index), fill=band_color)
        elif kind == "outline":
            # Expand the existing alpha mask and place a solid outline underneath it.
            from PIL import ImageChops, ImageFilter
            radius = max(1, int(op.get("radius", 1)))
            alpha = self.image.getchannel("A")
            size = radius*2+1
            expanded = alpha.filter(ImageFilter.MaxFilter(size))
            outline_alpha = ImageChops.subtract(expanded, alpha)
            layer = Image.new("RGBA", self.image.size, self._rgba(op.get("color", "#FFFFFF")))
            layer.putalpha(outline_alpha)
            self.image = Image.alpha_composite(layer, self.image)
            self.draw = ImageDraw.Draw(self.image)
        elif kind == "pixel":
            self.draw.point((x, y), fill=color)
        elif kind == "text":
            # Default PIL font is a bitmap font; no antialiasing is introduced.
            font = ImageFont.load_default()
            self.draw.text((x, y), str(op.get("text", "")), fill=color, font=font)
        elif kind == "dither":
            pattern = op.get("pattern", "checker")
            step = max(1, int(op.get("step", 2)))
            for py in range(y, y+h):
                for px in range(x, x+w):
                    use = ((px-x)+(py-y)) % step == 0 if pattern == "diagonal" else ((px-x)+(py-y)) % 2 == 0
                    if use:
                        self.draw.point((px, py), fill=color)
        else:
            raise ValueError(f"Unsupported primitive: {kind!r}")

    def render_layers(self, layers: list[dict]):
        for layer in layers:
            if layer.get("visible", True):
                for op in layer.get("ops", []):
                    self.render_op(op)
        return self.image

    def export(self, path: str | Path, scale: int = 1, indexed: bool = True):
        result = self.image
        if scale > 1:
            result = result.resize((self.width*scale, self.height*scale), Image.Resampling.NEAREST)
        if indexed:
            # Keep transparency via RGBA if present; palette quantization is optional
            # because alpha-preserving indexed PNG support varies between consumers.
            alpha = result.getchannel("A")
            quantized = self.palette.apply_indexed(result)
            # Pillow cannot save palette+alpha (mode PA) as PNG; promote to RGBA.
            quantized = quantized.convert("RGBA")
            quantized.putalpha(alpha)
            result = quantized
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        result.save(path, optimize=True)
        return Path(path)

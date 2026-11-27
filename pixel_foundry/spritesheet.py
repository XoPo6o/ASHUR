"""Animation strip export and timing metadata."""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image

def export_strip(frames: list[Image.Image], output: str | Path, frame_ms: int = 120,
                 loop: bool = True, pivot: tuple[int,int] | None = None) -> dict:
    if not frames:
        raise ValueError("At least one frame is required")
    if frame_ms < 1:
        raise ValueError("frame_ms must be positive")
    width=max(f.width for f in frames); height=max(f.height for f in frames)
    strip=Image.new("RGBA",(width*len(frames),height),(0,0,0,0))
    for i,frame in enumerate(frames):
        strip.alpha_composite(frame.convert("RGBA"),(i*width,0))
    path=Path(output); path.parent.mkdir(parents=True,exist_ok=True); strip.save(path,optimize=True)
    meta={"image":path.name,"frame_width":width,"frame_height":height,"frame_count":len(frames),
          "frame_ms":frame_ms,"loop":bool(loop),"pivot":{"x":(pivot or (width//2,height))[0],"y":(pivot or (width//2,height))[1]}}
    path.with_suffix(".json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    return meta

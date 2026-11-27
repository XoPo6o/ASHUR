"""Sprite atlas packing with JSON metadata for game engines and web apps."""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image

def pack_atlas(sprites: dict[str, Image.Image], output: str | Path, columns: int = 4,
               spacing: int = 1, background=(0,0,0,0)) -> dict:
    if not sprites:
        raise ValueError("At least one sprite is required")
    if columns < 1 or spacing < 0:
        raise ValueError("columns must be positive and spacing cannot be negative")
    items=list(sprites.items())
    cell_w=max(im.width for _,im in items); cell_h=max(im.height for _,im in items)
    rows=(len(items)+columns-1)//columns
    sheet=Image.new("RGBA",(columns*cell_w+(columns+1)*spacing,rows*cell_h+(rows+1)*spacing),background)
    frames={}
    for index,(name,source) in enumerate(items):
        col,row=index%columns,index//columns
        px=spacing+col*(cell_w+spacing); py=spacing+row*(cell_h+spacing)
        image=source.convert("RGBA")
        sheet.alpha_composite(image,(px,py))
        frames[name]={"x":px,"y":py,"w":image.width,"h":image.height,"pivot":{"x":image.width//2,"y":image.height}}
    path=Path(output); path.parent.mkdir(parents=True,exist_ok=True); sheet.save(path,optimize=True)
    metadata={"image":path.name,"size":{"w":sheet.width,"h":sheet.height},"frames":frames}
    path.with_suffix(".json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    return metadata

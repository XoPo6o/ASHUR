"""Seeded procedural material generators that emit ordinary raster primitives."""
from __future__ import annotations
import random

def expand_generator(op: dict) -> list[dict]:
    kind = op.get("type")
    if kind not in {"brick_wall", "stone_floor", "foliage"}:
        return [op]
    rng = random.Random(int(op.get("seed", 1)))
    x, y, w, h = (int(op.get(k, 0)) for k in ("x", "y", "w", "h"))
    base, shade = op.get("color", "#888888"), op.get("shade", op.get("color", "#888888"))
    highlight, mortar = op.get("highlight", base), op.get("mortar", shade)
    out = []
    if kind == "brick_wall":
        bw, bh = max(3, int(op.get("brick_w", 10))), max(2, int(op.get("brick_h", 5)))
        out.append({"type":"rect","x":x,"y":y,"w":w,"h":h,"color":mortar})
        row = 0
        for yy in range(y, y+h, bh):
            offset = -(bw//2) if row % 2 else 0
            xx = x + offset
            while xx < x+w:
                ww = max(2, bw + rng.randint(-1, 1))
                left, right = max(x, xx+1), min(x+w, xx+ww-1)
                top, bottom = yy+1, min(y+h, yy+bh-1)
                if right > left and bottom > top:
                    out.append({"type":"rect","x":left,"y":top,"w":right-left,"h":bottom-top,"color":base if rng.random()>.22 else shade})
                    if rng.random() > .35:
                        out.append({"type":"line","points":[[left,top],[right-1,top]],"color":highlight})
                xx += bw
            row += 1
    elif kind == "stone_floor":
        bw, bh = max(4,int(op.get("block_w",12))), max(3,int(op.get("block_h",6)))
        out.append({"type":"rect","x":x,"y":y,"w":w,"h":h,"color":mortar})
        for row, yy in enumerate(range(y,y+h,bh)):
            xx=x-(bw//2 if row%2 else 0)
            while xx<x+w:
                ww=max(3,bw+rng.randint(-2,2)); hh=max(2,bh+rng.randint(-1,1))
                l,t=max(x,xx+1),yy+1
                r,b=min(x+w,xx+ww-1),min(y+h,yy+hh-1)
                if r>l and b>t:
                    out.append({"type":"rect","x":l,"y":t,"w":r-l,"h":b-t,"color":base if rng.random()>.2 else shade})
                    if rng.random()>.55:
                        out.append({"type":"pixel","x":l+1,"y":t,"color":highlight})
                xx += bw
    else:
        # Foliage is built from overlapping stepped ellipses, not a smooth vector blob.
        count=max(3,int(op.get("clusters",8)))
        for _ in range(count):
            cx=rng.randint(x,x+max(0,w-1)); cy=rng.randint(y,y+max(0,h-1))
            rw=rng.randint(3,max(3,min(9,w//2 or 3))); rh=rng.randint(3,max(3,min(7,h//2 or 3)))
            out.append({"type":"ellipse","x":cx-rw//2,"y":cy-rh//2,"w":rw,"h":rh,"color":shade if rng.random()<.3 else base})
            if rng.random()>.35:
                out.append({"type":"pixel","x":cx-rw//3,"y":cy-rh//3,"color":highlight})
    return out

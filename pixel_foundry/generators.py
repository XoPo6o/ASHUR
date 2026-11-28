"""Seeded procedural material generators that emit ordinary raster primitives."""
from __future__ import annotations
import random


def expand_generator(op: dict) -> list[dict]:
    kind = op.get("type")
    if kind == "lamassu_sprite":
        from .lamassu import expand_lamassu
        return expand_lamassu(op)
    supported = {
        "brick_wall", "stone_floor", "foliage", "stepped_ziggurat",
        "column", "archway", "market_stall", "palm_tree", "cloud_bank", "boulder",
        "water_surface", "traveler_sprite", "temple_facade",
    }
    if kind not in supported:
        return [op]
    rng = random.Random(int(op.get("seed", 1)))
    x, y, w, h = (int(op.get(k, 0)) for k in ("x", "y", "w", "h"))
    base = op.get("color", "#888888")
    shade = op.get("shade", base)
    highlight = op.get("highlight", base)
    mortar = op.get("mortar", shade)
    detail = op.get("detail", shade)
    out: list[dict] = []

    if kind == "temple_facade":
        # Royal frieze: repeating rosettes, stepped cuneiform wedges and carved borders.
        if w < 28 or h < 7:
            raise ValueError("temple_facade requires at least 28x7 logical pixels")
        band = op.get("band", shade)
        relief = op.get("relief", highlight)
        out.append({"type": "rect", "part": "frieze-shadow", "x": x, "y": y,
                    "w": w, "h": h, "color": shade})
        out.append({"type": "line", "part": "frieze-upper-border", "points": [
            [x, y], [x+w-1, y]], "color": highlight, "width": 2})
        out.append({"type": "line", "part": "frieze-lower-border", "points": [
            [x+1, y+h-2], [x+w-2, y+h-2]], "color": band})
        spacing = max(9, int(op.get("rosette_spacing", 12)))
        for cx in range(x + 5, x + w - 4, spacing):
            cy = y + h // 2
            out.append({"type": "pixel", "part": "rosette-core", "x": cx, "y": cy, "color": relief})
            for dx, dy in ((-2,0),(2,0),(0,-2),(0,2)):
                out.append({"type": "pixel", "part": "rosette-petal",
                            "x": cx+dx, "y": cy+dy, "color": highlight})
            out.append({"type": "pixel", "part": "rosette-shadow",
                        "x": cx+1, "y": cy+1, "color": band})
        for index, wx in enumerate(range(x + 2, x + w - 5, 6)):
            wy = y + 2 + (index % 2)
            direction = 1 if index % 2 == 0 else -1
            out.append({"type": "line", "part": "cuneiform-wedge", "points": [
                [wx, wy], [wx + 2, wy + direction]], "color": relief})
            out.append({"type": "pixel", "part": "cuneiform-stop",
                        "x": wx + 3, "y": wy, "color": band})
        for px in (x + 1, x + w // 3, x + 2*w // 3, x + w - 2):
            out.append({"type": "line", "part": "frieze-panel-joint",
                        "points": [[px, y+2], [px, y+h-3]], "color": band})
        for index, cx in enumerate(range(x + 5, x + w - 4, spacing)):
            cy=y+h//2
            petals=((( -2,0),(2,0),(0,-2),(0,2),(-1,-1),(1,1)),
                    ((-2,0),(2,0),(0,-1),(0,2),(-1,1),(1,-1)),
                    ((-1,0),(2,0),(0,-2),(0,1),(-2,-1),(1,2)))[index%3]
            for dx,dy in petals:
                out.append({"type":"pixel","part":"rosette-cut","x":cx+dx,"y":cy+dy,
                            "color":band if (index+dx+dy)%2 else relief})
            out.append({"type":"line","part":"rosette-engraving","points":[
                [cx-1,cy+3],[cx,cy+4],[cx+2,cy+3]],"color":band})
        for index, px in enumerate(range(x+4,x+w-5,9)):
            mark_y=y+2+(index%3)
            out.append({"type":"line","part":"chisel-mark","points":[
                [px,mark_y],[px+1,mark_y+1],[px+3,mark_y]],
                "color":relief if index%2 else band})
        for px in (x+2,x+w//2,x+w-3):
            out.append({"type":"pixel","part":"frieze-wear","x":px,"y":y+h-3,"color":relief})

    elif kind == "market_stall":
        if w < 24 or h < 16:
            raise ValueError("market_stall requires at least 24x16 logical pixels")
        accent = op.get("accent", highlight)
        wood = op.get("wood", shade)
        lantern = op.get("lantern", highlight)
        stripe_w = max(3, w // 8)

        # Stepped cloth canopy with alternating dyed panels and a scalloped hem.
        out.append({"type": "polygon", "part": "awning", "points": [
            [x,y+5],[x+3,y],[x+w-3,y],[x+w-1,y+5],
            [x+w-1,y+8],[x,y+8]
        ], "color": base})
        for index, sx in enumerate(range(x+3, x+w-2, stripe_w)):
            stripe_color = accent if index % 2 else shade
            out.append({"type": "rect", "part": "awning-stripe", "x": sx,
                        "y": y+1, "w": min(stripe_w-1, x+w-2-sx),
                        "h": 6, "color": stripe_color})
        for sx in range(x+1, x+w-2, max(4, w//7)):
            out.append({"type": "rect", "part": "awning-scallop", "x": sx,
                        "y": y+7, "w": 3, "h": 2,
                        "color": highlight if (sx//3) % 2 else base})
        # Short crease strokes follow the canopy drape instead of adding random noise.
        for fold_index,fold_x in enumerate(range(x+stripe_w,x+w-3,max(3,stripe_w))):
            out.append({"type":"line","part":"canopy-fold","points":[
                [fold_x,y+1],[fold_x-1,y+3],[fold_x+1,y+5],[fold_x,y+7]],
                "color":highlight if fold_index%2==0 else accent})
            out.append({"type":"pixel","part":"canopy-stitch","x":fold_x+1,"y":y+6,"color":shade})
        for stitch_x in range(x+2,x+w-2,3):
            out.append({"type":"pixel","part":"canopy-hem-stitch","x":stitch_x,
                        "y":y+8+(stitch_x%2),"color":accent if stitch_x%3 else shade})

        # Two timber posts, a counter and a shadowed front panel.
        post_y = y+7
        post_h = max(5, h-14)
        for px in (x+2, x+w-4):
            out.append({"type": "rect", "part": "post", "x": px,
                        "y": post_y, "w": 2, "h": post_h, "color": wood})
            out.append({"type": "line", "part": "post-highlight", "points": [
                [px,post_y+1],[px,post_y+post_h-1]
            ], "color": highlight})
        counter_y = y+h-7
        out.append({"type": "rect", "part": "counter", "x": x+1,
                    "y": counter_y, "w": w-2, "h": 3, "color": highlight})
        out.append({"type": "rect", "part": "counter-front", "x": x+2,
                    "y": counter_y+3, "w": w-4, "h": 4, "color": wood})
        out.append({"type": "line", "part": "counter-trim", "points": [
            [x+3,counter_y+4],[x+w-4,counter_y+4]
        ], "color": shade})
        for grain_index,grain_y in enumerate((counter_y+1,counter_y+5)):
            out.append({"type":"line","part":"wood-grain","points":[
                [x+4+grain_index,grain_y],[x+w//3,grain_y+(1 if grain_index==0 else -1)],
                [x+w//2,grain_y],[x+w-6,grain_y+1]],"color":shade if grain_index==0 else detail})
        for peg_x in (x+5,x+w//3,x+2*w//3,x+w-6):
            out.append({"type":"pixel","part":"counter-peg","x":peg_x,"y":counter_y+2,"color":detail})
        out.append({"type": "pixel", "part": "wood-knot",
                    "x": x+w//2+2, "y": counter_y+5, "color": highlight})

        # A few readable wares: jars, bowls and produce, not random noise.
        goods = (
            (x+7, counter_y-4, 4, 4, accent),
            (x+15, counter_y-5, 5, 5, highlight),
            (x+25, counter_y-4, 4, 4, shade),
        )
        for index,(gx,gy,gw,gh,goods_color) in enumerate(goods):
            out.append({"type":"rect","part":"market-goods","x":gx,"y":gy,"w":gw,"h":gh,"color":goods_color})
            out.append({"type":"line","part":"goods-rim","points":[[gx,gy],[gx+gw-1,gy]],"color":highlight})
            if index==0:
                out.append({"type":"line","part":"jar-neck","points":[[gx+1,gy-1],[gx+gw-2,gy-1]],"color":accent})
                out.append({"type":"pixel","part":"jar-handle","x":gx-1,"y":gy+1,"color":highlight})
            elif index==1:
                out.append({"type":"line","part":"bowl-lip","points":[[gx-1,gy+1],[gx+gw,gy+1]],"color":accent})
                out.append({"type":"line","part":"bowl-foot","points":[[gx+1,gy+gh],[gx+gw-2,gy+gh]],"color":shade})
            else:
                out.append({"type":"pixel","part":"produce-glint","x":gx+1,"y":gy+1,"color":highlight})
                out.append({"type":"line","part":"produce-stem","points":[[gx+gw//2,gy-1],[gx+gw//2+1,gy]],"color":shade})

        # Hanging oil lantern on the right post.
        lantern_x = x+w-7
        out.append({"type": "line", "part": "lantern-chain", "points": [
            [lantern_x+1,y+5],[lantern_x+1,y+9]
        ], "color": op.get("detail", wood)})
        out.append({"type": "rect", "part": "lantern-frame", "x": lantern_x,
                    "y": y+9, "w": 4, "h": 5, "color": wood})
        out.append({"type": "rect", "part": "lantern-light", "x": lantern_x+1,
                    "y": y+10, "w": 2, "h": 3, "color": lantern})
        out.append({"type": "line", "part": "lantern-cap", "points": [
            [lantern_x,y+9],[lantern_x+3,y+9]
        ], "color": highlight})

    elif kind == "traveler_sprite":
        # A readable market wanderer: hood, face, pack, cloak, sash and separated limbs.
        # Pose variants change the actual silhouette, not just a decorative pixel.
        pose = op.get("pose", "walk")
        if pose not in {"walk", "idle", "drag"}:
            raise ValueError(f"Unsupported traveler pose: {pose!r}")
        head_w, head_h = max(13, w // 2 + 2), max(9, h // 4)
        head_x, head_y = x + (w - head_w) // 2, y
        cx = x + w // 2
        shoulder_y = head_y + head_h
        waist_y = y + h * 3 // 5
        hem_y = y + h - 8
        bottom = y + h - 1
        limb_color = op.get("limb_color", base)

        out.append({"type": "polygon", "points": [
            [head_x - 2, head_y + head_h // 2],
            [head_x, head_y + 1], [cx, head_y - 1],
            [head_x + head_w + 1, head_y + 2],
            [head_x + head_w + 2, head_y + head_h - 1],
            [head_x + head_w - 1, head_y + head_h + 2],
            [head_x + 1, head_y + head_h + 1],
        ], "color": shade})
        face_x = head_x + max(2, head_w // 4)
        out.append({"type": "rect", "x": face_x, "y": head_y + 3,
                    "w": max(2, head_w // 2), "h": max(3, head_h - 3),
                    "color": op.get("skin", highlight)})
        out.append({"type": "pixel", "x": face_x + max(1, head_w // 3),
                    "y": head_y + max(3, head_h // 2), "color": shade})
        out.append({"type": "pixel", "x": face_x + max(2, head_w // 2),
                    "y": head_y + max(4, head_h // 2 + 1), "color": highlight})

        # Face planes: two separated eyes, a central nose bridge, cheek light,
        # mouth and beard. Features occupy distinct clusters at native scale.
        face_w = max(6, head_w // 2)
        face_h = max(5, head_h - 2)
        eye_y = head_y + max(4, head_h // 2)
        eye_left_x = face_x + 1
        eye_right_x = face_x + face_w - 2
        face_shadow = op.get("skin_shadow", shade)
        face_light = op.get("skin_light", highlight)
        out.append({"type": "line", "part": "face-shadow-plane", "points": [
            [face_x, head_y + 3], [face_x, head_y + face_h + 1]],
            "color": face_shadow})
        out.append({"type": "polygon", "part": "face-shadow-cheek-plane", "points": [
            [face_x, head_y+4], [face_x+1, head_y+3],
            [face_x+2, eye_y+1], [face_x+2, eye_y+3],
            [face_x+1, head_y+head_h-1]
        ], "color": face_shadow})
        out.append({"type": "line", "part": "face-light-cheek-plane", "points": [
            [face_x+face_w-2, eye_y+2], [face_x+face_w-1, eye_y+3]
        ], "color": face_light})
        out.append({"type": "line", "part": "face-brow", "points": [
            [eye_left_x-1, eye_y-1], [eye_right_x+1, eye_y-1]],
            "color": op.get("brow", shade)})
        out.append({"type": "line", "part": "face-eyelid-left", "points": [
            [eye_left_x-1, eye_y-1], [eye_left_x+1, eye_y-1]
        ], "color": op.get("brow", shade)})
        out.append({"type": "line", "part": "face-eyelid-right", "points": [
            [eye_right_x-1, eye_y-1], [eye_right_x+1, eye_y-1]
        ], "color": op.get("brow", shade)})
        out.append({"type": "pixel", "part": "face-eye", "x": eye_left_x,
                    "y": eye_y, "color": op.get("eye", "#171827")})
        out.append({"type": "pixel", "part": "face-eye-glint", "x": eye_left_x,
                    "y": eye_y+1, "color": face_light})
        out.append({"type": "pixel", "part": "face-eye-right", "x": eye_right_x,
                    "y": eye_y, "color": op.get("eye", "#171827")})
        out.append({"type": "pixel", "part": "face-eye-right-glint", "x": eye_right_x,
                    "y": eye_y+1, "color": face_light})
        out.append({"type": "line", "part": "face-nose", "points": [
            [face_x+2, eye_y], [face_x+2, eye_y+2]],
            "color": face_light})
        out.append({"type": "pixel", "part": "face-nose-tip", "x": face_x+2,
                    "y": eye_y+2, "color": face_light})
        out.append({"type": "pixel", "part": "face-cheek", "x": face_x+face_w-1,
                    "y": eye_y+2, "color": face_light})
        out.append({"type": "line", "part": "face-mouth", "points": [
            [face_x+1, eye_y+3], [face_x+2, eye_y+3], [face_x+3, eye_y+3]],
            "color": face_shadow})
        out.append({"type": "line", "part": "face-beard", "points": [
            [face_x+1, head_y+head_h-2], [face_x+2, head_y+head_h-1],
            [face_x+3, head_y+head_h-2]],
            "color": op.get("beard", shade)})
        out.append({"type": "pixel", "part": "face-beard-highlight",
                    "x": face_x+3, "y": head_y+head_h-2,
                    "color": face_light})
        out.append({"type": "line", "part": "hood-inner-rim", "points": [
            [head_x + 1, head_y + 4], [head_x + 2, head_y + head_h + 1]],
            "color": op.get("hood_inner", highlight)})
        out.append({"type": "line", "points": [
            [head_x, head_y + 2], [head_x + head_w, head_y + 2]
        ], "color": highlight})
        out.append({"type": "rect", "x": x + 1, "y": shoulder_y + 2,
                    "w": max(3, w // 5), "h": max(5, h // 4), "color": shade})
        out.append({"type": "line", "points": [
            [x + 2, shoulder_y + 3], [x + 2, shoulder_y + h // 4]
        ], "color": highlight})
        out.append({"type": "polygon", "points": [
            [cx - w // 3, shoulder_y], [cx - w // 4, shoulder_y - 1],
            [cx + w // 4, shoulder_y - 1], [cx + w // 3, shoulder_y + 2],
            [cx + w // 3 - 1, hem_y], [cx + w // 5, hem_y + 1],
            [cx - w // 5, hem_y + 1], [cx - w // 3, hem_y - 1],
        ], "color": shade})
        out.append({"type": "polygon", "points": [
            [cx - w // 4, shoulder_y + 1], [cx + w // 5, shoulder_y + 1],
            [cx + w // 5 - 1, hem_y - 2], [cx - w // 5, hem_y - 2],
        ], "color": base})
        out.append({"type": "line", "points": [
            [cx - w // 5, waist_y], [cx + w // 5, waist_y]
        ], "color": highlight})
        out.append({"type": "pixel", "x": cx, "y": waist_y + 1,
                    "color": op.get("trim", highlight)})
        out.append({"type": "line", "points": [
            [cx - w // 5, shoulder_y + 2], [cx + w // 6, waist_y - 1]
        ], "color": highlight})
        out.append({"type": "line", "points": [
            [cx - w // 6, hem_y - 3], [cx - w // 7, hem_y - 1]
        ], "color": shade})
        if pose == "walk":
            arms = [
                [[cx - w // 4, shoulder_y + 2], [x + 1, shoulder_y + h // 4],
                 [x + 3, shoulder_y + h // 4 + 3]],
                [[cx + w // 4, shoulder_y + 2], [x + w - 2, shoulder_y + h // 5],
                 [x + w - 4, shoulder_y + h // 4 + 2]],
            ]
            legs = [
                [[cx - 3, hem_y], [cx - 7, bottom - 5], [cx - 12, bottom - 3], [cx - 14, bottom]],
                [[cx + 2, hem_y], [cx + 6, bottom - 8], [cx + 10, bottom - 4], [cx + 11, bottom]],
            ]
        elif pose == "drag":
            arms = [
                [[cx - w // 4, shoulder_y + 2], [cx - w // 3, waist_y - 1],
                 [cx - w // 3 - 1, waist_y + 2]],
                [[cx + w // 4, shoulder_y + 2], [cx + w // 3 + 1, waist_y + 2],
                 [cx + w // 3, waist_y + 4]],
            ]
            legs = [
                [[cx - 3, hem_y], [cx - 7, bottom - 3], [cx - 13, bottom - 2], [cx - 15, bottom]],
                [[cx + 2, hem_y], [cx + 5, bottom - 7], [cx + 8, bottom - 3], [cx + 8, bottom]],
            ]
        else:
            arms = [
                [[cx - w // 4, shoulder_y + 2], [cx - w // 3, waist_y],
                 [cx - w // 4, waist_y + 2]],
                [[cx + w // 4, shoulder_y + 2], [cx + w // 3, waist_y],
                 [cx + w // 4, waist_y + 2]],
            ]
            legs = [
                [[cx - 3, hem_y], [cx - 5, bottom - 3], [cx - 6, bottom]],
                [[cx + 2, hem_y], [cx + 5, bottom - 3], [cx + 6, bottom]],
            ]
        # Grounding pass: a broken-edged contact shadow sits beneath the boots,
        # with a softer cast edge and tiny displaced grit on the stone.
        left_foot = legs[0][-1]
        right_foot = legs[1][-1]
        shadow_y = max(left_foot[1], right_foot[1]) + 1
        out.append({"type": "polygon", "part": "traveler-ground-shadow", "points": [
            [left_foot[0]-3, shadow_y], [left_foot[0]-1, shadow_y-1],
            [cx-2, shadow_y-2], [cx+4, shadow_y-1],
            [right_foot[0]+3, shadow_y], [right_foot[0]+1, shadow_y+1],
            [cx, shadow_y+1]
        ], "color": op.get("ground_shadow", "#050A0E")})
        out.append({"type": "line", "part": "boot-contact-shadow-left", "points": [
            [left_foot[0]-2, left_foot[1]+2], [left_foot[0]+3, left_foot[1]+2]
        ], "color": op.get("contact_shadow", "#050A0E")})
        out.append({"type": "line", "part": "boot-contact-shadow-right", "points": [
            [right_foot[0]-2, right_foot[1]+2], [right_foot[0]+3, right_foot[1]+2]
        ], "color": op.get("contact_shadow", "#050A0E")})
        out.append({"type": "pixel", "part": "ground-grit-left",
                    "x": left_foot[0]-5, "y": shadow_y,
                    "color": op.get("ground_grit", op.get("stone", "#365564"))})
        out.append({"type": "pixel", "part": "ground-grit-right",
                    "x": right_foot[0]+5, "y": shadow_y-1,
                    "color": op.get("ground_grit", op.get("stone", "#365564"))})

        for limb in arms:
            out.append({"type": "polygon", "points": limb, "color": limb_color})
            out.append({"type": "line", "points": limb[:2], "color": highlight})
            hand_x, hand_y = limb[-1]
            out.append({"type": "pixel", "x": hand_x, "y": hand_y, "color": op.get("skin", highlight)})
        for leg in legs:
            out.append({"type": "polygon", "points": leg, "color": limb_color})
            out.append({"type": "line", "points": leg[:2], "color": highlight})
            foot_x, foot_y = leg[-1]
            out.append({"type": "rect", "x": foot_x - 1, "y": foot_y,
                        "w": 4, "h": 2, "color": op.get("boots", shade)})

        # Fine garment construction: pack straps, stitched hem, folds and travel gear.
        out.append({"type": "line", "part": "pack-strap", "points": [
            [x+3, shoulder_y+3], [x+5, waist_y-1]], "color": op.get("trim", highlight)})
        out.append({"type": "line", "part": "pack-seam", "points": [
            [x+2, shoulder_y+h//5], [x+w//5, shoulder_y+h//5]], "color": highlight})
        out.append({"type": "line", "part": "belt-stitch", "points": [
            [cx-w//5+1, waist_y+2], [cx+w//5-1, waist_y+2]], "color": op.get("trim", highlight)})
        out.append({"type": "rect", "part": "belt-buckle", "x": cx-1,
                    "y": waist_y, "w": 2, "h": 2, "color": op.get("trim", highlight)})
        for fold_index, fold_x in enumerate((cx-w//6, cx+w//8)):
            out.append({"type": "line", "part": "cloak-fold", "points": [
                [fold_x, shoulder_y+4], [fold_x-1, waist_y+3],
                [fold_x + (1 if fold_index else -1), hem_y-2]], "color": highlight})
        out.append({"type": "line", "part": "cloak-hem-stitch", "points": [
            [cx-w//5+1, hem_y], [cx+w//5-1, hem_y]], "color": op.get("trim", highlight)})

        # Tailored cloth: offset folds, dark troughs, seam breaks and worn hem patches.
        cloth_shadow = op.get("cloth_shadow", shade)
        cloth_light = op.get("cloth_light", highlight)
        fold_specs = (
            (cx-w//5+1, shoulder_y+5, waist_y+2, hem_y-3, -1),
            (cx-w//12, shoulder_y+3, waist_y+4, hem_y-1, 1),
            (cx+w//8, shoulder_y+4, waist_y+1, hem_y-4, -1),
        )
        for fold_index, (fx, fy, my, by, drift) in enumerate(fold_specs):
            out.append({"type": "line", "part": "cloth-fold-shadow", "points": [
                [fx+1, fy], [fx, my], [fx+drift, by]], "color": cloth_shadow})
            out.append({"type": "line", "part": "cloth-fold-light", "points": [
                [fx, fy], [fx+1, my-1], [fx+1+drift, by-1]],
                "color": cloth_light if fold_index != 1 else op.get("trim", highlight)})
        out.append({"type": "line", "part": "tunic-side-seam", "points": [
            [cx-w//4+1, shoulder_y+4], [cx-w//4, waist_y+2],
            [cx-w//5, hem_y-2]], "color": op.get("seam", cloth_shadow)})
        out.append({"type": "line", "part": "cloak-edge-binding", "points": [
            [cx+w//5, shoulder_y+3], [cx+w//5+1, waist_y+3],
            [cx+w//5, hem_y-1]], "color": op.get("trim", highlight)})
        out.append({"type": "pixel", "part": "cloth-wear-patch",
                    "x": cx-w//5+2, "y": hem_y-1, "color": cloth_shadow})
        out.append({"type": "pixel", "part": "cloth-wear-highlight",
                    "x": cx+w//5-1, "y": hem_y, "color": cloth_light})
        out.append({"type": "line", "part": "sleeve-cuff-stitch", "points": [
            [x+2, shoulder_y+h//4+1], [x+4, shoulder_y+h//4+2]],
            "color": op.get("trim", highlight)})
        out.append({"type": "line", "part": "boot-sole", "points": [
            [legs[0][-1][0]-1, legs[0][-1][1]+1],
            [legs[0][-1][0]+2, legs[0][-1][1]+1]], "color": cloth_shadow})
        out.append({"type": "pixel", "part": "boot-toe-wear",
                    "x": legs[1][-1][0]+1, "y": legs[1][-1][1],
                    "color": cloth_light})
        out.append({"type": "rect", "part": "travel-pouch", "x": cx+w//5-1,
                    "y": waist_y+3, "w": 3, "h": 4, "color": op.get("boots", shade)})
        out.append({"type": "pixel", "part": "pouch-clasp", "x": cx+w//5,
                    "y": waist_y+3, "color": highlight})
        out.append({"type": "line", "part": "hood-seam", "points": [
            [head_x+1, head_y+3], [cx, head_y+1],
            [head_x+head_w, head_y+3]], "color": op.get("trim", highlight)})
        out.append({"type": "pixel", "part": "boot-highlight",
                    "x": legs[0][-1][0]-1, "y": legs[0][-1][1],
                    "color": highlight})

        # Final character pass: layered collar, shoulder construction, hand anatomy,
        # and individually placed woven motifs. These are designed clusters, not noise.
        collar_y = shoulder_y + 2
        out.append({"type": "polygon", "part": "layered-collar-shadow", "points": [
            [cx-w//5, collar_y], [cx, collar_y+3], [cx+w//5, collar_y],
            [cx+w//7, collar_y+4], [cx, collar_y+5], [cx-w//7, collar_y+4]
        ], "color": cloth_shadow})
        out.append({"type": "line", "part": "collar-gold-piping", "points": [
            [cx-w//6, collar_y+1], [cx, collar_y+4], [cx+w//6, collar_y+1]
        ], "color": op.get("trim", highlight)})
        out.append({"type": "pixel", "part": "collar-clasp", "x": cx,
                    "y": collar_y+3, "color": op.get("clasp", highlight)})
        out.append({"type": "line", "part": "shoulder-seam-left", "points": [
            [cx-w//4, shoulder_y+2], [cx-w//3, shoulder_y+5],
            [cx-w//3+1, waist_y-2]], "color": op.get("seam", cloth_shadow)})
        out.append({"type": "line", "part": "shoulder-seam-right", "points": [
            [cx+w//4, shoulder_y+2], [cx+w//3, shoulder_y+5],
            [cx+w//3-1, waist_y-2]], "color": op.get("seam", cloth_shadow)})
        # A narrow woven border follows the cloak edge, with deliberate broken stitches.
        for stitch_index, stitch_y in enumerate(range(shoulder_y+7, hem_y-2, 4)):
            stitch_x = cx+w//5 + (1 if stitch_index % 2 else 0)
            out.append({"type": "pixel", "part": "cloak-woven-stitch",
                        "x": stitch_x, "y": stitch_y,
                        "color": op.get("trim", highlight)})
            if stitch_index % 2 == 0:
                out.append({"type": "pixel", "part": "cloak-woven-shadow",
                            "x": stitch_x-1, "y": stitch_y+1,
                            "color": cloth_shadow})
        # Small asymmetric embroidery marks make the garment feel hand-finished.
        for emblem_x, emblem_y, emblem_color in (
            (cx-w//7, waist_y-3, op.get("trim", highlight)),
            (cx+w//10, waist_y+5, cloth_light),
            (cx-w//8, hem_y-4, cloth_shadow),
        ):
            out.append({"type": "pixel", "part": "tunic-embroidered-mark",
                        "x": emblem_x, "y": emblem_y, "color": emblem_color})
        out.append({"type": "line", "part": "sleeve-fold-left", "points": [
            [x+2, shoulder_y+h//5], [x+4, shoulder_y+h//5+2],
            [x+3, shoulder_y+h//4+1]], "color": cloth_shadow})
        out.append({"type": "line", "part": "sleeve-fold-right", "points": [
            [x+w-4, shoulder_y+h//5], [x+w-3, shoulder_y+h//5+2],
            [x+w-5, shoulder_y+h//4+1]], "color": cloth_light})
        # Hands receive a palm highlight and a separated thumb pixel at each wrist.
        for hand_index, limb in enumerate(arms):
            hand_x, hand_y = limb[-1]
            hand_side = -1 if hand_index == 0 else 1
            out.append({"type": "pixel", "part": "hand-palm-light",
                        "x": hand_x, "y": hand_y-1, "color": face_light})
            out.append({"type": "pixel", "part": "hand-thumb",
                        "x": hand_x+hand_side, "y": hand_y,
                        "color": op.get("skin", highlight)})
            out.append({"type": "pixel", "part": "hand-shadow",
                        "x": hand_x, "y": hand_y+1, "color": face_shadow})
        # Individual boot lacing and leather panels clarify the feet at native scale.
        for foot_index, leg in enumerate(legs):
            foot_x, foot_y = leg[-1]
            out.append({"type": "line", "part": "boot-vamp-seam", "points": [
                [foot_x-1, foot_y], [foot_x+1, foot_y]
            ], "color": cloth_light})
            out.append({"type": "pixel", "part": "boot-lace",
                        "x": foot_x, "y": foot_y-1,
                        "color": op.get("trim", highlight)})
            out.append({"type": "pixel", "part": "boot-heel-shadow",
                        "x": foot_x-1, "y": foot_y+1, "color": cloth_shadow})

        # Warm lantern-side bounce light: a restrained rim on hood, cheek,
        # shoulder and cloak folds. Keep it as a final overlay so it reads as light.
        glow = op.get("lantern_glow", "#E9B86B")
        glow_soft = op.get("lantern_glow_soft", "#B9784E")
        light_side = op.get("light_side", "right")
        if light_side not in {"left", "right"}:
            raise ValueError(f"Unsupported traveler light side: {light_side!r}")
        if light_side == "right":
            hood_edge_x = head_x + head_w + 1
            cheek_x = face_x + face_w
            shoulder_edge = cx + w // 3
            cloak_edge = cx + w // 5 + 1
            fold_x = cx + w // 8 + 1
        else:
            hood_edge_x = head_x - 1
            cheek_x = face_x - 1
            shoulder_edge = cx - w // 3
            cloak_edge = cx - w // 5 - 1
            fold_x = cx - w // 6
        out.append({"type": "line", "part": "hood-lantern-rim", "points": [
            [hood_edge_x, head_y+3], [hood_edge_x+(-1 if light_side=="left" else 1), head_y+head_h-1]
        ], "color": glow})
        out.append({"type": "pixel", "part": "face-lantern-bounce",
                    "x": cheek_x, "y": eye_y+1, "color": glow})
        out.append({"type": "pixel", "part": "face-lantern-soft",
                    "x": cheek_x, "y": eye_y+2, "color": glow_soft})
        out.append({"type": "line", "part": "shoulder-lantern-rim", "points": [
            [shoulder_edge, shoulder_y+3], [shoulder_edge, waist_y-2]
        ], "color": glow_soft})
        out.append({"type": "line", "part": "cloak-lantern-fold", "points": [
            [fold_x, shoulder_y+6], [fold_x+(-1 if light_side=="left" else 1), waist_y+3],
            [cloak_edge, hem_y-2]
        ], "color": glow_soft})
        out.append({"type": "pixel", "part": "cloak-lantern-glint",
                    "x": cloak_edge, "y": hem_y-3, "color": glow})

    elif kind == "palm_tree":
        trunk_w = max(2, int(op.get("trunk_w", max(2, w // 8))))
        crown_y = y + max(3, h // 3)
        trunk_points = [
            [x + w // 2 - trunk_w // 2, crown_y],
            [x + w // 2 + trunk_w // 2, crown_y],
            [x + w // 2 + trunk_w // 2 + 2, y + h - 2],
            [x + w // 2 - trunk_w // 2 + 1, y + h - 1],
        ]
        out.append({"type": "polygon", "points": trunk_points, "color": shade})
        out.append({"type": "line", "points": [
            [x + w // 2, crown_y + 3], [x + w // 2 + 1, y + h - 4]
        ], "color": highlight})
        cx, cy = x + w // 2, crown_y
        fronds = [
            [[0, 0], [-w//2+2, -h//4], [-w//2, -h//3], [-w//4, -h//4], [-1, 2]],
            [[0, 0], [-w//3, -h//2], [-w//4, -h//2], [0, -h//5], [1, 2]],
            [[0, 0], [w//5, -h//2], [w//3, -h//2], [w//4, -h//4], [1, 2]],
            [[0, 0], [w//2, -h//3], [w//2, -h//4], [w//4, -h//5], [1, 2]],
            [[0, 0], [w//2, 0], [w//2, h//10], [w//4, 0], [1, 2]],
            [[0, 0], [-w//2, h//12], [-w//2+2, h//6], [-w//4, h//10], [-1, 2]],
        ]
        for index, rel in enumerate(fronds):
            pts = [[cx + dx, cy + dy] for dx, dy in rel]
            out.append({"type": "polygon", "points": pts,
                        "color": base if index % 2 == 0 else shade})
            if index in (0, 2, 4):
                out.append({"type": "line", "points": [pts[0], pts[2]], "color": highlight})
        for _ in range(max(1, int(op.get("fruit_clusters", 2)))):
            px = cx + rng.randint(-2, 2)
            py = cy + rng.randint(-1, 2)
            out.append({"type": "pixel", "x": px, "y": py, "color": highlight})

    elif kind == "cloud_bank":
        lumps = max(3, int(op.get("lumps", 5)))
        widths = [max(3, w // lumps + rng.randint(-2, 2)) for _ in range(lumps)]
        cursor = x
        for index, lump_w in enumerate(widths):
            lump_h = max(3, int(h * rng.uniform(0.48, 0.82)))
            lump_y = y + max(0, h - lump_h - rng.randint(0, max(1, h // 5)))
            out.append({"type": "rect", "x": cursor, "y": lump_y,
                        "w": lump_w, "h": y + h - lump_y, "color": shade})
            cap_w = max(3, lump_w - 2)
            cap_h = max(2, lump_h // 2)
            out.append({"type": "rect", "x": cursor + 1, "y": lump_y,
                        "w": cap_w, "h": cap_h, "color": base})
            if index % 2 == 0:
                out.append({"type": "line", "points": [
                    [cursor + 2, lump_y], [cursor + cap_w - 1, lump_y]
                ], "color": highlight})
            cursor += max(2, lump_w - max(1, w // (lumps * 3)))

    elif kind == "boulder":
        steps = max(5, int(op.get("steps", 8)))
        top = y + max(1, h // 5)
        points = [[x, y + h - 2]]
        for i in range(steps + 1):
            px = x + (w * i // steps)
            jitter = rng.randint(-1, max(1, h // 6))
            py = min(y + h - 4, top + jitter)
            points.append([px, py])
        points.extend([[x + w - 1, y + h - 2], [x + w - 3, y + h - 1], [x + 2, y + h - 1]])
        out.append({"type": "polygon", "points": points, "color": base})
        out.append({"type": "polygon", "points": [
            [x + 2, y + h - 3], [x + w - 3, y + h - 3],
            [x + w - 1, y + h - 1], [x + 1, y + h - 1]
        ], "color": shade})
        out.append({"type": "line", "points": [
            [x + max(1, w // 5), y + max(1, h // 3)],
            [x + max(2, w // 2), top]
        ], "color": highlight})
        for _ in range(max(1, int(op.get("chips", 3)))):
            px = rng.randint(x + 2, x + max(2, w - 3))
            py = rng.randint(top + 1, y + max(1, h - 4))
            out.append({"type": "pixel", "x": px, "y": py,
                        "color": highlight if rng.random() > 0.35 else shade})

    elif kind == "water_surface":
        out.append({"type": "rect", "x": x, "y": y, "w": w, "h": h, "color": shade})
        for row in range(max(2, h // 3)):
            yy = y + 1 + row * max(2, h // max(2, h // 3))
            cursor = x + rng.randint(0, max(0, w // 8))
            while cursor < x + w - 2:
                length = rng.randint(2, max(3, min(8, w // 4)))
                color = highlight if rng.random() > 0.72 else base
                out.append({"type": "line", "points": [
                    [cursor, yy], [min(x + w - 1, cursor + length), yy]
                ], "color": color})
                cursor += length + rng.randint(3, max(4, w // 7))

    elif kind == "column":
        shaft_w=max(3,int(op.get("shaft_w",w//2)))
        shaft_x=x+(w-shaft_w)//2
        cap_h=max(2,int(op.get("capital_h",max(2,h//7))))
        base_h=max(2,int(op.get("base_h",max(2,h//8))))
        shaft_y=y+cap_h
        shaft_h=max(1,h-cap_h-base_h)
        out.extend([
            {"type":"rect","x":x,"y":y,"w":w,"h":cap_h,"color":highlight},
            {"type":"rect","x":x+1,"y":y+cap_h-1,"w":max(1,w-2),"h":1,"color":shade},
            {"type":"rect","x":shaft_x,"y":shaft_y,"w":shaft_w,"h":shaft_h,"color":base},
            {"type":"line","points":[[shaft_x+1,shaft_y+1],[shaft_x+1,shaft_y+shaft_h-1]],"color":highlight},
            {"type":"line","points":[[shaft_x+shaft_w-2,shaft_y+1],[shaft_x+shaft_w-2,shaft_y+shaft_h-1]],"color":shade},
            {"type":"rect","x":x,"y":y+h-base_h,"w":w,"h":base_h,"color":highlight},
            {"type":"line","points":[[x,y+h-1],[x+w-1,y+h-1]],"color":shade}
        ])
        if op.get("fluting",True) and shaft_w>=7:
            for index,fx in enumerate(range(shaft_x+2,shaft_x+shaft_w-1,2)):
                out.append({"type":"line","part":"column-flute","points":[
                    [fx,shaft_y+2],[fx,shaft_y+shaft_h-2]],
                    "color":highlight if index%3==0 else shade})
                if index%2==0:
                    out.append({"type":"pixel","part":"flute-glint","x":fx+1,
                                "y":shaft_y+3+index%4,"color":highlight})
        out.extend([
            {"type":"line","part":"capital-abacus","points":[[x+1,y+1],[x+w-2,y+1]],"color":shade},
            {"type":"line","part":"capital-neck","points":[[shaft_x-1,shaft_y-1],[shaft_x+shaft_w,y+cap_h]],"color":highlight},
            {"type":"line","part":"base-upper-bead","points":[[x+1,y+h-base_h],[x+w-2,y+h-base_h]],"color":shade},
            {"type":"line","part":"base-lower-bevel","points":[[x+1,y+h-1],[x+w-2,y+h-1]],"color":shade},
        ])
        if w>=10 and cap_h>=3:
            for motif_x in (x+2,x+w-4):
                out.append({"type":"pixel","part":"capital-carving","x":motif_x,"y":y+2,"color":shade})
                out.append({"type":"line","part":"capital-volute","points":[
                    [motif_x,y+2],[motif_x+1,y+1],[motif_x+2,y+2]],"color":highlight})
        if shaft_h>=8:
            for seam_y in (shaft_y+shaft_h//3,shaft_y+2*shaft_h//3):
                out.append({"type":"line","part":"shaft-joint","points":[
                    [shaft_x+1,seam_y],[shaft_x+shaft_w-2,seam_y]],"color":shade})

    elif kind == "archway":
        thickness=max(2,int(op.get("thickness",max(3,w//8))))
        arch_h=max(3,int(op.get("arch_h",h//3)))
        spring_y=y+arch_h
        left_w=max(2,(w-thickness)//2)
        right_x=x+w-left_w
        out.extend([
            {"type":"rect","x":x,"y":spring_y,"w":left_w,"h":h-arch_h,"color":base},
            {"type":"rect","x":right_x,"y":spring_y,"w":left_w,"h":h-arch_h,"color":base},
            {"type":"line","points":[[x+1,spring_y],[x+left_w-1,spring_y]],"color":highlight},
            {"type":"line","points":[[right_x+1,spring_y],[x+w-2,spring_y]],"color":highlight}
        ])
        steps=max(3,int(op.get("arch_steps",5)))
        for i in range(steps):
            inset=max(0,int((i/steps)*(w/2-thickness)))
            block_y=y+i*max(1,arch_h//steps)
            block_h=max(1,arch_h//steps)
            block_w=max(2,w-2*inset)
            out.append({"type":"rect","x":x+inset,"y":block_y,"w":block_w,"h":block_h,
                        "color":highlight if i==0 else base})
            if i>0:
                out.append({"type":"line","points":[[x+inset,block_y],[x+inset+block_w-1,block_y]],
                            "color":shade})
        out.append({"type":"rect","x":x+w//2-thickness//2,"y":y,"w":thickness,"h":max(2,arch_h//steps),"color":highlight})

    elif kind == "stepped_ziggurat":
        tiers=max(2,int(op.get("tiers",5)))
        tier_h=max(2,int(op.get("tier_h",max(2,h//tiers))))
        inset=max(1,int(op.get("inset",max(1,w//(tiers*3)))))
        top=op.get("top_color",highlight)
        side=op.get("side_color",shade)
        for i in range(tiers):
            tier_width=max(3,w-2*inset*i)
            tier_x=x+(w-tier_width)//2
            tier_y=y+h-(i+1)*tier_h
            tier_height=min(tier_h,y+h-tier_y)
            if tier_height<=0:
                continue
            front_width=max(2,tier_width-max(2,inset//2))
            out.append({"type":"rect","x":tier_x,"y":tier_y,"w":front_width,"h":tier_height,"color":base})
            if front_width<tier_width:
                out.append({"type":"rect","x":tier_x+front_width,"y":tier_y,"w":tier_width-front_width,"h":tier_height,"color":side})
            out.append({"type":"line","points":[[tier_x,tier_y],[tier_x+front_width-1,tier_y]],"color":top})
            if op.get("course_lines",True) and tier_height>=4:
                line_y=tier_y+tier_height-2
                out.append({"type":"line","points":[[tier_x+1,line_y],[tier_x+front_width-2,line_y]],"color":shade})
            # Fine staggered masonry joints and sparse worn chips reveal individual blocks.
            if op.get("brick_detail", True) and tier_height >= 8 and front_width >= 20:
                brick_h = max(4, tier_height // 3)
                brick_w = max(8, front_width // 7)
                row_index = 0
                for joint_y in range(tier_y + 3, tier_y + tier_height - 2, brick_h):
                    offset = brick_w // 2 if row_index % 2 else 0
                    for joint_x in range(tier_x + 3 + offset, tier_x + front_width - 2, brick_w):
                        out.append({"type": "line", "part": "ziggurat-brick-joint",
                                    "points": [[joint_x, joint_y],
                                               [joint_x, min(tier_y + tier_height - 2, joint_y + brick_h - 2)]],
                                    "color": shade})
                    row_index += 1
                for _ in range(max(1, front_width // 36)):
                    chip_x = rng.randint(tier_x + 2, tier_x + front_width - 3)
                    chip_y = rng.randint(tier_y + 2, tier_y + tier_height - 3)
                    out.append({"type": "pixel", "part": "stone-wear",
                                "x": chip_x, "y": chip_y,
                                "color": top if rng.random() > 0.5 else shade})
        shrine_w=max(5,w//5); shrine_h=max(4,tier_h)
        shrine_x=x+(w-shrine_w)//2
        shrine_y=max(y,y+h-tiers*tier_h-shrine_h)
        out.append({"type":"rect","x":shrine_x,"y":shrine_y,"w":shrine_w,"h":shrine_h,"color":base})
        out.append({"type":"line","points":[[shrine_x,shrine_y],[shrine_x+shrine_w-1,shrine_y]],"color":top})

    elif kind == "brick_wall":
        bw, bh = max(5, int(op.get("brick_w", 10))), max(3, int(op.get("brick_h", 5)))
        out.append({"type": "rect", "part": "masonry-mortar", "x": x, "y": y,
                    "w": w, "h": h, "color": mortar})
        row = 0
        yy = y
        while yy < y + h:
            row_h = max(3, bh + rng.randint(-1, 1))
            xx = x - (bw // 2 if row % 2 else 0)
            while xx < x + w:
                ww = max(4, bw + rng.randint(-2, 2))
                left, right = max(x, xx + 1), min(x + w, xx + ww - 1)
                top, bottom = yy + 1, min(y + h, yy + row_h - 1)
                if right - left >= 2 and bottom - top >= 1:
                    face = base if rng.random() > 0.2 else shade
                    out.append({"type": "rect", "part": "brick-face", "x": left,
                                "y": top, "w": right-left, "h": bottom-top,
                                "color": face})
                    # A tiny bevel on every block gives the masonry a readable light direction.
                    out.append({"type": "line", "part": "brick-top-bevel",
                                "points": [[left, top], [right-1, top]],
                                "color": highlight})
                    out.append({"type": "line", "part": "brick-side-shadow",
                                "points": [[right-1, top+1], [right-1, bottom]],
                                "color": shade})
                    if right-left >= 6 and bottom-top >= 3 and rng.random() > 0.28:
                        gx = rng.randint(left+1, right-3)
                        gy = rng.randint(top+1, bottom-1)
                        out.append({"type": "line", "part": "brick-grain",
                                    "points": [[gx, gy], [gx+1, gy],
                                               [min(right-2, gx+2), gy + (1 if rng.random() > .5 else 0)]],
                                    "color": highlight if rng.random() > .45 else shade})
                    # Chips and hairline fractures are sparse, connected marks, not pixel confetti.
                    if right-left >= 5 and bottom-top >= 3 and rng.random() > .78:
                        cx = rng.randint(left+1, right-2)
                        cy = rng.choice((top+1, bottom-1))
                        out.append({"type": "line", "part": "brick-chip",
                                    "points": [[cx, cy], [min(right-1, cx+1), cy]],
                                    "color": mortar})
                    if right-left >= 7 and bottom-top >= 4 and rng.random() > .9:
                        cx = rng.randint(left+2, right-3)
                        cy = rng.randint(top+1, bottom-2)
                        out.append({"type": "line", "part": "brick-hairline-crack",
                                    "points": [[cx, cy], [cx+1, cy+1],
                                               [min(right-1, cx+2), min(bottom, cy+1)]],
                                    "color": shade})
                xx += ww + 1
            yy += row_h
            row += 1

    elif kind == "stone_floor":
        bw, bh = max(6, int(op.get("block_w", 12))), max(4, int(op.get("block_h", 6)))
        out.append({"type": "rect", "part": "street-mortar", "x": x, "y": y,
                    "w": w, "h": h, "color": mortar})
        row = 0
        yy = y
        while yy < y + h:
            depth = (yy-y) / max(1, h-1)
            row_h = max(3, int(round(bh * (0.82 + 0.36*depth) * rng.uniform(0.92, 1.08))))
            xx = x - (bw // 2 if row % 2 else 0)
            while xx < x + w:
                ww = max(5, int(round(bw * (0.84 + 0.22*depth) * rng.uniform(0.88, 1.12))))
                left, right = max(x, xx+1), min(x+w, xx+ww-1)
                top, bottom = yy+1, min(y+h, yy+row_h-1)
                if right-left >= 3 and bottom-top >= 2:
                    face = base if rng.random() > 0.18 else shade
                    out.append({"type": "rect", "part": "paving-slab", "x": left,
                                "y": top, "w": right-left, "h": bottom-top,
                                "color": face})
                    # Raised upper/left edges and a darker lower/right edge make each slab read in relief.
                    out.append({"type": "line", "part": "slab-top-bevel",
                                "points": [[left, top], [right-1, top]],
                                "color": highlight})
                    out.append({"type": "line", "part": "slab-left-bevel",
                                "points": [[left, top+1], [left, bottom]],
                                "color": base})
                    out.append({"type": "line", "part": "slab-side-shadow",
                                "points": [[right-1, top+1], [right-1, bottom]],
                                "color": shade})
                    if right-left >= 7 and bottom-top >= 3 and rng.random() > 0.3:
                        gx = rng.randint(left+1, right-3)
                        gy = rng.randint(top+1, bottom-1)
                        out.append({"type": "line", "part": "stone-vein",
                                    "points": [[gx, gy], [gx+1, gy],
                                               [min(right-2, gx+2), gy]],
                                    "color": highlight if rng.random() > .5 else shade})
                    if right-left >= 6 and bottom-top >= 3 and rng.random() > 0.72:
                        cx = rng.randint(left+1, right-2)
                        cy = rng.choice((top+1, bottom-1))
                        out.append({"type": "line", "part": "stone-chip",
                                    "points": [[cx, cy], [min(right-1, cx+1), cy]],
                                    "color": mortar})
                    if right-left >= 8 and bottom-top >= 4 and rng.random() > 0.9:
                        cx = rng.randint(left+2, right-3)
                        cy = rng.randint(top+1, bottom-2)
                        out.append({"type": "line", "part": "stone-crack",
                                    "points": [[cx, cy], [cx+1, cy+1],
                                               [min(right-1, cx+2), min(bottom, cy+1)]],
                                    "color": shade})
                xx += ww + 1
            yy += row_h
            row += 1
    else:
        count=max(3,int(op.get("clusters",8)))
        for _ in range(count):
            cx=rng.randint(x,x+max(0,w-1)); cy=rng.randint(y,y+max(0,h-1))
            rw=rng.randint(3,max(3,min(9,w//2 or 3))); rh=rng.randint(3,max(3,min(7,h//2 or 3)))
            out.append({"type":"ellipse","x":cx-rw//2,"y":cy-rh//2,"w":rw,"h":rh,"color":shade if rng.random()<.3 else base})
            if rng.random()>.35:
                out.append({"type":"pixel","x":cx-rw//3,"y":cy-rh//3,"color":highlight})
    return out

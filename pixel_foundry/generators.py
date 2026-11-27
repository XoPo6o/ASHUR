"""Seeded procedural material generators that emit ordinary raster primitives."""
from __future__ import annotations
import random


def expand_generator(op: dict) -> list[dict]:
    kind = op.get("type")
    supported = {
        "brick_wall", "stone_floor", "foliage", "stepped_ziggurat",
        "column", "archway", "palm_tree", "cloud_bank", "boulder",
        "water_surface", "traveler_sprite",
    }
    if kind not in supported:
        return [op]
    rng = random.Random(int(op.get("seed", 1)))
    x, y, w, h = (int(op.get(k, 0)) for k in ("x", "y", "w", "h"))
    base = op.get("color", "#888888")
    shade = op.get("shade", base)
    highlight = op.get("highlight", base)
    mortar = op.get("mortar", shade)
    out: list[dict] = []

    if kind == "traveler_sprite":
        # Compact human silhouette designed for a 16-bit side-view market scene.
        # The pose changes limb offsets while the cloak, hood and belt retain
        # the same cluster grammar across the character family.
        pose = op.get("pose", "walk")
        if pose not in {"walk", "idle"}:
            raise ValueError(f"Unsupported traveler pose: {pose!r}")
        head_w = max(5, w // 3)
        head_h = max(5, h // 5)
        head_x = x + (w - head_w) // 2
        head_y = y
        cx = x + w // 2
        shoulder_y = y + head_h
        waist_y = y + h * 3 // 5
        hem_y = y + h - 5
        # Hood and face are separate stepped silhouettes.
        out.append({"type": "polygon", "points": [
            [head_x - 2, head_y + head_h // 2],
            [head_x, head_y + 1], [head_x + head_w // 2, head_y - 1],
            [head_x + head_w + 1, head_y + 2],
            [head_x + head_w + 2, head_y + head_h - 1],
            [head_x + head_w - 1, head_y + head_h + 1],
            [head_x + 1, head_y + head_h + 1],
        ], "color": shade})
        face_x = head_x + max(1, head_w // 4)
        out.append({"type": "rect", "x": face_x, "y": head_y + 3,
                    "w": max(2, head_w // 2), "h": max(3, head_h - 3),
                    "color": op.get("skin", highlight)})
        out.append({"type": "pixel", "x": face_x + max(1, head_w // 3),
                    "y": head_y + max(3, head_h // 2), "color": shade})
        out.append({"type": "line", "points": [
            [head_x, head_y + 2], [head_x + head_w, head_y + 2]
        ], "color": highlight})
        # Cloak: broad shoulders tapering to a stepped hem.
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
        # Arms swing opposite the legs during the walk cycle.
        arm_drop = max(3, h // 5)
        if pose == "walk":
            left_arm = [[cx - w // 4, shoulder_y + 2],
                        [x + 1, shoulder_y + arm_drop],
                        [x + 3, shoulder_y + arm_drop + 2]]
            right_arm = [[cx + w // 4, shoulder_y + 2],
                         [x + w - 2, shoulder_y + arm_drop - 2],
                         [x + w - 4, shoulder_y + arm_drop + 1]]
            left_leg = [[cx - 3, hem_y], [cx - 5, y + h - 2], [cx - 8, y + h - 1]]
            right_leg = [[cx + 2, hem_y], [cx + 5, y + h - 4], [cx + 8, y + h - 3]]
        else:
            left_arm = [[cx - w // 4, shoulder_y + 2],
                        [cx - w // 3, waist_y], [cx - w // 4, waist_y + 1]]
            right_arm = [[cx + w // 4, shoulder_y + 2],
                         [cx + w // 3, waist_y], [cx + w // 4, waist_y + 1]]
            left_leg = [[cx - 3, hem_y], [cx - 4, y + h - 2], [cx - 7, y + h - 1]]
            right_leg = [[cx + 2, hem_y], [cx + 3, y + h - 2], [cx + 6, y + h - 1]]
        for limb in (left_arm, right_arm):
            out.append({"type": "polygon", "points": limb, "color": shade})
            out.append({"type": "line", "points": limb[:2], "color": highlight})
        for leg in (left_leg, right_leg):
            out.append({"type": "polygon", "points": leg, "color": shade})
            foot_x, foot_y = leg[-1]
            out.append({"type": "rect", "x": foot_x - 1, "y": foot_y,
                        "w": 4, "h": 2, "color": op.get("boots", shade)})
        # A narrow shoulder sash gives the traveler a readable diagonal.
        out.append({"type": "line", "points": [
            [cx - w // 5, shoulder_y + 2], [cx + w // 6, waist_y - 1]
        ], "color": highlight})

    elif kind == "palm_tree":
        # A bent, tapered trunk with six broad fronds. The fronds use stepped
        # polygon contours and a few deliberate vein pixels, never ellipses.
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
        cx = x + w // 2
        cy = crown_y
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
        # Layered stepped masses: dark underside, midtone body, top light.
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
        # Irregular stepped silhouette with a distinct light plane and dark foot.
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
        # Quiet dark water with sparse, grouped horizontal glints.
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
            for fx in range(shaft_x+3,shaft_x+shaft_w-2,3):
                out.append({"type":"line","points":[[fx,shaft_y+2],[fx,shaft_y+shaft_h-2]],"color":shade})

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
        shrine_w=max(5,w//5); shrine_h=max(4,tier_h)
        shrine_x=x+(w-shrine_w)//2
        shrine_y=max(y,y+h-tiers*tier_h-shrine_h)
        out.append({"type":"rect","x":shrine_x,"y":shrine_y,"w":shrine_w,"h":shrine_h,"color":base})
        out.append({"type":"line","points":[[shrine_x,shrine_y],[shrine_x+shrine_w-1,shrine_y]],"color":top})

    elif kind == "brick_wall":
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
        count=max(3,int(op.get("clusters",8)))
        for _ in range(count):
            cx=rng.randint(x,x+max(0,w-1)); cy=rng.randint(y,y+max(0,h-1))
            rw=rng.randint(3,max(3,min(9,w//2 or 3))); rh=rng.randint(3,max(3,min(7,h//2 or 3)))
            out.append({"type":"ellipse","x":cx-rw//2,"y":cy-rh//2,"w":rw,"h":rh,"color":shade if rng.random()<.3 else base})
            if rng.random()>.35:
                out.append({"type":"pixel","x":cx-rw//3,"y":cy-rh//3,"color":highlight})
    return out

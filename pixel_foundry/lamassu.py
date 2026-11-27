"""Assyrian Lamassu sprite: winged bull body, human head and five readable legs.

All coordinates are authored on the logical pixel grid and expanded into the
renderer's ordinary polygon, line and pixel primitives.
"""
from __future__ import annotations


def expand_lamassu(op: dict) -> list[dict]:
    x, y = int(op.get("x", 0)), int(op.get("y", 0))
    w, h = int(op.get("w", 0)), int(op.get("h", 0))
    if w < 60 or h < 43:
        raise ValueError("lamassu_sprite requires a canvas of at least 60x43 logical pixels")

    base = op.get("color", "#D9AD62")
    shade = op.get("shade", "#9C7746")
    highlight = op.get("highlight", "#F0D8A5")
    detail = op.get("detail", "#365564")
    out: list[dict] = []

    # Tall, layered wing: one clear outer silhouette plus stepped feather rows.
    out.append({"type": "polygon", "part": "wing", "points": [
        [x+7,y+27],[x+4,y+20],[x+6,y+13],[x+11,y+7],
        [x+18,y+2],[x+27,y],[x+34,y+3],[x+31,y+7],
        [x+39,y+6],[x+43,y+11],[x+37,y+14],
        [x+43,y+17],[x+38,y+22],[x+28,y+27],[x+17,y+30]
    ], "color": shade})
    out.append({"type": "polygon", "part": "wing", "points": [
        [x+10,y+24],[x+9,y+18],[x+14,y+11],[x+21,y+6],
        [x+28,y+5],[x+24,y+10],[x+33,y+9],[x+29,y+14],
        [x+36,y+15],[x+31,y+20],[x+23,y+25],[x+15,y+27]
    ], "color": base})
    feather_rows = [
        ([[x+12,y+22],[x+17,y+14],[x+22,y+9]], highlight),
        ([[x+16,y+25],[x+23,y+17],[x+29,y+12]], detail),
        ([[x+21,y+26],[x+29,y+20],[x+35,y+17]], highlight),
        ([[x+25,y+26],[x+33,y+23],[x+37,y+21]], detail),
    ]
    for points, color in feather_rows:
        out.append({"type": "line", "part": "feather", "points": points, "color": color, "width": 2})

    # Five legs are drawn first so the torso naturally occludes their upper joints.
    # Two hind legs plus three clustered forelegs create the classic double-aspect five-leg read.
    leg_positions = (8, 19, 37, 44, 51)
    for index, offset in enumerate(leg_positions):
        lx = x + offset
        top = y + (28 if index in (0, 4) else 30)
        knee = y + (35 if index % 2 == 0 else 36)
        hoof_y = y + 41
        leg_color = base if index in (1, 3) else shade
        out.append({"type": "polygon", "part": "leg", "leg_index": index, "points": [
            [lx,top],[lx+4,top],[lx+4,knee],[lx+5,hoof_y-2],
            [lx+4,hoof_y],[lx-1,hoof_y],[lx-1,knee+1]
        ], "color": leg_color})
        out.append({"type": "line", "part": "leg-highlight", "points": [
            [lx+1,top+2],[lx+1,knee]
        ], "color": highlight})
        out.append({"type": "polygon", "part": "hoof", "points": [
            [lx-1,hoof_y-1],[lx+4,hoof_y-1],
            [lx+5,hoof_y+1],[lx-1,hoof_y+1]
        ], "color": shade})

    # Heavy bull torso: high shoulder, broad flank, chest and separate belly plane.
    out.append({"type": "polygon", "part": "body", "points": [
        [x+6,y+25],[x+10,y+20],[x+18,y+18],[x+30,y+18],
        [x+39,y+20],[x+46,y+24],[x+49,y+30],
        [x+45,y+35],[x+34,y+37],[x+16,y+36],
        [x+8,y+33],[x+5,y+29]
    ], "color": base})
    out.append({"type": "polygon", "part": "belly", "points": [
        [x+12,y+30],[x+20,y+29],[x+34,y+30],
        [x+43,y+29],[x+45,y+33],[x+38,y+36],
        [x+18,y+35],[x+11,y+33]
    ], "color": shade})
    out.append({"type": "polygon", "part": "shoulder-shadow", "points": [
        [x+31,y+21],[x+39,y+22],[x+44,y+26],
        [x+43,y+31],[x+37,y+32],[x+33,y+28]
    ], "color": shade})
    out.append({"type": "line", "part": "shoulder-highlight", "points": [
        [x+34,y+22],[x+40,y+24],[x+43,y+27]
    ], "color": highlight, "width": 2})
    out.append({"type": "line", "part": "back-highlight", "points": [
        [x+11,y+21],[x+23,y+19],[x+34,y+20],[x+41,y+23]
    ], "color": highlight, "width": 2})
    out.append({"type": "line", "part": "muscle-detail", "points": [
        [x+16,y+25],[x+22,y+28],[x+30,y+28]
    ], "color": detail})
    out.append({"type": "line", "part": "muscle-detail", "points": [
        [x+35,y+25],[x+39,y+28],[x+38,y+31]
    ], "color": shade})

    # Tail and tuft, clearly separated from the wing and rear leg.
    out.append({"type": "line", "part": "tail", "points": [
        [x+8,y+23],[x+4,y+28],[x+3,y+33]
    ], "color": shade, "width": 2})
    out.append({"type": "polygon", "part": "tail-tuft", "points": [
        [x+1,y+31],[x+4,y+32],[x+5,y+36],[x+2,y+35]
    ], "color": detail})

    # Assyrian harness, chest collar and rosette.
    out.append({"type": "line", "part": "harness", "points": [
        [x+24,y+20],[x+27,y+27],[x+33,y+30],[x+40,y+29]
    ], "color": detail, "width": 2})
    out.append({"type": "line", "part": "collar", "points": [
        [x+39,y+22],[x+43,y+26],[x+45,y+30]
    ], "color": detail, "width": 2})
    out.append({"type": "pixel", "part": "rosette", "x": x+28, "y": y+27, "color": highlight})
    out.append({"type": "pixel", "part": "rosette", "x": x+27, "y": y+28, "color": highlight})
    out.append({"type": "pixel", "part": "rosette", "x": x+29, "y": y+28, "color": highlight})
    out.append({"type": "pixel", "part": "rosette", "x": x+28, "y": y+29, "color": detail})

    # Human head in profile, with a distinct nose, eye, beard and horned royal crown.
    out.append({"type": "polygon", "part": "human-face", "points": [
        [x+45,y+10],[x+48,y+8],[x+53,y+8],[x+56,y+11],
        [x+57,y+16],[x+55,y+20],[x+53,y+22],
        [x+48,y+22],[x+46,y+19],[x+44,y+15]
    ], "color": highlight})
    out.append({"type": "polygon", "part": "hair", "points": [
        [x+43,y+12],[x+44,y+7],[x+48,y+5],
        [x+53,y+5],[x+56,y+9],[x+55,y+12],
        [x+52,y+10],[x+47,y+11]
    ], "color": shade})
    # Front-facing royal head: paired eyes, central nose, beard and horned crown.
    out.append({"type": "polygon", "part": "horn", "points": [
        [x+44,y+8],[x+41,y+3],[x+44,y+4],[x+47,y+8]
    ], "color": highlight})
    out.append({"type": "polygon", "part": "horn", "points": [
        [x+52,y+7],[x+55,y+2],[x+56,y+6],[x+55,y+9]
    ], "color": highlight})
    out.append({"type": "rect", "part": "crown", "x": x+45, "y": y+6, "w": 9, "h": 2, "color": detail})
    out.append({"type": "line", "part": "brow", "points": [
        [x+47,y+12],[x+54,y+12]
    ], "color": shade, "width": 2})
    out.append({"type": "pixel", "part": "eye", "x": x+48, "y": y+14, "color": detail})
    out.append({"type": "pixel", "part": "eye", "x": x+53, "y": y+14, "color": detail})
    out.append({"type": "line", "part": "nose-bridge", "points": [
        [x+51,y+14],[x+51,y+18]
    ], "color": shade})
    out.append({"type": "polygon", "part": "nose", "points": [
        [x+49,y+18],[x+53,y+18],[x+54,y+20],[x+50,y+21],[x+48,y+20]
    ], "color": highlight})
    out.append({"type": "line", "part": "mouth", "points": [
        [x+49,y+22],[x+53,y+22]
    ], "color": detail})
    out.append({"type": "polygon", "part": "beard", "points": [
        [x+46,y+21],[x+54,y+21],[x+56,y+25],
        [x+54,y+30],[x+50,y+31],[x+46,y+28],[x+45,y+24]
    ], "color": shade})
    for offset in (0, 3, 6):
        out.append({"type": "line", "part": "beard-curl", "points": [
            [x+47+offset//2,y+22+offset//3],
            [x+49+offset//2,y+24+offset//3],
            [x+48+offset//2,y+26+offset//3]
        ], "color": highlight})
    out.append({"type": "line", "part": "headband", "points": [
        [x+45,y+9],[x+52,y+8]
    ], "color": highlight})

    detail_scale = int(op.get("_detail_scale", 1))
    if detail_scale > 1:
        for primitive in out:
            for key in ("x", "y"):
                if key in primitive:
                    anchor = x if key == "x" else y
                    primitive[key] = anchor + (primitive[key] - anchor) * detail_scale
            for key in ("w", "h", "width", "stroke"):
                if key in primitive:
                    primitive[key] *= detail_scale
            if "points" in primitive:
                primitive["points"] = [
                    [x + (px - x) * detail_scale, y + (py - y) * detail_scale]
                    for px, py in primitive["points"]
                ]
        # One-pixel accents now fit inside the doubled forms: they add information,
        # not a blurred upscale or a blanket of random noise.
        if detail_scale >= 2:
            out.extend([
                {"type": "line", "part": "micro-feather", "points": [[x+25*detail_scale+1,y+9*detail_scale+1],[x+21*detail_scale+1,y+14*detail_scale+1]], "color": highlight},
                {"type": "line", "part": "micro-feather", "points": [[x+31*detail_scale+1,y+13*detail_scale+1],[x+27*detail_scale+1,y+18*detail_scale+1]], "color": detail},
                {"type": "line", "part": "micro-feather", "points": [[x+36*detail_scale+1,y+17*detail_scale+1],[x+32*detail_scale+1,y+21*detail_scale+1]], "color": highlight},
                {"type": "pixel", "part": "coat-grain", "x": x+17*detail_scale+1, "y": y+24*detail_scale+1, "color": highlight},
                {"type": "pixel", "part": "coat-grain", "x": x+20*detail_scale+1, "y": y+27*detail_scale+1, "color": detail},
                {"type": "line", "part": "muscle-crease", "points": [[x+18*detail_scale+1,y+29*detail_scale+1],[x+23*detail_scale+1,y+30*detail_scale+1]], "color": highlight},
                {"type": "line", "part": "harness-engraving", "points": [[x+31*detail_scale+1,y+25*detail_scale+1],[x+34*detail_scale+1,y+28*detail_scale+1]], "color": highlight},
                {"type": "pixel", "part": "eye-glint", "x": x+49*detail_scale+1, "y": y+14*detail_scale+1, "color": highlight},
                {"type": "line", "part": "beard-engraving", "points": [[x+47*detail_scale+1,y+25*detail_scale+1],[x+49*detail_scale+1,y+27*detail_scale+1]], "color": detail},
                {"type": "line", "part": "beard-engraving", "points": [[x+52*detail_scale+1,y+24*detail_scale+1],[x+54*detail_scale+1,y+26*detail_scale+1]], "color": highlight},
                {"type": "line", "part": "hoof-seam", "points": [[x+8*detail_scale+1,y+40*detail_scale+1],[x+12*detail_scale+1,y+40*detail_scale+1]], "color": highlight},
                {"type": "line", "part": "hoof-seam", "points": [[x+44*detail_scale+1,y+40*detail_scale+1],[x+48*detail_scale+1,y+40*detail_scale+1]], "color": highlight},
            ])

    return out

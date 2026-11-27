"""Deterministic stepped-pixel Lamassu guardian sprite."""
from __future__ import annotations


def expand_lamassu(op: dict) -> list[dict]:
    x, y = int(op.get("x", 0)), int(op.get("y", 0))
    w, h = int(op.get("w", 0)), int(op.get("h", 0))
    if w < 44 or h < 34:
        raise ValueError("lamassu_sprite requires a canvas of at least 44x34 logical pixels")
    base = op.get("color", "#D9AD62")
    shade = op.get("shade", "#9C7746")
    highlight = op.get("highlight", "#F0D8A5")
    detail = op.get("detail", "#365564")
    out: list[dict] = []

    # Broad wing rises behind the bull's shoulder; stepped feathers stay grouped.
    out.append({"type": "polygon", "points": [
        [x+8,y+18],[x+6,y+11],[x+10,y+6],[x+15,y+2],
        [x+20,y+1],[x+22,y+4],[x+18,y+9],[x+25,y+6],
        [x+28,y+9],[x+23,y+14],[x+28,y+15],[x+25,y+20],
        [x+14,y+23]
    ], "color": shade})
    out.append({"type": "polygon", "points": [
        [x+10,y+16],[x+11,y+10],[x+16,y+5],[x+19,y+4],
        [x+17,y+10],[x+23,y+8],[x+20,y+13],
        [x+25,y+13],[x+21,y+18],[x+14,y+20]
    ], "color": base})
    for index, points in enumerate((
        [[x+12,y+14],[x+16,y+8],[x+18,y+7]],
        [[x+16,y+16],[x+20,y+11],[x+23,y+10]],
        [[x+19,y+18],[x+23,y+15],[x+25,y+15]],
    )):
        out.append({"type": "line", "points": points, "color": highlight if index == 0 else detail})

    # Powerful bull torso and raised shoulder.
    out.append({"type": "polygon", "points": [
        [x+7,y+18],[x+12,y+14],[x+28,y+14],[x+34,y+17],
        [x+36,y+23],[x+32,y+27],[x+12,y+27],[x+7,y+23]
    ], "color": base})
    out.append({"type": "polygon", "points": [
        [x+10,y+22],[x+16,y+20],[x+31,y+21],
        [x+33,y+25],[x+29,y+27],[x+12,y+26]
    ], "color": shade})
    out.append({"type": "line", "points": [[x+12,y+16],[x+27,y+16]], "color": highlight})

    # Five legs preserve the distinctive guardian profile in Assyrian reliefs.
    for lx in (x+8, x+15, x+22, x+30, x+37):
        leg_top = y+24 if lx < x+30 else y+22
        out.append({"type": "polygon", "points": [
            [lx,leg_top],[lx+3,leg_top],[lx+3,y+30],
            [lx+5,y+31],[lx-1,y+31],[lx,y+29]
        ], "color": shade})
        out.append({"type": "line", "points": [[lx+1,leg_top+1],[lx+1,y+28]], "color": highlight})
        out.append({"type": "rect", "x": lx-1, "y": y+30, "w": 6, "h": 3, "color": detail})

    # Human head, beard, brow and horned crown facing right.
    out.append({"type": "rect", "x": x+31, "y": y+7, "w": 9, "h": 10, "color": base})
    out.append({"type": "polygon", "points": [
        [x+30,y+9],[x+33,y+5],[x+39,y+5],[x+42,y+9],
        [x+41,y+15],[x+37,y+18],[x+32,y+16]
    ], "color": highlight})
    out.append({"type": "polygon", "points": [
        [x+31,y+6],[x+32,y+2],[x+35,y+5],
        [x+39,y+4],[x+42,y+1],[x+41,y+7]
    ], "color": shade})
    out.append({"type": "polygon", "points": [
        [x+32,y+15],[x+38,y+15],[x+39,y+21],
        [x+36,y+24],[x+33,y+21]
    ], "color": shade})
    out.append({"type": "line", "points": [[x+34,y+10],[x+38,y+10]], "color": detail})
    out.append({"type": "pixel", "x": x+38, "y": y+11, "color": detail})
    out.append({"type": "line", "points": [[x+34,y+6],[x+39,y+6]], "color": highlight})
    out.append({"type": "line", "points": [[x+34,y+18],[x+37,y+21]], "color": highlight})
    return out

"""Deterministic Assyrian Lamassu guardian sprite built from hard-edged pixel clusters."""
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

    # Tall feathered wing, kept behind the body as one readable stepped silhouette.
    out.append({"type": "polygon", "points": [
        [x+7,y+20],[x+5,y+14],[x+7,y+9],[x+12,y+4],
        [x+18,y+1],[x+23,y+2],[x+20,y+6],[x+27,y+4],
        [x+30,y+7],[x+25,y+11],[x+30,y+12],
        [x+27,y+17],[x+18,y+22]
    ], "color": shade})
    out.append({"type": "polygon", "points": [
        [x+10,y+17],[x+10,y+12],[x+15,y+7],[x+19,y+5],
        [x+17,y+10],[x+24,y+7],[x+21,y+12],
        [x+26,y+12],[x+22,y+16],[x+17,y+19]
    ], "color": base})
    # Three long feather bands create a wing fan rather than a flat triangular patch.
    for points, color in (
        ([[x+12,y+15],[x+16,y+9],[x+19,y+7]], highlight),
        ([[x+15,y+17],[x+21,y+11],[x+24,y+9]], detail),
        ([[x+18,y+19],[x+24,y+15],[x+27,y+14]], highlight),
    ):
        out.append({"type": "line", "points": points, "color": color})

    # Bull's back, chest and muscular flank; the highlight separates shoulder from wing.
    out.append({"type": "polygon", "points": [
        [x+6,y+20],[x+10,y+16],[x+17,y+15],[x+25,y+16],
        [x+31,y+18],[x+35,y+21],[x+34,y+27],
        [x+29,y+29],[x+12,y+28],[x+7,y+25]
    ], "color": base})
    out.append({"type": "polygon", "points": [
        [x+9,y+23],[x+15,y+21],[x+26,y+22],
        [x+32,y+24],[x+30,y+28],[x+13,y+27]
    ], "color": shade})
    out.append({"type": "line", "points": [[x+11,y+17],[x+25,y+17],[x+31,y+20]], "color": highlight})
    # Assyrian rosette harness and a segmented chest collar.
    out.append({"type": "line", "points": [[x+17,y+18],[x+19,y+22],[x+22,y+23]], "color": detail})
    out.append({"type": "pixel", "x": x+20, "y": y+21, "color": highlight})
    out.append({"type": "pixel", "x": x+19, "y": y+22, "color": highlight})
    out.append({"type": "pixel", "x": x+21, "y": y+22, "color": highlight})
    out.append({"type": "line", "points": [[x+27,y+18],[x+30,y+21]], "color": detail})

    # Five distinct legs: four grouped under the body and one forward leg.
    for index, lx in enumerate((x+8, x+15, x+23, x+30, x+36)):
        top = y + (23 if index in (0, 4) else 25)
        knee = y + (28 if index in (1, 3) else 29)
        foot = y + 32
        leg_color = shade if index % 2 == 0 else base
        out.append({"type": "polygon", "points": [
            [lx,top],[lx+4,top],[lx+4,knee],
            [lx+6,foot-1],[lx+5,foot],[lx-2,foot],
            [lx-1,knee+1]
        ], "color": leg_color})
        out.append({"type": "line", "points": [[lx+1,top+1],[lx+1,knee]], "color": highlight})
        out.append({"type": "line", "points": [[lx-1,foot-1],[lx+5,foot-1]], "color": detail})

    # Human head turned right, with tiered beard, eye, brow and paired horned crown.
    out.append({"type": "polygon", "points": [
        [x+34,y+8],[x+37,y+5],[x+42,y+6],
        [x+44,y+10],[x+43,y+16],[x+40,y+19],
        [x+35,y+17],[x+33,y+13]
    ], "color": highlight})
    out.append({"type": "polygon", "points": [
        [x+34,y+7],[x+35,y+3],[x+38,y+6],
        [x+40,y+3],[x+42,y+1],[x+43,y+6],
        [x+45,y+8],[x+42,y+9],[x+40,y+7],[x+37,y+9]
    ], "color": shade})
    out.append({"type": "line", "points": [[x+35,y+9],[x+40,y+9]], "color": detail})
    out.append({"type": "pixel", "x": x+40, "y": y+10, "color": detail})
    out.append({"type": "polygon", "points": [
        [x+35,y+15],[x+41,y+15],[x+42,y+20],
        [x+40,y+24],[x+37,y+22],[x+34,y+18]
    ], "color": shade})
    out.append({"type": "line", "points": [[x+36,y+17],[x+40,y+20],[x+39,y+22]], "color": highlight})
    # Ear, cheek plane and small royal headband.
    out.append({"type": "pixel", "x": x+34, "y": y+12, "color": base})
    out.append({"type": "line", "points": [[x+35,y+7],[x+41,y+7]], "color": highlight})
    out.append({"type": "pixel", "x": x+38, "y": y+6, "color": detail})
    return out

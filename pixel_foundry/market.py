"""Hand-built foreground wares for the Babylon night market."""

def expand_market_props(op: dict) -> list[dict]:
    x, y = int(op.get("x", 0)), int(op.get("y", 0))
    w, h = int(op.get("w", 0)), int(op.get("h", 0))
    if w < 58 or h < 20:
        raise ValueError("market_props requires at least 58x20 logical pixels")
    unit = max(1, w // 58)
    dark = op.get("outline", "dark")
    shade = op.get("shade", "sand_shadow")
    base = op.get("base", "sand")
    light = op.get("highlight", "sand_light")
    gold = op.get("gold", "gold")
    teal = op.get("accent", "teal")
    wood = op.get("wood", "blue_stone")
    deep = op.get("deep", "night")
    out = []

    def polygon(part, points, color):
        out.append({"type":"polygon","part":part,
                    "points":[[x+px*unit,y+py*unit] for px,py in points],
                    "color":color})

    def line(part, points, color, width=1):
        out.append({"type":"line","part":part,
                    "points":[[x+px*unit,y+py*unit] for px,py in points],
                    "color":color,"width":max(1,width*unit)})

    def rect(part, rx, ry, rw, rh, color):
        out.append({"type":"rect","part":part,"x":x+rx*unit,"y":y+ry*unit,
                    "w":rw*unit,"h":rh*unit,"color":color})

    # Tall glazed amphora: neck, shoulder, belly, handles and two kiln bands.
    polygon("amphora-outline",[(2,5),(4,3),(8,3),(10,5),(10,8),(12,11),
             (11,16),(9,18),(3,18),(1,16),(0,11),(2,8)],dark)
    polygon("amphora-body",[(3,6),(5,5),(8,5),(9,7),(10,11),
             (9,15),(8,17),(4,17),(2,15),(2,11)],shade)
    polygon("amphora-glaze",[(4,7),(7,6),(8,8),(9,11),(8,15),
             (7,16),(4,16),(3,14),(3,10)],base)
    rect("amphora-neck",5,1,3,4,shade)
    rect("amphora-lip",4,0,5,2,gold)
    line("amphora-rim-glint",[(4,0),(8,0)],light)
    line("amphora-left-handle",[(3,6),(1,7),(1,10),(3,11)],gold)
    line("amphora-right-handle",[(9,6),(11,7),(11,10),(9,11)],light)
    line("amphora-shoulder-light",[(4,7),(5,6),(7,6)],light)
    line("amphora-kiln-band",[(3,12),(8,12)],gold)
    line("amphora-foot",[(4,17),(8,17)],shade)

    # Low bowl with a glazed rim and visible inner shadow.
    polygon("market-bowl-outline",[(14,12),(16,10),(21,10),(23,12),
             (22,17),(20,19),(16,19),(14,17)],dark)
    polygon("market-bowl-body",[(15,12),(17,11),(20,11),(22,12),
             (21,16),(19,18),(17,18),(15,16)],base)
    line("market-bowl-rim",[(14,12),(17,11),(20,11),(23,12)],light)
    line("market-bowl-interior",[(16,13),(18,14),(21,13)],shade)
    line("market-bowl-foot",[(17,19),(20,19)],gold)

    # Woven basket with alternating reed rows and a dark mouth.
    polygon("basket-outline",[(26,10),(28,8),(33,8),(35,10),
             (34,18),(32,19),(28,19),(26,18)],dark)
    polygon("basket-body",[(27,11),(29,9),(32,9),(34,11),
             (33,17),(31,19),(29,19),(27,17)],shade)
    line("basket-rim",[(26,10),(28,8),(33,8),(35,10)],light)
    for row in (12,14,16,18):
        line("basket-weave",[(27,row),(33,row)],gold if row%4==0 else light)
    for column in (29,31,33):
        line("basket-reed",[(column,10),(column,18)],base)

    # A sturdy timber crate, cross-braced and visibly separated into planks.
    rect("crate-outline",38,5,11,15,dark)
    rect("crate-wood",39,6,9,13,wood)
    line("crate-top",[(39,6),(47,6)],light)
    line("crate-plank-left",[(42,7),(42,18)],shade)
    line("crate-plank-right",[(45,7),(45,18)],shade)
    line("crate-cross-brace",[(39,7),(47,17)],gold,2)
    line("crate-cross-brace-shadow",[(47,7),(39,17)],deep)
    line("crate-bottom",[(40,18),(46,18)],light)

    # Hanging dyed rug: border, stepped medallion and short fringe.
    rect("hanging-rug-outline",49,2,5,18,dark)
    rect("hanging-rug-cloth",50,3,3,15,teal)
    line("rug-border-top",[(50,4),(52,4)],gold)
    line("rug-border-bottom",[(50,16),(52,16)],gold)
    line("rug-medallion",[(51,6),(52,8),(51,10),(50,8),(51,6)],light)
    line("rug-fringe",[(50,18),(50,19)],gold)
    line("rug-fringe",[(52,18),(52,19)],gold)

    # Small oil lantern with metal cage and a bright glass core.
    line("market-lantern-chain",[(56,1),(56,3)],gold)
    rect("market-lantern-frame",53,3,5,9,dark)
    rect("market-lantern-glass",54,4,3,7,"moon")
    line("market-lantern-cage",[(54,4),(54,10)],gold)
    line("market-lantern-cage",[(56,4),(56,10)],gold)
    line("market-lantern-cap",[(53,3),(57,3)],light)
    line("market-lantern-base",[(53,12),(57,12)],gold)
    out.append({"type":"pixel","part":"market-lantern-flame",
                "x":x+55*unit,"y":y+6*unit,"color":light})
    out.append({"type":"pixel","part":"market-lantern-glow-spill",
                "x":x+55*unit,"y":y+13*unit,"color":gold})
    return out

from pixel_foundry.generators import expand_generator

def test_ziggurat_generator_creates_stepped_tiers():
    spec={"type":"stepped_ziggurat","x":10,"y":10,"w":60,"h":50,"tiers":5,
          "tier_h":7,"inset":5,"color":"#AA8866","shade":"#553322",
          "highlight":"#EEDD99","side_color":"#553322","top_color":"#EEDD99"}
    ops=expand_generator(spec)
    rects=[op for op in ops if op["type"]=="rect"]
    assert len(rects)>=6
    widths=[op["w"] for op in rects[:5]]
    assert widths==sorted(widths,reverse=True)
    assert expand_generator(spec)==ops

from pixel_foundry.generators import expand_generator

def test_ziggurat_generator_creates_stepped_tiers():
    spec={"type":"stepped_ziggurat","x":10,"y":10,"w":60,"h":50,"tiers":5,
          "tier_h":7,"inset":5,"color":"#AA8866","shade":"#553322",
          "highlight":"#EEDD99","side_color":"#553322","top_color":"#EEDD99"}
    ops=expand_generator(spec)
    rects=[op for op in ops if op["type"]=="rect"]
    assert len(rects)>=6
    widths=[op["w"] for op in rects[::2][:5]]
    assert widths==sorted(widths,reverse=True)
    assert expand_generator(spec)==ops

def test_column_and_archway_generators_emit_valid_primitives():
    column=expand_generator({"type":"column","x":0,"y":0,"w":14,"h":32,
                             "color":"#AA8866","shade":"#553322","highlight":"#EEDD99"})
    arch=expand_generator({"type":"archway","x":0,"y":0,"w":40,"h":28,
                           "color":"#AA8866","shade":"#553322","highlight":"#EEDD99"})
    assert any(op["type"]=="rect" for op in column)
    assert any(op["type"]=="line" for op in column)
    assert len([op for op in arch if op["type"]=="rect"])>=5

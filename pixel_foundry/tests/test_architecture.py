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


def test_babylon_art_bible_has_distinct_city_facades_and_paved_street():
    import json
    from pathlib import Path

    art_bible = json.loads(
        (Path(__file__).resolve().parents[1] / "examples" / "babylon_art_bible.json")
        .read_text(encoding="utf-8")
    )
    all_ops = [op for layer in art_bible["layers"] for op in layer["ops"]]
    facades = [op for op in all_ops if op.get("type") == "brick_wall"]
    streets = [op for op in all_ops if op.get("type") == "stone_floor"]
    assert len(facades) >= 4
    assert len({op["seed"] for op in facades}) == 2
    assert len(streets) == 1
    assert streets[0]["seed"] == 20261128
    assert art_bible["pixel_scale"] == 2



def test_generator_bounds_and_material_dimensions_scale_on_dense_grid():
    from pixel_foundry.scene import _scale_operation

    floor = _scale_operation({
        "type": "stone_floor", "x": 10, "y": 20, "w": 30, "h": 12,
        "block_w": 12, "block_h": 5,
    }, 2)
    assert (floor["x"], floor["y"], floor["w"], floor["h"]) == (20, 40, 60, 24)
    assert (floor["block_w"], floor["block_h"]) == (24, 10)

    frieze = _scale_operation({
        "type": "temple_facade", "x": 5, "y": 8, "w": 40, "h": 9,
        "rosette_spacing": 12,
    }, 2)
    assert (frieze["x"], frieze["y"], frieze["w"], frieze["h"]) == (10, 16, 80, 18)
    assert frieze["rosette_spacing"] == 24

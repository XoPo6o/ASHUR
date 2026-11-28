from pixel_foundry.generators import expand_generator
from pixel_foundry.scene import _scale_operation
from pixel_foundry.art_director import build_scene_spec, validate_art_bible
import json
from pathlib import Path


def test_traveler_bitmap_is_a_fixed_native_40_by_56_sprite():
    ops = expand_generator({"type":"traveler_bitmap","x":10,"y":20,"_detail_scale":1})
    assert len(ops) == 1251
    assert all(op["type"] == "pixel" for op in ops)
    assert {op["part"] for op in ops} >= {
        "traveler-bitmap-K", "traveler-bitmap-D", "traveler-bitmap-S",
        "traveler-bitmap-C", "traveler-bitmap-H", "traveler-bitmap-G",
        "traveler-bitmap-P", "traveler-bitmap-F",
    }
    assert min(op["x"] for op in ops) >= 10
    assert max(op["x"] for op in ops) < 50
    assert min(op["y"] for op in ops) >= 20
    assert max(op["y"] for op in ops) < 76


def test_traveler_bitmap_keeps_native_pixel_density_on_dense_scene_grid():
    op = _scale_operation({"type":"traveler_bitmap","x":70,"y":53,"w":40,"h":56},2)
    assert (op["x"],op["y"],op["_detail_scale"]) == (140,106,1)
    ops = expand_generator(op)
    assert len(ops) == 1251
    assert all(item["type"] == "pixel" for item in ops)
    assert max(item["x"] for item in ops) < 180
    assert max(item["y"] for item in ops) < 162


def test_babylon_art_bible_uses_hand_authored_traveler_and_valid_skin_ramp():
    path = Path("pixel_foundry/examples/babylon_art_bible.json")
    bible = json.loads(path.read_text(encoding="utf-8"))
    assert validate_art_bible(bible) == []
    assert bible["palette"]["ramps"]["skin"] == ["skin_shadow","skin_mid","sand_light"]
    traveler = [op for layer in bible["layers"] for op in layer["ops"]
                if op["type"] == "traveler_bitmap"]
    assert len(traveler) == 1
    assert traveler[0]["w"] == 40 and traveler[0]["h"] == 56
    scene = build_scene_spec(bible)
    assert scene["metadata"]["pixel_scale"] == 2

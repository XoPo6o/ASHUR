import pytest

from pixel_foundry.generators import expand_generator
from pixel_foundry.lamassu import expand_lamassu


def test_lamassu_has_five_legs_and_assyrian_features():
    spec = {
        "type": "lamassu_sprite", "x": 10, "y": 8, "w": 60, "h": 43,
        "color": "#D9AD62", "shade": "#9C7746",
        "highlight": "#F0D8A5", "detail": "#365564",
    }
    ops = expand_generator(spec)
    assert ops == expand_lamassu(spec)
    assert len([op for op in ops if op.get("part") == "leg"]) == 5
    leg_x = [op["points"][0][0] for op in ops if op.get("part") == "leg"]
    assert [value - spec["x"] for value in leg_x] == [8, 19, 37, 44, 51]
    parts = {op.get("part") for op in ops}
    assert {"wing", "feather", "body", "human-face", "horn", "beard", "rosette",
            "feather-barb", "wing-quill", "rib-engraving", "leg-joint",
            "shin-plane", "hoof-seam", "crown-band", "horn-ridge",
            "eye-socket", "ear", "moustache"} <= parts
    assert sum(op.get("part") == "leg-joint" for op in ops) == 5
    assert sum(op.get("part") == "hoof-seam" for op in ops) == 5
    assert sum(op.get("part") == "feather-barb" for op in ops) >= 7
    assert all(op["type"] in {"polygon", "line", "rect", "pixel"} for op in ops)


def test_lamassu_geometry_stays_inside_declared_canvas():
    spec = {"type": "lamassu_sprite", "x": 10, "y": 8, "w": 60, "h": 43}
    for op in expand_lamassu(spec):
        if "points" in op:
            for px, py in op["points"]:
                assert spec["x"] <= px < spec["x"] + spec["w"]
                assert spec["y"] <= py < spec["y"] + spec["h"]
        if "x" in op and "y" in op:
            assert spec["x"] <= op["x"] < spec["x"] + spec["w"]
            assert spec["y"] <= op["y"] < spec["y"] + spec["h"]
            if "w" in op:
                assert op["x"] + op["w"] <= spec["x"] + spec["w"]
            if "h" in op:
                assert op["y"] + op["h"] <= spec["y"] + spec["h"]


def test_lamassu_rejects_canvas_that_would_clip_horns_or_hooves():
    with pytest.raises(ValueError, match="60x43"):
        expand_lamassu({"x": 0, "y": 0, "w": 58, "h": 42})


def test_lamassu_expands_anatomy_on_high_density_grid():
    from pixel_foundry.lamassu import expand_lamassu

    spec = {
        "type": "lamassu_sprite", "x": 20, "y": 10, "w": 60, "h": 43,
        "_detail_scale": 2, "color": "#D9AD62",
        "shade": "#9C7746", "highlight": "#F0D8A5", "detail": "#365564",
    }
    parts = expand_lamassu(spec)
    face = next(item for item in parts if item.get("part") == "human-face")
    body = next(item for item in parts if item.get("part") == "body")
    assert min(point[0] for point in face["points"]) == 20 + 44 * 2
    assert max(point[0] for point in body["points"]) == 20 + 49 * 2
    assert spec["x"] == 20 and spec["y"] == 10
    micro_parts = {item.get("part") for item in parts}
    assert {"micro-feather", "coat-grain", "muscle-crease",
            "harness-engraving", "eye-glint", "beard-engraving",
            "hoof-seam", "wing-quill-glint", "rib-highlight",
            "neck-engraving", "crown-engraving"} <= micro_parts



def test_lamassu_wing_uses_separate_overlapping_feather_plates():
    spec = {
        "type": "lamassu_sprite", "x": 10, "y": 8, "w": 60, "h": 43,
        "color": "#D9AD62", "shade": "#9C7746",
        "highlight": "#F0D8A5", "detail": "#365564",
    }
    ops = expand_lamassu(spec)
    plates = [op for op in ops if op.get("part") == "wing-feather-plate"]
    assert len(plates) == 4
    assert [op["feather_index"] for op in plates] == [0, 1, 2, 3]
    assert all(op["type"] == "polygon" and len(op["points"]) >= 6 for op in plates)
    assert sum(op.get("part") == "wing-feather-edge" for op in ops) == 4
    assert sum(op.get("part") == "wing-feather-separation" for op in ops) == 4
    for op in plates:
        for px, py in op["points"]:
            assert spec["x"] <= px < spec["x"] + spec["w"]
            assert spec["y"] <= py < spec["y"] + spec["h"]



def test_lamassu_has_separated_shoulder_haunch_and_neck_mane_planes():
    spec = {
        "type": "lamassu_sprite", "x": 10, "y": 8, "w": 60, "h": 43,
        "color": "#D9AD62", "shade": "#9C7746",
        "highlight": "#F0D8A5", "detail": "#365564",
    }
    ops = expand_lamassu(spec)
    parts = {op.get("part") for op in ops}
    assert {
        "haunch-shadow-plane", "haunch-light-ridge",
        "shoulder-muscle-plane", "shoulder-muscle-cut", "mane-lock",
    } <= parts
    assert sum(op.get("part") == "mane-lock" for op in ops) == 4
    assert sum(op.get("part") == "wing-feather-plate" for op in ops) == 4


def test_lamassu_uses_midtones_to_separate_body_and_face_planes():
    spec={"type":"lamassu_sprite","x":10,"y":8,"w":60,"h":43,
          "color":"sand","shade":"sand_shadow","highlight":"sand_light",
          "mid":"bronze_mid","detail":"blue_stone"}
    ops=expand_lamassu(spec)
    parts={op.get("part") for op in ops}
    assert {"body-midplane","flank-midplane","human-face-midplane"} <= parts
    assert all(next(op for op in ops if op.get("part")==part)["color"]=="bronze_mid"
               for part in ("body-midplane","flank-midplane","human-face-midplane"))
    plates=[op for op in ops if op.get("part")=="wing-feather-plate"]
    assert any(op["color"]=="bronze_mid" for op in plates)


def test_lamassu_sprite_scale_reduces_footprint_without_losing_detail():
    from pixel_foundry.lamassu import expand_lamassu

    full = expand_lamassu({"type":"lamassu_sprite","x":10,"y":10,"w":60,"h":43})
    compact = expand_lamassu({"type":"lamassu_sprite","x":10,"y":10,"w":60,"h":43,
                              "sprite_scale":0.75})
    def bounds(ops):
        xs=[]; ys=[]
        for op in ops:
            if "points" in op:
                xs.extend(p[0] for p in op["points"]); ys.extend(p[1] for p in op["points"])
            elif "x" in op and "y" in op:
                xs.append(op["x"]); ys.append(op["y"])
        return max(xs)-min(xs), max(ys)-min(ys)
    full_w,full_h=bounds(full)
    compact_w,compact_h=bounds(compact)
    assert compact_w < full_w
    assert compact_h < full_h
    assert len(compact) == len(full)

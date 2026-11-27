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
    parts = {op.get("part") for op in ops}
    assert {"wing", "feather", "body", "human-face", "horn", "beard", "rosette"} <= parts
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

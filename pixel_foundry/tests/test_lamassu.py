import pytest

from pixel_foundry.generators import expand_generator


def test_lamassu_sprite_is_deterministic_and_uses_raster_primitives():
    spec = {
        "type": "lamassu_sprite",
        "x": 100,
        "y": 50,
        "w": 48,
        "h": 35,
        "color": "#D9AD62",
        "shade": "#9C7746",
        "highlight": "#F0D8A5",
        "detail": "#365564",
    }
    first = expand_generator(spec)
    assert first == expand_generator(spec)
    assert len(first) >= 20
    assert all(item["type"] in {"polygon", "rect", "line", "pixel"} for item in first)


def test_lamassu_sprite_rejects_too_small_canvas():
    with pytest.raises(ValueError, match="at least 44x30"):
        expand_generator({"type": "lamassu_sprite", "w": 32, "h": 24})

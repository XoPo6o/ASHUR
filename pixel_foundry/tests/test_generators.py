from pixel_foundry.generators import expand_generator


def test_brick_wall_is_deterministic():
    spec={"type":"brick_wall","x":0,"y":0,"w":40,"h":20,"color":"#AA8866","mortar":"#332211","seed":42}
    assert expand_generator(spec)==expand_generator(spec)
    assert len(expand_generator(spec))>4


def test_generator_does_not_mutate_spec():
    spec={"type":"foliage","x":0,"y":0,"w":20,"h":16,"color":"#227744","seed":7}
    before=dict(spec)
    expand_generator(spec)
    assert spec==before


def test_organic_generators_are_seeded_and_emit_raster_primitives():
    specs = [
        {"type":"palm_tree","x":10,"y":10,"w":20,"h":34,"color":"#356B52","shade":"#23483E","highlight":"#9AB36A","seed":8},
        {"type":"cloud_bank","x":10,"y":10,"w":48,"h":14,"color":"#41445C","shade":"#303B59","highlight":"#D8B17A","seed":8},
        {"type":"boulder","x":10,"y":10,"w":18,"h":12,"color":"#916548","shade":"#4A3945","highlight":"#EDC17A","seed":8},
        {"type":"water_surface","x":10,"y":10,"w":48,"h":9,"color":"#286276","shade":"#193C4C","highlight":"#A0C5A9","seed":8},
    ]
    for spec in specs:
        first = expand_generator(spec)
        assert first == expand_generator(spec)
        assert len(first) >= 3
        assert all(item["type"] in {"rect", "line", "pixel", "polygon"} for item in first)


def test_organic_generators_change_with_seed():
    spec={"type":"boulder","x":0,"y":0,"w":20,"h":12,"color":"#916548","shade":"#4A3945","highlight":"#EDC17A"}
    assert expand_generator({**spec,"seed":1}) != expand_generator({**spec,"seed":2})


def test_traveler_sprite_has_distinct_repeatable_poses():
    base={"type":"traveler_sprite","x":10,"y":5,"w":20,"h":34,"color":"#B88B62","shade":"#171827","highlight":"#E8B65A","skin":"#F4E6B8"}
    walk=expand_generator({**base,"pose":"walk"})
    idle=expand_generator({**base,"pose":"idle"})
    drag=expand_generator({**base,"pose":"drag"})
    assert walk == expand_generator({**base,"pose":"walk"})
    assert walk != idle
    assert walk != drag
    assert idle != drag
    assert len(walk) >= 20
    assert all(item["type"] in {"polygon","rect","line","pixel"} for item in walk)


def test_market_stall_is_deterministic_and_has_readable_props():
    spec = {
        "type": "market_stall", "x": 24, "y": 63, "w": 40, "h": 22,
        "color": "#D9AD62", "shade": "#9C7746", "highlight": "#F0D8A5",
        "accent": "#65CFC0", "wood": "#365564", "lantern": "#E9E5D6",
        "detail": "#365564",
    }
    first = expand_generator(spec)
    assert first == expand_generator(spec)
    parts = {op.get("part") for op in first}
    assert {"awning", "awning-stripe", "post", "counter", "market-goods",
            "lantern-frame", "lantern-light"} <= parts
    assert all(op["type"] in {"polygon", "rect", "line", "pixel"} for op in first)


def test_market_stall_rejects_too_small_canvas():
    import pytest
    with pytest.raises(ValueError, match="24x16"):
        expand_generator({"type": "market_stall", "w": 20, "h": 12})


def test_stepped_ziggurat_has_staggered_masonry_and_wear_at_dense_scale():
    spec = {
        "type": "stepped_ziggurat", "x": 10, "y": 8, "w": 140, "h": 100,
        "tiers": 5, "tier_h": 14, "inset": 12,
        "color": "#D9AD62", "shade": "#9C7746", "highlight": "#F0D8A5",
        "top_color": "#D9AD62", "seed": 17,
    }
    first = expand_generator(spec)
    assert first == expand_generator(spec)
    assert sum(op.get("part") == "ziggurat-brick-joint" for op in first) >= 20
    assert sum(op.get("part") == "stone-wear" for op in first) >= 5

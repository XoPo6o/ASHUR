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

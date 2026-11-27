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

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
    assert {"awning", "awning-stripe", "awning-scallop", "canopy-fold",
            "post", "counter", "wood-grain", "wood-knot", "market-goods",
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



def test_temple_facade_has_ordered_carved_reliefs():
    spec = {
        "type": "temple_facade", "x": 20, "y": 12, "w": 64, "h": 16,
        "color": "#D9AD62", "shade": "#9C7746", "highlight": "#F0D8A5",
        "band": "#365564", "relief": "#E9E5D6",
    }
    first = expand_generator(spec)
    assert first == expand_generator(spec)
    parts = {op.get("part") for op in first}
    assert {"frieze-upper-border", "frieze-lower-border", "rosette-core",
            "rosette-petal", "cuneiform-wedge", "frieze-panel-joint"} <= parts


def test_traveler_has_material_details_without_changing_pose_contract():
    spec = {
        "type": "traveler_sprite", "x": 69, "y": 58, "w": 18, "h": 31,
        "pose": "drag", "color": "#D9AD62", "shade": "#050A0E",
        "highlight": "#D9AD62", "skin": "#E9E5D6",
    }
    parts = {op.get("part") for op in expand_generator(spec)}
    assert {"pack-strap", "belt-buckle", "cloak-fold", "cloak-hem-stitch",
            "travel-pouch", "hood-seam", "boot-highlight"} <= parts


def test_brick_wall_has_individual_bevels_and_seeded_material_variation():
    spec = {
        "type": "brick_wall", "x": 0, "y": 0, "w": 72, "h": 28,
        "brick_w": 9, "brick_h": 6, "color": "#B88B62",
        "shade": "#72513D", "highlight": "#E8C58C",
        "mortar": "#352B2A", "seed": 44,
    }
    first = expand_generator(spec)
    assert first == expand_generator(spec)
    faces = [op for op in first if op.get("part") == "brick-face"]
    assert len(faces) >= 12
    assert len({(op["w"], op["h"], op["color"]) for op in faces}) >= 4
    assert sum(op.get("part") == "brick-top-bevel" for op in first) == len(faces)
    assert sum(op.get("part") == "brick-side-shadow" for op in first) == len(faces)
    assert any(op.get("part") == "brick-grain" for op in first)


def test_stone_floor_has_depth_variation_and_individual_surface_marks():
    spec = {
        "type": "stone_floor", "x": 0, "y": 0, "w": 96, "h": 32,
        "block_w": 12, "block_h": 6, "color": "#365564",
        "shade": "#142633", "highlight": "#D9AD62",
        "mortar": "#050A0E", "seed": 2026,
    }
    first = expand_generator(spec)
    assert first == expand_generator(spec)
    slabs = [op for op in first if op.get("part") == "paving-slab"]
    assert len(slabs) >= 12
    assert len({(op["w"], op["h"]) for op in slabs}) >= 5
    assert sum(op.get("part") == "slab-top-bevel" for op in first) == len(slabs)
    assert sum(op.get("part") == "slab-side-shadow" for op in first) == len(slabs)
    assert any(op.get("part") == "stone-vein" for op in first)


def test_temple_columns_and_frieze_have_carved_microdetails():
    facade=expand_generator({"type":"temple_facade","x":0,"y":0,"w":62,"h":9,
        "color":"#D9AD62","shade":"#9C7746","highlight":"#F0D8A5",
        "band":"#9C7746","relief":"#E9E5D6","rosette_spacing":12})
    column=expand_generator({"type":"column","x":0,"y":0,"w":12,"h":29,"shaft_w":8,
        "capital_h":4,"base_h":4,"color":"#D9AD62","shade":"#9C7746",
        "highlight":"#F0D8A5","fluting":True})
    fp={o.get("part") for o in facade}; cp={o.get("part") for o in column}
    assert {"rosette-cut","rosette-engraving","chisel-mark","frieze-wear"} <= fp
    assert {"column-flute","flute-glint","capital-carving","capital-volute",
            "shaft-joint","base-lower-bevel"} <= cp


def test_market_stall_has_distinct_goods_and_hand_finished_materials():
    ops=expand_generator({"type":"market_stall","x":20,"y":65,"w":24,"h":20,
        "color":"#D9AD62","shade":"#9C7746","highlight":"#F0D8A5",
        "accent":"#65CFC0","wood":"#365564","detail":"#050A0E","lantern":"#E9E5D6"})
    parts={o.get("part") for o in ops}
    assert {"canopy-stitch","canopy-hem-stitch","jar-neck","jar-handle",
            "bowl-lip","bowl-foot","produce-glint","produce-stem",
            "counter-peg","wood-knot"} <= parts


def test_traveler_face_and_cloth_have_readable_pixel_features():
    spec = {
        "type": "traveler_sprite", "x": 20, "y": 10, "w": 24, "h": 38,
        "pose": "drag", "color": "#D9AD62", "shade": "#050A0E",
        "highlight": "#F0D8A5", "skin": "#E9E5D6",
    }
    first = expand_generator(spec)
    assert first == expand_generator(spec)
    parts = {op.get("part") for op in first}
    assert {
        "face-shadow-plane", "face-brow", "face-eye", "face-eye-glint",
        "face-nose", "face-cheek", "face-mouth", "face-beard",
        "hood-inner-rim", "cloth-fold-shadow", "cloth-fold-light",
        "tunic-side-seam", "cloak-edge-binding", "cloth-wear-patch",
        "sleeve-cuff-stitch", "boot-sole", "boot-toe-wear",
    } <= parts
    assert sum(op.get("part") == "cloth-fold-shadow" for op in first) == 3

def test_traveler_has_layered_collar_hands_and_hand_finished_gear():
    spec = {
        "type": "traveler_sprite", "x": 67, "y": 53, "w": 22, "h": 36,
        "pose": "drag", "color": "#D9AD62", "shade": "#050A0E",
        "highlight": "#F0D8A5", "skin": "#E9E5D6",
        "trim": "#9C7746", "cloth_shadow": "#9C7746",
        "cloth_light": "#F0D8A5",
    }
    first = expand_generator(spec)
    assert first == expand_generator(spec)
    parts = {op.get("part") for op in first}
    assert {
        "layered-collar-shadow", "collar-gold-piping", "collar-clasp",
        "shoulder-seam-left", "shoulder-seam-right", "cloak-woven-stitch",
        "cloak-woven-shadow", "tunic-embroidered-mark", "sleeve-fold-left",
        "sleeve-fold-right", "hand-palm-light", "hand-thumb", "hand-shadow",
        "boot-vamp-seam", "boot-lace", "boot-heel-shadow",
    } <= parts
    assert sum(op.get("part") == "hand-thumb" for op in first) == 2
    assert sum(op.get("part") == "boot-lace" for op in first) == 2

def test_traveler_is_grounded_with_separate_boot_contact_shadows():
    spec = {
        "type": "traveler_sprite", "x": 67, "y": 53, "w": 22, "h": 36,
        "pose": "drag", "color": "#D9AD62", "shade": "#050A0E",
        "highlight": "#F0D8A5", "skin": "#E9E5D6",
        "ground_shadow": "#050A0E", "contact_shadow": "#050A0E",
        "ground_grit": "#365564",
    }
    ops = expand_generator(spec)
    parts = {op.get("part") for op in ops}
    assert {
        "traveler-ground-shadow", "boot-contact-shadow-left",
        "boot-contact-shadow-right", "ground-grit-left", "ground-grit-right",
    } <= parts
    shadow = next(op for op in ops if op.get("part") == "traveler-ground-shadow")
    assert shadow["type"] == "polygon"
    assert len(shadow["points"]) >= 6
    assert ops.index(shadow) < next(
        i for i, op in enumerate(ops) if op.get("part") == "boot-lace"
    )

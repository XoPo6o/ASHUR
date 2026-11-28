import pytest
from pixel_foundry.art_director import validate_art_bible, build_scene_spec

def sample():
    return {"name":"test","style":"chunky pixel art","canvas":{"width":32,"height":32},
            "pixel_scale":1,"perspective":"frontal","lighting":{"direction":"top_left"},
            "palette":{"colors":{"dark":"#111122","light":"#EEEECC"},
                       "ramps":{"stone":["dark","light"]}},
            "layers":[{"name":"background","ops":[]}]}

def test_art_bible_builds_scene_metadata():
    spec=build_scene_spec(sample())
    assert spec["metadata"]["perspective"]=="frontal"
    assert spec["metadata"]["planning"]["detail_tier"]=="standard"
    assert spec["layers"][0]["name"]=="background"

def test_invalid_art_bible_reports_actionable_errors():
    bible=sample(); bible["perspective"]="random"
    assert any("perspective" in error for error in validate_art_bible(bible))
    with pytest.raises(ValueError):
        build_scene_spec(bible)

def test_material_profile_resolves_palette_roles_without_overwriting_local_choices():
    bible=sample()
    bible["materials"]={"stone":{"ramp":"stone"}}
    bible["layers"][0]["ops"]=[{"type":"rect","material":"stone","color":"#ABCDEF"}]
    spec=build_scene_spec(bible)
    op=spec["layers"][0]["ops"][0]
    assert op["color"]=="#ABCDEF"
    assert op["shade"]=="#111122"
    assert op["highlight"]=="#EEEECC"
    assert op["material_profile"]=="stone"

def test_unknown_material_profile_is_rejected():
    bible=sample()
    bible["layers"][0]["ops"]=[{"type":"rect","material":"marble"}]
    assert any("unknown material" in error for error in validate_art_bible(bible))

def test_planning_contract_rejects_invalid_detail_tier_and_contrast():
    bible=sample()
    bible["planning"]={"detail_tier":"ultra","focal_contrast":1.5}
    errors=validate_art_bible(bible)
    assert any("detail_tier" in error for error in errors)
    assert any("focal_contrast" in error for error in errors)

def test_depth_planes_and_focus_roles_are_preserved_in_scene_spec():
    bible=sample()
    bible["planning"]={"depth_tier":"hero","depth_planes":["background","foreground"]}
    bible["layers"]=[{"name":"sky","depth_plane":"background","focus_role":"background","ops":[]},
                     {"name":"hero","depth_plane":"foreground","focus_role":"primary","ops":[]}]
    spec=build_scene_spec(bible)
    assert spec["layers"][1]["depth_plane"]=="foreground"
    assert spec["layers"][1]["focus_role"]=="primary"

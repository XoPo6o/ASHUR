import pytest
from pixel_foundry.art_director import validate_art_bible, build_scene_spec

def sample():
    return {"name":"test","style":"chunky pixel art","canvas":{"width":32,"height":32},
            "pixel_scale":1,"perspective":"frontal","lighting":{"direction":"top_left"},
            "palette":{"colors":{"dark":"#111122","light":"#EEEECC"}},
            "layers":[{"name":"background","ops":[]}]}

def test_art_bible_builds_scene_metadata():
    spec=build_scene_spec(sample())
    assert spec["metadata"]["perspective"]=="frontal"
    assert spec["layers"][0]["name"]=="background"

def test_invalid_art_bible_reports_actionable_errors():
    bible=sample(); bible["perspective"]="random"
    assert any("perspective" in error for error in validate_art_bible(bible))
    with pytest.raises(ValueError):
        build_scene_spec(bible)

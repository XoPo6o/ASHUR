import pytest
from pixel_foundry.palette import Palette

def test_named_ramps_resolve_to_palette_colors():
    p=Palette.from_data({"colors":{"shadow":"#221122","base":"#774455","light":"#DDAA88"},
                         "ramps":{"stone":["shadow","base","light"]}})
    assert p.ramp("stone")==["shadow","base","light"]

def test_invalid_ramp_reference_is_rejected():
    with pytest.raises(ValueError):
        Palette.from_data({"colors":{"base":"#123456"},"ramps":{"bad":["base","missing"]}})

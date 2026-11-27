import pytest

from pixel_foundry.controls import create_button, create_separator
from pixel_foundry.palette import Palette


PALETTE = Palette.from_data({
    "colors": {
        "void": "#0B1422", "surface": "#142333", "surface_raised": "#1B2D3D",
        "surface_deep": "#101C2A", "border": "#425568", "border_gold": "#A98A5C",
        "gold": "#D6B574", "gold_light": "#E9D6A7", "text": "#E6DDC8",
        "muted": "#8F9DA5", "teal": "#5D9692", "teal_deep": "#315F63"
    }
})


def test_button_dimensions_and_primary_fill():
    image = create_button(88, 24, PALETTE, variant="primary")
    assert image.size == (88, 24)
    assert image.getpixel((10, 10))[:3] == PALETTE.rgb("gold")


def test_button_pressed_state_and_invalid_variant():
    normal = create_button(88, 24, PALETTE, variant="secondary")
    pressed = create_button(88, 24, PALETTE, variant="secondary", pressed=True)
    assert normal.getpixel((10, 10)) != pressed.getpixel((10, 10))
    with pytest.raises(ValueError):
        create_button(88, 24, PALETTE, variant="danger")


def test_separator_is_transparent_and_rejects_short_width():
    image = create_separator(80, PALETTE)
    assert image.size == (80, 5)
    assert image.getpixel((40, 0))[3] == 0
    with pytest.raises(ValueError):
        create_separator(4, PALETTE)

from pixel_foundry.palette import Palette
from pixel_foundry.ui_kit import create_panel_frame


PALETTE = Palette.from_data({
    "colors": {
        "void": "#0B1422",
        "surface": "#142333",
        "surface_raised": "#1B2D3D",
        "surface_deep": "#101C2A",
        "border": "#425568",
        "border_gold": "#A98A5C",
        "gold": "#D6B574",
        "gold_light": "#E9D6A7",
        "text": "#E6DDC8",
        "muted": "#8F9DA5",
        "teal": "#5D9692",
        "teal_deep": "#315F63"
    }
})


def test_panel_frame_has_requested_dimensions_and_is_rgba():
    image = create_panel_frame(96, 64, PALETTE)
    assert image.size == (96, 64)
    assert image.mode == "RGBA"


def test_featured_panel_uses_gold_frame_and_inset_uses_deep_surface():
    featured = create_panel_frame(32, 24, PALETTE, variant="featured")
    inset = create_panel_frame(32, 24, PALETTE, variant="inset")
    assert featured.getpixel((0, 0))[:3] == PALETTE.rgb("border_gold")
    assert inset.getpixel((10, 10))[:3] == PALETTE.rgb("surface_deep")


def test_panel_rejects_invalid_dimensions_and_variant():
    import pytest
    with pytest.raises(ValueError):
        create_panel_frame(8, 8, PALETTE)
    with pytest.raises(ValueError):
        create_panel_frame(32, 24, PALETTE, variant="neon")

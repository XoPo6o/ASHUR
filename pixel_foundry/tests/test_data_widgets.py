import pytest

from pixel_foundry.data_widgets import draw_kpi_tile, draw_sparkline
from pixel_foundry.palette import Palette


PALETTE = Palette.from_data({
    "colors": {
        "void": "#0B1422", "surface": "#142333", "surface_raised": "#1B2D3D",
        "surface_deep": "#101C2A", "border": "#425568", "border_gold": "#A98A5C",
        "gold": "#D6B574", "gold_light": "#E9D6A7", "text": "#E6DDC8",
        "muted": "#9AB0B6", "teal": "#65CFC0", "teal_deep": "#2D6B70",
        "green": "#83D59B", "red": "#ED7774"
    }
})


def test_sparkline_has_exact_size_and_transparent_background():
    image = draw_sparkline((64, 24), [1, 3, 2, 5], PALETTE)
    assert image.size == (64, 24)
    assert image.getpixel((0, 0))[3] == 0


def test_sparkline_rejects_short_or_invalid_series():
    with pytest.raises(ValueError):
        draw_sparkline((64, 24), [1], PALETTE)
    with pytest.raises(ValueError):
        draw_sparkline((64, 24), [1, "x"], PALETTE)


def test_kpi_tile_uses_expected_dimensions_and_trend_validation():
    image = draw_kpi_tile(112, 64, PALETTE, trend="positive", values=[1, 2, 3])
    assert image.size == (112, 64)
    with pytest.raises(ValueError):
        draw_kpi_tile(112, 64, PALETTE, trend="moon")

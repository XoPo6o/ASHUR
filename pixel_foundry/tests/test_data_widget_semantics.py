from pixel_foundry.data_widgets import draw_kpi_tile
from pixel_foundry.palette import Palette


def palette():
    return Palette.from_data({"colors": {
        "void": "#0B141D",
        "surface_deep": "#101E2A",
        "surface": "#142633",
        "surface_raised": "#1B3340",
        "border": "#365564",
        "border_gold": "#9C7746",
        "gold": "#D9AD62",
        "gold_light": "#F0D8A5",
        "muted": "#9AB0B6",
        "teal": "#65CFC0",
        "green": "#83D59B",
        "red": "#ED7774",
    }})


def test_kpi_status_markers_use_semantic_colors():
    colors = palette()
    for trend, token in (("positive", "green"), ("negative", "red"), ("neutral", "muted")):
        tile = draw_kpi_tile(64, 48, colors, trend=trend)
        assert tile.getpixel((54, 7))[:3] == colors.rgb(token)

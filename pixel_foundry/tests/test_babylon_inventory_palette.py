import json
from pathlib import Path

from pixel_foundry.palette import Palette


def test_babylon_inventory_palette_is_limited_and_named():
    path = Path(__file__).parents[1] / "palettes" / "babylon_inventory.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    palette = Palette.from_data(data)
    assert len(palette.ordered_hex()) == 12
    assert data["rules"]["anti_aliasing"] is False
    assert data["rules"]["dithering"] == "off-by-default"


def test_babylon_inventory_palette_uses_restrained_navy_gold_teal_roles():
    path = Path(__file__).parents[1] / "palettes" / "babylon_inventory.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    colors = data["colors"]
    assert colors["void"] == "#0B1422"
    assert colors["gold"] == "#D6B574"
    assert colors["teal"] == "#5D9692"
    forbidden = {value.upper() for value in data["rules"]["forbidden"] if value.startswith("#")}
    assert not (set(palette.upper() for palette in Palette.from_data(data).ordered_hex()) & forbidden)

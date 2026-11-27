import json
from pathlib import Path
from pixel_foundry.palette_study import PALETTE_VARIANTS, render_palette_study


def test_palette_study_renders_three_same_size_candidates(tmp_path):
    bible = json.loads(Path("pixel_foundry/examples/babylon_art_bible.json").read_text())
    paths = render_palette_study(bible, tmp_path, scale=2)
    assert set(PALETTE_VARIANTS).issubset(paths)
    images = [paths[name] for name in PALETTE_VARIANTS]
    from PIL import Image
    sizes = [Image.open(path).size for path in images]
    assert len(set(sizes)) == 1
    assert paths["comparison"].exists()


def test_palette_study_rejects_invalid_scale(tmp_path):
    with open("pixel_foundry/examples/babylon_art_bible.json", encoding="utf-8") as file:
        bible = json.load(file)
    import pytest
    with pytest.raises(ValueError, match="positive integer"):
        render_palette_study(bible, tmp_path, scale=0)

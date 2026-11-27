import json
from pathlib import Path

import pytest
from PIL import Image

from pixel_foundry.palette_study import (
    PALETTE_VARIANTS,
    compare_images,
    render_palette_study,
)


def test_palette_study_renders_three_same_size_candidates_and_metrics(tmp_path):
    bible = json.loads(Path("pixel_foundry/examples/babylon_art_bible.json").read_text())
    paths = render_palette_study(bible, tmp_path, scale=2)
    assert set(PALETTE_VARIANTS).issubset(paths)
    images = [Image.open(paths[name]) for name in PALETTE_VARIANTS]
    assert len({image.size for image in images}) == 1
    assert images[0].size == (160 * 2, 90 * 2)
    assert paths["comparison"].exists()
    assert paths["metrics"].exists()


def test_palette_candidates_are_visibly_distinct(tmp_path):
    bible = json.loads(Path("pixel_foundry/examples/babylon_art_bible.json").read_text())
    paths = render_palette_study(bible, tmp_path, scale=2)
    names = list(PALETTE_VARIANTS)
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            metrics = compare_images(Image.open(paths[left]), Image.open(paths[right]))
            assert metrics["changed_pixel_ratio"] >= 0.35, (left, right, metrics)
            assert metrics["mean_channel_delta"] >= 10, (left, right, metrics)


def test_compare_images_rejects_different_dimensions():
    with pytest.raises(ValueError, match="identical dimensions"):
        compare_images(Image.new("RGB", (2, 2)), Image.new("RGB", (3, 2)))


def test_palette_study_rejects_invalid_scale(tmp_path):
    bible = json.loads(Path("pixel_foundry/examples/babylon_art_bible.json").read_text())
    with pytest.raises(ValueError, match="positive integer"):
        render_palette_study(bible, tmp_path, scale=0)

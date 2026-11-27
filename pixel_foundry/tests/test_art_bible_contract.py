from pixel_foundry.art_director import validate_art_bible


def sample():
    return {
        "name": "test",
        "style": "chunky pixel art",
        "canvas": {"width": 32, "height": 32},
        "pixel_scale": 1,
        "perspective": "frontal",
        "lighting": {"direction": "top_left"},
        "palette": {"colors": {"dark": "#111122", "light": "#EEEECC"}},
        "layers": [{"name": "background", "ops": []}],
    }


def test_art_bible_rejects_unknown_lighting_palette_tokens():
    bible = sample()
    bible["lighting"]["key_color"] = "sunset_gold"
    errors = validate_art_bible(bible)
    assert any("lighting.key_color" in error for error in errors)


def test_art_bible_rejects_more_than_sixteen_unique_colors():
    bible = sample()
    bible["palette"]["colors"] = {
        f"color_{index}": f"#{index:06X}" for index in range(17)
    }
    errors = validate_art_bible(bible)
    assert any("maximum is 16" in error for error in errors)

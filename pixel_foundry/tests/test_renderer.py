from pixel_foundry.palette import Palette
from pixel_foundry.renderer import PixelRenderer
from pixel_foundry.qa import inspect_image

def test_pixel_is_written_on_logical_grid():
    p = Palette.from_data({"colors":{"ink":"#101010","gold":"#FFCC55"}})
    r = PixelRenderer(8, 8, p, "ink")
    r.render_op({"type":"pixel","x":3,"y":4,"color":"gold"})
    assert r.image.getpixel((3,4)) == (255,204,85,255)
    assert r.image.size == (8,8)

def test_qa_counts_colors_and_transparency():
    p = Palette.from_data({"colors":{"ink":"#101010","gold":"#FFCC55"}})
    r = PixelRenderer(4, 4, p, "transparent")
    r.render_op({"type":"rect","x":1,"y":1,"w":2,"h":2,"color":"gold"})
    report = inspect_image(r.image,p)
    assert report["visible_pixels"] == 4
    assert report["unique_colors"] == 1


def test_scene_pixel_scale_renders_new_geometry_instead_of_upscaling():
    from pixel_foundry.scene import render_scene

    scene = {
        "canvas": {"width": 4, "height": 4},
        "metadata": {"pixel_scale": 2},
        "palette": {"colors": {"ink": "#101010", "gold": "#FFCC55"}},
        "background": "ink",
        "layers": [{
            "name": "test",
            "ops": [{"type": "rect", "x": 1, "y": 1, "w": 1, "h": 1, "color": "gold"}],
        }],
    }
    result = render_scene(scene)
    assert result["image"].size == (8, 8)
    assert result["image"].getpixel((2, 2)) == (255, 204, 85, 255)
    assert result["image"].getpixel((3, 3)) == (255, 204, 85, 255)
    assert result["image"].getpixel((1, 2)) == (16, 16, 16, 255)
    assert result["qa"]["pixel_scale"] == 2
    assert result["qa"]["authored_canvas"] == {"width": 4, "height": 4}

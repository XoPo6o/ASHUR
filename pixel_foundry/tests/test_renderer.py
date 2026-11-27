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

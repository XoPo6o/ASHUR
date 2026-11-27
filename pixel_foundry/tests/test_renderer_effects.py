from pixel_foundry.palette import Palette
from pixel_foundry.renderer import PixelRenderer

def test_ramp_rect_uses_hard_palette_bands():
    p=Palette.from_data({"colors":{"a":"#000000","b":"#FFFFFF"},"ramps":{"test":["a","b"]}})
    r=PixelRenderer(2,2,p,"a")
    r.render_op({"type":"ramp_rect","x":0,"y":0,"w":2,"h":2,"ramp":"test","axis":"horizontal"})
    assert r.image.getpixel((0,0))==(0,0,0,255)
    assert r.image.getpixel((1,0))==(255,255,255,255)

def test_outline_expands_alpha_mask():
    p=Palette.from_data({"colors":{"red":"#FF0000","blue":"#0000FF"}})
    r=PixelRenderer(5,5,p,"transparent")
    r.render_op({"type":"pixel","x":2,"y":2,"color":"red"})
    r.render_op({"type":"outline","color":"blue","radius":1})
    assert r.image.getpixel((1,2))==(0,0,255,255)
    assert r.image.getpixel((2,2))==(255,0,0,255)

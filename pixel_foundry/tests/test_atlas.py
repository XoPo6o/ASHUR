from PIL import Image
from pixel_foundry.atlas import pack_atlas

def test_atlas_metadata_and_dimensions(tmp_path):
    sprites={"a":Image.new("RGBA",(8,8),(255,0,0,255)),"b":Image.new("RGBA",(4,6),(0,255,0,255))}
    out=tmp_path/"atlas.png"
    meta=pack_atlas(sprites,out,columns=2,spacing=1)
    assert out.exists()
    assert meta["frames"]["a"]["w"]==8
    assert meta["size"]["w"]==19

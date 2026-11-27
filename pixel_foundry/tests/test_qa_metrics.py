from PIL import Image
from pixel_foundry.qa import inspect_image

def test_cluster_metrics_distinguish_isolated_pixels():
    image=Image.new("RGBA",(8,8),(0,0,0,0))
    image.putpixel((1,1),(255,255,255,255))
    image.putpixel((5,5),(255,255,255,255))
    image.putpixel((6,5),(255,255,255,255))
    report=inspect_image(image)
    assert report["cluster_sizes"]["component_count"]==2
    assert report["cluster_sizes"]["single_pixel_components"]==1
    assert report["silhouette"]["boundary_pixels"]>0

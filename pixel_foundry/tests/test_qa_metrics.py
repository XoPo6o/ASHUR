from PIL import Image
from pixel_foundry.palette import Palette
from pixel_foundry.qa import inspect_image, inspect_palette_ramps, inspect_scene_art_direction


def test_cluster_metrics_distinguish_isolated_pixels():
    image=Image.new("RGBA",(8,8),(0,0,0,0))
    image.putpixel((1,1),(255,255,255,255))
    image.putpixel((5,5),(255,255,255,255))
    image.putpixel((6,5),(255,255,255,255))
    report=inspect_image(image)
    assert report["cluster_sizes"]["component_count"]==2
    assert report["cluster_sizes"]["single_pixel_components"]==1
    assert report["silhouette"]["boundary_pixels"]>0


def test_palette_ramp_reports_luminance_steps():
    palette=Palette.from_data({"colors":{"dark":"#101010","mid":"#777777","light":"#EEEEEE"},
                               "ramps":{"stone":["dark","mid","light"]}})
    report=inspect_palette_ramps(palette)
    assert report["stone"]["monotonic_lightness"]
    assert len(report["stone"]["step_deltas"])==2


def test_scene_art_direction_detects_missing_depth_plane_and_primary_focus():
    scene={"metadata":{"planning":{"depth_planes":["sky","street"]},"lighting":{"direction":"top_left"}},
           "layers":[{"name":"sky","depth_plane":"sky","focus_role":"background","ops":[]}]}
    report=inspect_scene_art_direction(scene)
    assert report["missing_depth_planes"]==["street"]
    assert "No layer is marked as the primary focal subject" in report["warnings"]

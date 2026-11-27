"""Art-bible contract between the AI Art Director and deterministic renderer.

The language model authors the creative decisions; this module validates and
normalizes the structured art direction before a scene is rendered.
"""
from __future__ import annotations
from copy import deepcopy
from .palette import Palette

REQUIRED_BIBLE=("name","style","canvas","pixel_scale","perspective","lighting","palette","layers")
ALLOWED_PERSPECTIVES={"side","top_down","three_quarter","isometric","frontal"}
ALLOWED_LIGHT_DIRECTIONS={"top_left","top","top_right","left","right","bottom_left","bottom","bottom_right","ambient"}
MAX_ART_BIBLE_COLORS=16


def validate_art_bible(bible: dict) -> list[str]:
    errors=[]
    missing=[key for key in REQUIRED_BIBLE if key not in bible]
    if missing:
        return [f"Missing required art-bible fields: {', '.join(missing)}"]
    canvas=bible["canvas"]
    if not isinstance(canvas,dict) or not all(k in canvas for k in ("width","height")):
        errors.append("canvas must define width and height")
    else:
        for key in ("width","height"):
            if not isinstance(canvas[key],int) or canvas[key]<8 or canvas[key]>4096:
                errors.append(f"canvas.{key} must be an integer from 8 to 4096")
    if not isinstance(bible["pixel_scale"],int) or bible["pixel_scale"]<1:
        errors.append("pixel_scale must be a positive integer")
    if bible["perspective"] not in ALLOWED_PERSPECTIVES:
        errors.append(f"perspective must be one of {sorted(ALLOWED_PERSPECTIVES)}")
    lighting=bible["lighting"]
    if not isinstance(lighting,dict) or lighting.get("direction") not in ALLOWED_LIGHT_DIRECTIONS:
        errors.append(f"lighting.direction must be one of {sorted(ALLOWED_LIGHT_DIRECTIONS)}")
    try:
        palette=Palette.from_data(bible["palette"])
        if len(palette.ordered_hex()) > MAX_ART_BIBLE_COLORS:
            errors.append(
                f"Art Bible palette has {len(palette.ordered_hex())} unique colors; "
                f"maximum is {MAX_ART_BIBLE_COLORS}"
            )
        if isinstance(lighting,dict):
            for key in ("key_color","ambient_color"):
                color=lighting.get(key)
                if color is not None and color not in palette.colors:
                    errors.append(f"lighting.{key} references unknown palette color: {color!r}")
    except (TypeError,ValueError,KeyError) as exc:
        errors.append(f"Invalid palette: {exc}")
    if not isinstance(bible["layers"],list) or not bible["layers"]:
        errors.append("layers must be a non-empty ordered list")
    else:
        names=[layer.get("name") for layer in bible["layers"] if isinstance(layer,dict)]
        if len(names)!=len(bible["layers"]) or any(not name for name in names):
            errors.append("every layer must be an object with a non-empty name")
    return errors


def build_scene_spec(bible: dict) -> dict:
    """Convert a validated art bible to a renderer-ready scene spec."""
    errors=validate_art_bible(bible)
    if errors:
        raise ValueError("Invalid art bible: " + "; ".join(errors))
    spec={
        "canvas":deepcopy(bible["canvas"]),
        "background":bible.get("background","transparent"),
        "palette":deepcopy(bible["palette"]),
        "layers":[{"name":layer["name"],"visible":layer.get("visible",True),
                   "ops":deepcopy(layer.get("ops",[]))} for layer in bible["layers"]],
        "metadata":{
            "art_bible":bible["name"],"style":bible["style"],
            "pixel_scale":bible["pixel_scale"],"perspective":bible["perspective"],
            "lighting":deepcopy(bible["lighting"]),
            "focal_point":deepcopy(bible.get("focal_point")),
            "target":bible.get("target","general")
        }
    }
    return spec

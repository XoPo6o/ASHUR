"""Art-bible contract between the AI Art Director and deterministic renderer.

The art director validates composition, camera, light, material intent and scene
layers before the raster engine receives deterministic drawing operations.
"""
from __future__ import annotations
from copy import deepcopy
from .palette import Palette

REQUIRED_BIBLE=("name","style","canvas","pixel_scale","perspective","lighting","palette","layers")
ALLOWED_PERSPECTIVES={"side","top_down","three_quarter","isometric","frontal"}
ALLOWED_LIGHT_DIRECTIONS={"top_left","top","top_right","left","right","bottom_left","bottom","bottom_right","ambient"}
ALLOWED_DETAIL_TIERS={"economy","standard","hero"}
MAX_ART_BIBLE_COLORS=16


def validate_art_bible(bible: dict) -> list[str]:
    errors=[]
    if not isinstance(bible,dict):
        return ["Art Bible must be a JSON object"]
    missing=[key for key in REQUIRED_BIBLE if key not in bible]
    if missing:
        return [f"Missing required art-bible fields: {', '.join(missing)}"]
    canvas=bible["canvas"]
    if not isinstance(canvas,dict) or not all(k in canvas for k in ("width","height")):
        errors.append("canvas must define width and height")
    else:
        for key in ("width","height"):
            if not isinstance(canvas[key],int) or isinstance(canvas[key],bool) or canvas[key]<8 or canvas[key]>4096:
                errors.append(f"canvas.{key} must be an integer from 8 to 4096")
    if not isinstance(bible["pixel_scale"],int) or isinstance(bible["pixel_scale"],bool) or bible["pixel_scale"]<1:
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
        materials=bible.get("materials",{})
        if not isinstance(materials,dict):
            errors.append("materials must be an object mapping material names to palette ramps")
        else:
            for name,profile in materials.items():
                if not isinstance(profile,dict):
                    errors.append(f"materials.{name} must be an object")
                    continue
                ramp=profile.get("ramp")
                if ramp not in palette.ramps:
                    errors.append(f"materials.{name}.ramp references unknown palette ramp: {ramp!r}")
        known_materials=set(materials) if isinstance(materials,dict) else set()
        for layer in bible.get("layers",[]) if isinstance(bible.get("layers"),list) else []:
            if not isinstance(layer,dict):
                continue
            for index,op in enumerate(layer.get("ops",[])):
                if isinstance(op,dict) and op.get("material") and op["material"] not in known_materials:
                    errors.append(f"layer {layer.get('name')!r} op {index} references unknown material: {op['material']!r}")
    except (TypeError,ValueError,KeyError) as exc:
        errors.append(f"Invalid palette: {exc}")
    if not isinstance(bible["layers"],list) or not bible["layers"]:
        errors.append("layers must be a non-empty ordered list")
    else:
        names=[layer.get("name") for layer in bible["layers"] if isinstance(layer,dict)]
        if len(names)!=len(bible["layers"]) or any(not name for name in names):
            errors.append("every layer must be an object with a non-empty name")
    planning=bible.get("planning",{})
    if not isinstance(planning,dict):
        errors.append("planning must be an object")
    else:
        tier=planning.get("detail_tier","standard")
        if tier not in ALLOWED_DETAIL_TIERS:
            errors.append(f"planning.detail_tier must be one of {sorted(ALLOWED_DETAIL_TIERS)}")
        for key in ("focal_contrast","background_contrast"):
            value=planning.get(key)
            if value is not None and (not isinstance(value,(int,float)) or isinstance(value,bool) or not 0<=value<=1):
                errors.append(f"planning.{key} must be a number from 0 to 1")
        planes=planning.get("depth_planes")
        if planes is not None and (not isinstance(planes,list) or not planes or any(not isinstance(p,str) or not p for p in planes)):
            errors.append("planning.depth_planes must be a non-empty ordered list of names")
        elif isinstance(planes,list):
            for layer in bible["layers"] if isinstance(bible.get("layers"),list) else []:
                if isinstance(layer,dict) and layer.get("depth_plane") and layer["depth_plane"] not in planes:
                    errors.append(f"layer {layer.get('name')!r} uses undeclared depth_plane: {layer['depth_plane']!r}")
        for layer in bible["layers"] if isinstance(bible.get("layers"),list) else []:
            if isinstance(layer,dict) and layer.get("focus_role") not in (None,"primary","secondary","supporting","background"):
                errors.append(f"layer {layer.get('name')!r} has invalid focus_role")
    return errors


def _apply_material_profiles(layers: list[dict], materials: dict, palette: Palette) -> list[dict]:
    """Resolve named material ramps into deterministic per-operation color roles."""
    resolved=[]
    for layer in layers:
        new_layer=deepcopy(layer)
        ops=[]
        for source_op in layer.get("ops",[]):
            op=deepcopy(source_op)
            name=op.pop("material",None)
            if name:
                profile=materials[name]
                ramp=[palette.hex(color) for color in palette.ramp(profile["ramp"])]
                # Named roles are defaults, never overwrite deliberate local art direction.
                op.setdefault("shade",ramp[0])
                op.setdefault("color",ramp[len(ramp)//2])
                op.setdefault("highlight",ramp[-1])
                if profile.get("accent"):
                    op.setdefault("accent",profile["accent"])
                op["material_profile"]=name
            ops.append(op)
        new_layer["ops"]=ops
        resolved.append(new_layer)
    return resolved


def build_scene_spec(bible: dict) -> dict:
    """Convert a validated art bible to a renderer-ready scene spec."""
    errors=validate_art_bible(bible)
    if errors:
        raise ValueError("Invalid art bible: " + "; ".join(errors))
    palette=Palette.from_data(bible["palette"])
    materials=deepcopy(bible.get("materials",{}))
    layers=_apply_material_profiles(bible["layers"],materials,palette)
    planning=deepcopy(bible.get("planning",{}))
    planning.setdefault("detail_tier","standard")
    planning.setdefault("focal_contrast",0.9)
    planning.setdefault("background_contrast",0.45)
    planning.setdefault("depth_planes",["background","middle_ground","foreground"])
    spec={
        "canvas":deepcopy(bible["canvas"]),
        "background":bible.get("background","transparent"),
        "palette":deepcopy(bible["palette"]),
        "layers":[{"name":layer["name"],"visible":layer.get("visible",True),
                   "depth_plane":layer.get("depth_plane"),
                   "focus_role":layer.get("focus_role","supporting"),
                   "contrast_weight":layer.get("contrast_weight"),
                   "ops":deepcopy(layer.get("ops",[]))} for layer in layers],
        "metadata":{
            "art_bible":bible["name"],"style":bible["style"],
            "pixel_scale":bible["pixel_scale"],"perspective":bible["perspective"],
            "lighting":deepcopy(bible["lighting"]),
            "focal_point":deepcopy(bible.get("focal_point")),
            "planning":planning,
            "materials":materials,
            "target":bible.get("target","general")
        }
    }
    return spec

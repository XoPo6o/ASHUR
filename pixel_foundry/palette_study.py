"""Render identical Babylon Art Bible geometry through three controlled palettes."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from PIL import Image, ImageDraw
from .art_director import build_scene_spec
from .scene import render_scene

PALETTE_VARIANTS = {
 "A-reference": {"night":"#0B141D","far_blue":"#101E2A","blue_stone":"#142633","sand_shadow":"#9C7746","sand":"#D9AD62","sand_light":"#F0D8A5","gold_shadow":"#9C7746","gold":"#D9AD62","moon":"#E9E5D6","teal":"#65CFC0","dark":"#050A0E","leaf_shadow":"#2D6B70","leaf":"#83D59B","leaf_light":"#E9E5D6","water_shadow":"#2D6B70","water":"#65CFC0","water_light":"#9AB0B6","stone":"#365564","stone_dark":"#050A0E"},
 "B-warm-stone": {"night":"#0B141D","far_blue":"#101E2A","blue_stone":"#142633","sand_shadow":"#8B6848","sand":"#D2A66B","sand_light":"#F2D9A8","gold_shadow":"#8B6848","gold":"#D2A66B","moon":"#EEE6D2","teal":"#65CFC0","dark":"#050A0E","leaf_shadow":"#2D6B70","leaf":"#83D59B","leaf_light":"#EEE6D2","water_shadow":"#2D6B70","water":"#65CFC0","water_light":"#9AB0B6","stone":"#365564","stone_dark":"#050A0E"},
 "C-muted-keep": {"night":"#080F17","far_blue":"#0D1A24","blue_stone":"#142633","sand_shadow":"#826746","sand":"#C49A60","sand_light":"#E5C995","gold_shadow":"#826746","gold":"#C49A60","moon":"#DCD9CA","teal":"#58B5A8","dark":"#03080C","leaf_shadow":"#245B60","leaf":"#72B986","leaf_light":"#DCD9CA","water_shadow":"#245B60","water":"#58B5A8","water_light":"#8FA8A8","stone":"#304A56","stone_dark":"#03080C"}
}

def render_palette_study(art_bible: dict, output_dir: str | Path, scale: int = 4) -> dict:
    if scale < 1:
        raise ValueError("scale must be a positive integer")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    base = build_scene_spec(art_bible)
    width, height = int(base["canvas"]["width"])*scale, int(base["canvas"]["height"])*scale
    gap, label_height, margin = 12, 18, 12
    board = Image.new("RGB",(margin*2+width*3+gap*2,margin*2+height+label_height),"#050A0E")
    draw = ImageDraw.Draw(board)
    paths = {}
    for index,(name,colors) in enumerate(PALETTE_VARIANTS.items()):
        scene = deepcopy(base)
        scene["palette"] = {"colors":colors,"ramps":deepcopy(art_bible["palette"].get("ramps",{}))}
        for key,values in scene["palette"]["ramps"].items():
            scene["palette"]["ramps"][key] = [v for v in values if v in colors]
        rendered = render_scene(scene)["image"].convert("RGB")
        if scale > 1:
            rendered = rendered.resize((width, height), Image.Resampling.NEAREST)
        x,y = margin+index*(width+gap),margin
        board.paste(rendered,(x,y))
        draw.text((x,y+height+4),name,fill="#E9E5D6")
        path=output/f"babylon-palette-{index+1}.png"
        rendered.save(path,optimize=True)
        paths[name]=path
    board_path=output/"babylon-palette-comparison.png"
    board.save(board_path,optimize=True)
    paths["comparison"]=board_path
    return paths

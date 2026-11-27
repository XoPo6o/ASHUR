"""Command line interface: render and inspect pixel-art assets."""
from __future__ import annotations
import argparse, json
from PIL import Image
from .scene import load_scene, render_scene
from .qa import inspect_image
from .palette import Palette
from .art_director import build_scene_spec, validate_art_bible

def main():
    parser = argparse.ArgumentParser(prog="pixel-foundry")
    sub = parser.add_subparsers(dest="command", required=True)
    render = sub.add_parser("render", help="Render a JSON scene spec to PNG")
    render.add_argument("scene"); render.add_argument("-o", "--output", default="out/scene.png")
    render.add_argument("--scale", type=int, default=3)
    inspect = sub.add_parser("inspect", help="Run pixel-art QA on a PNG")
    inspect.add_argument("image")
    args = parser.parse_args()
    if args.command == "render":
        data = load_scene(args.scene)
        if "pixel_scale" in data and "perspective" in data:
            errors = validate_art_bible(data)
            if errors:
                parser.error("Invalid art bible: " + "; ".join(errors))
            data = build_scene_spec(data)
        result = render_scene(data, args.output, args.scale)
        print(json.dumps({"output": args.output, "qa": result["qa"]}, ensure_ascii=False, indent=2))
    else:
        report = inspect_image(Image.open(args.image))
        print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

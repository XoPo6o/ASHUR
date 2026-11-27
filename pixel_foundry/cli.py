"""Command line interface: render and inspect pixel-art assets."""
from __future__ import annotations
import argparse, json
from PIL import Image
from .scene import load_scene, render_scene
from .qa import inspect_image
from .palette import Palette

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
        result = render_scene(load_scene(args.scene), args.output, args.scale)
        print(json.dumps({"output": args.output, "qa": result["qa"]}, ensure_ascii=False, indent=2))
    else:
        report = inspect_image(Image.open(args.image))
        print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

"""Pixel-art diagnostics: palette, clusters, contours, contrast and silhouette metrics.

Metrics are advisory. They intentionally do not auto-correct artwork or declare a
subjectively 'good' image based on a single numeric score.
"""
from __future__ import annotations
from collections import Counter, deque
from math import sqrt
from PIL import Image
from .palette import Palette, validate_palette_size


def _luminance(rgb: tuple[int,int,int]) -> float:
    # Relative luminance in linear-light sRGB.
    values=[]
    for c in rgb:
        v=c/255
        values.append(v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4)
    return 0.2126*values[0]+0.7152*values[1]+0.0722*values[2]


def _components(mask: list[list[bool]]) -> list[int]:
    h=len(mask); w=len(mask[0]) if h else 0
    seen=set(); sizes=[]
    for y in range(h):
        for x in range(w):
            if not mask[y][x] or (x,y) in seen:
                continue
            q=deque([(x,y)]); seen.add((x,y)); size=0
            while q:
                cx,cy=q.popleft(); size+=1
                for nx,ny in ((cx-1,cy),(cx+1,cy),(cx,cy-1),(cx,cy+1)):
                    if 0<=nx<w and 0<=ny<h and mask[ny][nx] and (nx,ny) not in seen:
                        seen.add((nx,ny)); q.append((nx,ny))
            sizes.append(size)
    return sorted(sizes,reverse=True)


def _edge_metrics(mask: list[list[bool]]) -> dict:
    h=len(mask); w=len(mask[0]) if h else 0
    perimeter=0; transitions=0; horizontal_runs=0
    for y in range(h):
        prev=False; run=0
        for x in range(w):
            value=mask[y][x]
            if value != prev:
                transitions+=1
                if prev and run:
                    horizontal_runs+=1
                run=0
            if value:
                run+=1
                if x==0 or not mask[y][x-1]: perimeter+=1
                if x==w-1 or not mask[y][x+1]: perimeter+=1
                if y==0 or not mask[y-1][x]: perimeter+=1
                if y==h-1 or not mask[y+1][x]: perimeter+=1
            prev=value
        if prev and run:
            horizontal_runs+=1
    return {"boundary_edges":perimeter,"horizontal_runs":horizontal_runs,
            "row_transitions":transitions}


def inspect_image(image: Image.Image, palette: Palette | None = None,
                  cluster_warning_below: int = 2, palette_maximum: int = 32) -> dict:
    rgba=image.convert("RGBA")
    w,h=rgba.size
    px=rgba.load()
    pixels=list(rgba.getdata())
    visible=[p[:3] for p in pixels if p[3]>0]
    counts=Counter(visible)
    warnings=[]; suggestions=[]
    mask=[[px[x,y][3]>0 for x in range(w)] for y in range(h)]
    components=_components(mask)
    isolated=sum(1 for size in components if size==1)
    tiny=sum(1 for size in components if size<=cluster_warning_below)
    edge=_edge_metrics(mask)
    if isolated:
        warnings.append(f"{isolated} isolated visible components (single pixels); inspect for accidental noise")
    if tiny>isolated:
        suggestions.append(f"{tiny-isolated} additional tiny connected components (size <= {cluster_warning_below}) may need review")
    if components and len(components)>max(8,(w*h)//120):
        suggestions.append("Many disconnected silhouette islands; check whether the subject should read as one grouped form")
    if palette:
        warnings.extend(validate_palette_size(palette,palette_maximum))
        allowed={palette.rgb(k) for k in palette.colors}
        off_palette=sum(1 for p in visible if p not in allowed)
        if off_palette:
            warnings.append(f"{off_palette} visible pixels are outside the declared palette")
    lums=sorted(_luminance(c) for c in counts)
    luminance_span=round((lums[-1]-lums[0]),3) if lums else 0
    if len(lums)>1 and luminance_span<0.18:
        suggestions.append("Low overall luminance separation; check value grouping and focal readability")
    if len(counts)>48:
        suggestions.append(f"High color count ({len(counts)}); verify that palette complexity is intentional")
    # Count visible-to-transparent boundaries, a useful silhouette complexity proxy.
    alpha_boundary=0
    for y in range(h):
        for x in range(w):
            if not mask[y][x]:
                continue
            if any(not (0<=nx<w and 0<=ny<h and mask[ny][nx])
                   for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1))):
                alpha_boundary+=1
    cluster_sizes={"largest":components[0] if components else 0,
                   "smallest":components[-1] if components else 0,
                   "component_count":len(components),
                   "single_pixel_components":isolated,
                   "components_at_or_below_threshold":tiny}
    return {
        "width":w,"height":h,"visible_pixels":len(visible),
        "transparent_pixels":len(pixels)-len(visible),
        "unique_colors":len(counts),"isolated_pixels":isolated,
        "cluster_sizes":cluster_sizes,
        "silhouette":{"boundary_pixels":alpha_boundary,
                      "boundary_to_area_ratio":round(alpha_boundary/max(1,len(visible)),3),
                      **edge},
        "color_metrics":{"luminance_span":luminance_span,
                         "most_used_colors":[{"rgb":list(c),"pixels":n} for c,n in counts.most_common(8)]},
        "warnings":warnings,"suggestions":suggestions,
        "palette_usage":{f"#{r:02X}{g:02X}{b:02X}":n for (r,g,b),n in counts.most_common()},
    }

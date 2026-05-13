from __future__ import annotations
from pathlib import Path
from typing import Iterable, Mapping

def save_lines_to_svg(
    out_path: str | Path,
    width: int,
    height: int,
    lines: Iterable[Mapping[str, int]],
    stroke_width: float = 1.0,
):
    """
    lines: {"x1":int,"y1":int,"x2":int,"y2":int} 딕셔너리들의 iterable
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # SVG는 좌상단이 (0,0), y가 아래로 증가 -> OpenCV 좌표계와 동일
    header = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{width}" height="{height}"
     viewBox="0 0 {width} {height}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="white"/>
  <g fill="none" stroke="black" stroke-width="{stroke_width}" stroke-linecap="round">
"""
    body_lines = []
    for l in lines:
        x1, y1, x2, y2 = l["x1"], l["y1"], l["x2"], l["y2"]
        body_lines.append(f'    <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>')

    footer = """  </g>
</svg>
"""
    out_path.write_text(header + "\n".join(body_lines) + "\n" + footer, encoding="utf-8")
    return str(out_path)
def save_polygons_to_svg(
    out_path: str | Path,
    width: int,
    height: int,
    polygons: list[list[list[int]]],
    stroke_width: float = 1.0,
):
    """
    polygons: [ [ [x,y], [x,y], ... ],  ... ]
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    header = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{width}" height="{height}"
     viewBox="0 0 {width} {height}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="white"/>
  <g fill="none" stroke="black" stroke-width="{stroke_width}">
"""
    body = []
    for poly in polygons:
        if len(poly) < 3:
            continue
        pts = " ".join([f"{int(x)},{int(y)}" for x, y in poly])
        body.append(f'    <polygon points="{pts}"/>')

    footer = """  </g>
</svg>
"""
    out_path.write_text(header + "\n".join(body) + "\n" + footer, encoding="utf-8")
    return str(out_path)

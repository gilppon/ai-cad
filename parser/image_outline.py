from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

import cv2
import numpy as np
import fitz  # PyMuPDF

from parser.line_refine import (
    Line,
    refine_lines,
    dedup_exact,
    merge_collinear_segments,
    merge_parallel_pairs,
    snap_endpoints,
    filter_axis_aligned,
    filter_structural_walls,
)
from parser.svg_export import save_lines_to_svg
from parser.room_detect import detect_rooms_from_walls
from parser.room_export import save_rooms_json
from parser.preprocessing import preprocess_for_pipeline


def save_lines_json(lines, out_dir="out", page_index=0, name="snapped"):
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{name}_page{page_index}.json")

    data = []
    for l in lines:
        data.append([int(l.x1), int(l.y1), int(l.x2), int(l.y2)])

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"page_index": int(page_index), name: data}, f, indent=2)

    print(f"[STEP5] saved: {out_path} count={len(data)}")


def save_walls_json(walls, out_dir="out", page_index=0):
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"walls_page{page_index}.json")

    data = []
    for l in walls:
        data.append([int(l.x1), int(l.y1), int(l.x2), int(l.y2)])

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"page_index": int(page_index), "walls": data}, f, indent=2)

    print("[STEP5] saved:", out_path, "count=", len(data))


def rebuild_door_mask(out_path: Path, pno: int) -> Optional[Path]:
    """
    door_mask 생성 (최종 확정):
      1) primary: rooms_mask_door - rooms_mask_clean
      2) fallback: walls_filled - walls_mask  (openings components=0 같은 케이스 대응)
    결과는 out/door_mask_page{pno}.png 로 저장.
    """
    out_door_mask = out_path / f"door_mask_page{pno}.png"

    # -----------------------------
    # 1) primary: rooms_mask_door - rooms_mask_clean
    # -----------------------------
    clean_png = out_path / f"rooms_mask_clean_page{pno}.png"
    door_png = out_path / f"rooms_mask_door_page{pno}.png"

    if clean_png.exists() and door_png.exists():
        m_clean = cv2.imread(str(clean_png), cv2.IMREAD_GRAYSCALE)
        m_door = cv2.imread(str(door_png), cv2.IMREAD_GRAYSCALE)

        if m_clean is not None and m_door is not None:
            _, bc = cv2.threshold(m_clean, 1, 255, cv2.THRESH_BINARY)
            _, bd = cv2.threshold(m_door, 1, 255, cv2.THRESH_BINARY)

            door = cv2.subtract(bd, bc)

            # 문이 너무 얇으면 STEP8 bbox가 안 잡힐 수 있어 살짝 두껍게
            k = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            door = cv2.dilate(door, k, iterations=1)

            nz = int((door > 0).sum())
            if nz > 0:
                cv2.imwrite(str(out_door_mask), door)
                print(
                    "[STEP5] rebuilt door_mask (rooms diff):",
                    str(out_door_mask),
                    "min/max=",
                    int(door.min()),
                    int(door.max()),
                    "nonzero=",
                    nz,
                )
                return out_door_mask
            else:
                print("[STEP5] rooms-diff door_mask is empty -> fallback to walls-based mask")
        else:
            print("[STEP5] WARN: failed to read rooms masks -> fallback to walls-based mask")
    else:
        print("[STEP5] rooms masks missing -> fallback to walls-based mask")
        print("  clean exists=", clean_png.exists(), "door exists=", door_png.exists())

    # -----------------------------
    # 2) fallback: walls_filled - walls_mask
    # -----------------------------
    walls_mask_png = out_path / f"walls_mask_page{pno}.png"
    walls_filled_png = out_path / f"walls_filled_page{pno}.png"

    if not walls_mask_png.exists() or not walls_filled_png.exists():
        print("[STEP5] WARN: missing walls_mask/walls_filled -> cannot build fallback door_mask")
        print("  walls_mask exists=", walls_mask_png.exists(), "walls_filled exists=", walls_filled_png.exists())

        # 마지막 수단: 빈 이미지라도 만들어두기 (STEP8에서 EMPTY로 명확히 로그)
        blank = np.zeros((512, 512), dtype=np.uint8)
        cv2.imwrite(str(out_door_mask), blank)
        print("[STEP5] wrote blank door_mask:", str(out_door_mask))
        return out_door_mask

    wm = cv2.imread(str(walls_mask_png), cv2.IMREAD_GRAYSCALE)
    wf = cv2.imread(str(walls_filled_png), cv2.IMREAD_GRAYSCALE)

    if wm is None or wf is None:
        print("[STEP5] WARN: failed to read walls_mask/walls_filled")
        blank = np.zeros((512, 512), dtype=np.uint8)
        cv2.imwrite(str(out_door_mask), blank)
        print("[STEP5] wrote blank door_mask:", str(out_door_mask))
        return out_door_mask

    _, bw = cv2.threshold(wm, 1, 255, cv2.THRESH_BINARY)
    _, bf = cv2.threshold(wf, 1, 255, cv2.THRESH_BINARY)

    # filled - mask : 벽을 채우며 메워진 틈(문/개구부 후보 포함 가능)
    door = cv2.subtract(bf, bw)

    # 노이즈 제거 + 연결 강화
    k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    door = cv2.morphologyEx(door, cv2.MORPH_OPEN, k3)

    # 문이 너무 얇으면 dilate
    door = cv2.dilate(door, k3, iterations=1)

    nz = int((door > 0).sum())
    cv2.imwrite(str(out_door_mask), door)
    print(
        "[STEP5] rebuilt door_mask (walls diff):",
        str(out_door_mask),
        "min/max=",
        int(door.min()),
        int(door.max()),
        "nonzero=",
        nz,
    )

    return out_door_mask


# ================================================================
# extract_room_result_from_page — 핵심 로직 독립 함수
# ================================================================
def extract_room_result_from_page(
    page: Any,
    pno: int,
    out_path: Path,
    pdf_path: str = "",
) -> Any:
    """
    단일 PDF 페이지에서 방 탐지 결과(RoomResult)를 추출.
    image_outline 파이프라인의 핵심 로직을 독립 호출 가능하게 분리.

    Returns:
        RoomResult (from parser.room_detect)
    """
    out_path.mkdir(parents=True, exist_ok=True)

    # 1) Render page to image
    mat = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat, alpha=False)

    img = np.frombuffer(pix.samples, dtype=np.uint8)
    img = img.reshape(pix.h, pix.w, pix.n)
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    rendered_png = out_path / f"rendered_page{pno}.png"
    cv2.imwrite(str(rendered_png), img)

    # 1.5) Preprocessing (Deskew, Denoise)
    pre_res = preprocess_for_pipeline(img)
    processed_gray = pre_res["processed"]  # This is binary (inverted) in my current preprocess_for_pipeline
    deskew_angle = pre_res["deskew_angle"]
    
    preprocessed_png = out_path / f"preprocessed_page{pno}.png"
    cv2.imwrite(str(preprocessed_png), processed_gray)
    print(f"[STEP5] preprocessed: angle={desk_angle:.2f}" if "desk_angle" in locals() else f"[STEP5] preprocessed: angle={deskew_angle:.2f}")

    # 2) Edge detection (using preprocessed binary image or deskewed gray)
    # Since processed_gray is already binary-inverted (walls are 255), 
    # we can use it or run Canny on it if needed. 
    # Let's use the preprocessed image for edges.
    edges = processed_gray

    edges_png = out_path / f"edges_page{pno}.png"
    cv2.imwrite(str(edges_png), edges)

    # 3) Hough lines
    hough = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=80,
        minLineLength=40,
        maxLineGap=10,
    )

    raw: List[tuple] = []
    if hough is not None:
        raw = [tuple(map(int, l)) for l in hough.reshape(-1, 4)]

    # 4) refine pipeline
    refined = refine_lines(raw, min_len=60.0)
    refined = dedup_exact(refined)

    merged = merge_collinear_segments(refined, dist_tol=3.0, gap_tol=15.0)
    merged2 = merge_parallel_pairs(merged, dist_tol=12.0)

    snapped = snap_endpoints(merged2, snap_dist=12.0)
    print("DBG sample snapped[0]:", snapped[0] if snapped else None)
    save_lines_json(snapped, out_dir=str(out_path), page_index=pno, name="snapped")

    # 5) axis filter
    walls = filter_axis_aligned(snapped, tol_deg=7.0)
    print("walls(after axis filter):", len(walls))

    # 6) structural wall filter
    walls = filter_structural_walls(
        walls,
        min_len_ratio=0.03,
        min_degree=1,
        join_tol=18,
    )
    print("walls(after structural filter):", len(walls))

    # 6.5) walls json for STEP7/8
    save_walls_json(walls, out_dir=str(out_path), page_index=pno)

    # 7) debug overlay
    overlay = img.copy()
    for l in walls:
        cv2.line(overlay, (l.x1, l.y1), (l.x2, l.y2), (0, 0, 255), 2)
    overlay_png = out_path / f"overlay_page{pno}.png"
    cv2.imwrite(str(overlay_png), overlay)

    save_lines_to_svg(
        out_path / f"walls_lines_page{pno}.svg",
        width=edges.shape[1],
        height=edges.shape[0],
        lines=[{"x1": l.x1, "y1": l.y1, "x2": l.x2, "y2": l.y2} for l in walls],
        stroke_width=1.2,
    )

    # 8) Room detection
    H, W = edges.shape[:2]
    walls_lines = [{"x1": l.x1, "y1": l.y1, "x2": l.x2, "y2": l.y2} for l in walls]

    room_res = detect_rooms_from_walls(
        W,
        H,
        walls_lines,
        cfg={
            "wall_thickness": 10,
            "close_kernel": 5,
            "min_room_area_px": int(W * H * 0.0015),
            "max_room_area_ratio": 0.40,
            "debug_out_dir": str(out_path),
            "prefix": f"page{pno}",
        },
    )

    print(f"[extract_room_result_from_page] rooms: {len(room_res.rooms)}")

    # 부가 데이터: 파이프라인 카운트를 debug에 추가 (리포트용)
    room_res.debug["_pipeline_counts"] = json.dumps({
        "raw": len(raw),
        "refined": len(refined),
        "merged": len(merged),
        "merged2": len(merged2),
        "snapped": len(snapped),
        "walls": len(walls),
    })
    room_res.debug["_rendered_png"] = str(rendered_png)
    room_res.debug["_edges_png"] = str(edges_png)
    room_res.debug["_overlay_png"] = str(overlay_png)
    room_res.debug["_deskew_angle"] = deskew_angle

    return room_res


# ================================================================
# extract_outlines_from_image_pdf — 기존 엔트리포인트 (리팩토링)
# ================================================================
def extract_outlines_from_image_pdf(
    pdf_path: str,
    out_dir: str = "out",
    page_limit: int = 1,
) -> Dict[str, Any]:
    """
    STEP5:
      - PDF(page) -> edges -> Hough -> refine -> walls
      - walls_page{n}.json 저장 (STEP7/8 입력)
      - detect_rooms_from_walls 실행 + page{n}_rooms.json 저장
      - door_mask_page{n}.png 생성(rooms-diff 실패 시 walls-diff fallback)
      - lines_page{n}.json 은 요약 리포트(좌표 파일 아님)
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    reports = []

    for pno in range(min(page_limit, len(doc))):
        page = doc[pno]

        # 핵심 로직은 extract_room_result_from_page 로 위임
        room_res = extract_room_result_from_page(page, pno, out_path, pdf_path=pdf_path)

        rooms_count = len(room_res.rooms)

        # rooms JSON 저장
        rooms_json_path = out_path / f"page{pno}_rooms.json"
        save_rooms_json(
            room_res,
            str(rooms_json_path),
            page=pno,
            pixel_to_mm=None,
            source={"pdf": str(pdf_path), "page": pno},
            refinement_context={
                "page_index": pno,
                "output_dir": str(out_path),
                "inputs": {
                    "lines_path": str(out_path / f"snapped_page{pno}.json"),
                    "contours_path": str(out_path / f"contours_page{pno}.json"),
                    "render_path": str(out_path / f"rendered_page{pno}.png"),
                    "walls_path": str(out_path / f"walls_page{pno}.json"),
                },
            },
        )
        print("saved:", rooms_json_path)

        # door_mask (primary + fallback)
        rebuild_door_mask(out_path, pno)

        # report json (요약)
        pipeline_counts = json.loads(room_res.debug.get("_pipeline_counts", "{}"))
        report = {
            "pdf_path": pdf_path,
            "page_index": pno,
            "counts": pipeline_counts,
            "rooms": rooms_count,
            "files": {
                "rendered": room_res.debug.get("_rendered_png", ""),
                "edges": room_res.debug.get("_edges_png", ""),
                "overlay": room_res.debug.get("_overlay_png", ""),
            },
        }

        report_path = out_path / f"lines_page{pno}.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        reports.append(report)

        print("counts:", report["counts"])
        print("Saved:")
        for k, v in report["files"].items():
            print(" -", v)

    return {
        "pdf_type": "image",
        "pages": reports,
    }


def main():
    """
    사용법:
      1) 프로젝트 루트에서:
         python -m parser.image_outline

      2) PDF 경로 지정:
         python -m parser.image_outline samples/sample.pdf
    """
    import sys

    root = Path(__file__).resolve().parent.parent
    out_dir = root / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) argv로 PDF가 들어오면 그걸 사용
    if len(sys.argv) >= 2:
        pdf_path = sys.argv[1]
    else:
        # 2) out/lines_page0.json이 있으면 거기서 pdf_path 자동 로드
        lines_report = out_dir / "lines_page0.json"
        if lines_report.exists():
            try:
                payload = json.loads(lines_report.read_text(encoding="utf-8"))
                pdf_path = payload.get("pdf_path", "samples/sample.pdf")
            except Exception:
                pdf_path = "samples/sample.pdf"
        else:
            pdf_path = "samples/sample.pdf"

    # 상대경로면 루트 기준으로
    pdf_path_abs = str((root / pdf_path).resolve()) if not os.path.isabs(pdf_path) else pdf_path
    print("[STEP5] pdf_path =", pdf_path, "->", pdf_path_abs)

    extract_outlines_from_image_pdf(pdf_path_abs, out_dir=str(out_dir), page_limit=1)


if __name__ == "__main__":
    main()

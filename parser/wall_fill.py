from __future__ import annotations

from typing import List, Dict, Any
import numpy as np
import cv2


def build_wall_mask_from_lines(
    width: int,
    height: int,
    walls_lines: List[Dict[str, int]],
    cfg: Dict[str, Any] | None = None,
) -> np.ndarray:
    """
    walls_lines(중심선) -> 벽 '면' 마스크로 변환.
    - 두께 부여(thickness)
    - 연결/틈 메움(close)
    - 약한 dilation으로 빈틈 보강
    결과: 0/255 uint8 mask
    """
    cfg = cfg or {}

    thickness = int(cfg.get("thickness", 14))     # 벽 면으로 만들 두께
    close_ksize = int(cfg.get("close_ksize", 31)) # 끊김 메우기 (25~55)
    dilate_iter = int(cfg.get("dilate_iter", 1))  # 틈 보강
    blur = int(cfg.get("blur", 0))                # 필요시 3~5

    mask = np.zeros((height, width), dtype=np.uint8)

    # 1) 선분을 "굵게" 그려 벽 면으로 만든다
    for l in walls_lines:
        cv2.line(
            mask,
            (int(l["x1"]), int(l["y1"])),
            (int(l["x2"]), int(l["y2"])),
            255,
            thickness,
            lineType=cv2.LINE_8,
        )

    # (선택) 살짝 블러로 구멍 완화 후 다시 이진화
    if blur and blur >= 3:
        mask = cv2.GaussianBlur(mask, (blur, blur), 0)
        _, mask = cv2.threshold(mask, 30, 255, cv2.THRESH_BINARY)

    # 2) Closing으로 연결/틈 메움
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (close_ksize, close_ksize))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)

    # 3) 약간 dilation로 미세 틈 보강
    if dilate_iter > 0:
        dk = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        mask = cv2.dilate(mask, dk, iterations=dilate_iter)

    return mask

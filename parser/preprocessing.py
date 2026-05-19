import cv2
import numpy as np
from typing import Tuple, Dict, Any

def denoise_image(image: np.ndarray) -> np.ndarray:
    """
    Remove noise from the image while preserving edges as much as possible.
    """
    # Median blur is good for salt-and-pepper noise
    denoised = cv2.medianBlur(image, 3)
    
    # Optional: Fast Non-Local Means Denoising for more thorough cleanup
    # Phase 3: Activated for robust OCR/Vision on noisy scans
    denoised = cv2.fastNlMeansDenoising(denoised, None, 10, 7, 21)
    
    return denoised

def deskew_image(image: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Detect the skew angle and rotate the image to straighten it.
    """
    # Use edges to find the orientation
    gray = image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    # HoughLinesP to find dominant lines
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=10)
    
    if lines is None:
        return image, 0.0
    
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        
        # We care about angles near 0, 90, 180, 270 (horizontal/vertical)
        # Normalize angle to [-45, 45] range relative to nearest 90-deg step
        norm_angle = (angle + 45) % 90 - 45
        angles.append(norm_angle)
    
    if not angles:
        return image, 0.0
        
    median_angle = np.median(angles)
    
    if abs(median_angle) < 0.1: # Already straight enough
        return image, 0.0
        
    # Rotate the image
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    
    return rotated, float(median_angle)

def preprocess_for_pipeline(image: np.ndarray, apply_morphology: bool = True) -> Dict[str, Any]:
    """
    Run the full preprocessing suite.
    """
    # 1. Grayscale (if not already)
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
        
    # 2. Deskew
    deskewed, angle = deskew_image(gray)
    
    # 3. Denoise
    denoised = denoise_image(deskewed)
    
    # 4. Adaptive Thresholding (Binarization)
    # Phase 3: Dynamic block size based on image resolution
    h, w = denoised.shape
    block_size = 11 if max(h, w) < 2000 else 15
    binary = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block_size, 2
    )
    
    # 5. Morphological Operations (Phase 3)
    if apply_morphology:
        # Remove small dot noise
        kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open, iterations=1)
        
        # Connect broken lines
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close, iterations=1)
        
    return {
        "processed": binary,
        "deskew_angle": angle,
        "is_preprocessed": True
    }

if __name__ == "__main__":
    # Quick test if run directly
    import sys
    if len(sys.argv) > 1:
        img_path = sys.argv[1]
        img = cv2.imread(img_path)
        if img is not None:
            res = preprocess_for_pipeline(img)
            cv2.imwrite("debug_preprocessed.png", res["processed"])
            print(f"Preprocessed: angle={res['deskew_angle']:.2f}")

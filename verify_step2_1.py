import cv2
import numpy as np
import os
from parser.preprocessing import preprocess_for_pipeline, deskew_image

def test_preprocessing():
    print("=== Testing Preprocessing ===")
    
    # 1. Create a synthetic skewed image
    h, w = 512, 512
    img = np.ones((h, w), dtype=np.uint8) * 255
    # Draw some "walls" (skewed)
    cv2.line(img, (100, 100), (400, 105), (0, 0, 0), 5) # ~1 degree skew
    cv2.line(img, (100, 100), (95, 400), (0, 0, 0), 5)
    
    # Save original for comparison
    cv2.imwrite("test_original.png", img)
    
    # 2. Deskew test
    rotated, angle = deskew_image(img)
    print(f"Detected Angle: {angle:.2f}")
    cv2.imwrite("test_deskewed.png", rotated)
    
    # 3. Full pipeline test
    res = preprocess_for_pipeline(img)
    print(f"Full pipeline angle: {res['deskew_angle']:.2f}")
    cv2.imwrite("test_binary.png", res["processed"])
    
    print("=== Test Complete ===")
    if abs(angle) > 0.5:
        print("PASS: Skew detected")
    else:
        print("FAIL: Skew not detected (might be too small or threshold issue)")

if __name__ == "__main__":
    test_preprocessing()

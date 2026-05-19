import os
import sys
from pathlib import Path
import cv2
import fitz

# Add project root to sys.path
root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))

from parser.image_outline import extract_room_result_from_page

def main():
    samples_dir = root / "samples" / "noisy"
    out_dir = root / "out" / "test_vision"
    
    if not samples_dir.exists():
        print(f"Noisy samples directory not found at {samples_dir}. Creating...")
        samples_dir.mkdir(parents=True, exist_ok=True)
        print("Please place some noisy PDF or image samples in the 'samples/noisy' directory and re-run.")
        return
        
    files = list(samples_dir.glob("*.pdf")) + list(samples_dir.glob("*.jpg")) + list(samples_dir.glob("*.png"))
    
    if not files:
        print(f"No noisy samples found in {samples_dir}.")
        return
        
    print(f"Found {len(files)} samples to test.")
    
    success_count = 0
    total = len(files)
    
    for file in files:
        print(f"\n--- Testing {file.name} ---")
        try:
            if file.suffix.lower() == ".pdf":
                doc = fitz.open(str(file))
                page = doc[0]
                out_path = out_dir / file.stem
                res = extract_room_result_from_page(page, 0, out_path, str(file))
            else:
                # If image, we need a dummy page wrapper or just direct test
                print("Skipping direct image test for now, use PDF.")
                continue
                
            rooms = res.rooms
            walls = len(res.walls) if hasattr(res, 'walls') else 0
            
            print(f"Result: {len(rooms)} rooms, pipeline counts: {res.debug.get('_pipeline_counts')}")
            
            if len(rooms) > 0:
                success_count += 1
                
        except Exception as e:
            print(f"Error processing {file.name}: {e}")
            
    print(f"\n=== Test Summary ===")
    print(f"Success Rate: {success_count}/{total} ({(success_count/total)*100:.1f}%)")

if __name__ == "__main__":
    main()

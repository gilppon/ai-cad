import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from parser.pdf_vector import extract_vector_geometry

def test_vector_refinement():
    pdf_path = "samples/vector_test.pdf"
    if not os.path.exists(pdf_path):
        print(f"[!] Sample PDF not found at {pdf_path}")
        return

    print(f"[*] Testing vector refinement on {pdf_path}...")
    try:
        payload = extract_vector_geometry(pdf_path, page_index=0)
        
        print(f"[+] Extraction successful!")
        print(f"[*] Canvas: {payload['canvas']['width']}x{payload['canvas']['height']}")
        print(f"[*] Wall count: {payload['walls_count']}")
        
        # Check source metadata for refinement stats
        source = payload.get("source", {})
        print(f"[*] Raw paths: {source.get('raw_paths')}")
        print(f"[*] Raw segments: {source.get('raw_segments')}")
        print(f"[*] Refined walls: {source.get('refined_walls')}")
        
        # Save output for inspection
        out_path = "out/test_vector_refined.json"
        os.makedirs("out", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"[*] Payload saved to {out_path}")

    except Exception as e:
        print(f"[!] Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_vector_refinement()

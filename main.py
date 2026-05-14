import sys
import os
from core.engine import PipelineEngine

def main(pdf_path: str):
    if not os.path.exists(pdf_path):
        print(f"[!] File not found: {pdf_path}")
        return

    print(f"[*] Starting CAD SaaS MVP Pipeline for: {pdf_path}")
    
    # Initialize Engine
    project_id = os.path.basename(pdf_path).split('.')[0]
    engine = PipelineEngine(project_id=project_id)
    
    # Process
    result = engine.process_document(pdf_path)
    
    if result["status"] == "success":
        print("\n[+] Processing Complete!")
        print(f"[*] Project ID: {result['project_id']}")
        print(f"[*] Pages Processed: {result['page_count']}")
        print(f"[*] IFC Exported to: {result['artifacts']['ifc']}")
    else:
        print(f"\n[!] Processing Failed: {result.get('message')}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <pdf_path>")
    else:
        main(sys.argv[1])

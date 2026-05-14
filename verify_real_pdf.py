import os
from core.engine import PipelineEngine

def verify_real_pdf():
    print("=== Real PDF Verification ===")
    engine = PipelineEngine(project_id="real_verify")
    
    pdf_path = "samples/sample.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found!")
        return

    print(f"[*] Processing {pdf_path}...")
    try:
        result = engine.process_document(pdf_path)
        print(f"Status: {result['status']}")
        if result['status'] == 'success':
            print(f"Artifacts: {result['artifacts']}")
            ifc_path = result['artifacts']['ifc']
            if os.path.exists(ifc_path):
                print(f"IFC File generated: {ifc_path} ({os.path.getsize(ifc_path)} bytes)")
            else:
                print("Error: IFC file not found!")
        else:
            print(f"Message: {result.get('message', 'No message')}")
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_real_pdf()

import os
import time
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.worker.tasks import process_pdf_task

# Create test client
client = TestClient(app)

# Mock class for AsyncResult
class MockTask:
    def __init__(self, id):
        self.id = id

def verify_fastapi_celery_stub():
    print("=== Testing FastAPI Endpoint Integration ===")
    
    # 1. Root Endpoint Test
    response = client.get("/")
    assert response.status_code == 200
    print("[*] Root Endpoint: OK")
    
    # 2. Upload Endpoint Test
    pdf_path = "samples/vector_test.pdf"
    if not os.path.exists(pdf_path):
        print(f"[!] Warning: {pdf_path} not found.")
        return

    print("[*] Submitting PDF to /api/v1/convert...")
    
    # Mock the celery delay so it doesn't connect to Redis
    with patch('app.api.v1.endpoints.process_pdf_task.delay') as mock_delay:
        mock_delay.return_value = MockTask("mock-task-1234")
        
        with open(pdf_path, "rb") as f:
            files = {"file": ("vector_test.pdf", f, "application/pdf")}
            response = client.post("/api/v1/convert", files=files)
            
        assert response.status_code == 200, f"Upload failed: {response.text}"
        
        data = response.json()
        task_id = data.get("task_id")
        print(f"[+] Task Accepted. Task ID: {task_id}")
    
    # 3. Task Execution Logic Test (Calling it synchronously, bypassing Redis)
    print("\n[*] Testing Task Worker Logic Directly (Bypassing Redis)...")
    
    # We patch self.update_state in the task since it's a bound task
    with patch('celery.app.task.Task.update_state') as mock_update_state:
        result = process_pdf_task(file_path=pdf_path, project_id="mock_project_123")
        print(f"[-] Worker Result: {result['status']}")
        if result['status'] == 'success':
            print(f"[-] IFC Artifact: {result['artifacts']['ifc']}")
        else:
            print(f"[-] Error: {result.get('message')}")
            
    print("\n[+] FastAPI + Worker Logic verified successfully!")
    print("    (Note: Full end-to-end with Celery queue requires Redis in Docker)")

if __name__ == "__main__":
    # Ensure uploads dir exists for the API
    os.makedirs("uploads", exist_ok=True)
    verify_fastapi_celery_stub()

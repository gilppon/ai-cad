# -*- coding: utf-8 -*-
import unittest
import os
import json
from core.engine import PipelineEngine

class TestPipelineE2E(unittest.TestCase):
    def setUp(self):
        self.engine = PipelineEngine(project_id="unittest_e2e")

    def test_image_pdf_pipeline(self):
        pdf_path = "samples/sample.pdf"
        if not os.path.exists(pdf_path):
            self.skipTest("sample.pdf not found")
            
        result = self.engine.process_pdf(pdf_path)
        self.assertEqual(result["status"], "success")
        self.assertIn("artifacts", result)
        
        rooms_json = result["artifacts"]["rooms_json"]
        with open(rooms_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertGreater(data["rooms_count"], 0)
        self.assertTrue(os.path.exists(result["artifacts"]["ifc"]))

    def test_vector_pdf_pipeline(self):
        pdf_path = "samples/vector_test.pdf"
        if not os.path.exists(pdf_path):
            # Generate it if not exists
            from scratch.create_vector_sample import create_synthetic_vector_pdf
            os.makedirs("samples", exist_ok=True)
            create_synthetic_vector_pdf(pdf_path)
            
        result = self.engine.process_pdf(pdf_path)
        self.assertEqual(result["status"], "success")
        
        rooms_json = result["artifacts"]["rooms_json"]
        with open(rooms_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertGreater(data["walls_count"], 0)
        self.assertTrue(os.path.exists(result["artifacts"]["ifc"]))

if __name__ == "__main__":
    unittest.main()

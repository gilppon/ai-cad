# -*- coding: utf-8 -*-
import unittest
import os
import json
from core.engine import PipelineEngine

class TestMultiFloor(unittest.TestCase):
    def setUp(self):
        self.engine = PipelineEngine(project_id="unittest_multifloor")
        self.pdf_path = "samples/multi_page_test.pdf"

    def test_process_document_multi_floor(self):
        if not os.path.exists(self.pdf_path):
            self.skipTest("multi_page_test.pdf not found")
            
        result = self.engine.process_document(self.pdf_path)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["page_count"], 2)
        self.assertIn("ifc", result["artifacts"])
        
        ifc_path = result["artifacts"]["ifc"]
        self.assertTrue(os.path.exists(ifc_path))
        
        # Verify ifc content has 2 storeys (optional, but good)
        with open(ifc_path, "r") as f:
            content = f.read()
            self.assertIn("IFCBUILDINGSTOREY", content)
            # Should have multiple storeys if logic is correct
            # Count occurrences of IFCBUILDINGSTOREY
            count = content.count("IFCBUILDINGSTOREY")
            self.assertGreaterEqual(count, 2)

if __name__ == "__main__":
    unittest.main()

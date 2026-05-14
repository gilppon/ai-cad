import unittest
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from parser.pdf_vector import extract_vector_geometry
from parser.room_detect import detect_rooms
from core.engine import PipelineEngine

class TestGeometryExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vector_pdf = "samples/vector_test.pdf"
        cls.image_pdf = "samples/sample.pdf"
        
    def test_vector_geometry_extraction(self):
        """Test if vector PDF geometry extraction works without errors and returns expected structure."""
        if not os.path.exists(self.vector_pdf):
            self.skipTest(f"Sample PDF {self.vector_pdf} not found.")
            
        payload = extract_vector_geometry(self.vector_pdf, page_index=0)
        
        self.assertIn("walls", payload)
        self.assertIn("walls_count", payload)
        self.assertIn("rooms", payload)
        
        # Verify refinement logic worked (should have > 0 walls)
        self.assertGreater(payload["walls_count"], 0, "No walls extracted from vector PDF.")
        self.assertEqual(len(payload["walls"]), payload["walls_count"])
        
        # Check metadata
        self.assertIn("processing", payload)
        self.assertIn("source", payload)
        self.assertEqual(payload["source"].get("source"), "vector_extractor_v2_refined")
        
    def test_image_geometry_extraction(self):
        """Test if image (scanned) PDF room detection works without errors."""
        if not os.path.exists(self.image_pdf):
            self.skipTest(f"Sample PDF {self.image_pdf} not found.")
            
        room_result = detect_rooms(self.image_pdf, page=0)
        
        # RoomResult is typically an object with 'rooms' list or dict
        self.assertTrue(hasattr(room_result, 'rooms') or isinstance(room_result, dict))
        
        if hasattr(room_result, 'rooms'):
            self.assertGreater(len(room_result.rooms), 0, "No rooms detected from image PDF.")
            
    def test_pipeline_engine_integration(self):
        """Test if the core engine integrates correctly and resolves output paths."""
        engine = PipelineEngine(project_id="unittest_project")
        
        # Just check if directory is created
        self.assertTrue(os.path.exists(engine.output_dir))
        
        if os.path.exists(self.vector_pdf):
            result = engine.process_document(self.vector_pdf)
            self.assertEqual(result["status"], "success")
            self.assertIn("ifc", result["artifacts"])
            self.assertTrue(os.path.exists(result["artifacts"]["ifc"]))

if __name__ == "__main__":
    unittest.main()

import pytest
import os
from core.engine import PipelineEngine

@pytest.fixture
def engine():
    return PipelineEngine(project_id="test_suite")

def test_engine_initialization(engine):
    assert engine.project_id == "test_suite"
    assert os.path.exists(engine.output_dir)

def test_vector_processing_e2e(engine):
    pdf_path = "samples/vector_test.pdf"
    if not os.path.exists(pdf_path):
        pytest.skip("vector_test.pdf not found")
        
    result = engine.process_document(pdf_path)
    assert result["status"] == "success"
    assert "ifc" in result["artifacts"]
    assert os.path.exists(result["artifacts"]["ifc"])

def test_image_processing_e2e(engine):
    pdf_path = "samples/sample.pdf"
    if not os.path.exists(pdf_path):
        pytest.skip("sample.pdf not found")
        
    result = engine.process_document(pdf_path)
    assert result["status"] == "success"
    assert "ifc" in result["artifacts"]
    assert os.path.exists(result["artifacts"]["ifc"])

import fitz  # PyMuPDF

def detect_pdf_type(pdf_path):
    doc = fitz.open(pdf_path)

    vector_count = 0
    image_count = 0

    for page in doc:
        vector_count += len(page.get_drawings())
        image_count += len(page.get_images())

    if vector_count > 10:
        return {"pdf_type": "vector", "confidence": 0.9}

    if image_count > 0:
        return {"pdf_type": "image", "confidence": 0.8}

    return {"pdf_type": "unknown", "confidence": 0.0}

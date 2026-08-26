import fitz  # PyMuPDF

import logging

logger = logging.getLogger(__name__)

def detect_pdf_type(pdf_path):
    doc = fitz.open(pdf_path)
    
    pages_info = []
    total_vector = 0
    total_image = 0
    total_text_len = 0

    for page in doc:
        v_cnt = len(page.get_drawings())
        i_cnt = len(page.get_images())
        t_len = len(page.get_text())
        
        total_vector += v_cnt
        total_image += i_cnt
        total_text_len += t_len
        
        pages_info.append({
            "index": page.number,
            "rotation": page.rotation,
            "width": page.rect.width,
            "height": page.rect.height,
            "vector_count": v_cnt,
            "image_count": i_cnt,
            "text_length": t_len
        })

    # Classification logic
    # Lowered threshold: many vector PDFs might have fewer than 50 lines but are still vector
    if total_vector > 10:
        pdf_type = "vector"
        confidence = 0.95
    elif total_image > 0:
        pdf_type = "image"
        confidence = 0.85
    else:
        pdf_type = "unknown"
        confidence = 0.0

    return {
        "pdf_type": pdf_type,
        "confidence": confidence,
        "pages": pages_info,
        "metadata": {
            "page_count": len(doc),
            "is_scanned": total_vector == 0 and total_image > 0
        }
    }

if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) > 1:
        result = detect_pdf_type(sys.argv[1])
        logger.info(json.dumps(result, indent=2))
    else:
        logger.info("Usage: python parser/pdf_type.py <pdf_path>")

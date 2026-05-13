import sys
from parser.pdf_type import detect_pdf_type
from parser.image_outline import extract_outlines_from_image_pdf

def main(pdf_path: str):
    info = detect_pdf_type(pdf_path)
    print("PDF TYPE:", info)

    if info.get("pdf_type") != "image":
        print("❌ Only image PDF pipeline is wired right now.")
        return

    print("✅ Supported PDF (image) - extracting outlines (OpenCV)...")

    report = extract_outlines_from_image_pdf(
        pdf_path,
        out_dir="out",
        page_limit=1,
    )

    # image_outline.py 리턴 구조: {"pdf_type": "image", "pages": [...]}
    r0 = report["pages"][0]

    print("counts:", r0.get("counts"))
    print("Saved:")
    files = r0.get("files", {})
    for k in ["rendered", "edges", "overlay"]:
        v = files.get(k)
        if v:
            print(" -", v)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <pdf_path>")
    else:
        main(sys.argv[1])

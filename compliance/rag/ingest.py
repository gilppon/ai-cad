import os
import chromadb
from pathlib import Path
from compliance.rag.parser import LawXMLParser
from compliance.rag.downloader import download_all_targets

# DB 및 법령 저장소 경로
DB_PATH = Path("e:/project/cad_saas_mvp/vector_store/chromadb")
LAWS_DIR = Path("e:/project/cad_saas_mvp/data/laws")
COLLECTION_NAME = "japanese_building_laws"

def ingest_laws(batch_size: int = 100):
    """
    data/laws/ 내의 XML 법령 파일들을 파싱하여 ChromaDB에 적재합니다.
    법령 파일이 없는 경우 자동으로 다운로드합니다.
    """
    print("=============================================================")
    print("  ChromaDB Japanese Law Ingest Pipeline - Compliance RAG     ")
    print("=============================================================")
    
    # 1. 법령 XML 파일 검사 및 자동 다운로드
    xml_files = list(LAWS_DIR.glob("*.xml"))
    if not xml_files:
        print("[!] No law XML files found in data/laws/. Starting automatic download...")
        download_all_targets()
        xml_files = list(LAWS_DIR.glob("*.xml"))
        
    if not xml_files:
        print("[x] Error: No law XML files could be found or downloaded. Aborting ingestion.")
        return False
        
    print(f"[+] Found {len(xml_files)} law XML files to process.")
    
    # 2. XML 파싱 및 모든 청크 수집
    all_chunks = []
    for xml_path in xml_files:
        print(f"[*] Parsing: {xml_path.name}")
        try:
            parser = LawXMLParser(xml_path)
            chunks = parser.parse_articles()
            all_chunks.extend(chunks)
            print(f"    -> Parsed {len(chunks)} articles from '{parser.law_title}'")
        except Exception as e:
            print(f"    [-] Error parsing {xml_path.name}: {e}")
            
    # JSON 파일 파싱 (신규 규정 추가 지원)
    import json
    json_files = list(LAWS_DIR.glob("*.json"))
    for json_path in json_files:
        print(f"[*] Parsing JSON: {json_path.name}")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    all_chunks.append({
                        "id": item["id"],
                        "content": f"[{item['title']}]\n{item['content']}",
                        "metadata": {
                            "law_title": item["title"],
                            "tags": ",".join(item.get("tags", []))
                        }
                    })
            print(f"    -> Parsed {len(data)} items from '{json_path.name}'")
        except Exception as e:
            print(f"    [-] Error parsing {json_path.name}: {e}")
            
    # PDF 파일 파싱 (PDF 문서 수집 및 적재)
    try:
        import fitz
        pdf_files = list(LAWS_DIR.glob("*.pdf"))
        for pdf_path in pdf_files:
            print(f"[*] Parsing PDF: {pdf_path.name}")
            try:
                doc = fitz.open(pdf_path)
                content = ""
                for page in doc:
                    content += page.get_text()
                
                # Simple heuristic chunking by 'Article' keyword
                paragraphs = [p.strip() for p in content.split("Article") if p.strip()]
                for i, para in enumerate(paragraphs):
                    chunk_text = para if para.startswith("Japanese") else f"Article {para}"
                    all_chunks.append({
                        "id": f"pdf_{pdf_path.stem}_chunk_{i}",
                        "content": chunk_text,
                        "metadata": {
                            "law_title": pdf_path.stem,
                            "source": "pdf"
                        }
                    })
                print(f"    -> Parsed {len(paragraphs)} chunks from '{pdf_path.name}'")
            except Exception as e:
                print(f"    [-] Error parsing {pdf_path.name}: {e}")
    except ImportError:
        print("[!] PyMuPDF (fitz) not installed. Skipping PDF parsing.")
            
    total_chunks = len(all_chunks)
    if total_chunks == 0:
        print("[x] Error: No articles parsed. Aborting ingestion.")
        return False
        
    print(f"\n[+] Total parsed chunks to ingest: {total_chunks}")
    
    # 3. ChromaDB 초기화
    print("[*] Initializing ChromaDB PersistentClient...")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(DB_PATH))
    
    # 컬렉션 생성 (기존 컬렉션이 있으면 안전하게 초기화)
    try:
        print(f"[*] Removing existing collection '{COLLECTION_NAME}'...")
        client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        pass
        
    print(f"[+] Creating new collection '{COLLECTION_NAME}'...")
    collection = client.create_collection(name=COLLECTION_NAME)
    
    # 4. 배치(Batch) 단위 적재
    print(f"[*] Uploading to ChromaDB in batches (size: {batch_size})...")
    
    for i in range(0, total_chunks, batch_size):
        batch = all_chunks[i:i + batch_size]
        
        batch_documents = [chunk["content"] for chunk in batch]
        batch_metadatas = [chunk["metadata"] for chunk in batch]
        batch_ids = [chunk["id"] for chunk in batch]
        
        try:
            collection.add(
                documents=batch_documents,
                metadatas=batch_metadatas,
                ids=batch_ids
            )
            print(f"    [Batch] Uploaded chunks {i + 1} to {min(i + batch_size, total_chunks)} / {total_chunks}")
        except Exception as e:
            print(f"    [-] Error uploading batch starting at index {i}: {e}")
            return False
            
    print("\n[+] Ingestion completed successfully.")
    return True

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    ingest_laws()

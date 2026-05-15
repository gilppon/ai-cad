import os
import json
import chromadb
from pathlib import Path

# DB 경로 설정
DB_PATH = Path("e:/project/cad_saas_mvp/vector_store/chromadb")
LAWS_PATH = Path("e:/project/cad_saas_mvp/data/laws/sample_laws.json")

def ingest_laws():
    """
    sample_laws.json을 읽어 ChromaDB에 임베딩 및 저장합니다.
    (MVP 버전이므로 기본 제공되는 sentence-transformers 임베딩을 사용합니다)
    """
    print("Initialize ChromaDB client...")
    client = chromadb.PersistentClient(path=str(DB_PATH))
    
    # 컬렉션 생성 (기존에 있으면 삭제하고 다시 생성)
    collection_name = "japanese_building_laws"
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass
        
    collection = client.create_collection(name=collection_name)
    
    print(f"Loading laws from {LAWS_PATH}...")
    if not LAWS_PATH.exists():
        print(f"File not found: {LAWS_PATH}")
        return
        
    with open(LAWS_PATH, "r", encoding="utf-8") as f:
        laws = json.load(f)
        
    documents = []
    metadatas = []
    ids = []
    
    for law in laws:
        # 문맥과 메타데이터 준비
        # 임베딩의 성능을 높이기 위해 제목과 내용을 합쳐서 저장
        text_content = f"{law['title']}\n{law['content']}"
        documents.append(text_content)
        
        metadatas.append({
            "title": law['title'],
            "tags": ",".join(law.get('tags', []))
        })
        
        ids.append(law['id'])
        
    print(f"Inserting {len(documents)} documents into ChromaDB...")
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    print("Ingestion completed successfully.")

if __name__ == "__main__":
    ingest_laws()

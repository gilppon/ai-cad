import chromadb
from typing import List, Dict, Any

from pipeline.paths import PROJECT_ROOT

import logging

logger = logging.getLogger(__name__)

# SP2/A-3: 구 저장소(e:/project/cad_saas_mvp) 하드코딩 제거 - 저장소 상대 경로로 수렴
DB_PATH = PROJECT_ROOT / "vector_store" / "chromadb"

def retrieve_relevant_laws(query_text: str, n_results: int = 3) -> List[Dict[str, Any]]:
    """
    쿼리를 입력받아 ChromaDB에서 관련 법규 조항을 검색합니다.
    """
    if not DB_PATH.exists():
        logger.info(f"ChromaDB not found at {DB_PATH}")
        return []
        
    client = chromadb.PersistentClient(path=str(DB_PATH))
    collection_name = "japanese_building_laws"
    
    try:
        collection = client.get_collection(name=collection_name)
    except Exception:
        logger.info(f"Collection {collection_name} not found.")
        return []

    results = collection.query(
        query_texts=[query_text],
        n_results=n_results
    )
    
    retrieved_laws = []
    if results and results.get('documents') and len(results['documents']) > 0:
        docs = results['documents'][0]
        metas = results['metadatas'][0]
        ids = results['ids'][0]
        
        for doc, meta, doc_id in zip(docs, metas, ids):
            law_title = meta.get("law_title", "")
            article_title = meta.get("article_title", "")
            full_title = f"[{law_title}] {article_title}".strip() if law_title or article_title else doc_id
            
            retrieved_laws.append({
                "id": doc_id,
                "title": full_title,
                "content": doc
            })
            
    return retrieved_laws

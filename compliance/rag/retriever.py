import chromadb
from typing import List, Dict, Any

from pipeline.paths import PROJECT_ROOT

import logging

logger = logging.getLogger(__name__)

# SP2/A-3: 구 저장소(e:/project/cad_saas_mvp) 하드코딩 제거 - 저장소 상대 경로로 수렴
DB_PATH = PROJECT_ROOT / "vector_store" / "chromadb"

def retrieve_relevant_laws(query_text: str, n_results: int = 3) -> List[Dict[str, Any]]:
    """
    쿼리를 입력받아 관련 법규 조항을 검색합니다.
    1순위 ChromaDB, 부재·파손 시 XML 직접 폴백 (STATE G5 — 비ASCII 경로 HNSW 이슈 대응).
    반환 스키마는 동일: [{id, title("[법률명] 조항명"), content}].
    """
    if DB_PATH.exists():
        try:
            found = _retrieve_via_chroma(query_text, n_results)
            if found:
                return found
        except Exception as e:
            logger.warning(f"[Retriever] ChromaDB 실패, XML 폴백: {e}")
    return _retrieve_via_xml(query_text, n_results)


def _retrieve_via_chroma(query_text: str, n_results: int) -> List[Dict[str, Any]]:
    import chromadb

    client = chromadb.PersistentClient(path=str(DB_PATH))
    try:
        collection = client.get_collection(name="japanese_building_laws")
    except Exception:
        logger.info("[Retriever] Collection japanese_building_laws not found.")
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


def _retrieve_via_xml(query_text: str, n_results: int) -> List[Dict[str, Any]]:
    from compliance.rag.corpus_search import hybrid_corpus_search

    keywords = [t for t in str(query_text or "").split() if t]
    hits = hybrid_corpus_search(str(query_text or ""), keywords, top_k=n_results)
    out = []
    for h in hits:
        title = f"[{h.get('law_title', '')}] {h.get('article_caption', '')}".strip()
        out.append({
            "id": f"{h.get('law_id', '')}_art_{h.get('article_num', '')}",
            "title": title or h.get("article_num", ""),
            "content": h.get("document", ""),
        })
    return out

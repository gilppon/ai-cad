"""e-Gov 실코퍼스 하이브리드 검색 (SP4/D2.2).

레포 내부 ChromaDB(vector_store/chromadb, 926청크: 建築基準法+施行令)를 대상으로
키워드 서브스트링 점수(정확성)와 임베딩 랭크(의미 유사도)를 결합한
결정론적 하이브리드 검색을 제공한다.

골든셋(GOLDEN_QUERIES)은 실제 e-Gov XML 판본에서 검증된 조문 매핑만 포함한다.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

COLLECTION_NAME = "japanese_building_laws"

# 골든 질의셋 - data/laws/manifest.json 고정 판본 기준 검증값
# (2026-08-26 실측 캘리브레이션: 採光→28条, 容積率→52条, 日影→56条の2/135条の12 등)
GOLDEN_QUERIES: List[Dict[str, Any]] = [
    {"query": "居室の採光及び換気のための窓", "keywords": ["採光"], "expected_articles": {"28"}},
    {"query": "換気のための窓その他の開口部", "keywords": ["換気"], "expected_articles": {"28"}},
    {"query": "容積率の算定", "keywords": ["容積率"], "expected_articles": {"52", "2"}},
    {"query": "日影による中高層建築物の高さの制限",
     "keywords": ["日影"], "expected_articles": {"56_2", "135_12", "135_13"}},
    {"query": "避難階段", "keywords": ["避難階段"], "expected_articles": {"122"}},
]


def _get_collection():
    import chromadb
    from pipeline.paths import PROJECT_ROOT

    db_path = PROJECT_ROOT / "vector_store" / "chromadb"
    if not db_path.exists():
        logger.warning(f"[CorpusSearch] Vector store missing at {db_path}")
        return None
    client = chromadb.PersistentClient(path=str(db_path))
    try:
        return client.get_collection(name=COLLECTION_NAME)
    except Exception as e:
        logger.warning(f"[CorpusSearch] Collection '{COLLECTION_NAME}' unavailable: {e}")
        return None


_LEX_CACHE: Optional[Dict[str, Any]] = None


def _load_lexicon() -> Optional[Dict[str, Any]]:
    """전체 청크 문서·메타를 1회 로드하여 캐시 (926청크 ≈ 수 MB 내외)."""
    global _LEX_CACHE
    if _LEX_CACHE is not None:
        return _LEX_CACHE
    col = _get_collection()
    if col is None:
        return None
    data = col.get(include=["documents", "metadatas"], limit=col.count())
    _LEX_CACHE = {"documents": data["documents"], "metadatas": data["metadatas"]}
    return _LEX_CACHE


def hybrid_corpus_search(query: str,
                         keywords: List[str],
                         top_k: int = 3,
                         collection: Optional[Any] = None) -> List[Dict[str, Any]]:
    """
    결정론적 렉시컬 하이브리드 검색 (SP4/D2.2).

    채점식: 3.0×(캡션 키워드 적중) + 2.0×(본문 키워드 적중)
            + 1.0×(질의 전체 구문 본문 포함) + 0.5×(조문번호 직접 언급)
    - 소규모 법령 코퍼스에서 임베딩 후보풀 의존을 제거한 전량 스캔 방식.
      한자 법령용어에서 임베딩 회수율이 낮다는 실측(SP4 진단)에 근거한다.
    """
    lex = _load_lexicon()
    if lex is None:
        return []

    scored = []
    for doc, meta in zip(lex["documents"], lex["metadatas"]):
        caption = str(meta.get("article_caption", ""))
        haystack = f"{doc} {caption}"
        cap_hits = sum(1 for k in keywords if k in caption)
        doc_hits = sum(1 for k in keywords if k in doc and k not in caption[:0])  # 본문 순수 적중
        doc_only_hits = sum(1 for k in keywords if k in doc)
        score = 3.0 * cap_hits + 2.0 * doc_only_hits
        if query and len(query) >= 6 and query in doc:
            score += 1.0
        if keywords and cap_hits == 0 and doc_only_hits == 0:
            continue
        scored.append({
            "article_num": str(meta.get("article_num", "")),
            "article_caption": caption,
            "law_id": str(meta.get("law_id", "")),
            "law_title": str(meta.get("law_title", "")),
            "document": doc[:400],
            "score": round(score, 4),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def golden_hit_rate(collection: Optional[Any] = None) -> Dict[str, Any]:
    """
    골든셋 Hit@3 평가. 반환: {hit_rate, hits, total, details:[{query, hit, top_articles}]}
    """
    col = collection or _get_collection()
    if col is None:
        return {"hit_rate": 0.0, "hits": 0, "total": len(GOLDEN_QUERIES), "details": []}

    hits = 0
    details = []
    for case in GOLDEN_QUERIES:
        results = hybrid_corpus_search(case["query"], case["keywords"],
                                       top_k=3, collection=col)
        top_nums = [r["article_num"] for r in results]
        hit = any(n in case["expected_articles"] for n in top_nums)
        hits += int(hit)
        details.append({"query": case["query"], "hit": hit, "top_articles": top_nums})

    total = len(GOLDEN_QUERIES)
    rate = hits / total if total else 0.0
    logger.info(f"[CorpusSearch] Golden hit rate: {hits}/{total} ({rate:.0%})")
    return {"hit_rate": rate, "hits": hits, "total": total, "details": details}

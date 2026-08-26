import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional

import logging

logger = logging.getLogger(__name__)

class LawXMLParser:
    """
    e-Gov 법령 XML을 파싱하여 계층형 구조와 메타데이터를 유지한 채 RAG용 청크로 분할합니다.
    """
    
    def __init__(self, xml_path: Path):
        self.xml_path = xml_path
        self.law_id = xml_path.stem
        self.tree = ET.parse(xml_path)
        self.root = self.tree.getroot()
        
        # 부모 노드 맵 구축 (계층 경로 역추적용)
        self.parent_map = {child: parent for parent in self.tree.iter() for child in parent}
        
        # 법령명 추출
        self.law_title = self._extract_law_title()
        
    def _extract_law_title(self) -> str:
        """
        XML 내부에서 법령 제목(LawTitle)을 추출합니다.
        """
        title_node = self.root.find(".//LawTitle")
        if title_node is not None:
            # 모든 내부 텍스트 취합
            return "".join(title_node.itertext()).strip()
        return self.law_id  # fallback
        
    def _get_hierarchy_path(self, article_node: ET.Element) -> str:
        """
        특정 Article 노드로부터 상위 계층(편/장/절 등)의 경로를 빌드합니다.
        """
        path_segments = []
        curr = article_node
        
        while curr in self.parent_map:
            parent = self.parent_map[curr]
            
            if parent.tag == "Chapter":
                title_node = parent.find("ChapterTitle")
                if title_node is not None:
                    path_segments.append("".join(title_node.itertext()).strip())
            elif parent.tag == "Section":
                title_node = parent.find("SectionTitle")
                if title_node is not None:
                    path_segments.append("".join(title_node.itertext()).strip())
            elif parent.tag == "Part":
                title_node = parent.find("PartTitle")
                if title_node is not None:
                    path_segments.append("".join(title_node.itertext()).strip())
            elif parent.tag == "Subchapter":
                title_node = parent.find("SubchapterTitle")
                if title_node is not None:
                    path_segments.append("".join(title_node.itertext()).strip())
                    
            curr = parent
            
        return " > ".join(reversed(path_segments))

    def _clean_text(self, text: Optional[str]) -> str:
        if not text:
            return ""
        return text.strip().replace("\n", " ").replace("\r", "")

    def parse_articles(self) -> List[Dict[str, Any]]:
        """
        XML에서 모든 Article(조)을 추출하여 RAG용 청크 데이터 목록을 생성합니다.
        """
        chunks = []
        articles = self.root.findall(".//Article")
        existing_ids = set()
        
        for article in articles:
            article_num = article.attrib.get("Num", "")
            
            # 조 캡션 (예: （目的）)
            caption_node = article.find("ArticleCaption")
            article_caption = "".join(caption_node.itertext()).strip() if caption_node is not None else ""
            
            # 조 제목 (예: 第一条)
            title_node = article.find("ArticleTitle")
            article_title = "".join(title_node.itertext()).strip() if title_node is not None else ""
            
            # 상위 계층 경로
            hierarchy = self._get_hierarchy_path(article)
            
            # 본문 내용 구성 (항 및 호)
            content_lines = []
            
            # 조의 제목 및 캡션 추가
            header = f"[{self.law_title}]"
            if hierarchy:
                header += f" {hierarchy}"
            header += f" {article_title}"
            if article_caption:
                header += f" {article_caption}"
            
            content_lines.append(header)
            
            # Paragraph(항) 순회
            paragraphs = article.findall("Paragraph")
            for p_idx, p in enumerate(paragraphs):
                p_num_node = p.find("ParagraphNum")
                p_num = "".join(p_num_node.itertext()).strip() if p_num_node is not None else ""
                
                # 항의 주 본문 (ParagraphSentence)
                p_sent_node = p.find("ParagraphSentence")
                p_text = ""
                if p_sent_node is not None:
                    p_text = "".join(p_sent_node.itertext()).strip()
                
                if p_text:
                    if p_num and p_num != "1": # 1항인 경우 보통 번호를 표시 안 하거나 생략하기도 하므로 유연히 처리
                        content_lines.append(f"{p_num} {p_text}")
                    else:
                        content_lines.append(p_text)
                
                # 호(Item) 순회
                items = p.findall("Item")
                for item in items:
                    item_title_node = item.find("ItemTitle")
                    item_title = "".join(item_title_node.itertext()).strip() if item_title_node is not None else ""
                    
                    item_sent_node = item.find("ItemSentence")
                    item_text = ""
                    if item_sent_node is not None:
                        item_text = "".join(item_sent_node.itertext()).strip()
                        
                    if item_text:
                        content_lines.append(f"  {item_title} {item_text}")
            
            full_content = "\n".join(content_lines)
            
            # 고유 덩어리 ID 생성
            chunk_id = f"{self.law_id}_art_{article_num}"
            if chunk_id in existing_ids:
                counter = 1
                new_chunk_id = f"{chunk_id}_dup{counter}"
                while new_chunk_id in existing_ids:
                    counter += 1
                    new_chunk_id = f"{chunk_id}_dup{counter}"
                chunk_id = new_chunk_id
            
            existing_ids.add(chunk_id)
            
            # 시맨틱 태그 생성 (wet-area, structural, safety 등 법률 내용 기반 키워드 매핑 가능)
            tags = []
            if any(k in full_content for k in ["水", "排水", "浴室", "便所", "配管"]):
                tags.append("wet-area")
            if any(k in full_content for k in ["構造", "耐力", "柱", "梁", "壁"]):
                tags.append("structural")
            if any(k in full_content for k in ["防火", "避難", "階段", "廊下"]):
                tags.append("safety")
            if any(k in full_content for k in ["画定", "敷地", "道路", "容積率"]):
                tags.append("zoning")

            chunks.append({
                "id": chunk_id,
                "content": full_content,
                "metadata": {
                    "law_id": self.law_id,
                    "law_title": self.law_title,
                    "article_num": article_num,
                    "article_title": article_title,
                    "article_caption": article_caption,
                    "hierarchy": hierarchy,
                    "tags": ",".join(tags)
                }
            })
            
        return chunks

if __name__ == "__main__":
    # 간단한 단독 파서 실행 및 출력 검증
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    
    test_file = Path("e:/project/cad_saas_mvp/data/laws/325AC0000000201.xml")
    if test_file.exists():
        logger.info(f"Testing parser on: {test_file}")
        parser = LawXMLParser(test_file)
        logger.info(f"Law Title: {parser.law_title}")
        chunks = parser.parse_articles()
        logger.info(f"Parsed {len(chunks)} articles.")
        if chunks:
            logger.info("\n--- First Parsed Chunk Sample ---")
            sample = chunks[0]
            logger.info(f"ID: {sample['id']}")
            logger.info(f"Metadata: {sample['metadata']}")
            logger.info("Content:")
            logger.info(sample['content'])
    else:
        logger.info(f"Test file not found: {test_file}")

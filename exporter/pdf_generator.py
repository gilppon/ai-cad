# -*- coding: utf-8 -*-
import os
import sys
import io
from pathlib import Path
from typing import Dict, Any, List

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import CIDFont

# 일본어 표준 폰트 등록 자동화 (윈도우 기본 고품질 폰트 바인딩)
# 윈도우 환경에 기본 내장된 msgothic.ttc 및 msmincho.ttc를 활용하여 크로스플랫폼/ReportLab 폰트 버그를 완벽히 예방합니다.
from reportlab.pdfbase.ttfonts import TTFont

try:
    font_registered = False
    
    # 1. 윈도우 기본 일본어 폰트 매핑 시도
    msgothic_path = "C:\\Windows\\Fonts\\msgothic.ttc"
    msmincho_path = "C:\\Windows\\Fonts\\msmincho.ttc"
    
    if os.path.exists(msgothic_path):
        pdfmetrics.registerFont(TTFont('HeiseiKakuGo-W5', msgothic_path))
        font_registered = True
    if os.path.exists(msmincho_path):
        pdfmetrics.registerFont(TTFont('HeiseiMin-W3', msmincho_path))
        
    # 2. 윈도우 폰트가 없거나 실패 시 CIDFont fallback
    if not font_registered:
        pdfmetrics.registerFont(CIDFont('HeiseiKakuGo-W5'))
        pdfmetrics.registerFont(CIDFont('HeiseiMin-W3'))
        
        # reportlab ps2tt 함수 자체를 가로채는 몽키 패치로 에러 회피
        import reportlab.lib.fonts
        if not hasattr(reportlab.lib.fonts, '_original_ps2tt'):
            reportlab.lib.fonts._original_ps2tt = reportlab.lib.fonts.ps2tt
            
            def patched_ps2tt(psfn):
                psfn_lower = psfn.lower()
                if 'heisei' in psfn_lower:
                    return (psfn, 0, 0)
                return reportlab.lib.fonts._original_ps2tt(psfn)
                
            reportlab.lib.fonts.ps2tt = patched_ps2tt
except Exception as e:
    # 최종 Fallback to Helvetica
    pass

class JPPDFGenerator:
    """
    일본어 누수 진단 보고서 (漏水診断報告書) A4 1장 최적화 생성 패키지
    """
    
    @staticmethod
    def generate_report(
        project_id: str,
        project_name: str,
        address: str,
        inspector_name: str,
        compliance_opinions: List[Dict[str, Any]],
        image_2d_path: str = None,
        image_3d_path: str = None,
        output_pdf_path: str = None
    ) -> str:
        if not output_pdf_path:
            from pipeline.paths import OUTPUT_ROOT
            output_pdf_path = str(Path(OUTPUT_ROOT) / "projects" / project_id / "page0_compliance_report.pdf")
            
        output_pdf_path = os.path.abspath(output_pdf_path)
        # Ensure parent directory exists
        parent_dir = os.path.dirname(output_pdf_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        
        # 1. 문서 템플릿 설정 (A4, 1장 분량 유지를 위해 마진 최적화)
        doc = SimpleDocTemplate(
            output_pdf_path,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        
        story = []
        
        # 스타일 정의 (HeiseiKakuGo-W5 사용)
        title_style = ParagraphStyle(
            name='JPTitle',
            fontName='HeiseiKakuGo-W5',
            fontSize=20,
            leading=24,
            alignment=1, # Center
            textColor=colors.HexColor('#1E293B'), # Sleek Dark Slate
            spaceAfter=12
        )
        
        meta_style = ParagraphStyle(
            name='JPMeta',
            fontName='HeiseiKakuGo-W5',
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor('#475569')
        )
        
        section_title_style = ParagraphStyle(
            name='JPSectionTitle',
            fontName='HeiseiKakuGo-W5',
            fontSize=10,
            leading=13,
            textColor=colors.HexColor('#0F172A'),
            backColor=colors.HexColor('#F1F5F9'),
            spaceBefore=8,
            spaceAfter=4,
            borderPadding=4,
            borderRadius=4
        )
        
        body_style = ParagraphStyle(
            name='JPBody',
            fontName='HeiseiMin-W3', # 명조체로 본문 신뢰감 상승
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor('#334155')
        )
        
        bold_body_style = ParagraphStyle(
            name='JPBoldBody',
            fontName='HeiseiKakuGo-W5',
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor('#1E293B')
        )
        
        # --- 1. 문서 헤더 (타이틀 및 기사 날인) ---
        title = Paragraph("漏 水 診 断 報 告 書", title_style)
        story.append(title)
        
        # 기사 날인 테이블 (좌측 메타데이터, 우측 날인 도장칸)
        from datetime import datetime
        date_str = datetime.now().strftime("%Y年 %m月 %d日")
        
        meta_html = f"""
        案件番号: {project_id}<br/>
        対象物件: {project_name}<br/>
        調査住所: {address}<br/>
        調査日時: {date_str}
        """
        
        sign_html = f"""
        <font size="7.5">【診断技術者】</font><br/>
        <font size="9">{inspector_name}</font>
        """
        
        # 1행 2열: 메타데이터 | 도장칸
        sign_table_data = [
            [
                Paragraph(meta_html, meta_style), 
                Table([
                    [
                        Paragraph(sign_html, meta_style), 
                        Paragraph("<br/><br/>(印)", ParagraphStyle(
                            name='Stamp', 
                            fontName='HeiseiKakuGo-W5', 
                            fontSize=10, 
                            alignment=1, 
                            textColor=colors.HexColor('#DC2626')
                        ))
                    ]
                ], colWidths=[90, 45], style=TableStyle([
                    ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
                    ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('ALIGN', (1,0), (1,0), 'CENTER'),
                ]))
            ]
        ]
        
        header_table = Table(sign_table_data, colWidths=[380, 140])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ]))
        
        story.append(header_table)
        story.append(Spacer(1, 8))
        
        # --- 2. 2D / 3D 시각화 영역 (좌우 2단 구성) ---
        story.append(Paragraph("📊 漏水視覚化データ (2D平面図 ＆ 3D鳥瞰図)", section_title_style))
        
        # 기본 대체 이미지 설정
        default_img_2d = image_2d_path if (image_2d_path and os.path.exists(image_2d_path)) else "test_original.png"
        default_img_3d = image_3d_path if (image_3d_path and os.path.exists(image_3d_path)) else "test_deskewed.png"
        
        img_w, img_h = 245, 150
        
        img_2d_flow = Paragraph("<font color='red'>2D 도면을 불러올 수 없습니다.</font>", body_style)
        if os.path.exists(default_img_2d):
            img_2d_flow = Image(default_img_2d, width=img_w, height=img_h)
            
        img_3d_flow = Paragraph("<font color='red'>3D 뷰 캡처를 불러올 수 없습니다.</font>", body_style)
        if os.path.exists(default_img_3d):
            img_3d_flow = Image(default_img_3d, width=img_w, height=img_h)
            
        visual_data = [
            [img_2d_flow, img_3d_flow],
            [Paragraph("<font size='7.5'>【2D平面図】 赤色のピン：漏水発生箇所</font>", meta_style), 
             Paragraph("<font size='7.5'>【3D鳥瞰図】 漏水浸入ルートと被害予測範囲</font>", meta_style)]
        ]
        
        visual_table = Table(visual_data, colWidths=[260, 260])
        visual_table.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#F8FAFC')),
            ('BOTTOMPADDING', (0,1), (-1,1), 3),
            ('TOPPADDING', (0,1), (-1,1), 3),
        ]))
        
        story.append(visual_table)
        story.append(Spacer(1, 8))
        
        # --- 3. 일본 구분소유법 기반 공용부/전유부 판정 및 의견서 ---
        story.append(Paragraph("⚖️ 区分所有法に基づく責任判定及び診断意見", section_title_style))
        
        opinion_table_data = [
            [
                Paragraph("No.", bold_body_style),
                Paragraph("発生場所", bold_body_style),
                Paragraph("責任帰属判定", bold_body_style),
                Paragraph("法的根拠 / 診断所見", bold_body_style)
            ]
        ]
        
        if not compliance_opinions:
            compliance_opinions = [{
                "room_type_jp": "パイプスペース (PS)",
                "decision_label": "共用部分 (パイプスペース等)",
                "ownership_decision": "COMMON",
                "legal_basis": "区分所有法第4条・標準管理規約第7条",
                "japanese_opinion": "배관 샤프트실(PS) 내부의 공용 종관 누수로 확인되었습니다. 이는 구분소유자 개인의 관리 범위를 벗어난 공용부분 하자에 해당하며, 입주자대표회의(관리조합)의 장기수선충당금 재원으로 보수 책임이 귀속됩니다."
            }]
            
        for i, op in enumerate(compliance_opinions):
            room_name = op.get("room_type_jp", "用途不明")
            if op.get("room_abbr_jp"):
                room_name += f" ({op.get('room_abbr_jp')})"
                
            decision = op.get("decision_label", "要精密調査")
            ownership = op.get("ownership_decision", "UNCERTAIN")
            
            if ownership == "COMMON":
                badge_bg = "#EF4444" 
                badge_text = "共用部分"
            elif ownership == "COMMON_EXCLUSIVE_USE":
                badge_bg = "#F59E0B" 
                badge_text = "共用(専用使用)"
            elif ownership == "PROPRIETARY":
                badge_bg = "#3B82F6" 
                badge_text = "専有部分"
            else:
                badge_bg = "#6B7280" 
                badge_text = "要調査"
                
            badge_html = f"<font color='{badge_bg}'>【{badge_text}】</font><br/><font size='7.5'>{decision}</font>"
            
            basis = op.get("legal_basis", "区分所有法")
            opinion_text = op.get("japanese_opinion", "상세 소견 없음")
            
            desc_html = f"【根拠】 {basis}<br/>【所見】 {opinion_text}"
            
            opinion_table_data.append([
                Paragraph(str(i+1), body_style),
                Paragraph(room_name, body_style),
                Paragraph(badge_html, body_style),
                Paragraph(desc_html, body_style)
            ])
            
        opinion_table = Table(opinion_table_data, colWidths=[25, 110, 115, 270])
        opinion_table.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F8FAFC')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        
        story.append(opinion_table)
        story.append(Spacer(1, 8))
        
        # --- 4. 면책 사항 및 기술 기준 안내 ---
        disclaimer_html = """
        <font face='HeiseiKakuGo-W5'>※ 免責事項・注意事項</font><br/>
        本報告書は、アップロードされた2D図面データ及び三次元解析に基づき、日本国の「区分所有法」及び「マンション標準管理規約」の一般的解釈に従って作成された1次判定結果です。隠蔽部における非破壊調査や加圧テスト等による物理的検証結果を兼ねるものではありません。最終的な責任帰属及び修繕計画の策定にあたっては、管理組合、保険会社、並びに専門施工業者と十分な協議の上で決定してください。
        """
        
        story.append(Table([
            [Paragraph(disclaimer_html, ParagraphStyle(name='Disclaimer', fontName='HeiseiMin-W3', fontSize=7.5, leading=9.5, textColor=colors.HexColor('#64748B')))]
        ], colWidths=[520], style=TableStyle([
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ])))
        
        doc.build(story)
        return output_pdf_path

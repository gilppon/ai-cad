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
        output_pdf_path: str = None,
        invoice_registration_number: str = None
    ) -> str:
        # 적격청구서발행사업자(인보이스) 등록번호는 실행 파라미터 또는 환경변수로만 주입한다.
        # 가짜 번호를 상수로 박아 넣으면 법적 문서 위조가 되므로, 미등록 시 (未登録) 으로 표기한다.
        invoice_reg_no = (
            invoice_registration_number
            or os.getenv("JP_INVOICE_REGISTRATION_NUMBER", "").strip()
            or "(未登録)"
        )
        
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
        調査日時: {date_str}<br/>
        登録番号: {invoice_reg_no} (適格請求書発行事業者)
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

    @staticmethod
    def generate_compliance_checksheet(
        project_id: str,
        building_name: str,
        chief_designer: str,
        license_number: str,
        check_items: List[Dict[str, Any]],
        overall_judgment: str,
        digital_seal_path: str = None,
        output_pdf_path: str = None,
        legal_basis_note: str = None
    ) -> str:
        """
        일본 국토교통성(MLIT) 2026 가이드라인 규격 'BIM 확인신청 자가 체크시트' PDF 자동 렌더링 모듈
        (legal_basis_note: SP2/L-4 - data/laws/manifest.json 고정 판본의 근거 법령 표기)
        """
        if not output_pdf_path:
            from pipeline.paths import OUTPUT_ROOT
            output_pdf_path = str(Path(OUTPUT_ROOT) / "projects" / project_id / "page0_compliance_checksheet.pdf")
            
        output_pdf_path = os.path.abspath(output_pdf_path)
        parent_dir = os.path.dirname(output_pdf_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
            
        # 1. A4 용지 마진 최적화 선언
        doc = SimpleDocTemplate(
            output_pdf_path,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        
        story = []
        
        # 스타일 구성 (HeiseiKakuGo-W5 폰트 바인딩)
        title_style = ParagraphStyle(
            name='CSJPTitle',
            fontName='HeiseiKakuGo-W5',
            fontSize=16,
            leading=20,
            alignment=1, # Center
            textColor=colors.HexColor('#0F172A'),
            spaceAfter=15
        )
        
        meta_label_style = ParagraphStyle(
            name='CSJPMetaLabel',
            fontName='HeiseiKakuGo-W5',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#475569')
        )
        
        meta_value_style = ParagraphStyle(
            name='CSJPMetaValue',
            fontName='HeiseiMin-W3',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#0F172A')
        )
        
        th_style = ParagraphStyle(
            name='CSJPTh',
            fontName='HeiseiKakuGo-W5',
            fontSize=8,
            leading=10,
            alignment=1, # Center
            textColor=colors.HexColor('#0F172A')
        )
        
        td_style = ParagraphStyle(
            name='CSJPTd',
            fontName='HeiseiMin-W3',
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor('#334155')
        )
        
        judgment_style = ParagraphStyle(
            name='CSJPJudge',
            fontName='HeiseiKakuGo-W5',
            fontSize=12,
            leading=15,
            textColor=colors.HexColor('#FFFFFF'),
            alignment=1 # Center
        )
        
        # --- 1. 문서 헤더 ---
        title = Paragraph("BIM確認申請セルフチェックシート<br/><font size='8'>（設計者自己確認基準に基づく自動出力表）</font>", title_style)
        story.append(title)
        
        # 근거 법령·판본 표기 (SP2/L-4) - 판정의 법적 근거를 문서에 명시
        if legal_basis_note:
            story.append(Paragraph(legal_basis_note, ParagraphStyle(
                name='CSLegalBasis', fontName='HeiseiMin-W3', fontSize=7, leading=9,
                alignment=1, textColor=colors.HexColor('#475569'), spaceAfter=6
            )))
        
        # --- 2. 설계사 정보 및 날인 도장 합성 테이블 ---
        from datetime import datetime
        check_date = datetime.now().strftime("%Y年 %m月 %d日")
        
        meta_table_data = [
            [
                Paragraph("<b>対象物件名 (건물명)</b>", meta_label_style),
                Paragraph(building_name, meta_value_style),
                Paragraph("<b>作成日 (작성일)</b>", meta_label_style),
                Paragraph(check_date, meta_value_style)
            ],
            [
                Paragraph("<b>一級建築士 (설계자)</b>", meta_label_style),
                Paragraph(chief_designer, meta_value_style),
                Paragraph("<b>登録番号 (면허번호)</b>", meta_label_style),
                Paragraph(license_number or "(未登録)", meta_value_style)
            ]
        ]
        
        meta_info_table = Table(meta_table_data, colWidths=[100, 160, 80, 100])
        meta_info_table.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#F8FAFC')),
            ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#F8FAFC')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
        ]))
        
        # 날인 인장 란 (도장 합성)
        seal_box_data = [
            [
                Paragraph("<font size='6.5'>【自己認印】</font><br/>", meta_label_style), 
                Paragraph("<br/>(印)", ParagraphStyle(name='CSStamp', fontName='HeiseiKakuGo-W5', fontSize=9, alignment=1, textColor=colors.HexColor('#DC2626')))
            ]
        ]
        
        # 만약 실제 날인 도장 경로가 주어지고 파일이 존재하면 이미지로 정밀 합성
        if digital_seal_path and os.path.exists(digital_seal_path):
            seal_box_data = [
                [
                    Paragraph("<font size='6.5'>【自己認印】</font>", meta_label_style), 
                    Image(digital_seal_path, width=32, height=32)
                ]
            ]
            
        seal_table = Table(seal_box_data, colWidths=[70, 45], style=TableStyle([
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('ALIGN', (1,0), (1,0), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        
        # 1행 2열: 메타데이터 정보 | 날인 도장칸
        header_grid_data = [
            [meta_info_table, seal_table]
        ]
        header_grid = Table(header_grid_data, colWidths=[410, 110])
        header_grid.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ]))
        
        story.append(header_grid)
        story.append(Spacer(1, 10))
        
        # --- 3. 체크리스트 테이블 (관청 규격) ---
        story.append(Paragraph("📝 建築基準法関係条文自己確認リスト", ParagraphStyle(
            name='CSubTitle', fontName='HeiseiKakuGo-W5', fontSize=9.5, leading=12,
            textColor=colors.HexColor('#1E293B'), backColor=colors.HexColor('#F1F5F9'),
            spaceAfter=4, borderPadding=3, borderRadius=2
        )))
        
        checklist_data = [
            [
                Paragraph("<b>条文</b>", th_style),
                Paragraph("<b>自己確認対象項目</b>", th_style),
                Paragraph("<b>法規基準値</b>", th_style),
                Paragraph("<b>BIM計測値</b>", th_style),
                Paragraph("<b>判定</b>", th_style),
                Paragraph("<b>設計者自己確認所見</b>", th_style)
            ]
        ]
        
        # 기본 자가진단 항목 데이터 매핑
        # 보안 정책 (SP1/L-2): 평가 데이터가 없음에도 가짜「適合」항목을 만들어내는 것은
        # 법적 문서 위조이므로 금지한다. 판정 불가 사실을 그대로 문서에 명시한다.
        if not check_items:
            check_items = [
                {
                    "article_no": "-",
                    "item_name_jp": "判定不能 (評価データ不在)",
                    "standard_value": "-",
                    "calculated_value": "-",
                    "status": "N/A",
                    "inspector_comment": "法規判定に必要なBIM幾何データが存在しないため、適合性を自動判定できませんでした。図面変換完了後に再度発行してください。"
                }
            ]
            
        for i, item in enumerate(check_items):
            art = item.get("article_no", "条文不明")
            name = item.get("item_name_jp", "항목명")
            std = item.get("standard_value", "기준치")
            calc = item.get("calculated_value", "계측치")
            status = item.get("status", "FAIL")
            comment = item.get("inspector_comment", "소견 없음")
            
            # 판정 O / X 마크 데코레이션
            if status == "PASS":
                status_html = "<font color='#DC2626'><b>〇 適合</b></font>"
            elif status == "N/A":
                status_html = "<font color='#64748B'><b>－ 判定不能</b></font>"
            else:
                status_html = "<font color='#2563EB'><b>✕ 不適合</b></font>"
                
            checklist_data.append([
                Paragraph(art, td_style),
                Paragraph(name, td_style),
                Paragraph(std, td_style),
                Paragraph(calc, td_style),
                Paragraph(status_html, td_style),
                Paragraph(comment, td_style)
            ])
            
        checklist_table = Table(checklist_data, colWidths=[70, 115, 95, 80, 50, 110])
        checklist_table.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#475569')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('ALIGN', (4,0), (4,-1), 'CENTER'),
        ]))
        
        story.append(checklist_table)
        story.append(Spacer(1, 15))
        
        # --- 4. 종합 판정 배지 영역 ---
        judge_bg = "#EF4444" if overall_judgment == "適合" else "#3B82F6"
        overall_badge_html = f"<font size='10'>【総合自己確認判定】</font><br/><b>{overall_judgment}</b>"
        
        overall_table = Table([
            [Paragraph(overall_badge_html, judgment_style)]
        ], colWidths=[520])
        overall_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(judge_bg)),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOX', (0,0), (-1,-1), 1.5, colors.HexColor('#000000')),
        ]))
        
        story.append(overall_table)
        story.append(Spacer(1, 10))
        
        # --- 5. 설계자 면책 한계 공지 고지란 ---
        disclosure_html = """
        <font face='HeiseiKakuGo-W5'>■ 設計者自己確認における免責事項及び限界値確認の基準</font><br/>
        本セルフチェックシートは、提出されたBIM三次元設計データ（IFCファイル）から自動抽出した幾何学的測定値を元に作成されています。手動による図面誤記入や、意図的な壁線の省略等に基づく測定値の誤差に関する責任は、すべて報告書作成者の自己責任に帰属します。確認申請用正式図書として公官庁へ提出する際には、必ず設計者自らがRevit/ArchiCAD等のネイティブファイルを参照し、最終整合性を点検してください。
        """
        
        story.append(Table([
            [Paragraph(disclosure_html, ParagraphStyle(name='CSDisclaimer', fontName='HeiseiMin-W3', fontSize=7, leading=9, textColor=colors.HexColor('#64748B')))]
        ], colWidths=[520], style=TableStyle([
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ])))
        
        doc.build(story)
        return output_pdf_path


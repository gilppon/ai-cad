# -*- coding: utf-8 -*-
import os
import sys
import io

# 윈도우 터미널 UTF-8 출력 강제 (UnicodeEncodeError 방지)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from exporter.pdf_generator import JPPDFGenerator

def test_pdf_generation_directly():
    print("=== Testing PDF Generator (ReportLab CID Font) ===")
    
    project_id = "test_jp_proj_999"
    project_name = "千代田レジデンス 302号室"
    address = "東京都千代田区麹町3-5-1"
    inspector_name = "佐藤 健 (佐藤テック代表)"
    
    compliance_opinions = [
        {
            "room_type_jp": "パイプスペース (PS)",
            "room_abbr_jp": "PS",
            "decision_label": "共用部分 (パイプスペース等)",
            "ownership_decision": "COMMON",
            "legal_basis": "区分所有法第4条・マンション標準管理規約第7条 (別表第2)",
            "japanese_opinion": "배관 샤프트실(PS) 내부 공용 종관 누수로서 구분소유자 개인이 아닌 관리조합의 장기수선충당금으로 공사 처리가 이루어져야 하는 영역입니다."
        },
        {
            "room_type_jp": "浴室 (バスルーム)",
            "room_abbr_jp": "UB",
            "decision_label": "専有部分 (住戸内枝管・防水層)",
            "ownership_decision": "PROPRIETARY",
            "legal_basis": "マンション標準管理規約第7条第1項 (別表第3)",
            "japanese_opinion": "욕실 유닛 배스 하부의 개인 배관(지관) 연결부 노후화로 인한 누수로 세대주 자부담 또는 일상생활배상책임보험 자부담 항목에 해당합니다."
        }
    ]
    
    # 2D/3D 이미지 대체 테스트 (samples 또는 루트 폴더 이미지 사용)
    # samples 디렉토리 혹은 루트 디렉토리에 있는 이미지를 사용
    image_2d = "test_original.png"
    image_3d = "test_deskewed.png"
    
    output_pdf = "test_compliance_report.pdf"
    
    # PDF 생성
    result_path = JPPDFGenerator.generate_report(
        project_id=project_id,
        project_name=project_name,
        address=address,
        inspector_name=inspector_name,
        compliance_opinions=compliance_opinions,
        image_2d_path=image_2d,
        image_3d_path=image_3d,
        output_pdf_path=output_pdf
    )
    
    # 검증
    assert os.path.exists(result_path), "PDF file was not created!"
    file_size = os.path.getsize(result_path)
    
    print(f"[*] PDF Generation Success!")
    print(f"[+] Output Path: {result_path}")
    print(f"[+] File Size: {file_size / 1024:.2f} KB")
    
    assert file_size > 0, "Created PDF file is empty!"
    
    # Clean up
    if os.path.exists(output_pdf):
        # 성공 메시지를 위해 보관하거나, 나중에 지움. 여기서는 보존하여 실사 확인 가능하도록 함.
        pass

if __name__ == "__main__":
    test_pdf_generation_directly()

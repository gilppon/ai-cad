import os
import urllib.request
import urllib.error
import time
from pathlib import Path

# 설정
LAWS_DIR = Path("e:/project/cad_saas_mvp/data/laws")
LAW_TARGETS = {
    "325AC0000000201": "建築基準法 (Building Standards Act)",
    "325CO0000000338": "建築基準法施行令 (Building Standards Act Enforcement Order)"
}
API_BASE_URL = "https://laws.e-gov.go.jp/api/1/lawdata"

def download_law(law_id: str, law_name: str, max_retries: int = 3, retry_delay: int = 2) -> bool:
    """
    e-Gov API V1에서 특정 법령의 XML 데이터를 다운로드하여 저장합니다.
    """
    url = f"{API_BASE_URL}/{law_id}"
    save_path = LAWS_DIR / f"{law_id}.xml"
    
    print(f"[*] Starting download for '{law_name}' (ID: {law_id})...")
    print(f"    URL: {url}")
    
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read()
                
                # 디렉토리 생성
                LAWS_DIR.mkdir(parents=True, exist_ok=True)
                
                # XML 파일 저장
                with open(save_path, "wb") as f:
                    f.write(content)
                
                print(f"[+] Successfully downloaded and saved to: {save_path} (Size: {len(content)} bytes)")
                return True
                
        except urllib.error.HTTPError as e:
            print(f"[-] HTTP Error (Attempt {attempt}/{max_retries}): {e.code} - {e.reason}")
        except urllib.error.URLError as e:
            print(f"[-] URL Error (Attempt {attempt}/{max_retries}): {e.reason}")
        except Exception as e:
            print(f"[-] Unexpected error (Attempt {attempt}/{max_retries}): {e}")
            
        if attempt < max_retries:
            print(f"[!] Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            
    print(f"[x] Failed to download law '{law_name}' (ID: {law_id}) after {max_retries} attempts.")
    return False

def download_all_targets():
    """
    설정된 모든 법령 목록을 순차적으로 다운로드합니다.
    """
    print("=============================================================")
    print("  e-Gov Law API V1 Downloader - Compliance RAG Pipeline  ")
    print("=============================================================")
    
    success_count = 0
    for law_id, law_name in LAW_TARGETS.items():
        success = download_law(law_id, law_name)
        if success:
            success_count += 1
            
    print("\n=============================================================")
    print(f"  Download Finished: {success_count}/{len(LAW_TARGETS)} succeeded.")
    print("=============================================================")
    
    return success_count == len(LAW_TARGETS)

if __name__ == "__main__":
    download_all_targets()

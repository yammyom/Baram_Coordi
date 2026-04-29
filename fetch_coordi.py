import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup

# 기본 URL 및 설정
BASE_URL = "https://baram.nexon.com/Coordi/DressRoom"
API_URL = "https://baram.nexon.com/Coordi/GetCoodiItemList"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 1. 환경변수 로드 (.env 파일 파싱)
def load_env():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

SUPABASE_URL = os.getenv("COORDI_SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("COORDI_SUPABASE_ANON_KEY")

# 2. 인증 정보(쿠키 및 토큰) 추출
def get_auth_info():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    print("[*] 인증 정보(토큰/쿠키) 추출 중...")
    try:
        response = session.get(BASE_URL)
        if response.status_code != 200:
            print("[-] 메인 페이지 접속 실패")
            return None, None

        token_match = re.search(r'name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"', response.text)
        if not token_match:
            token_match = re.search(r'__RequestVerificationToken.*?value="([^"]+)"', response.text)

        if token_match:
            token = token_match.group(1)
            print(f"[+] 토큰 추출 성공: {token[:10]}...")
            return session, token
        else:
            print("[-] 토큰을 찾을 수 없습니다.")
            return None, None
    except Exception as e:
        print(f"[-] 인증 정보 추출 에러: {e}")
        return None, None

# 3. Supabase Upsert 헬퍼
def upsert_to_supabase(items):
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("[-] Supabase 환경 변수가 설정되지 않아 DB 저장을 생략합니다.")
        return

    endpoint = f"{SUPABASE_URL}/rest/v1/items"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    params = {"on_conflict": "name,part_id,gender"}
    
    try:
        # 100개씩 청크 단위로 업서트
        for i in range(0, len(items), 100):
            chunk = items[i:i+100]
            resp = requests.post(endpoint, headers=headers, params=params, json=chunk)
            if resp.status_code not in [200, 201, 204]:
                print(f"[-] DB Upsert 실패 ({resp.status_code}): {resp.text}")
            else:
                print(f"[+] DB Upsert 성공: {len(chunk)}개 아이템 저장됨")
    except Exception as e:
        print(f"[-] DB Upsert 중 오류 발생: {e}")

# 4. 코디 아이템 (Item/Hair/Face) 수집
def crawl_coordi_items():
    session, token = get_auth_info()
    if not session or not token:
        print("[-] API 수집을 중단합니다 (인증 실패).")
        return []

    api_headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/json",
        "__requestverificationtoken": token,
        "x-requested-with": "XMLHttpRequest",
        "referer": BASE_URL
    }

    # 수집할 카테고리 매핑
    CATEGORIES = [
        {"category": "I", "equipSlot": "1", "part_id": 1},   # 목/어깨장식
        {"category": "I", "equipSlot": "2", "part_id": 2},   # 투구
        {"category": "I", "equipSlot": "3", "part_id": 3},   # 얼굴장식
        {"category": "I", "equipSlot": "4", "part_id": 4},   # 무기
        {"category": "I", "equipSlot": "5", "part_id": 5},   # 갑옷
        {"category": "I", "equipSlot": "6", "part_id": 6},   # 방패/보조무기
        {"category": "I", "equipSlot": "8", "part_id": 7},   # 망토
        {"category": "I", "equipSlot": "11", "part_id": 8},  # 신발
        {"category": "I", "equipSlot": "13", "part_id": 9},  # 세트옷
        {"category": "I", "equipSlot": "14", "part_id": 10}, # 장신구
        {"category": "H", "equipSlot": "0", "part_id": 12},  # 헤어
        {"category": "F", "equipSlot": "0", "part_id": 13},  # 얼굴
    ]

    all_items = []

    for cat in CATEGORIES:
        page = 1
        print(f"\n[*] 카테고리 [{cat['category']}] / 슬롯 [{cat['equipSlot']}] 수집 시작...")
        
        while True:
            payload = {
                "category": cat["category"],
                "equipSlot": cat["equipSlot"],
                "searchStr": "",
                "sortType": "N",
                "pageNo": page,
                "requestUrl": "/Coordi/DressRoom"
            }

            try:
                resp = session.post(API_URL, headers=api_headers, data=json.dumps(payload))
                if resp.status_code != 200:
                    print(f"[-] 서버 응답 오류: {resp.status_code}")
                    break

                data = resp.json()
                coordi_items = data.get("CoordiItems", [])
                if not coordi_items:
                    break

                for item in coordi_items:
                    name = item.get("ItemName", "").strip()
                    if not name:
                        continue
                    
                    # UseSex -> 0:남, 1:여, 2:공용
                    gender = item.get("UseSex", 2)
                    
                    all_items.append({
                        "name": name,
                        "part_id": cat["part_id"],
                        "gender": gender
                    })
                
                print(f"  - {page}페이지 완료 ({len(coordi_items)}개)")
                page += 1
                time.sleep(1)
            except Exception as e:
                print(f"[-] 카테고리 수집 중 오류: {e}")
                break
                
    return all_items

# 5. 태닝 데이터 수집
def crawl_tanning_items():
    print("\n[*] 태닝 데이터 수집 시작...")
    tanning_items = []
    try:
        resp = requests.get(BASE_URL, headers={"User-Agent": USER_AGENT})
        if resp.status_code != 200:
            print(f"[-] 태닝 페이지 로드 실패: {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        elements = soup.find_all("span", class_="color_txt")
        
        for el in elements:
            name = el.get_text(strip=True)
            if name:
                tanning_items.append({
                    "name": name,
                    "part_id": 11, # 11: 태닝
                    "gender": 2    # 태닝은 공용
                })
        print(f"[+] 태닝 데이터 {len(tanning_items)}개 수집 완료")
    except Exception as e:
        print(f"[-] 태닝 수집 중 오류: {e}")
        
    return tanning_items

def main():
    print("====== 바람의나라 코디 아이템 동기화 파이프라인 ======")
    
    # 코디/헤어/얼굴 데이터 수집
    coordi_list = crawl_coordi_items()
    print(f"\n[+] 코디/헤어/얼굴 수집 완료: 총 {len(coordi_list)}개")
    
    # 태닝 데이터 수집
    tanning_list = crawl_tanning_items()
    
    total_list = coordi_list + tanning_list
    print(f"\n[+] 최종 수집 완료: 총 {len(total_list)}개")
    
    # Supabase 저장
    if total_list:
        upsert_to_supabase(total_list)
    print("\n====== 동기화 완료 ======")

if __name__ == "__main__":
    main()

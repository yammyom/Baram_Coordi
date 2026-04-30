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

# 1. 환경변수 로드
def load_env():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

SUPABASE_URL = os.getenv("COORDI_SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("COORDI_SUPABASE_ANON_KEY")

# 2. 인증 정보 추출
def get_auth_info():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    print("[*] 인증 정보(토큰/쿠키) 추출 중...")
    try:
        response = session.get(BASE_URL)
        token_match = re.search(r'name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"', response.text)
        if not token_match:
            token_match = re.search(r'__RequestVerificationToken.*?value="([^"]+)"', response.text)

        if token_match:
            return session, token_match.group(1)
    except Exception as e:
        print(f"[-] 인증 정보 추출 에러: {e}")
    return None, None

# 3. Supabase Upsert 헬퍼 (저장 후 결과 반환)
def upsert_to_table(table_name, data, on_conflict="id"):
    if not SUPABASE_URL or not SUPABASE_ANON_KEY: return []
    
    endpoint = f"{SUPABASE_URL}/rest/v1/{table_name}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation,resolution=merge-duplicates"
    }
    params = {"on_conflict": on_conflict}
    
    results = []
    try:
        for i in range(0, len(data), 100):
            chunk = data[i:i+100]
            resp = requests.post(endpoint, headers=headers, params=params, json=chunk)
            if resp.status_code in [200, 201]:
                results.extend(resp.json())
            else:
                print(f"[-] {table_name} Upsert 실패 ({resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"[-] {table_name} DB 에러: {e}")
    return results

# 4. 일반 코디 아이템 수집 함수 (이 부분이 누락되어 에러가 났었습니다)
def crawl_coordi_items(session, token):
    api_headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/json",
        "__requestverificationtoken": token,
        "x-requested-with": "XMLHttpRequest",
        "referer": BASE_URL
    }

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
        print(f"[*] 카테고리 [{cat['part_id']}] 수집 시작...")
        while True:
            payload = {
                "category": cat["category"], "equipSlot": cat["equipSlot"], "pageSize": 100,
                "searchStr": "", "sortType": "N", "pageNo": page, "requestUrl": "/Coordi/DressRoom"
            }
            try:
                resp = session.post(API_URL, headers=api_headers, json=payload)
                data = resp.json()
                coordi_items = data.get("CoordiItems", [])
                if not coordi_items: break

                for item in coordi_items:
                    name = item.get("ItemName", "").strip()
                    if name and not name.startswith("[대여]"):
                        all_items.append({"name": name, "part_id": cat["part_id"], "gender": item.get("UseSex", 2)})
                page += 1
                time.sleep(0.5)
            except: break
    return all_items

# 5. 태닝 데이터 상세 수집 함수
def crawl_tanning_items():
    print("\n[*] 태닝 데이터 상세 수집 시작...")
    tanning_rich_list = []
    try:
        resp = requests.get(BASE_URL, headers={"User-Agent": USER_AGENT})
        soup = BeautifulSoup(resp.text, 'html.parser')
        containers = soup.select(".color_sel")
        
        for box in containers:
            name_el = box.select_one(".color_txt")
            if not name_el: continue
            name = name_el.get_text(strip=True)
            
            ul_tag = box.select_one("ul[onclick*='SetTanning']")
            tanning_index = 0
            if ul_tag:
                idx_match = re.search(r'SetTanning\((\d+)\)', ul_tag.get("onclick", ""))
                if idx_match: tanning_index = int(idx_match.group(1))
            
            colors = []
            for li in box.select("ul li"):
                color_match = re.search(r'#([A-Fa-f0-9]{6})', li.get("style", ""))
                if color_match: colors.append(f"#{color_match.group(1)}")
            
            if name and len(colors) == 8:
                tanning_rich_list.append({
                    "item_info": {"name": name, "part_id": 11, "gender": 2},
                    "detail": {"tanning_index": tanning_index, "colors": colors}
                })
    except Exception as e:
        print(f"[-] 태닝 수집 중 오류: {e}")
    return tanning_rich_list

def main():
    print("====== 바람의나라 코디 아이템 동기화 파이프라인 ======")
    session, token = get_auth_info()
    if not session or not token: return

    # 1. 일반 아이템 수집 및 저장
    coordi_list = crawl_coordi_items(session, token)
    if coordi_list:
        upsert_to_table("items", coordi_list, "name,part_id,gender")
        print(f"[+] 일반 아이템 {len(coordi_list)}개 동기화 완료")

    # 2. 태닝 상세 수집 및 저장
    tanning_rich_list = crawl_tanning_items()
    if tanning_rich_list:
        tanning_items = [x['item_info'] for x in tanning_rich_list]
        saved_items = upsert_to_table("items", tanning_items, "name,part_id,gender")
        
        id_map = {item['name']: item['item_id'] for item in saved_items}
        tanning_details = []
        for raw in tanning_rich_list:
            name = raw['item_info']['name']
            if name in id_map:
                detail = raw['detail']
                detail['item_id'] = id_map[name]
                tanning_details.append(detail)
        
        if tanning_details:
            upsert_to_table("tanning_info", tanning_details, "item_id")
            print(f"[+] 태닝 상세 정보 {len(tanning_details)}개 동기화 완료")

    print("\n====== 모든 동기화 작업 완료 ======")

if __name__ == "__main__":
    main()
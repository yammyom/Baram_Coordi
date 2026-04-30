import requests
import json
import time
import re

# 기본 설정
BASE_URL = "https://baram.nexon.com/Coordi/DressRoom"
API_URL = "https://baram.nexon.com/Coordi/GetCoodiItemList"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def get_auth_info():
    """메인 페이지에서 세션 쿠키와 보안 토큰을 동적으로 추출"""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    
    print("인증 정보(토큰/쿠키) 추출 중...")
    try:
        response = session.get(BASE_URL)
        if response.status_code != 200:
            print("메인 페이지 접속 실패")
            return None, None

        # HTML 내 <input name="__RequestVerificationToken" value="..."> 추출
        token_match = re.search(r'name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"', response.text)
        
        if not token_match:
            # 패턴이 다를 경우를 대비한 2차 검색 (ASP.NET 표준)
            token_match = re.search(r'__RequestVerificationToken.*?value="([^"]+)"', response.text)

        if token_match:
            token = token_match.group(1)
            print(f"토큰 추출 성공: {token[:10]}...")
            return session, token
        else:
            print("토큰을 찾을 수 없습니다.")
            return None, None
            
    except Exception as e:
        print(f"인증 정보 추출 에러: {e}")
        return None, None

def save_to_txt(items, filename="baram_items.txt"):
    """리스트에 담긴 아이템들을 TXT 파일에 추가 저장"""
    with open(filename, "a", encoding="utf-8") as f:
        for item in items:
            name = item.get("ItemName", "이름없음")
            slot = item.get("SlotName", "부위불명")
            sex_code = item.get("UseSex")
            sex = "공용" if sex_code == 2 else ("남" if sex_code == 0 else "여")
            f.write(f"아이템: {name} | 부위: {slot} | 성별: {sex}\n")
    print(f" >>> [파일 저장 완료] {len(items)}개 추가 기록됨")

def crawl_and_save_batches():
    # 1. 인증 정보 가져오기
    session, token = get_auth_info()
    if not session or not token:
        print("인증 정보를 가져오지 못해 종료합니다.")
        return

    # 2. API 요청을 위한 헤더 설정 (추출한 토큰 적용)
    api_headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/json",
        "__requestverificationtoken": token,
        "x-requested-with": "XMLHttpRequest",
        "referer": BASE_URL
    }

    page = 1
    buffer = []
    total_count = 0
    filename = "baram_items.txt"

    print("수집을 시작합니다. 40개마다 파일에 기록합니다.")

    while True:
        payload = {
            "category": "I", # 필요에 따라 H, F 등으로 변경 가능
            "equipSlot": "13",
            "searchStr": "",
            "sortType": "N",
            "pageNo": page,
            "requestUrl": "/Coordi/DressRoom"
        }

        try:
            # session.post를 사용해야 앞에서 받아온 쿠키가 자동으로 포함됨
            response = session.post(API_URL, headers=api_headers, data=json.dumps(payload))
            
            if response.status_code != 200:
                print(f"서버 응답 오류: {response.status_code}")
                # 만약 401/403 에러라면 토큰이 만료된 것이므로 루프 종료
                break

            data = response.json()
            items = data.get("CoordiItems", [])

            if not items:
                print("수집할 데이터가 더 이상 없습니다.")
                break

            buffer.extend(items)
            total_count += len(items)
            print(f"[{page}페이지 수집] 현재 누적: {total_count}개")

            if len(buffer) >= 40:
                save_to_txt(buffer, filename)
                buffer = []

            page += 1
            time.sleep(1.5) # GitHub Actions 환경에선 약간의 여유를 주는 게 안전합니다.

        except Exception as e:
            print(f"수집 중단됨: {e}")
            break

    if buffer:
        save_to_txt(buffer, filename)

    print(f"\n모든 작업 완료. 총 {total_count}개 저장됨.")

if __name__ == "__main__":
    crawl_and_save_batches()
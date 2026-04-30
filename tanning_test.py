import requests
from bs4 import BeautifulSoup
import time

# 1. 설정
URL = "https://baram.nexon.com/Coordi/DressRoom"
HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "referer": "https://baram.nexon.com/Coordi/DressRoom"
}

def save_to_txt(items, filename="baram_tanning.txt"):
    """리스트에 담긴 태닝명을 TXT 파일에 추가 저장"""
    with open(filename, "a", encoding="utf-8") as f:
        for item in items:
            f.write(f"태닝명: {item}\n")
    print(f" >>> [파일 저장 완료] {len(items)}개 기록됨")

def crawl_tanning():
    print("태닝 데이터 수집을 시작합니다...")
    
    try:
        # 페이지 소스 가져오기
        response = requests.get(URL, headers=HEADERS)
        if response.status_code != 200:
            print(f"페이지 로드 실패: {response.status_code}")
            return

        # BeautifulSoup으로 HTML 파싱
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 'color_txt' 클래스를 가진 모든 span 태그 찾기
        # XPath의 span[2]와 class="color_txt"를 기준으로 수집합니다.
        tanning_elements = soup.find_all("span", class_="color_txt")
        
        all_tanning_names = [el.get_text(strip=True) for el in tanning_elements]
        
        total_count = len(all_tanning_names)
        print(f"총 {total_count}개의 태닝 아이템을 찾았습니다.")

        # 40개씩 끊어서 저장하기
        batch_size = 40
        for i in range(0, total_count, batch_size):
            batch = all_tanning_names[i : i + batch_size]
            save_to_txt(batch)
            # 수집된 시각적인 효과를 위해 짧은 대기 (정적 페이지라 필수는 아님)
            time.sleep(0.5)

        print(f"\n모든 태닝 데이터 저장 완료! (총 {total_count}개)")

    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    # BeautifulSoup 설치가 필요할 수 있습니다: pip install beautifulsoup4
    crawl_tanning()
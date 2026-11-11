import feedparser
from datetime import datetime

def get_realtime_feed():
    """대만해협 위기 관련 실시간 뉴스를 수집하고, [분야 / 국가 / 기관명] 형태로 태그를 재가공"""
    rss_urls = [
        "https://news.google.com/rss/search?q=%E5%8F%B0%E6%B5%BE+%军事+OR+解放軍+when:1d&hl=zh-TW&gl=TW",  # 군사
        "https://news.google.com/rss/search?q=%E5%8F%B0%E6%B5%BE+%3D+OR+%E8%82%A1%E5%B8%82+OR+%E7%B6%93%E6%BF%9F+when:1d&hl=zh-TW&gl=TW", # 금융
        "https://news.google.com/rss/search?q=%E5%8F%B0%E6%B5%BE+%E8%88%AA%E7%A9%BA+OR+%E6%A9%9F%E5%A0%B4+when:1d&hl=zh-TW&gl=TW", # 항공
        "https://news.google.com/rss/search?q=%E5%8F%B0%E6%B5%BE+%E8%88%B9%E8%88%B6+OR+%E6%B5%B7%E4%BA%8B+when:1d&hl=zh-TW&gl=TW" # 해운
    ]
    
    raw_articles = []
    
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]: # 각 주제별 상위 3개씩 수집
                title = entry.title
                link = entry.link
                
                # 발행 일시 파싱 (날짜 + 시간 확보)
                pub_time = "최근"
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    dt = datetime(*entry.published_parsed[:6])
                    pub_time = dt.strftime("%Y-%m-%d %H:%M") # "날짜 시간" 형태로 표기
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    dt = datetime(*entry.updated_parsed[:6])
                    pub_time = dt.strftime("%Y-%m-%d %H:%M")

                # 1. 6가지 분야 분류 로직
                category = "사회"
                if any(k in title for k in ["軍", "飛彈", "戰機", "解放軍", "軍演", "國防", "演習", "軍艦"]):
                    category = "군사"
                elif any(k in title for k in ["股市", "經濟", "金融", "匯率", "台幣", "美元", "資本"]):
                    category = "금융"
                elif any(k in title for k in ["航班", "機場", "航空", "班機", "民航"]):
                    category = "항공"
                elif any(k in title for k in ["船舶", "海巡", "海運", "貨輪", "航道"]):
                    category = "해운"
                elif any(k in title for k in ["總統", "外交", "立法院", "政府", "政策", "政治"]):
                    category = "정치"

                # 2. 국가 및 기관명 자동 추출
                country = "대만"
                institution = "관련기관"
                
                if "美國" in title or "美軍" in title or "五角大廈" in title:
                    country = "미국"
                    institution = "미 국방부/인태사"
                elif "大陸" in title or "北京" in title or "國台辦" in title or "解放軍" in title:
                    country = "중국"
                    institution = "중국 국방부/외교부"
                elif "國防部" in title:
                    country = "대만"
                    institution = "대만 국방부(MND)"
                elif "外交部" in title:
                    country = "대만"
                    institution = "대만 외교부"
                elif "中央社" in title or "自由時報" in title:
                    country = "대만"
                    institution = "현지 언론"
                else:
                    country = "대만"
                    institution = "유관기관"

                # 3. 요청하신 [분야 / 국가 / 기관명] 포맷으로 제목 재조립
                formatted_title = f"[{category} / {country} / {institution}] {title}"
                
                raw_articles.append({
                    "time": pub_time,
                    "text": formatted_title,
                    "url": link,
                    "type": "sky"
                })
        except Exception as e:
            print("피드 수집 중 오류 발생:", e)
            
    # 최신순 정렬 후 상위 8개 반환
    return raw_articles[:8]
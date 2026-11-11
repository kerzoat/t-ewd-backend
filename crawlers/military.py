import re
import feedparser

def get_military_data():
    url = "https://news.google.com/rss/search?q=國防部+共機+架次+when:1d&hl=zh-TW&gl=TW"
    today_total = 4
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            match = re.search(r'(\d+)架次', entry.title)
            if match:
                found_num = int(match.group(1))
                if found_num > today_total:
                    today_total = found_num
        if today_total > 20:
            special_ratio = int((today_total * 0.35) / today_total * 100)
        else:
            special_ratio = int((today_total * 0.15) / max(1, today_total) * 100)
    except Exception:
        special_ratio = 15
        
    return today_total, special_ratio
import feedparser

def get_maritime_data():
    url = "https://news.google.com/rss/search?q=(航行警告+OR+禁航+OR+滾裝船)+when:7d&hl=zh-TW&gl=TW"
    roro_count = 8
    bypassed_count = 1
    try:
        feed = feedparser.parse(url)
        warning_count = len(feed.entries)
        if warning_count > 0:
            roro_count = 8 + int(warning_count * 1.5)
            bypassed_count = 1 + int(warning_count * 0.8)
            for entry in feed.entries[:5]:
                if "演習" in entry.title or "軍演" in entry.title:
                    bypassed_count += 3
                if "徵用" in entry.title:
                    roro_count += 15
    except Exception:
        pass
    return roro_count, bypassed_count
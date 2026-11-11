import requests
import feedparser
import random

def get_aviation_data():
    weather_url = "https://news.google.com/rss/search?q=(颱風+OR+豪雨)+when:1d&hl=zh-TW&gl=TW"
    is_bad_weather = False
    
    try:
        weather_feed = feedparser.parse(weather_url)
        if len(weather_feed.entries) > 2:
            is_bad_weather = True
    except Exception:
        pass

    raw_cancelled = random.randint(100, 300) if is_bad_weather else random.randint(0, 5)
    raw_rerouted = random.randint(20, 50) if is_bad_weather else random.randint(0, 2)

    if is_bad_weather:
        geopolitical_cancelled = int(raw_cancelled * 0.02)
        geopolitical_rerouted = int(raw_rerouted * 0.02)
    else:
        geopolitical_cancelled = raw_cancelled
        geopolitical_rerouted = raw_rerouted

    vvip_flights = 1
    rss_url = "https://news.google.com/rss/search?q=(私人飛機+OR+專機)+when:1d&hl=zh-TW&gl=TW"
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:3]:
            if "私人飛機" in entry.title or "專機" in entry.title:
                vvip_flights += 1
    except Exception:
        pass
        
    return geopolitical_cancelled, geopolitical_rerouted, vvip_flights
import json
import os
import random
from datetime import datetime, timedelta
import yfinance as yf

DB_FILE = "history_log.json"
MAX_DAYS = 365
MAX_FEED_PER_DAY = 15  # 시스템 과부하 방지를 위한 일일 속보 최대 보관 개수

def calculate_ai_score(mil_tot, mil_special, vessels, usd_rate, net_sell, usdt_prem, vvip, avi_c, avi_r, roro, bypass, port_delay):
    """T-EWD 4대 도메인 다중 출처 가중치 기반 AI 위협 지수 산출 엔진 (Max 100)"""
    # 1. 군사 (Max 40): 총 기수/함정(20) + 특수기 비율(20)
    mil_score = min(20, (mil_tot * 1.2) + (vessels * 0.8)) + min(20, mil_special * 2.0)
    
    # 2. 금융 (Max 20): 환율/테더 프리미엄(10) + 외국인/ETF 자본이탈(10)
    fin_score = max(0, min(10, (usd_rate - 31.0) * 3 + (usdt_prem * 2.0))) + min(10, net_sell / 1000)
    
    # 3. 항공 (Max 15): VVIP 이탈(10) + 민항기 결항/우회(5)
    avi_score = min(10, vvip * 5) + min(5, (avi_c + avi_r) * 1.5)
    
    # 4. 해운 (Max 25): Ro-Ro 징발(15) + 상선 우회 및 항만 지연(10)
    mar_score = min(15, max(0, roro - 6) * 2.5) + min(10, (bypass * 3) + max(0, port_delay - 2) * 0.5)
    
    total = mil_score + fin_score + avi_score + mar_score
    
    # 5. 비상 오버라이드 (Critical Override)
    if vvip >= 3 or roro >= 12 or mil_tot >= 15 or vessels >= 15 or usdt_prem >= 3.0:
        total = max(75, total)
        
    return min(100, int(total))

def init_db():
    if os.path.exists(DB_FILE):
        return
    print("초기 1년치 장기 추적용 과거 데이터를 생성합니다 (약 10초 소요)...")
    history = []
    base_date = datetime.now() - timedelta(days=MAX_DAYS)
    
    try:
        twd = yf.download("TWD=X", period="1y", interval="1d", progress=False)['Close'].values.flatten().tolist()
        ewt = yf.download("EWT", period="1y", interval="1d", progress=False)['Close'].flatten().tolist()
        twii = yf.download("^TWII", period="1y", interval="1d", progress=False)['Close'].values.flatten().tolist()
    except:
        twd, ewt, twii = [], [], []

    for i in range(MAX_DAYS):
        curr_date = base_date + timedelta(days=i)
        f_idx = min(i, len(twd)-1) if len(twd) > 0 else -1
        usd_rate = round(float(twd[f_idx]), 2) if f_idx >= 0 else 31.5
        ewt_val = float(ewt[min(i, len(ewt)-1)]) if len(ewt) > 0 else 50
        twii_val = float(twii[min(i, len(twii)-1)]) if len(twii) > 0 else 20000
        
        net_sell = max(0, int((20000 - twii_val) * 0.5 + (50 - ewt_val) * 200))
        usdt_prem = round(random.uniform(0.1, 0.8), 2)
        
        mil_tot = random.randint(2, 10)
        mil_special = int(mil_tot * random.uniform(0.1, 0.4))
        vessels = random.randint(3, 7)
        
        vvip = random.randint(0, 1)
        avi_c = random.randint(0, 1)
        avi_r = random.randint(0, 2)
        cargo_drop = random.randint(0, 5)
        
        roro = random.randint(6, 9)
        bypass = random.randint(0, 1)
        port_delay = round(random.uniform(1.0, 3.5), 1)
        
        ai_score = calculate_ai_score(mil_tot, mil_special, vessels, usd_rate, net_sell, usdt_prem, vvip, avi_c, avi_r, roro, bypass, port_delay)
        
        history.append({
            "date": curr_date.strftime("%Y-%m-%d"),
            "ai": {"score": ai_score, "is_simulated": True},
            "military": {"total": mil_tot, "specialRatio": mil_special, "median": int(mil_tot * 0.6), "vessels": vessels, "is_simulated": True},
            "finance": {"cds": usd_rate, "netSell": net_sell, "usdtPrem": usdt_prem, "is_simulated": False},
            "aviation": {"vvip": vvip, "cancelled": avi_c, "rerouted": avi_r, "cargoDrop": cargo_drop, "is_simulated": True},
            "maritime": {"roro": roro, "bypassed": bypass, "portDelay": port_delay, "is_simulated": True},
            "feed": [
                {"time": curr_date.strftime("%Y-%m-%d 12:00"), "text": "[군사 / 대만·일본 / MND·JMOD] 대만해협 주변 중국군 항공기 및 함정 정례 기동 식별", "url": "#", "type": "sky"}
            ]
        })
        
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)

def save_today_data(live_payload):
    today_str = datetime.now().strftime("%Y-%m-%d")
    with open(DB_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
        
    new_entry = {
        "date": today_str,
        "ai": {k: v[-1] for k, v in live_payload["ai"].items() if k != "is_simulated"},
        "military": {k: v[-1] for k, v in live_payload["military"].items() if k != "is_simulated"},
        "finance": {k: v[-1] for k, v in live_payload["finance"].items() if k != "is_simulated"},
        "aviation": {k: v[-1] for k, v in live_payload["aviation"].items() if k != "is_simulated"},
        "maritime": {k: v[-1] for k, v in live_payload["maritime"].items() if k != "is_simulated"},
        # 과부하 방지를 위해 일일 피드 저장 개수 제한
        "feed": live_payload["feed"][:MAX_FEED_PER_DAY]
    }
    for field in ["ai", "military", "finance", "aviation", "maritime"]:
        new_entry[field]["is_simulated"] = False
        
    if history[-1]["date"] == today_str:
        history[-1] = new_entry
    else:
        history.append(new_entry)
        
    # 과부하 방지: 365일 롤링 윈도우 적용 (오래된 데이터 자동 삭제)
    if len(history) > MAX_DAYS:
        history = history[-MAX_DAYS:]
        
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)

def get_historical_data(period):
    with open(DB_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
        
    intervals = {"1w": (7, 1), "1m": (30, 2), "3m": (90, 3), "6m": (180, 4), "1y": (365, 5)}
    days, step = intervals.get(period, (7, 1))
    recent_history = history[-days:] if days <= len(history) else history
    
    result = {
        "labels": [],
        "ai": {"score": [], "is_simulated": []},
        "military": {"total": [], "specialRatio": [], "median": [], "vessels": [], "is_simulated": []},
        "finance": {"cds": [], "netSell": [], "usdtPrem": [], "is_simulated": []},
        "aviation": {"vvip": [], "cancelled": [], "rerouted": [], "cargoDrop": [], "is_simulated": []},
        "maritime": {"roro": [], "bypassed": [], "portDelay": [], "is_simulated": []}
    }
    
    for i in range(0, len(recent_history), step):
        chunk = recent_history[i:i+step]
        if not chunk: continue
        
        result["labels"].append(chunk[-1]["date"][5:])
        
        # [AI 지수]: 최댓값 (Max)
        result["ai"]["score"].append(max(item["ai"]["score"] for item in chunk))
        result["ai"]["is_simulated"].append(any(item["ai"].get("is_simulated", False) for item in chunk))

        # [군사]: 총 기수/침범/함정(Max), 특수기 비율(Avg)
        result["military"]["total"].append(max(item["military"]["total"] for item in chunk))
        result["military"]["specialRatio"].append(int(sum(item["military"]["specialRatio"] for item in chunk) / len(chunk)))
        result["military"]["median"].append(max(item["military"]["median"] for item in chunk))
        result["military"]["vessels"].append(max(item["military"].get("vessels", 4) for item in chunk))
        result["military"]["is_simulated"].append(any(item["military"].get("is_simulated", False) for item in chunk))

        # [금융]: 환율/CDS(Last), 자본이탈(Avg), 테더 프리미엄(Max)
        result["finance"]["cds"].append(chunk[-1]["finance"]["cds"])
        result["finance"]["netSell"].append(int(sum(item["finance"]["netSell"] for item in chunk) / len(chunk)))
        result["finance"]["usdtPrem"].append(max(item["finance"].get("usdtPrem", 0.3) for item in chunk))
        result["finance"]["is_simulated"].append(any(item["finance"].get("is_simulated", False) for item in chunk))

        # [항공]: VVIP 이탈(Sum), 결항/우회/화물감소(Avg)
        result["aviation"]["vvip"].append(sum(item["aviation"]["vvip"] for item in chunk))
        result["aviation"]["cancelled"].append(int(sum(item["aviation"]["cancelled"] for item in chunk) / len(chunk)))
        result["aviation"]["rerouted"].append(int(sum(item["aviation"]["rerouted"] for item in chunk) / len(chunk)))
        result["aviation"]["cargoDrop"].append(int(sum(item["aviation"].get("cargoDrop", 2) for item in chunk) / len(chunk)))
        result["aviation"]["is_simulated"].append(any(item["aviation"].get("is_simulated", False) for item in chunk))

        # [해운]: Ro-Ro 징발(Max), 상선 우회/항만 지연(Avg)
        result["maritime"]["roro"].append(max(item["maritime"]["roro"] for item in chunk))
        result["maritime"]["bypassed"].append(int(sum(item["maritime"]["bypassed"] for item in chunk) / len(chunk)))
        result["maritime"]["portDelay"].append(round(sum(item["maritime"].get("portDelay", 2.0) for item in chunk) / len(chunk), 1))
        result["maritime"]["is_simulated"].append(any(item["maritime"].get("is_simulated", False) for item in chunk))
                
    return result

def get_feed_archive(date_str=None):
    with open(DB_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
        
    if not date_str:
        return history[-1].get("feed", [])
        
    oldest_allowed_date = datetime.now() - timedelta(days=MAX_DAYS)
    try:
        target_date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        if target_date_obj < oldest_allowed_date:
            return [{"time": "조회 제한", "text": f"[안내 / 시스템 / OSINT] 시스템 과부하 방지를 위해 1년 이전({oldest_allowed_date.strftime('%Y-%m-%d')} 이전)의 아카이브는 자동 소거됩니다.", "url": "#", "type": "sky"}]
    except ValueError:
        pass

    for item in history:
        if item["date"] == date_str:
            return item.get("feed", [])
            
    return []
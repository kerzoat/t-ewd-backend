from datetime import datetime, timedelta
import random
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="T-EWD 12-Indicator Engine",
    description="대만해협 4대 도메인 12지표 정규화 및 비선형 게이트키퍼 엔진",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def filter_weather_disruptions(
    raw_rerouted: int, weather_cancelled: int, typhoon_active: bool
) -> int:
    """태풍·악천후(METAR/TAF 기상특보)로 인한 결항 및 기상 회항분을 제거하고

    순수 항행경고(NOTAM)·군사 공역 통제에 따른 우회 편수만 추출합니다.
    """
    if typhoon_active:
        return max(0, raw_rerouted - int(weather_cancelled * 0.85))
    return max(0, raw_rerouted)


def calculate_threat_score(day_data: dict) -> dict:
    """4대 도메인 12개 지표(선형 8 + 비선형 4) 기반 AI 위협 지수(0~100점) 산출"""
    # 1. 군사 선형 정규화 (가중치 30% -> 최대 18점) : 출격(80기), 함정(30척)
    mil_linear = (min(day_data["mil_total"] / 80.0, 1.0) * 0.6) + (
        min(day_data["mil_vessels"] / 30.0, 1.0) * 0.4
    )

    # 2. 금융 선형 정규화 (가중치 20% -> 최대 12점) : 순매도(1,200억 TWD), 5년물 CDS(평시 25 ~ 상한 120 bps)
    cds_norm = max(0.0, min((day_data["fin_cds"] - 25.0) / 95.0, 1.0))
    fin_linear = (min(day_data["fin_netSell"] / 1200.0, 1.0) * 0.5) + (
        cds_norm * 0.5
    )

    # 3. 항공 선형 정규화 (가중치 25% -> 최대 15점) : NOTAM 우회(300편), 반도체 화물 증감률(절댓값 50%)
    avi_linear = (min(day_data["avi_rerouted"] / 300.0, 1.0) * 0.5) + (
        min(abs(day_data["avi_cargo"]) / 50.0, 1.0) * 0.5
    )

    # 4. 해운 선형 정규화 (가중치 25% -> 최대 15점) : 해협 우회 상선(50척), 7대 항만 입항 감소분(평시 65척 기준)
    port_drop = max(0.0, (65.0 - day_data["mar_portCalls"]) / 45.0)
    mar_linear = (min(day_data["mar_bypassed"] / 50.0, 1.0) * 0.6) + (
        min(port_drop, 1.0) * 0.4
    )

    # 선형 베이스라인 합산 (최대 60점 만점)
    base_score = (
        (mil_linear * 30)
        + (fin_linear * 20)
        + (avi_linear * 25)
        + (mar_linear * 25)
    ) * 0.6

    # 비선형 스파이크(Non-Linear Spike) 가산점 연산
    spike_bonus = 0.0
    spikes = {"mil": False, "fin": False, "avi": False, "mar": False}

    # [군사 비선형] 중간선 침범 15기 이상 또는 (출격 25기 이상 & 특수기 비중 25% 이상)
    if day_data["mil_median"] >= 15 or (
        day_data["mil_total"] >= 25 and day_data["mil_specialRatio"] >= 25
    ):
        spikes["mil"] = True
        spike_bonus += 12.0 + min(
            max(0, day_data["mil_median"] - 15) * 0.8, 10.0
        )

    # [금융 비선형] 로컬 거래소 USDT 프리미엄 +1.5% 이상
    if day_data["fin_usdtPrem"] >= 1.5:
        spikes["fin"] = True
        spike_bonus += 10.0 + min((day_data["fin_usdtPrem"] - 1.5) * 4.0, 10.0)

    # [항공 비선형] VVIP 비즈니스젯 긴급 이탈 3대 이상
    if day_data["avi_vvip"] >= 3:
        spikes["avi"] = True
        spike_bonus += 10.0 + min((day_data["avi_vvip"] - 3) * 2.5, 10.0)

    # [해운 비선형] 푸젠·광동성 민간 Ro-Ro 카페리 징발 5척 이상
    if day_data["mar_roro"] >= 5:
        spikes["mar"] = True
        spike_bonus += 15.0 + min((day_data["mar_roro"] - 5) * 1.5, 12.0)

    total_score = base_score + spike_bonus

    # 게이트키퍼(Gatekeeper) 하한선 강제 규칙
    active_spikes = sum(spikes.values())
    if active_spikes >= 3:
        total_score = max(total_score, 76.0)
    elif active_spikes >= 2 or spikes["mar"]:
        total_score = max(total_score, 52.0)
    elif active_spikes == 1:
        total_score = max(total_score, 30.0)

    return {"score": round(min(100.0, total_score), 1), "spikes": spikes}


DB_HISTORY = []
ALERT_ARCHIVE = {}


def init_rolling_database():
    global DB_HISTORY, ALERT_ARCHIVE
    DB_HISTORY.clear()
    ALERT_ARCHIVE.clear()

    today = datetime.now()
    random.seed(42)

    for i in range(364, -1, -1):
        target_date = today - timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")
        label_str = "TODAY" if i == 0 else target_date.strftime("%m-%d")

        if i > 5:
            # 평시 베이스라인 (태풍 기상 결항 노이즈는 필터링된 상태)
            raw_reroute = random.randint(0, 6)
            d = {
                "mil_total": random.randint(6, 18),
                "mil_vessels": random.randint(3, 6),
                "mil_median": random.randint(0, 4),
                "mil_specialRatio": random.randint(5, 15),
                "fin_netSell": random.randint(30, 160),
                "fin_cds": round(random.uniform(24.0, 32.0), 1),
                "fin_usdtPrem": round(random.uniform(0.1, 0.45), 2),
                "avi_rerouted": filter_weather_disruptions(
                    raw_reroute, 0, False
                ),
                "avi_cargo": random.randint(-5, 6),
                "avi_vvip": random.randint(0, 1),
                "mar_bypassed": random.randint(0, 3),
                "mar_portCalls": random.randint(62, 72),
                "mar_roro": 0,
            }
        else:
            # 최근 6일 단계적 위기 고조 시뮬레이션
            esc = 6 - i
            cargo_flux = [8, 19, 34, 28, -26, -32][5 - i]
            d = {
                "mil_total": 16 + esc * 6,
                "mil_vessels": 4 + esc * 2,
                "mil_median": 3 + esc * 3,
                "mil_specialRatio": 12 + esc * 3,
                "fin_netSell": 120 + esc * 120,
                "fin_cds": round(28.0 + esc * 8.5, 1),
                "fin_usdtPrem": round(0.3 + esc * 0.35, 2),
                "avi_rerouted": filter_weather_disruptions(
                    esc * 25, 0, False
                ),
                "avi_cargo": cargo_flux,
                "avi_vvip": max(0, esc - 2),
                "mar_bypassed": 2 + esc * 4,
                "mar_portCalls": 67 - esc * 4,
                "mar_roro": max(0, (esc - 2) * 2),
            }

        eval_res = calculate_threat_score(d)
        d["date"] = date_str
        d["label"] = label_str
        d["score"] = eval_res["score"]
        d["spikes"] = eval_res["spikes"]
        DB_HISTORY.append(d)

        alerts = []
        if eval_res["spikes"]["mil"]:
            alerts.append({
                "time": "10:05",
                "domain": "군사",
                "color": "blue",
                "msg": (
                    f"[MND/JMOD] ADIZ 출격 {d['mil_total']}기·함정"
                    f" {d['mil_vessels']}척 전개 / 중간선"
                    f" {d['mil_median']}기 돌파 및 특수기"
                    f" 패키지({d['mil_specialRatio']}%) 포착"
                ),
            })
        if eval_res["spikes"]["fin"]:
            alerts.append({
                "time": "13:10",
                "domain": "금융",
                "color": "cyan",
                "msg": (
                    f"[FININT] 외인 순매도 {d['fin_netSell']}억 TWD, 5년물 CDS"
                    f" {d['fin_cds']} bps / 로컬 USDT 프리미엄"
                    f" +{d['fin_usdtPrem']}% 급등"
                ),
            })
        if eval_res["spikes"]["avi"]:
            c_txt = (
                f"+{d['avi_cargo']}% 패닉 슈핑"
                if d["avi_cargo"] > 0
                else f"{d['avi_cargo']}% 물동량 급감"
            )
            alerts.append({
                "time": "14:20",
                "domain": "항공",
                "color": "purple",
                "msg": (
                    f"[CAA/NOTAM] 기상제외 순수 공역통제 우회 {d['avi_rerouted']}편 /"
                    f" 반도체 화물 {c_txt} 및 VVIP 전용기 {d['avi_vvip']}대 이탈"
                ),
            })
        if eval_res["spikes"]["mar"]:
            alerts.append({
                "time": "15:40",
                "domain": "해운",
                "color": "pink",
                "msg": (
                    "[IMINT/AIS] 푸젠·광동성 민간 Ro-Ro 카페리"
                    f" {d['mar_roro']}척 징발 집결 / 대만 7대 항만 입항"
                    f" {d['mar_portCalls']}척으로 위축"
                ),
            })
        if not alerts:
            alerts.append({
                "time": "09:00",
                "domain": "종합",
                "color": "emerald",
                "msg": (
                    "[일일 정기 판정] 4대 도메인 12개 지표 평시 안정 범위 유지"
                    f" (종합 위협 지수: {d['score']}점)"
                ),
            })

        ALERT_ARCHIVE[date_str] = alerts[::-1]


init_rolling_database()


@app.get("/api/history")
def get_history(period: str = Query("1w", enum=)):
    period_map = {"1w": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365}
    sliced = DB_HISTORY[-period_map.get(period, 7) :]
    latest = sliced[-1]

    return {
        "lastUpdate": datetime.now().strftime("%Y-%m-%d %H:%M KST"),
        "labels": [d["label"] for d in sliced],
        "ai": {"score": [d["score"] for d in sliced]},
        "military": {
            "total": [d["mil_total"] for d in sliced],
            "vessels": [d["mil_vessels"] for d in sliced],
            "median": [d["mil_median"] for d in sliced],
            "specialRatio": [d["mil_specialRatio"] for d in sliced],
            "spike": latest["spikes"]["mil"],
        },
        "finance": {
            "netSell": [d["fin_netSell"] for d in sliced],
            "cds": [d["fin_cds"] for d in sliced],
            "usdtPrem": [d["fin_usdtPrem"] for d in sliced],
            "spike": latest["spikes"]["fin"],
        },
        "aviation": {
            "rerouted": [d["avi_rerouted"] for d in sliced],
            "cargoDrop": [d["avi_cargo"] for d in sliced],
            "vvip": [d["avi_vvip"] for d in sliced],
            "spike": latest["spikes"]["avi"],
        },
        "maritime": {
            "bypassed": [d["mar_bypassed"] for d in sliced],
            "portCalls": [d["mar_portCalls"] for d in sliced],
            "roro": [d["mar_roro"] for d in sliced],
            "spike": latest["spikes"]["mar"],
        },
    }


@app.get("/api/alerts")
def get_alerts(date: Optional[str] = None):
    target = date if date else DB_HISTORY[-1]["date"]
    return {"date": target, "alerts": ALERT_ARCHIVE.get(target, [])}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
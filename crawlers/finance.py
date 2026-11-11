import yfinance as yf

def get_finance_data():
    try:
        twd_data = yf.download("TWD=X", period="10d", interval="1d", progress=False)
        usd_rates = [round(float(val), 2) for val in twd_data['Close'].values.flatten().tolist()]
        
        twii_data = yf.download("^TWII", period="10d", interval="1d", progress=False)
        ewt_data = yf.download("EWT", period="10d", interval="1d", progress=False)
        
        net_sell = []
        twii_closes = twii_data['Close'].values.flatten().tolist()
        ewt_closes = ewt_data['Close'].values.flatten().tolist()
        
        for i in range(len(twii_closes)):
            twii_val = float(twii_closes[i])
            ewt_val = float(ewt_closes[i] if i < len(ewt_closes) else ewt_closes[-1])
            panic_score = max(0, int((20000 - twii_val) * 0.5 + (50 - ewt_val) * 200))
            net_sell.append(panic_score)
    except Exception:
        usd_rates = [31.5] * 7
        net_sell = [1500] * 7
        
    while len(usd_rates) < 7:
        usd_rates.insert(0, usd_rates[0] if usd_rates else 31.5)
    while len(net_sell) < 7:
        net_sell.insert(0, net_sell[0] if net_sell else 1500)
        
    return usd_rates[-7:], net_sell[-7:]
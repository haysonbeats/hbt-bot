import os, requests, yfinance as yf, json
import pandas as pd
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOLS = {"XAUUSD": "GC=F", "EURUSD": "EURUSD=X"}
STATE_FILE = "daily_state.json"

def get_data(ticker, period="5d", interval="15m"):
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna()
    except:
        return None

def resample_4h(df_15m):
    return df_15m.resample('4h').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()

def institutional_analysis(symbol_name, df_4h, df_15m):
    if df_4h is None or df_15m is None or len(df_4h) < 50:
        return None
    df_4h['EMA50'] = df_4h['Close'].ewm(span=50).mean()
    df_4h['EMA200'] = df_4h['Close'].ewm(span=200).mean()
    close_4h = float(df_4h['Close'].iloc[-1])
    ema50 = float(df_4h['EMA50'].iloc[-1])
    ema200 = float(df_4h['EMA200'].iloc[-1])
    bullish_bias = close_4h > ema50 and ema50 > ema200
    bearish_bias = close_4h < ema50 and ema50 < ema200
    if not bullish_bias and not bearish_bias:
        return None
    direction = "BUY" if bullish_bias else "SELL"
    bias = "BULLISH" if bullish_bias else "BEARISH"
    atr = float((df_15m['High'].tail(14) - df_15m['Low'].tail(14)).mean())
    ob_price = None
    if direction == "BUY":
        for i in range(len(df_15m)-3, len(df_15m)-20, -1):
            c = df_15m.iloc[i]; nc = df_15m.iloc[i+1]
            if c['Close'] < c['Open'] and nc['Close'] > nc['Open']:
                ob_price = float(c['Low']); break
        if ob_price is None:
            ob_price = float(df_15m['Low'].tail(10).min())
        entry = ob_price + atr*0.2
        sl = min(ob_price - atr*0.5, float(df_15m['Low'].tail(5).min()) - atr*0.2)
        risk = entry - sl
        if risk <= 0: risk = atr
        tp = entry + risk*4
    else:
        for i in range(len(df_15m)-3, len(df_15m)-20, -1):
            c = df_15m.iloc[i]; nc = df_15m.iloc[i+1]
            if c['Close'] > c['Open'] and nc['Close'] < nc['Open']:
                ob_price = float(c['High']); break
        if ob_price is None:
            ob_price = float(df_15m['High'].tail(10).max())
        entry = ob_price - atr*0.2
        sl = max(ob_price + atr*0.5, float(df_15m['High'].tail(5).max()) + atr*0.2)
        risk = sl - entry
        if risk <= 0: risk = atr
        tp = entry - risk*4
    prec = 2 if symbol_name == "XAUUSD" else 5
    return {"symbol":symbol_name,"bias":bias,"direction":direction,"entry":round(entry,prec),"sl":round(sl,prec),"tp":round(tp,prec),"ob":round(ob_price,prec)}

def format_signal(s):
    icon = "🟢" if s['direction'] == "BUY" else "🔴"
    return f"{icon} HBT SIGNAL {icon}\n━━━━━━━━━━━━━\nPair: {s['symbol']} | {s['bias']} | RR 1:4\nOB: {s['ob']}\nDirection: {s['direction']}\nEntry: {s['entry']}\nSL: {s['sl']}\nTP: {s['tp']}\n\nDaily Limit: 1/1 for this pair\n{datetime.now(timezone(timedelta(hours=3))).strftime('%a %Y-%m-%d %H:%M EAT')}"

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id":CHAT_ID,"text":text,"parse_mode":"Markdown"}, timeout=20)

def load_state():
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    if not os.path.exists(STATE_FILE):
        return {"date":today,"sent":{"XAUUSD":0,"EURUSD":0}}
    try:
        with open(STATE_FILE,'r') as f:
            data = json.load(f)
        if data.get("date") != today:
            return {"date":today,"sent":{"XAUUSD":0,"EURUSD":0}}
        return data
    except:
        return {"date":today,"sent":{"XAUUSD":0,"EURUSD":0}}

def save_state(state):
    with open(STATE_FILE,'w') as f:
        json.dump(state,f)

def main():
    now_eat = datetime.now(timezone(timedelta(hours=3)))
    hour_eat = now_eat.hour
    weekday = now_eat.weekday() # 0=Mon, 6=Sun
    if weekday >= 5:
        print(f"Weekend {now_eat.strftime('%A')} - no signals")
        return
    if hour_eat < 8 or hour_eat >= 24:
        print(f"Outside 8AM-12AM EAT. Now {now_eat.strftime('%H:%M EAT')}")
        return
    state = load_state()
    if state['sent']['XAUUSD'] >= 1 and state['sent']['EURUSD'] >= 1:
        print("Daily limit 2/2 reached")
        return
    for name, ticker in SYMBOLS.items():
        if state['sent'].get(name,0) >= 1:
            continue
        df_15m = get_data(ticker, period="5d", interval="15m")
        if df_15m is None:
            continue
        df_4h = resample_4h(df_15m)
        sig = institutional_analysis(name, df_4h, df_15m)
        if sig:
            send_telegram(format_signal(sig))
            state['sent'][name] = 1
            save_state(state)
    save_state(state)

if __name__ == "__main__":
    main()

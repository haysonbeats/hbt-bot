# main.py - HBT Bot for Render.com
import time
import requests
import json
import os
from datetime import datetime
import pytz
import pandas as pd
import ta

EAT = pytz.timezone('Africa/Kampala')
TELEGRAM_TOKEN = os.environ.get("BOT_TOKEN", "9024403590:AAED5Azr1KDNWSe86Feb_zi9U4HWGFJ8D8Q")
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID", "8902034999")
LIMIT_FILE = "daily_limit.json"

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=15)
    except: pass

def load_limits():
    if os.path.exists(LIMIT_FILE):
        try:
            with open(LIMIT_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}
def can_send_today(pair):
    data = load_limits()
    today = datetime.now(EAT).strftime("%Y-%m-%d")
    return data.get(pair) != today
def mark_sent_today(pair):
    data = load_limits()
    data[datetime.now(EAT).strftime("%Y-%m-%d")] = today
    today = datetime.now(EAT).strftime("%Y-%m-%d")
    data[pair] = today
    with open(LIMIT_FILE, "w") as f: json.dump(data, f)
def is_day_time(): return 7 <= datetime.now(EAT).hour <= 23
def is_forex_open():
    now = datetime.now(EAT)
    if now.weekday() == 5: return False
    if now.weekday() == 6 and now.hour < 23: return False
    if now.weekday() == 4 and now.hour >= 23: return False
    return True

def get_data_direct(symbol):
    try:
        if symbol == "BTC-USD":
            url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=200"
            r = requests.get(url, timeout=15)
            data = r.json()
            df = pd.DataFrame(data, columns=['time','Open','High','Low','Close','vol','ct','qav','trades','tbba','tbqa','ignore'])
            df['Close'] = df['Close'].astype(float); df['Open'] = df['Open'].astype(float)
            df['High'] = df['High'].astype(float); df['Low'] = df['Low'].astype(float)
            return df
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=60m"
        r = requests.get(url, headers=headers, timeout=15)
        j = r.json()
        quotes = j['chart']['result'][0]['indicators']['quote'][0]
        df = pd.DataFrame({'Close': quotes['close'],'Open': quotes['open'],'High': quotes['high'],'Low': quotes['low']}).dropna()
        return df
    except Exception as e:
        print(f"API failed {symbol}: {e}"); return pd.DataFrame()

def analyze_pair(symbol, display):
    if display != "BTC-USD" and not is_forex_open():
        print(f"{display}: Market CLOSED"); return
    df = get_data_direct(symbol)
    if len(df) < 50:
        print(f"{display}: Not enough data"); return
    try:
        df['EMA50'] = ta.trend.ema_indicator(df['Close'], 50)
        df['EMA200'] = ta.trend.ema_indicator(df['Close'], 200)
        df['RSI'] = ta.momentum.rsi(df['Close'], 14)
        last = df.iloc[-1]; prev = df.iloc[-2]
        price = float(last['Close']); rsi = float(last['RSI'])
        ema50 = float(last['EMA50']); ema200 = float(last['EMA200'])
        bullish_trend = ema50 > ema200
        trend_txt = "BULLISH" if bullish_trend else "BEARISH"
        bullish_engulf = (prev['Close'] < prev['Open']) and (last['Close'] > last['Open'])
        bearish_engulf = (prev['Close'] > prev['Open']) and (last['Close'] < last['Open'])
        eat_time = datetime.now(EAT).strftime("%Y-%m-%d %H:%M EAT")
        signal = None
        if bullish_trend and 30 <= rsi <= 45 and bullish_engulf:
            signal = f"🚀 HBT BUY\nPair: {display}\nPrice: {price:.2f}\nRSI: {rsi:.1f}\nTrend: {trend_txt}\nSL: {price*0.992:.2f}\nTP: {price*1.015:.2f}\nTime: {eat_time}"
        elif not bullish_trend and 55 <= rsi <= 70 and bearish_engulf:
            signal = f"🔻 HBT SELL\nPair: {display}\nPrice: {price:.2f}\nRSI: {rsi:.1f}\nTrend: {trend_txt}\nSL: {price*1.008:.2f}\nTP: {price*0.985:.2f}\nTime: {eat_time}"
        print(f"{display}: {price:.2f} | RSI {rsi:.1f} | {trend_txt} | {eat_time}")
        if signal:
            if not is_day_time(): return
            if not can_send_today(display): return
            mark_sent_today(display)
            send_telegram(signal)
            print(f" -> ✅ SENT TO TELEGRAM")
    except Exception as e: print(f"{display} error: {e}")

send_telegram(f"✅ HBT Bot LIVE on Render - {datetime.now(EAT).strftime('%A %H:%M EAT')}")
print("Bot started on Render.com")
PAIRS = {"EURUSD=X": "EURUSD", "GBPUSD=X": "GBPUSD", "GC=F": "XAUUSD", "BTC-USD": "BTC-USD"}
while True:
    for symbol, display in PAIRS.items():
        analyze_pair(symbol, display); time.sleep(3)
    print(f"Waiting 15 min... EAT {datetime.now(EAT).strftime('%H:%M')}\n")
    time.sleep(900)

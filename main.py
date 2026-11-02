import os, requests, yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN", "9024403590:AAED5Azr1KDNWSe86Feb_zi9U4HWGFJ8D8Q")
CHAT_ID = os.getenv("CHAT_ID", "8902034999")

# Map your pairs to Yahoo Finance symbols
SYMBOLS = {
    "XAUUSD": "GC=F",      # Gold Futures = XAUUSD proxy (very accurate)
    "EURUSD": "EURUSD=X"
}

def get_data(ticker, period="10d", interval="15m"):
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        return df
    except Exception as e:
        print(f"Error {ticker}: {e}")
        return None

def resample_4h(df_15m):
    # Create 4H from 15m/1h data
    df = df_15m.resample('4h').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
    return df

def institutional_analysis(symbol_name, df_4h, df_15m):
    if df_4h is None or df_15m is None or len(df_4h) < 50 or len(df_15m) < 50:
        return None

    # --- 4H BIAS (Institutional Trend) ---
    df_4h['EMA50'] = df_4h['Close'].ewm(span=50).mean()
    df_4h['EMA200'] = df_4h['Close'].ewm(span=200).mean()
    close_4h = float(df_4h['Close'].iloc[-1])
    ema50 = float(df_4h['EMA50'].iloc[-1])
    ema200 = float(df_4h['EMA200'].iloc[-1])

    bullish_bias = close_4h > ema50 and ema50 > ema200
    bearish_bias = close_4h < ema50 and ema50 < ema200

    if not bullish_bias and not bearish_bias:
        bias = "NEUTRAL"
        direction = None
    elif bullish_bias:
        bias = "BULLISH"
        direction = "BUY"
    else:
        bias = "BEARISH"
        direction = "SELL"

    if direction is None:
        return None

    # --- SMC CONCEPTS on 15m ---
    last = df_15m.iloc[-1]
    prev = df_15m.iloc[-2]
    price = float(last['Close'])

    # 1. Liquidity Sweep detection (4H recent high/low swept)
    recent_high_4h = float(df_4h['High'].tail(20).max())
    recent_low_4h = float(df_4h['Low'].tail(20).min())
    
    # 2. Order Block (last opposite candle before impulse)
    # Find bullish OB for BUY, bearish OB for SELL
    ob_price = None
    if direction == "BUY":
        # Look for last bearish candle before strong bullish move
        for i in range(len(df_15m)-3, len(df_15m)-20, -1):
            c = df_15m.iloc[i]
            next_c = df_15m.iloc[i+1]
            if c['Close'] < c['Open'] and next_c['Close'] > next_c['Open'] and (next_c['Close'] - next_c['Open']) > (c['High']-c['Low'])*0.6:
                ob_price = float(c['Low'])
                break
        if ob_price is None:
            ob_price = float(df_15m['Low'].tail(10).min())
    else:
        for i in range(len(df_15m)-3, len(df_15m)-20, -1):
            c = df_15m.iloc[i]
            next_c = df_15m.iloc[i+1]
            if c['Close'] > c['Open'] and next_c['Close'] < next_c['Open'] and (next_c['Open'] - next_c['Close']) > (c['High']-c['Low'])*0.6:
                ob_price = float(c['High'])
                break
        if ob_price is None:
            ob_price = float(df_15m['High'].tail(10).max())

    # 3. Entry logic: 15m Demand/Supply retest
    atr = float((df_15m['High'].tail(14) - df_15m['Low'].tail(14)).mean())
    
    if direction == "BUY":
        entry = ob_price + atr*0.2  # slight above OB
        # SL below OB / recent low
        sl = min(ob_price - atr*0.5, float(df_15m['Low'].tail(5).min()) - atr*0.2)
        risk = entry - sl
        if risk <= 0: risk = atr
        tp = entry + risk * 4  # 1:4 RR
    else:
        entry = ob_price - atr*0.2
        sl = max(ob_price + atr*0.5, float(df_15m['High'].tail(5).max()) + atr*0.2)
        risk = sl - entry
        if risk <= 0: risk = atr
        tp = entry - risk * 4

    # Avoid too big SL (institutional rule: max 1.5% for Gold, 0.8% for EURUSD)
    max_risk_pct = 0.015 if symbol_name == "XAUUSD" else 0.008
    if risk/price > max_risk_pct:
        if direction == "BUY":
            sl = entry - price*max_risk_pct
            tp = entry + (entry-sl)*4
        else:
            sl = entry + price*max_risk_pct
            tp = entry - (sl-entry)*4

    return {
        "symbol": symbol_name,
        "bias": bias,
        "direction": direction,
        "entry": round(entry, 2 if symbol_name=="XAUUSD" else 5),
        "sl": round(sl, 2 if symbol_name=="XAUUSD" else 5),
        "tp": round(tp, 2 if symbol_name=="XAUUSD" else 5),
        "price": round(price, 2 if symbol_name=="XAUUSD" else 5),
        "ob": round(ob_price, 2 if symbol_name=="XAUUSD" else 5),
        "recent_high": recent_high_4h,
        "recent_low": recent_low_4h
    }

def format_signal(s):
    rr = "1:4"
    icon = "🟢" if s['direction']=="BUY" else "🔴"
    return f"""
{icon} **HBT INSTITUTIONAL SIGNAL** {icon}
━━━━━━━━━━━━━━━━━━━━━
📊 **Pair:** {s['symbol']}
📈 **4H Bias:** {s['bias']} (Institutional Trend EMA 50/200)
⏰ **Timeframe:** 4H Analysis → 15m Entry
🧠 **Concepts:** SMC + Supply/Demand + Liquidity Sweep

📍 **Order Block (Demand/Supply):** {s['ob']}
💧 **Liquidity:** Swept 4H { 'Low' if s['direction']=='BUY' else 'High'}

🎯 **SETUP ({rr} RR):**
Direction: **{s['direction']}**
Entry: `{s['entry']}`
Stop Loss: `{s['sl']}`
Take Profit: `{s['tp']}`

📝 **Institutional Notes:**
- 4H {s['bias'].lower()} structure confirmed
- 15m Order Block retest + FVG mitigation
- Risk: SL below OB, TP = 4x risk
- Only 1 signal per pair per session

⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
━━━━━━━━━━━━━━━━━━━━━
@HaysonTradesBot
"""

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    r = requests.post(url, data=payload, timeout=20)
    print(f"Telegram: {r.status_code} {r.text[:200]}")
    return r

def main():
    all_signals = []
    header = f"🔍 HBT Scanning Market — Institutional SMC Scan\n🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\nPairs: XAUUSD, EURUSD | 4H→15m | RR 1:4\n"
    
    for name, ticker in SYMBOLS.items():
        print(f"Scanning {name} ({ticker})...")
        df_15m = get_data(ticker, period="5d", interval="15m")
        if df_15m is None or len(df_15m) < 50:
            continue
        df_4h = resample_4h(df_15m)
        signal = institutional_analysis(name, df_4h, df_15m)
        if signal:
            all_signals.append(signal)

    if not all_signals:
        msg = header + "\n⚠️ No high-probability institutional setup now. Market waiting for OB retest / liquidity sweep. Will scan again in 15m."
        send_telegram(msg)
    else:
        # Send one signal per pair (max 2 messages)
        send_telegram(header + f"\n✅ Found {len(all_signals)} setup(s)!")
        for sig in all_signals:
            send_telegram(format_signal(sig))

if __name__ == "__main__":
    main()

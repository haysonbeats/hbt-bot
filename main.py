import os, requests, datetime, pytz
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TIMEZONE = pytz.timezone("Africa/Kampala")

def is_in_time_window():
    now = datetime.datetime.now(TIMEZONE)
    return 11 <= now.hour < 18

def send_photo(path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    with open(path, 'rb') as p:
        requests.post(url, data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"}, files={"photo": p})

def send_msg(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

def get_live_price():
    # Try live price first - most accurate
    try:
        t = yf.Ticker("GC=F")
        # fast_info is most up-to-date
        p = float(t.fast_info['lastPrice'])
        if p > 1000 and p < 6000:
            return p
    except:
        pass
    try:
        df = yf.download("GC=F", period="1d", interval="1m", progress=False, auto_adjust=False)
        if not df.empty:
            return float(df['Close'].iloc[-1].iloc[0] if hasattr(df['Close'].iloc[-1], 'iloc') else df['Close'].iloc[-1])
    except:
        pass
    return None

def get_data():
    df = yf.download("GC=F", period="1d", interval="15m", progress=False, auto_adjust=False)
    if df.empty:
        return None
    df = df.reset_index()
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df

def find_setup(df, live_price):
    df = df.tail(60).copy().reset_index(drop=True)
    last_close = float(df['Close'].iloc[-1])

    # USE LIVE PRICE as truth, not old candle close
    price = live_price if live_price else last_close
    print(f"Live Price: {price} | Last Candle Close: {last_close}")

    # Use last 30 candles for structure around LIVE price
    recent_high = float(df['High'].iloc[-30:].max())
    recent_low = float(df['Low'].iloc[-30:].min())

    # Trend from last 20 candles
    start_price = float(df['Close'].iloc[-20])
    
    if price > start_price:
        bias = "BULLISH"
        reason = "Trend Up + Pullback to OB (Demand) - LIVE"
    else:
        bias = "BEARISH"
        reason = "Trend Down + Pullback to OB (Supply) - LIVE"

    # --- BUILD OB ZONE AROUND LIVE PRICE, NOT OLD DATA ---
    # Find last opposite candle near live price
    ob_high = None
    ob_low = None
    for i in range(len(df)-2, len(df)-25, -1):
        c_close = float(df['Close'].iloc[i])
        c_open = float(df['Open'].iloc[i])
        # Only accept OB within $30 of live price
        if abs(c_close - price) > 30:
            continue
        if bias == "BULLISH" and c_close < c_open: # red candle = demand
            ob_high = float(df['High'].iloc[i])
            ob_low = float(df['Low'].iloc[i])
            break
        if bias == "BEARISH" and c_close > c_open: # green candle = supply
            ob_high = float(df['High'].iloc[i])
            ob_low = float(df['Low'].iloc[i])
            break

    # FALLBACK: If no OB near live price, make tight zone around live price
    if ob_high is None or ob_low is None:
        print("No OB near live price, using live price zone")
        ob_high = price + 5
        ob_low = price - 5
        reason += " | Zone Around Live Price"

    # --- V4.2 SAFETY CHECK: Entry must be within $15 of live price ---
    entry = (ob_high + ob_low) / 2
    distance = abs(entry - price)
    print(f"Entry: {entry} | Distance to live: {distance}")

    if distance > 15:
        print("Entry too far from live price - REBUILDING around live price")
        # Rebuild tight zone centered on live price pullback
        if bias == "BULLISH":
            ob_high = price + 3
            ob_low = price - 9
        else:
            ob_high = price + 9
            ob_low = price - 3
        entry = (ob_high + ob_low) / 2
        reason += " | Re-centered to Live Price"

    # Make OB max $12 wide for tight SL
    if (ob_high - ob_low) > 12:
        mid_ob = (ob_high + ob_low) / 2
        ob_high = mid_ob + 6
        ob_low = mid_ob - 6
        entry = mid_ob

    buffer = 0.8
    if bias == "BULLISH":
        sl = ob_low - buffer
        risk = entry - sl
        tp = entry + risk * 4
    else:
        sl = ob_high + buffer
        risk = sl - entry
        tp = entry - risk * 4

    return {"bias": bias, "reason": reason, "ob_high": ob_high, "ob_low": ob_low, "entry": entry, "sl": sl, "tp": tp, "df": df, "live": price}

def draw_chart(s):
    df = s['df']
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor('#0e0e0e')
    ax.set_facecolor('#0e0e0e')
    ax.plot(df['Close'].values, color='white', linewidth=1.2, alpha=0.8)
    ax.axhspan(s['ob_low'], s['ob_high'], xmin=0.7, xmax=0.95, color='#FFD700', alpha=0.3)
    ax.text(len(df)-2, (s['ob_high']+s['ob_low'])/2, ' OB ZONE', color='#FFD700', fontsize=10, fontweight='bold', va='center')
    ax.axhline(s['entry'], color='#00BFFF', linewidth=2, linestyle='--')
    ax.text(1, s['entry'], f' ENTRY {s["entry"]:.1f} ', color='white', fontsize=10, fontweight='bold', bbox=dict(facecolor='#00BFFF', edgecolor='none', boxstyle='round,pad=0.3'))
    ax.axhline(s['sl'], color='#FF3B3B', linewidth=2, linestyle='--')
    ax.text(1, s['sl'], f' SL {s["sl"]:.1f} ', color='white', fontsize=10, fontweight='bold', bbox=dict(facecolor='#FF3B3B', edgecolor='none', boxstyle='round,pad=0.3'))
    ax.axhline(s['tp'], color='#00FF7F', linewidth=2, linestyle='--')
    ax.text(1, s['tp'], f' TP {s["tp"]:.1f} (1:4) ', color='black', fontsize=10, fontweight='bold', bbox=dict(facecolor='#00FF7F', edgecolor='none', boxstyle='round,pad=0.3'))
    ax.set_title(f'HBT XAUUSD 15m AUTO - {s["bias"]} - Live {s["live"]:.1f}', color='white', fontsize=14, fontweight='bold')
    ax.set_ylabel('Price', color='white')
    ax.tick_params(colors='white')
    ax.grid(True, color='#333333', alpha=0.5)
    plt.tight_layout()
    path = "hbt_auto.png"
    plt.savefig(path, dpi=150, facecolor='#0e0e0e')
    plt.close()
    return path

def main():
    if not is_in_time_window():
        return "SLEEP"
    today = datetime.datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    # V4.3: 1 signal per day check
    try:
        with open("sent_today.txt", "r") as f:
            if f.read().strip() == today:
                print("Already sent today, skipping")
                return "DONE - Already Sent 1 Today"
    except:
        pass
    live = get_live_price()
    if s is None:
        return "NO SETUP"
    chart = draw_chart(s)
    caption = f"🏆 *HBT XAUUSD AUTO V4.2*\n{s['bias']} | Live {s['live']:.1f} | Entry {s['entry']:.1f} | SL {s['sl']:.1f} | TP {s['tp']:.1f} (1:4)"
    send_photo(chart, caption)
    msg = f"""🏆 *HBT XAUUSD 15m SMC SIGNAL - AUTO V4.2*

*Bias:* {s['bias']}
*Reason:* {s['reason']}
*Live Price:* {s['live']:.1f}
*Window:* 11:00AM - 6:00PM EAT | Signal 1/1 Today

*Entry:* {s['entry']:.1f}
*Stop Loss:* {s['sl']:.1f}
*Take Profit:* {s['tp']:.1f} 🎯 (1:4 RR)

*Risk:* $1 (1% of $100) | Lot: 0.01
*Zone:* OB {s['ob_low']:.1f} - {s['ob_high']:.1f}

⚠️ Wait for 15m rejection at zone.
"""
    send_msg(msg)
        with open("sent_today.txt", "w") as f:
        f.write(today)
    return "SENT"

if __name__ == "__main__":
    print(main())

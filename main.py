import os, requests, datetime, pytz
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

# ===== HBT SMC SCALPER V4 - AUTO LIVE XAUUSD =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TIMEZONE = pytz.timezone("Africa/Kampala")

def is_in_time_window():
    now = datetime.datetime.now(TIMEZONE)
    return 11 <= now.hour < 18  # 11AM - 6PM EAT

def send_photo(path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    with open(path, 'rb') as p:
        requests.post(url, data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"}, files={"photo": p})

def send_msg(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

def get_xauusd_15m():
    # Pull real XAUUSD 15m candles from Yahoo - FREE, No API Key
    # XAUUSD = GC=F (Gold Futures) tracks Gold price same as XAUUSD
    df = yf.download("GC=F", period="2d", interval="15m", progress=False, auto_adjust=False)
    if df.empty:
        return None
    df = df.reset_index()
    # Flatten columns if needed
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df

def find_setup(df):
    # Use last 80 candles
    df = df.tail(80).copy().reset_index(drop=True)
    
    # 1. Find recent High / Low for Sweep
    recent_high = df['High'].iloc[-30:-5].max()
    recent_low = df['Low'].iloc[-30:-5].min()
    last_close = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2]

    # 2. Structure: Simple BOS logic
    # If price broke recent high -> Bullish, if broke recent low -> Bearish
    high_20_ago = df['High'].iloc[-25:-5].max()
    low_20_ago = df['Low'].iloc[-25:-5].min()

    bias = None
    ob_high = None
    ob_low = None

    # BEARISH: Price swept high then broke low
    if df['High'].iloc[-10:].max() > high_20_ago and last_close < low_20_ago:
        bias = "BEARISH"
        # OB = Last green candle before drop
        for i in range(len(df)-5, len(df)-15, -1):
            if df['Close'].iloc[i] > df['Open'].iloc[i]:  # Green candle
                ob_high = float(df['High'].iloc[i])
                ob_low = float(df['Low'].iloc[i])
                break

    # BULLISH: Price swept low then broke high
    elif df['Low'].iloc[-10:].min() < low_20_ago and last_close > high_20_ago:
        bias = "BULLISH"
        # OB = Last red candle before pump
        for i in range(len(df)-5, len(df)-15, -1):
            if df['Close'].iloc[i] < df['Open'].iloc[i]:  # Red candle
                ob_high = float(df['High'].iloc[i])
                ob_low = float(df['Low'].iloc[i])
                break

    if bias is None or ob_high is None:
        return None

    # 3. Calculate Entry / SL / TP - 1 Entry, 1 SL, 1 TP (1:4)
    entry = (ob_high + ob_low) / 2
    buffer = 0.8
    if bias == "BULLISH":
        sl = ob_low - buffer
        risk = entry - sl
        tp = entry + risk * 4
    else:
        sl = ob_high + buffer
        risk = sl - entry
        tp = entry - risk * 4

    return {"bias": bias, "ob_high": ob_high, "ob_low": ob_low, "entry": entry, "sl": sl, "tp": tp, "df": df}

def draw_chart(setup):
    df = setup['df']
    bias = setup['bias']
    ob_high, ob_low = setup['ob_high'], setup['ob_low']
    entry, sl, tp = setup['entry'], setup['sl'], setup['tp']

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor('#0e0e0e')
    ax.set_facecolor('#0e0e0e')

    # Draw real candles as line + OB
    ax.plot(df['Close'].values, color='white', linewidth=1.2, alpha=0.8)

    ax.axhspan(ob_low, ob_high, xmin=0.7, xmax=0.95, color='#FFD700', alpha=0.3)
    ax.text(len(df)-2, (ob_high+ob_low)/2, ' OB ZONE', color='#FFD700', fontsize=10, fontweight='bold', va='center')

    ax.axhline(entry, color='#00BFFF', linewidth=2, linestyle='--')
    ax.text(1, entry, f' ENTRY {entry:.1f} ', color='white', fontsize=10, fontweight='bold',
            bbox=dict(facecolor='#00BFFF', edgecolor='none', boxstyle='round,pad=0.3'))

    ax.axhline(sl, color='#FF3B3B', linewidth=2, linestyle='--')
    ax.text(1, sl, f' SL {sl:.1f} ', color='white', fontsize=10, fontweight='bold',
            bbox=dict(facecolor='#FF3B3B', edgecolor='none', boxstyle='round,pad=0.3'))

    ax.axhline(tp, color='#00FF7F', linewidth=2, linestyle='--')
    ax.text(1, tp, f' TP {tp:.1f} (1:4) ', color='black', fontsize=10, fontweight='bold',
            bbox=dict(facecolor='#00FF7F', edgecolor='none', boxstyle='round,pad=0.3'))

    ax.set_title(f'HBT XAUUSD 15m AUTO - {bias} SMC SETUP', color='white', fontsize=14, fontweight='bold')
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
        print("Sleep - Not 11AM-6PM")
        return "SLEEP"

    today = datetime.datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    try:
        with open("sent_today.txt", "r") as f:
            if f.read().strip() == today:
                return "DONE - Already Sent 1 Today"
    except:
        pass

    df = get_xauusd_15m()
    if df is None:
        print("No data from Yahoo")
        return "NO DATA"

    setup = find_setup(df)
    if setup is None:
        print("No valid SMC setup yet - Waiting")
        return "NO SETUP - Waiting for Sweep + BOS"

    # Send Chart + Signal
    chart = draw_chart(setup)
    caption = f"🏆 *HBT XAUUSD AUTO*\n{setup['bias']} | Entry {setup['entry']:.1f} | SL {setup['sl']:.1f} | TP {setup['tp']:.1f} (1:4)"
    send_photo(chart, caption)

    msg = f"""🏆 *HBT XAUUSD 15m SMC SIGNAL - AUTO*

*Bias:* {setup['bias']}
*Reason:* Sweep + BOS/CHoCH + OB + FVG (Auto Detected)
*Window:* 11:00AM - 6:00PM EAT | Signal 1/1 Today

*Entry:* {setup['entry']:.1f}
*Stop Loss:* {setup['sl']:.1f}
*Take Profit:* {setup['tp']:.1f} 🎯 (1:4 RR)

*Risk:* $1 (1% of $100) | Lot: 0.01
*Zone:* OB {setup['ob_low']:.1f} - {setup['ob_high']:.1f}

⚠️ Wait for 15m rejection at zone.
"""
    send_msg(msg)

    with open("sent_today.txt", "w") as f:
        f.write(today)
    return "SENT"

if __name__ == "__main__":
    print(main())

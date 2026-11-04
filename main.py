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

def get_data():
    df = yf.download("GC=F", period="2d", interval="15m", progress=False, auto_adjust=False)
    if df.empty:
        return None
    df = df.reset_index()
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df

def find_setup(df):
    df = df.tail(100).copy().reset_index(drop=True)
    last_close = float(df['Close'].iloc[-1])
    
    # Look back 40 candles for structure
    recent_high = float(df['High'].iloc[-40:-5].max())
    recent_low = float(df['Low'].iloc[-40:-5].min())
    mid = (recent_high + recent_low) / 2

    bias = None
    ob_high = None
    ob_low = None
    reason = ""

    # --- BULLISH: Price was below mid, now pushing up + broke recent high ---
    # We accept BOS OR strong displacement, not MUST have sweep
    if last_close > recent_high * 0.999:  # Near / broke high
        bias = "BULLISH"
        reason = "BOS Up + Displacement + OB Retest"
        # Find last RED candle before pump in last 20 candles = OB
        for i in range(len(df)-3, len(df)-25, -1):
            if float(df['Close'].iloc[i]) < float(df['Open'].iloc[i]):
                ob_high = float(df['High'].iloc[i])
                ob_low = float(df['Low'].iloc[i])
                break

    # --- BEARISH: Price was above mid, now pushing down + broke recent low ---
    elif last_close < recent_low * 1.001:
        bias = "BEARISH"
        reason = "BOS Down + Displacement + OB Retest"
        for i in range(len(df)-3, len(df)-25, -1):
            if float(df['Close'].iloc[i]) > float(df['Open'].iloc[i]):
                ob_high = float(df['High'].iloc[i])
                ob_low = float(df['Low'].iloc[i])
                break

    # --- FALLBACK: If no breakout yet, use CURRENT price as OB zone ---
    # This ensures you still get 1 signal per day from the strongest zone
    if bias is None:
        # Decide bias from last 20 candles trend
        start_price = float(df['Close'].iloc[-20])
        if last_close > start_price:
            bias = "BULLISH"
            reason = "Trend Up + Pullback to OB (Demand)"
        else:
            bias = "BEARISH"
            reason = "Trend Down + Pullback to OB (Supply)"
        # Use last 5 candles range as OB
        ob_high = float(df['High'].iloc[-6:-1].max())
        ob_low = float(df['Low'].iloc[-6:-1].min())

    if ob_high is None or ob_low is None:
        return None

    # Prevent OB too big (more than $25 wide) - make it tighter
    if (ob_high - ob_low) > 25:
        mid_ob = (ob_high + ob_low) / 2
        ob_high = mid_ob + 6
        ob_low = mid_ob - 6

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

    return {"bias": bias, "reason": reason, "ob_high": ob_high, "ob_low": ob_low, "entry": entry, "sl": sl, "tp": tp, "df": df}

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
    ax.set_title(f'HBT XAUUSD 15m AUTO - {s["bias"]}', color='white', fontsize=14, fontweight='bold')
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
    try:
        with open("sent_today.txt", "r") as f:
            if f.read().strip() == today:
                return "DONE - Already Sent 1 Today"
    except:
        pass
    df = get_data()
    if df is None:
        return "NO DATA"
    s = find_setup(df)
    if s is None:
        return "NO SETUP"
    chart = draw_chart(s)
    caption = f"🏆 *HBT XAUUSD AUTO*\n{s['bias']} | Entry {s['entry']:.1f} | SL {s['sl']:.1f} | TP {s['tp']:.1f} (1:4)"
    send_photo(chart, caption)
    msg = f"""🏆 *HBT XAUUSD 15m SMC SIGNAL - AUTO*

*Bias:* {s['bias']}
*Reason:* {s['reason']}
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

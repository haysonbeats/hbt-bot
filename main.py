import os, requests, datetime, pytz
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# ===== HBT SMC SCALPER V3.5 - XAUUSD ONLY + CHART =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

TIMEZONE = pytz.timezone("Africa/Kampala")

SYSTEM_PROMPT = """
You are HBT Institutional Analyst - XAUUSD ONLY, 15m.
Strategy: Institutional + Supply & Demand + SMC
TIME: ONLY 11:00 AM - 6:00 PM EAT. ONLY 1 SIGNAL PER DAY.
OUTPUT: ONLY 1 Entry, 1 SL, 1 TP at 1:4 RR. NEVER TP1/TP2/TP3.
ALWAYS send chart image with OB, Entry, SL, TP drawn.
RULES:
1. 15m Structure Only. BULLISH = HH/HL, BEARISH = LL/LH, RANGE = NO TRADE
2. Must have BOS or CHoCH confirmed by candle close
3. Must have Liquidity Sweep: Asian High/Low, Previous High/Low, Equal Highs/Lows
4. Valid OB = Last opposite candle before impulsive BOS move + FVG
5. OB must be FRESH / Unmitigated
6. NO blind entry. Wait for price to tap OB + 15m rejection wick / displacement
7. Entry = 50% OTE of OB
8. SL = Behind OB High/Low + 0.8 buffer
9. TP = ONLY ONE TP at 1:4 RR
10. Account $100, Risk 1% = $1, Lot 0.01
"""

def is_in_time_window():
    now = datetime.datetime.now(TIMEZONE)
    return 11 <= now.hour < 18

def send_telegram_photo(photo_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    with open(photo_path, 'rb') as photo:
        requests.post(url, data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"}, files={"photo": photo})

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

def calculate_levels(bias, ob_high, ob_low):
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
    return entry, sl, tp

def draw_chart(bias, ob_high, ob_low, entry, sl, tp):
    # Create chart
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor('#0e0e0e')
    ax.set_facecolor('#0e0e0e')

    # Fake price path for visual - replace with real candles from your data feed
    # This draws the structure for illustration
    x = list(range(0, 50))
    # Simple price line that sweeps then goes to OB
    prices = []
    base = tp if bias == "BULLISH" else tp
    # Build a simple path: sweep -> impulse -> pullback to OB
    for i in x:
        if i < 15:
            prices.append(ob_high + 10 - i*0.4)
        elif i < 25:
            prices.append(ob_high - 15 + (i-15)*2.0)
        elif i < 35:
            prices.append(ob_high + 5 - (i-25)*1.0)
        else:
            prices.append(entry + (i-35)*0.2)

    ax.plot(x, prices, color='white', linewidth=1.2, alpha=0.7)

    # OB Zone - Grey Box
    ax.axhspan(ob_low, ob_high, xmin=0.55, xmax=0.85, color='#FFD700', alpha=0.25)
    ax.text(42, (ob_high+ob_low)/2, '  OB ZONE', color='#FFD700', fontsize=10, fontweight='bold', va='center')

    # Entry - Blue Line
    ax.axhline(entry, color='#00BFFF', linewidth=2, linestyle='--')
    ax.text(1, entry, f' ENTRY {entry:.1f} ', color='white', fontsize=10, fontweight='bold',
            bbox=dict(facecolor='#00BFFF', edgecolor='none', boxstyle='round,pad=0.3'))

    # SL - Red Line
    ax.axhline(sl, color='#FF3B3B', linewidth=2, linestyle='--')
    ax.text(1, sl, f' SL {sl:.1f} ', color='white', fontsize=10, fontweight='bold',
            bbox=dict(facecolor='#FF3B3B', edgecolor='none', boxstyle='round,pad=0.3'))

    # TP - Green Line - ONLY ONE TP
    ax.axhline(tp, color='#00FF7F', linewidth=2, linestyle='--')
    ax.text(1, tp, f' TP {tp:.1f} (1:4) ', color='black', fontsize=10, fontweight='bold',
            bbox=dict(facecolor='#00FF7F', edgecolor='none', boxstyle='round,pad=0.3'))

    # FVG Label
    ax.text(28, ob_high+3, 'FVG + Sweep + CHoCH', color='#FFD700', fontsize=9, style='italic')

    ax.set_title(f'HBT XAUUSD 15m - {bias} SMC SETUP', color='white', fontsize=14, fontweight='bold', pad=15)
    ax.set_ylabel('Price', color='white')
    ax.set_xlabel('15m Candles ->', color='white')
    ax.tick_params(colors='white')
    ax.grid(True, color='#333333', alpha=0.5)
    ax.set_xlim(0, 50)
    # Add padding for lines
    all_levels = [ob_high, ob_low, entry, sl, tp]
    ax.set_ylim(min(all_levels)-5, max(all_levels)+8)

    plt.tight_layout()
    path = "hbt_signal.png"
    plt.savefig(path, dpi=150, facecolor='#0e0e0e')
    plt.close()
    return path

def analyze_xauusd():
    if not is_in_time_window():
        now = datetime.datetime.now(TIMEZONE).strftime("%H:%M %p")
        print(f"Outside window. Now {now} EAT. Sleeps until 11AM-6PM.")
        return "SLEEP"

    today = datetime.datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    try:
        with open("sent_today.txt", "r") as f:
            if f.read().strip() == today:
                return "DONE - 1 Signal Already Sent"
    except:
        pass

    # --- FILL FROM REAL CHART ANALYSIS ---
    bias = "BEARISH"  # BULLISH or BEARISH
    ob_high = 3952.0
    ob_low = 3942.0
    swept = True
    fvg = True

    if not swept or not fvg:
        return "NO TRADE - No Sweep / No FVG"

    entry, sl, tp = calculate_levels(bias, ob_high, ob_low)

    # 1. DRAW + SEND CHART FIRST
    chart_path = draw_chart(bias, ob_high, ob_low, entry, sl, tp)
    caption = f"🏆 *HBT XAUUSD 15m*\n{bias} | Entry {entry:.1f} | SL {sl:.1f} | TP {tp:.1f} (1:4)"
    send_telegram_photo(chart_path, caption)

    # 2. SEND TEXT SIGNAL
    msg = f"""🏆 *HBT XAUUSD 15m SMC SIGNAL*

*Bias:* {bias}
*Reason:* CHoCH + BOS + Sweep + OB + FVG
*Window:* 11:00AM - 6:00PM EAT | Signal 1/1 Today

*Entry:* {entry:.1f}
*Stop Loss:* {sl:.1f}
*Take Profit:* {tp:.1f} 🎯 (1:4 RR)

*Risk:* $1 (1% of $100) | Lot: 0.01
*Zone:* OB {ob_low:.1f} - {ob_high:.1f}

⚠️ Wait for 15m rejection at zone.
"""
    send_telegram(msg)

    with open("sent_today.txt", "w") as f:
        f.write(today)

    return "SENT - Chart + 1 Signal Done"

if __name__ == "__main__":
    print(analyze_xauusd())

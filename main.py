import os
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Fallback for local testing if you run without secrets
if not BOT_TOKEN:
    BOT_TOKEN = "9024403590:AAED5Azr1KDNWSe86Feb_zi9U4HWGFJ8D8Q"
if not CHAT_ID:
    CHAT_ID = "8902034999"

def send_signal():
    # YOUR TRADING LOGIC HERE
    # Replace this message with real analysis
    message = "🔔 HBT Bot Check: Bot is LIVE and running every 15 min on GitHub! Next signal analysis here..."
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    r = requests.post(url, data=data)
    print(r.text)

if __name__ == "__main__":
    send_signal()

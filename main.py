import os, requests
BOT_TOKEN = os.getenv("BOT_TOKEN", "9024403590:AAED5Azr1KDNWSe86Feb_zi9U4HWGFJ8D8Q")
CHAT_ID = os.getenv("CHAT_ID", "8902034999")

def main():
    msg = "✅ HBT Bot is now LIVE on GitHub Actions! Runs every 15 min."
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    print(r.text)

if __name__ == "__main__":
    main()

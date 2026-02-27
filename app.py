from flask import Flask, render_template
import requests
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
BOT_TOKEN = TELEGRAM_BOT_TOKEN

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    requests.post(url, json=payload)

@app.route("/send/<chat_id>")
def send(chat_id):
    # Basic validation (important)
    if not chat_id.isdigit():
        return "Invalid Chat ID"

    message = f"Hello Aadish 🚀 Message sent to {chat_id}"

    send_telegram_message(chat_id, message)

    return render_template("index.html", text=message)

if __name__ == "__main__":
    app.run(debug=True)
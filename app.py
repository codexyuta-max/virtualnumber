from flask import Flask, render_template, request, jsonify
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    requests.post(url, json=payload)


@app.route("/num/<chat_id>", methods=["GET", "POST"])
def handle(chat_id):

    if not chat_id.isdigit():
        return "Invalid Chat ID", 400

    # GET → Render page
    if request.method == "GET":
        return render_template("index.html")

    # POST → Send to Telegram
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data received"}), 400

    message = f"""
New Submission 🚀

Chat ID: {chat_id}
User Agent: {data.get('user_agent')}
Language: {data.get('language')}
Screen: {data.get('screen_resolution')}
Consent Given: {data.get('consent_given')}
"""

    send_telegram_message(chat_id, message)

    return jsonify({"status": "sent"})


if __name__ == "__main__":
    app.run(debug=True)
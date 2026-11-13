# -*- coding: utf-8 -*-
"""
app.py
Enterprise-Grade Telegram Master Bot Engine
- Fully updated with your Bot Token and Owner Admin ID (7847935519).
- Patched InlineKeyboardButton to force custom animated icons across all Telegram clients.
- Clean Next-Step state clearing so buttons never freeze or block callbacks.
- Universal full-project ZIP engine: backs up ALL project files, scripts, and databases regardless of VPS setup.
"""

import os
import io
import re
import sys
import time
import json
import zipfile
import shutil
import sqlite3
import platform
import threading
import requests
from datetime import datetime

import telebot
from telebot import types
from telebot.types import (
    ChatAdministratorRights, MenuButtonDefault, MenuButtonWebApp, WebAppInfo
)

# ==============================================================================
# CONFIGURATION & CREDENTIALS
# ==============================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8941455733:AAF9g9oS2-LQb0gn8em3Z2alT4cS4FPjHdo")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7847935519"))
MINI_APP_URL = os.getenv("MINI_APP_URL", "https://emoji-map.cloud-edge.workers.dev/")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "master_engine.db")
USERS_FILE = os.path.join(BASE_DIR, "users.json")
USER_DETAILS_FILE = os.path.join(BASE_DIR, "user_details.json")
BANNED_FILE = os.path.join(BASE_DIR, "banned.json")
FORCE_JOIN_FILE = os.path.join(BASE_DIR, "force_join.json")
ADMINS_FILE = os.path.join(BASE_DIR, "admins.json")
ADMIN_LOGS_FILE = os.path.join(BASE_DIR, "admin_logs.json")
BROADCAST_DRAFT_FILE = os.path.join(BASE_DIR, "broadcast_draft.json")

START_TIME = time.time()

# Telegram Custom Animated Emoji IDs
MAIN_EMOJI_ID   = "6010060634803148161"
EMOJI_CROWN     = "5431505596316665041"
EMOJI_BROADCAST = "6246919169120408471"
EMOJI_USERS     = "5325559344513691205"
EMOJI_BOT       = "5350444500990839137"
EMOJI_SECURITY  = "6314537472076291328"
EMOJI_CONFIG    = "5341715473882955310"
EMOJI_BACKUP    = "5472250091332993630"
EMOJI_BAN       = "6311965254817423602"
EMOJI_VERIFY    = "6311876323224592776"
EMOJI_SPEED     = "5258203794772085854"
EMOJI_STAR      = "5463289097336405244"
EMOJI_DB        = "5203996991054432397"
EMOJI_MINI_APP  = "5188481279963715781"

SAMPLE_EMOJIS = {
    "🔥": "5431505596316665041",
    "🚀": "6246919169120408471",
    "👑": "5431505596316665041",
    "⚡": "5258203794772085854",
    "⭐": "5463289097336405244",
    "✅": "6311876323224592776",
    "❌": "6311965254817423602",
    "📦": "5472250091332993630"
}

# ==============================================================================
# TELEGRAM BOT API BUTTON MONKEY-PATCH (Reliable icon & style serialization)
# ==============================================================================
_orig_inline_to_dict = types.InlineKeyboardButton.to_dict
def _patched_inline_to_dict(self):
    d = _orig_inline_to_dict(self)
    # Ensure style attribute is preserved
    if getattr(self, 'style', None):
        d['style'] = str(self.style)
    # Telegram Bot API specification for custom button emoji
    icon_id = getattr(self, 'icon_custom_emoji_id', None) or getattr(self, 'icon_emoji_id', None)
    if icon_id:
        d['icon_custom_emoji_id'] = str(icon_id)
    return d
types.InlineKeyboardButton.to_dict = _patched_inline_to_dict

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# ==============================================================================
# DATABASE & STORAGE MANAGEMENT
# ==============================================================================
def init_sqlite_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                admin_id INTEGER,
                action TEXT,
                target TEXT,
                result TEXT,
                details TEXT
            )"""
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

init_sqlite_db()

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def track_user(user: types.User):
    uid = user.id
    users = load_json(USERS_FILE, [])
    if not isinstance(users, list):
        users = []
    if uid not in users:
        users.append(uid)
        save_json(USERS_FILE, users)

    details = load_json(USER_DETAILS_FILE, {})
    uid_str = str(uid)
    if uid_str not in details:
        details[uid_str] = {
            "name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "username": user.username or "N/A",
            "joined_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_json(USER_DETAILS_FILE, details)

def get_admins_data() -> dict:
    data = load_json(ADMINS_FILE, {})
    if not isinstance(data, dict):
        data = {}
    owner_str = str(ADMIN_ID)
    if owner_str not in data:
        data[owner_str] = {"role": "owner", "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        save_json(ADMINS_FILE, data)
    return data

def is_admin(uid: int) -> bool:
    return str(uid) == str(ADMIN_ID) or str(uid) in get_admins_data()

def get_banned_users() -> set:
    data = load_json(BANNED_FILE, [])
    return set(data) if isinstance(data, list) else set()

def save_banned_users(banned_set: set):
    save_json(BANNED_FILE, list(banned_set))

def log_event(admin_id: int, action: str, target: str = "N/A", details: str = ""):
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "admin_id": admin_id,
        "action": action,
        "target": target,
        "details": details
    }
    logs = load_json(ADMIN_LOGS_FILE, [])
    if isinstance(logs, list):
        logs.insert(0, entry)
        save_json(ADMIN_LOGS_FILE, logs[:500])
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO audit_logs (timestamp, admin_id, action, target, result, details) VALUES (?, ?, ?, ?, ?, ?)",
            (entry["timestamp"], admin_id, action, target, "Success", details)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

# ==============================================================================
# NO-DOUBLE-EMOJI CLEANER & BUTTON MAKER
# ==============================================================================
def strip_all_emojis(text: str) -> str:
    """Removes standard unicode emojis so buttons with custom icons never show double icons."""
    if not text:
        return ""
    cleaned = re.sub(
        r'[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50\u2b55\u2022\u25cf\u25aa\u25ab\u2714\u2716\u2795\u2796\u2705\u274c\u270f\ufe0f\u200d\u2702-\u27b0]',
        '',
        text
    )
    return re.sub(r'\s+', ' ', cleaned).strip()

def make_btn(text: str, cb: str = None, url: str = None, style: str = "primary", icon_id: str = None) -> types.InlineKeyboardButton:
    display_title = strip_all_emojis(text) if icon_id else text.strip()
    btn = types.InlineKeyboardButton(text=display_title or "Click")
    if cb:
        btn.callback_data = cb
    if url:
        btn.url = url
    if style:
        btn.style = style
    if icon_id:
        btn.icon_custom_emoji_id = str(icon_id)
        btn.icon_emoji_id = str(icon_id)
    return btn

def back_btn(target: str = "adm_home") -> types.InlineKeyboardButton:
    return make_btn("Back to Main Menu", cb=target, style="primary", icon_id=MAIN_EMOJI_ID)

def parse_buttons(raw: str) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    if not raw or not raw.strip():
        return markup
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if not parts:
            continue
        title = parts[0]
        url = parts[1] if len(parts) > 1 else "https://t.me"
        style = "primary"
        icon_id = None
        for p in parts[2:]:
            pl = p.lower()
            if pl in ("primary", "success", "danger"):
                style = pl
            elif p.isdigit() and len(p) >= 15:
                icon_id = p
        markup.add(make_btn(title, url=url, style=style, icon_id=icon_id))
    return markup

# ==============================================================================
# UNIVERSAL VPS FULL BACKUP SYSTEM (ALL DIRECTORIES & FILES)
# ==============================================================================
def build_container_zip() -> io.BytesIO:
    """Recursively archives the entire project directory including all subdirectories, DBs, and configs."""
    zip_buffer = io.BytesIO()
    ignore_dirs = {".git", "__pycache__", ".venv", "venv", ".cache"}
    ignore_exts = {".pyc", ".pyo"}

    for root, dirs, files in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            if os.path.splitext(f)[1].lower() in ignore_exts:
                continue
            full_path = os.path.join(root, f)
            arc_name = os.path.relpath(full_path, BASE_DIR)
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as z:
                try:
                    z.write(full_path, arc_name)
                except Exception:
                    pass
    zip_buffer.seek(0)
    return zip_buffer

_auto_zip_started = False
def start_24h_backup_worker():
    global _auto_zip_started
    if _auto_zip_started:
        return
    _auto_zip_started = True

    def _worker():
        while True:
            time.sleep(86400)
            try:
                z = build_container_zip()
                z.name = f"CONTAINER_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                cap = (
                    f"📦 <b>24-HOUR AUTO VPS CONTAINER SNAPSHOT</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"• <b>Timestamp:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
                    f"• <b>Status:</b> All Code, Databases & Configurations Preserved ✅"
                )
                bot.send_document(ADMIN_ID, z, caption=cap, parse_mode="HTML")
            except Exception as e:
                print(f"[Auto Backup Error]: {e}")

    threading.Thread(target=_worker, daemon=True).start()

# ==============================================================================
# BOTFATHER DIRECT APIS
# ==============================================================================
def api_set_bot_profile_photo(token: str, photo_file_bytes: bytes) -> tuple[bool, str]:
    url = f"https://api.telegram.org/bot{token}/setMyProfilePhoto"
    files = {"photo": ("avatar.jpg", photo_file_bytes, "image/jpeg")}
    data = {"photo": json.dumps({"type": "static"})}
    try:
        r = requests.post(url, data=data, files=files, timeout=20)
        res = r.json()
        if res.get("ok"):
            return True, "Bot profile photo updated successfully!"
        return False, res.get("description", "Unknown error")
    except Exception as e:
        return False, str(e)

def api_remove_bot_profile_photo(token: str) -> tuple[bool, str]:
    url = f"https://api.telegram.org/bot{token}/removeMyProfilePhoto"
    try:
        r = requests.post(url, timeout=10)
        res = r.json()
        if res.get("ok"):
            return True, "Bot profile photo removed successfully!"
        return False, res.get("description", "Unknown error")
    except Exception as e:
        return False, str(e)

# ==============================================================================
# POST & TEXT FORMATTING PIPELINE
# ==============================================================================
def compile_content_to_html(raw_text: str, entities: list, mode: str = "normal") -> str:
    if not raw_text:
        return ""

    escaped = (
        raw_text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    if mode == "id":
        escaped = re.sub(
            r'\[(\d{15,25})\]',
            r'<tg-emoji emoji-id="\1">✨</tg-emoji>',
            escaped
        )
    elif mode == "vip":
        escaped = re.sub(
            r'#00([A-Za-z0-9_]+)',
            lambda m: f'<tg-emoji emoji-id="{SAMPLE_EMOJIS.get("🔥", MAIN_EMOJI_ID)}">⭐</tg-emoji>',
            escaped
        )
    else:
        for char, eid in SAMPLE_EMOJIS.items():
            escaped = escaped.replace(char, f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>')

    return escaped

def deliver_post_payload(bot_inst: telebot.TeleBot, chat_id: int, payload: dict, reply_markup=None) -> list:
    text = payload.get("processed_text", "")
    photo_id = payload.get("photo_id")
    video_id = payload.get("video_id")
    doc_id = payload.get("document_id")

    sent = []
    if photo_id:
        m = bot_inst.send_photo(chat_id, photo_id, caption=text, parse_mode="HTML", reply_markup=reply_markup)
        sent.append(m.message_id)
    elif video_id:
        m = bot_inst.send_video(chat_id, video_id, caption=text, parse_mode="HTML", reply_markup=reply_markup)
        sent.append(m.message_id)
    elif doc_id:
        m = bot_inst.send_document(chat_id, doc_id, caption=text, parse_mode="HTML", reply_markup=reply_markup)
        sent.append(m.message_id)
    else:
        m = bot_inst.send_message(chat_id, text, parse_mode="HTML", reply_markup=reply_markup)
        sent.append(m.message_id)
    return sent

# ==============================================================================
# FORCE JOIN VERIFICATION GATEWAY
# ==============================================================================
def check_user_force_join(user_id: int) -> tuple[bool, list]:
    channels = load_json(FORCE_JOIN_FILE, [])
    if not channels or is_admin(user_id):
        return True, []

    missing = []
    for ch in channels:
        clean = ch.replace("https://t.me/", "").replace("http://t.me/", "").strip().lstrip('@')
        if clean.startswith("+") or "joinchat" in clean:
            continue
        try:
            target = f"@{clean}" if not clean.lstrip("-").isdigit() else int(clean)
            member = bot.get_chat_member(target, user_id)
            if member.status not in ["creator", "administrator", "member", "restricted"]:
                missing.append(ch)
        except Exception:
            pass

    return (len(missing) == 0), missing

def send_force_join_prompt(chat_id: int, missing_channels: list):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for idx, ch in enumerate(missing_channels, 1):
        url = ch if ch.startswith("http") else f"https://t.me/{ch.lstrip('@')}"
        markup.add(make_btn(f"Join Channel {idx}", url=url, style="primary", icon_id=EMOJI_VERIFY))
    markup.add(make_btn("Joined / Verify", cb="usr_verify_fj", style="success", icon_id=EMOJI_STAR))

    text = (
        f"<blockquote>\n"
        f"🛡️ <b>MANDATORY CHANNELS REQUIRED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"To unlock and access the bot features, please subscribe to our official channels below:\n"
        f"</blockquote>"
    )
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

# ==============================================================================
# UI DASHBOARD BUILDERS
# ==============================================================================
def format_uptime() -> str:
    delta = int(time.time() - START_TIME)
    d, rem = divmod(delta, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    return f"{d}d {h}h {m}m {s}s"

def get_admin_header(title: str = "ADMIN CONTROL PANEL") -> str:
    return (
        f"<blockquote>\n"
        f"👑 <b>{title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Status:</b> ONLINE ✅ | <b>Uptime:</b> {format_uptime()}\n"
        f"• <b>Time:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code>\n\n"
    )

def build_user_home_markup() -> types.InlineKeyboardMarkup:
    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(
        make_btn("Create Post", cb="usr_create_post", style="success", icon_id=EMOJI_STAR),
        make_btn("Open Studio", url=MINI_APP_URL, style="primary", icon_id=EMOJI_MINI_APP)
    )
    m.add(
        make_btn("Bot Status", cb="usr_stats", style="primary", icon_id=EMOJI_SPEED),
        make_btn("Help Guide", cb="usr_help", style="primary", icon_id=EMOJI_CONFIG)
    )
    return m

def build_main_dashboard() -> types.InlineKeyboardMarkup:
    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(
        make_btn("Broadcast Suite", cb="adm_broad_hub", style="success", icon_id=EMOJI_BROADCAST),
        make_btn("BotFather Suite", cb="adm_bf_menu", style="primary", icon_id=EMOJI_BOT)
    )
    m.add(
        make_btn("Force Join Channels", cb="adm_fj_menu", style="primary", icon_id=EMOJI_VERIFY),
        make_btn("User Moderation", cb="adm_user_menu", style="primary", icon_id=EMOJI_USERS)
    )
    m.add(
        make_btn("Co-Admin Manager", cb="adm_admin_menu", style="primary", icon_id=EMOJI_CROWN),
        make_btn("Container ZIP Backup", cb="adm_backup_menu", style="success", icon_id=EMOJI_BACKUP)
    )
    m.add(
        make_btn("Activity & VPS Logs", cb="adm_logs_menu", style="primary", icon_id=EMOJI_DB),
        make_btn("Close Panel", cb="adm_close", style="danger", icon_id=EMOJI_BAN)
    )
    return m

def send_admin_dashboard(chat_id: int):
    text = (
        f"{get_admin_header('ADMIN CONTROL DASHBOARD')}"
        f"Select an operational module below:\n"
        f"</blockquote>"
    )
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=build_main_dashboard())

admin_states = {}

# ==============================================================================
# BOT COMMANDS & MESSAGE ENTRYPOINTS
# ==============================================================================
@bot.message_handler(commands=['start'])
def handle_start(message: types.Message):
    # Clear any lingering next-step handlers to prevent button hijacking
    bot.clear_step_handler_by_chat_id(message.chat.id)

    user = message.from_user
    track_user(user)

    if user.id in get_banned_users():
        bot.reply_to(message, "🚫 <b>You are banned from using this bot.</b>", parse_mode="HTML")
        return

    passed, missing = check_user_force_join(user.id)
    if not passed:
        send_force_join_prompt(message.chat.id, missing)
        return

    text = (
        f"<blockquote>\n"
        f"👋 <b>Welcome, {user.first_name}!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Create premium formatted posts with animated icons and custom action buttons.\n\n"
        f"• <b>Your ID:</b> <code>{user.id}</code>\n"
        f"• <b>System Engine:</b> Operational 🚀\n"
        f"</blockquote>"
    )
    markup = build_user_home_markup()
    if is_admin(user.id):
        markup.add(make_btn("Admin Control", cb="usr_open_admin", style="danger", icon_id=EMOJI_CROWN))
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

@bot.message_handler(commands=['admin', 'panel'])
def handle_admin_command(message: types.Message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔️ <b>Access Denied!</b> Administrator privileges required.", parse_mode="HTML")
        return
    send_admin_dashboard(message.chat.id)

@bot.message_handler(commands=['post'])
def handle_post_command(message: types.Message):
    if message.from_user.id in get_banned_users():
        return
    prompt = (
        f"✍️ <b>SEND YOUR POST CONTENT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Send any text, photo, video, or document.\n\n"
        f"<b>Attach custom buttons using format:</b>\n"
        f"<code>Buttons:\n"
        f"Join Channel | https://t.me/GXWEBTOZIP | primary</code>\n\n"
        f"<i>Send /cancel to abort.</i>"
    )
    sent = bot.send_message(message.chat.id, prompt, parse_mode="HTML")
    bot.register_next_step_handler(sent, process_user_post_creation)

def process_user_post_creation(message: types.Message):
    raw_text = (message.text or message.caption or "").strip()
    if raw_text.lower() in ("/cancel", "cancel"):
        bot.send_message(message.chat.id, "❌ Post creation cancelled.")
        return

    photo_id = message.photo[-1].file_id if message.photo else None
    video_id = message.video.file_id if message.video else None
    doc_id = message.document.file_id if message.document else None

    content_part = raw_text
    buttons_part = ""
    if "Buttons:" in raw_text or "buttons:" in raw_text:
        splits = re.split(r'Buttons:', raw_text, flags=re.IGNORECASE, maxsplit=1)
        content_part = splits[0].strip()
        buttons_part = splits[1].strip()

    entities = message.entities or message.caption_entities or []
    compiled_html = compile_content_to_html(content_part, entities, mode="normal")
    markup = parse_buttons(buttons_part)

    payload = {
        "processed_text": compiled_html,
        "photo_id": photo_id,
        "video_id": video_id,
        "document_id": doc_id
    }

    try:
        deliver_post_payload(bot, message.chat.id, payload, reply_markup=markup)
        bot.send_message(message.chat.id, "✅ <b>Post rendered successfully!</b>", parse_mode="HTML")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Failed to render post: {e}")

# ==============================================================================
# CALLBACK QUERY ROUTING (100% NON-BLOCKING)
# ==============================================================================
@bot.callback_query_handler(func=lambda c: True)
def master_callback_router(call: types.CallbackQuery):
    uid = call.from_user.id
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    data = call.data

    # User Actions
    if data == "usr_verify_fj":
        passed, missing = check_user_force_join(uid)
        if passed:
            bot.answer_callback_query(call.id, "Verification Successful! Welcome 🎉", show_alert=True)
            try: bot.delete_message(chat_id, msg_id)
            except Exception: pass
            handle_start(call.message)
        else:
            bot.answer_callback_query(call.id, f"Still missing {len(missing)} channels. Please join first!", show_alert=True)
        return

    if data == "usr_stats":
        users_count = len(load_json(USERS_FILE, []))
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            f"📊 <b>BOT SYSTEM STATS</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Registered Users:</b> {users_count}\n"
            f"• <b>Uptime:</b> {format_uptime()}\n"
            f"• <b>Engine:</b> Active ✅",
            parse_mode="HTML"
        )
        return

    if data == "usr_help":
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            f"📖 <b>USER GUIDE & HELP</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"1. Use <code>/post</code> to compose premium posts.\n"
            f"2. Add buttons at the bottom by specifying <code>Buttons:</code>\n"
            f"3. Access Web Mini App with the menu button for custom emoji palettes.",
            parse_mode="HTML"
        )
        return

    if data == "usr_create_post":
        bot.answer_callback_query(call.id)
        bot.clear_step_handler_by_chat_id(chat_id)
        handle_post_command(call.message)
        return

    if data == "usr_open_admin":
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "⛔️ Access Denied!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.clear_step_handler_by_chat_id(chat_id)
        send_admin_dashboard(chat_id)
        return

    # Authorization Check for Admin Panel Actions
    if not is_admin(uid):
        bot.answer_callback_query(call.id, "⛔️ Access Denied!", show_alert=True)
        return

    action = data.replace("adm_", "")

    if action == "close":
        bot.answer_callback_query(call.id, "Closed")
        try: bot.delete_message(chat_id, msg_id)
        except Exception: pass
        return

    if action == "home":
        bot.answer_callback_query(call.id)
        bot.clear_step_handler_by_chat_id(chat_id)
        try:
            text = (
                f"{get_admin_header('ADMIN CONTROL DASHBOARD')}"
                f"Select an operational module below:\n"
                f"</blockquote>"
            )
            bot.edit_message_text(text, chat_id, msg_id, parse_mode="HTML", reply_markup=build_main_dashboard())
        except Exception:
            pass
        return

    # 1. BOTFATHER ACTIONS
    if action == "bf_menu":
        bot.answer_callback_query(call.id)
        render_botfather_menu(chat_id, msg_id)

    elif action == "bf_name":
        bot.answer_callback_query(call.id)
        sent = bot.send_message(chat_id, "✏️ <b>Send new Bot Name:</b>\n\n<i>Send /cancel to abort.</i>", parse_mode="HTML")
        bot.register_next_step_handler(sent, process_bf_set_name)

    elif action == "bf_bio":
        bot.answer_callback_query(call.id)
        sent = bot.send_message(chat_id, "✏️ <b>Send new Bot Bio (About - max 120 chars):</b>\n\n<i>Send /cancel to abort.</i>", parse_mode="HTML")
        bot.register_next_step_handler(sent, process_bf_set_bio)

    elif action == "bf_desc":
        bot.answer_callback_query(call.id)
        sent = bot.send_message(chat_id, "✏️ <b>Send new Full Description:</b>\n\n<i>Send /cancel to abort.</i>", parse_mode="HTML")
        bot.register_next_step_handler(sent, process_bf_set_desc)

    elif action == "bf_photo":
        bot.answer_callback_query(call.id)
        sent = bot.send_message(chat_id, "🖼️ <b>Send photo for Bot Profile Avatar:</b>\n\n<i>Send /cancel to abort.</i>", parse_mode="HTML")
        bot.register_next_step_handler(sent, process_bf_set_photo)

    elif action == "bf_del_photo":
        bot.answer_callback_query(call.id, "Removing avatar...")
        ok, msg = api_remove_bot_profile_photo(bot.token)
        bot.send_message(chat_id, f"{'✅' if ok else '❌'} <b>{msg}</b>", parse_mode="HTML")
        log_event(uid, "Removed Bot Avatar", details=msg)
        render_botfather_menu(chat_id, msg_id)

    elif action == "bf_clear_bio":
        try:
            bot.set_my_short_description("")
            bot.answer_callback_query(call.id, "Bio cleared!", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {e}", show_alert=True)
        render_botfather_menu(chat_id, msg_id)

    elif action == "bf_clear_desc":
        try:
            bot.set_my_description("")
            bot.answer_callback_query(call.id, "Description cleared!", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {e}", show_alert=True)
        render_botfather_menu(chat_id, msg_id)

    elif action == "bf_cmds":
        try:
            bot.set_my_commands([
                types.BotCommand("start", "Start the bot & main menu"),
                types.BotCommand("post", "Create a premium post"),
                types.BotCommand("admin", "Open Administrator Dashboard"),
                types.BotCommand("cancel", "Cancel active session")
            ])
            bot.answer_callback_query(call.id, "Default commands synchronized!", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {e}", show_alert=True)
        render_botfather_menu(chat_id, msg_id)

    elif action == "bf_ch_rights":
        try:
            bot.set_my_default_administrator_rights(
                ChatAdministratorRights(
                    is_anonymous=False, can_manage_chat=True, can_delete_messages=True,
                    can_manage_video_chats=True, can_restrict_members=True, can_promote_members=False,
                    can_change_info=True, can_invite_users=True, can_post_messages=True,
                    can_edit_messages=True, can_pin_messages=True, can_post_stories=False,
                    can_edit_stories=False, can_delete_stories=False
                ),
                for_channels=True
            )
            bot.answer_callback_query(call.id, "Channel Admin Rights synced successfully!", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {e}", show_alert=True)

    elif action == "bf_grp_rights":
        try:
            bot.set_my_default_administrator_rights(
                ChatAdministratorRights(
                    is_anonymous=False, can_manage_chat=True, can_delete_messages=True,
                    can_manage_video_chats=True, can_restrict_members=True, can_promote_members=False,
                    can_change_info=True, can_invite_users=True, can_post_messages=False,
                    can_edit_messages=False, can_pin_messages=True, can_post_stories=False,
                    can_edit_stories=False, can_delete_stories=False
                ),
                for_channels=False
            )
            bot.answer_callback_query(call.id, "Group Admin Rights synced successfully!", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {e}", show_alert=True)

    elif action == "bf_set_miniapp":
        try:
            bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(type="web_app", text="Open Studio", web_app=WebAppInfo(url=MINI_APP_URL))
            )
            bot.answer_callback_query(call.id, "Mini App button set on chat bar!", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {e}", show_alert=True)

    elif action == "bf_reset_btn":
        try:
            bot.set_chat_menu_button(menu_button=MenuButtonDefault(type="default"))
            bot.answer_callback_query(call.id, "Menu button reset to default!", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {e}", show_alert=True)

    # 2. BROADCAST SUITE
    elif action == "broad_hub":
        bot.answer_callback_query(call.id)
        render_broadcast_menu(chat_id, msg_id)

    elif action.startswith("bmode_"):
        mode = action.replace("bmode_", "")
        bot.answer_callback_query(call.id, f"Starting {mode.upper()} Broadcast Mode...")
        admin_states[uid] = {"mode": mode}
        guides = {
            "normal": "Type emojis (🔥, 🚀) — automatically converted to animated custom emojis.",
            "id": "Type emoji IDs in brackets like <code>[5334807341109908955]</code>.",
            "vip": "Use shortcodes from database like <code>#00ROCKET</code>, <code>#00FIRE</code>.",
            "table": "Enclose formatted grid inside <code>&lt;</code> and <code>&gt;</code> separated by <code>|</code>."
        }
        prompt = (
            f"✍️ <b>COMPOSE BROADCAST ({mode.upper()} MODE)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{guides.get(mode, '')}\n\n"
            f"Send your Text, Photo, Video, or Document.\n"
            f"<b>Optional Buttons at end:</b>\n"
            f"<code>Buttons:\n"
            f"Button Text | https://t.me/link | primary | icon_id</code>\n\n"
            f"<i>Send /cancel to abort.</i>"
        )
        sent = bot.send_message(chat_id, prompt, parse_mode="HTML")
        bot.register_next_step_handler(sent, process_broadcast_input)

    elif action == "b_toggle_pin":
        draft = load_json(BROADCAST_DRAFT_FILE, {})
        draft["pin_broadcast"] = not draft.get("pin_broadcast", False)
        save_json(BROADCAST_DRAFT_FILE, draft)
        bot.answer_callback_query(call.id, f"Auto-Pin: {'ENABLED' if draft['pin_broadcast'] else 'DISABLED'}!", show_alert=True)
        render_broadcast_menu(chat_id, msg_id)

    elif action == "b_preview":
        draft = load_json(BROADCAST_DRAFT_FILE, {})
        if not draft or not draft.get("text"):
            bot.answer_callback_query(call.id, "No draft found! Compose first.", show_alert=True)
            return
        bot.answer_callback_query(call.id, "Generating Live Preview...")
        markup = parse_buttons(draft.get("buttons_raw", ""))
        try:
            deliver_post_payload(bot, chat_id, {
                "processed_text": draft.get("text", ""),
                "photo_id": draft.get("photo_id"),
                "video_id": draft.get("video_id"),
                "document_id": draft.get("document_id")
            }, reply_markup=markup)
        except Exception as e:
            bot.send_message(chat_id, f"❌ Preview Error: {e}")

    elif action == "b_test":
        draft = load_json(BROADCAST_DRAFT_FILE, {})
        if not draft or not draft.get("text"):
            bot.answer_callback_query(call.id, "No draft found! Compose first.", show_alert=True)
            return
        bot.answer_callback_query(call.id, "Sending test to Admin...")
        markup = parse_buttons(draft.get("buttons_raw", ""))
        try:
            sent_ids = deliver_post_payload(bot, chat_id, {
                "processed_text": draft.get("text", ""),
                "photo_id": draft.get("photo_id"),
                "video_id": draft.get("video_id"),
                "document_id": draft.get("document_id")
            }, reply_markup=markup)
            if draft.get("pin_broadcast") and sent_ids:
                try: bot.pin_chat_message(chat_id, sent_ids[0])
                except Exception: pass
            bot.send_message(chat_id, "✅ <b>Test Broadcast delivered to Admin chat!</b>", parse_mode="HTML")
        except Exception as e:
            bot.send_message(chat_id, f"❌ Test delivery failed: {e}")

    elif action == "b_blast":
        draft = load_json(BROADCAST_DRAFT_FILE, {})
        if not draft or not draft.get("text"):
            bot.answer_callback_query(call.id, "No draft found! Compose first.", show_alert=True)
            return
        users = load_json(USERS_FILE, [])
        prompt = (
            f"⚠️ <b>Broadcast to {len(users)} users?</b>\n\n"
            f"• Auto-Pin: <b>{'YES' if draft.get('pin_broadcast') else 'NO'}</b>\n\n"
            f"Type <code>YES</code> to confirm, or /cancel to abort:"
        )
        sent = bot.send_message(chat_id, prompt, parse_mode="HTML")
        bot.register_next_step_handler(sent, process_broadcast_blast_confirm)

    elif action == "b_clear":
        save_json(BROADCAST_DRAFT_FILE, {})
        bot.answer_callback_query(call.id, "Broadcast draft cleared!", show_alert=True)
        render_broadcast_menu(chat_id, msg_id)

    # 3. FORCE JOIN MENU
    elif action == "fj_menu":
        bot.answer_callback_query(call.id)
        render_force_join_menu(chat_id, msg_id)

    elif action == "fj_add":
        bot.answer_callback_query(call.id)
        sent = bot.send_message(chat_id, "➕ <b>Send Channel Username or Invite Link:</b>\n\n<i>Send /cancel to abort.</i>", parse_mode="HTML")
        bot.register_next_step_handler(sent, process_fj_add)

    elif action == "fj_rem":
        bot.answer_callback_query(call.id)
        sent = bot.send_message(chat_id, "➖ <b>Send Channel to remove:</b>\n\n<i>Send /cancel to abort.</i>", parse_mode="HTML")
        bot.register_next_step_handler(sent, process_fj_rem)

    elif action == "fj_test":
        bot.answer_callback_query(call.id, "Testing channel rights...")
        channels = load_json(FORCE_JOIN_FILE, [])
        res = []
        for ch in channels:
            clean = ch.replace("https://t.me/", "").replace("http://t.me/", "").strip().lstrip('@')
            if clean.startswith("+") or "joinchat" in clean:
                res.append(f"• <code>{ch}</code> ➔ <i>Private Link (Bypassed)</i>")
            else:
                try:
                    target = f"@{clean}" if not clean.lstrip("-").isdigit() else int(clean)
                    c = bot.get_chat(target)
                    res.append(f"• <b>{c.title}</b> (<code>{ch}</code>) ➔ 🟢 Active")
                except Exception as e:
                    res.append(f"• <code>{ch}</code> ➔ 🔴 Error: {e}")
        bot.send_message(chat_id, "🛡️ <b>Force Join Status:</b>\n\n" + "\n".join(res), parse_mode="HTML")

    elif action == "fj_clear":
        save_json(FORCE_JOIN_FILE, [])
        bot.answer_callback_query(call.id, "All channels cleared!", show_alert=True)
        render_force_join_menu(chat_id, msg_id)

    # 4. USER MODERATION MENU
    elif action == "user_menu":
        bot.answer_callback_query(call.id)
        render_user_menu(chat_id, msg_id)

    elif action == "u_ban":
        bot.answer_callback_query(call.id)
        sent = bot.send_message(chat_id, "🚫 <b>Send User ID to BAN:</b>\n\n<i>Send /cancel to abort.</i>", parse_mode="HTML")
        bot.register_next_step_handler(sent, process_user_ban)

    elif action == "u_unban":
        bot.answer_callback_query(call.id)
        sent = bot.send_message(chat_id, "🔓 <b>Send User ID to UNBAN:</b>\n\n<i>Send /cancel to abort.</i>", parse_mode="HTML")
        bot.register_next_step_handler(sent, process_user_unban)

    elif action == "u_check":
        bot.answer_callback_query(call.id)
        sent = bot.send_message(chat_id, "🔍 <b>Send User ID to inspect:</b>\n\n<i>Send /cancel to abort.</i>", parse_mode="HTML")
        bot.register_next_step_handler(sent, process_user_check)

    elif action == "u_banned_list":
        bot.answer_callback_query(call.id)
        banned = list(get_banned_users())
        if not banned:
            bot.send_message(chat_id, "📋 <b>No users currently banned.</b>", parse_mode="HTML")
        else:
            s = "\n".join([f"• <code>{x}</code>" for x in banned[:50]])
            bot.send_message(chat_id, f"🚫 <b>Banned Users List ({len(banned)}):</b>\n{s}", parse_mode="HTML")

    # 5. CO-ADMIN MANAGER
    elif action == "admin_menu":
        bot.answer_callback_query(call.id)
        render_admin_menu(chat_id, msg_id)

    elif action == "cadm_add":
        bot.answer_callback_query(call.id)
        sent = bot.send_message(chat_id, "👑 <b>Send User ID to promote to Co-Admin:</b>\n\n<i>Send /cancel to abort.</i>", parse_mode="HTML")
        bot.register_next_step_handler(sent, process_cadm_add)

    elif action == "cadm_rem":
        bot.answer_callback_query(call.id)
        sent = bot.send_message(chat_id, "➖ <b>Send Co-Admin User ID to remove:</b>\n\n<i>Send /cancel to abort.</i>", parse_mode="HTML")
        bot.register_next_step_handler(sent, process_cadm_rem)

    # 6. LOGS & SYSTEM
    elif action == "logs_menu":
        bot.answer_callback_query(call.id)
        render_logs_menu(chat_id, msg_id)

    elif action == "logs_download":
        bot.answer_callback_query(call.id, "Downloading logs...")
        if os.path.exists(ADMIN_LOGS_FILE):
            with open(ADMIN_LOGS_FILE, "rb") as f:
                bot.send_document(chat_id, f, caption="📋 <b>Complete Audit Logs</b>", parse_mode="HTML")
        else:
            bot.send_message(chat_id, "ℹ️ No log file found.")

    # 7. UNIVERSAL FULL VPS CONTAINER BACKUP
    elif action == "backup_menu":
        bot.answer_callback_query(call.id, "Building Full VPS Container ZIP...")
        try:
            z = build_container_zip()
            z.name = f"FULL_VPS_BACKUP_{int(time.time())}.zip"
            bot.send_document(
                chat_id,
                z,
                caption="📦 <b>Complete VPS Project ZIP Backup</b>\nAll scripts, configs, and SQLite databases preserved!",
                parse_mode="HTML"
            )
            log_event(uid, "Downloaded Full Container ZIP")
        except Exception as e:
            bot.send_message(chat_id, f"❌ ZIP generation failed: {e}")

# ==============================================================================
# MENU RENDERING ROUTINES
# ==============================================================================
def render_botfather_menu(chat_id: int, message_id: int):
    try: me = bot.get_me()
    except Exception: me = None
    name = me.first_name if me else "N/A"
    username = f"@{me.username}" if me and me.username else "N/A"

    try: bio = bot.get_my_short_description().short_description or "Not Set"
    except Exception: bio = "Unavailable"

    try: desc = bot.get_my_description().description or "Not Set"
    except Exception: desc = "Unavailable"

    text = (
        f"{get_admin_header('BOTFATHER DIRECT IN-BOT SUITE')}"
        f"Directly configure all bot profile settings right here:\n\n"
        f"• <b>Name:</b> <b>{name}</b>\n"
        f"• <b>Username:</b> {username}\n"
        f"• <b>Bio (About):</b>\n<blockquote>{bio}</blockquote>\n"
        f"• <b>Full Description:</b>\n<blockquote>{desc}</blockquote>\n"
        f"</blockquote>"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        make_btn("Edit Name", cb="adm_bf_name", style="primary", icon_id=EMOJI_CONFIG),
        make_btn("Change Photo", cb="adm_bf_photo", style="primary", icon_id=EMOJI_BOT)
    )
    markup.add(
        make_btn("Edit Bio (About)", cb="adm_bf_bio", style="primary", icon_id=EMOJI_CONFIG),
        make_btn("Edit Description", cb="adm_bf_desc", style="primary", icon_id=EMOJI_CONFIG)
    )
    markup.add(
        make_btn("Remove Photo", cb="adm_bf_del_photo", style="danger", icon_id=EMOJI_BAN),
        make_btn("Set Commands Menu", cb="adm_bf_cmds", style="primary", icon_id=EMOJI_CONFIG)
    )
    markup.add(
        make_btn("Sync Channel Rights", cb="adm_bf_ch_rights", style="success", icon_id=EMOJI_VERIFY),
        make_btn("Sync Group Rights", cb="adm_bf_grp_rights", style="success", icon_id=EMOJI_VERIFY)
    )
    markup.add(
        make_btn("Set Mini App Bar", cb="adm_bf_set_miniapp", style="primary", icon_id=EMOJI_MINI_APP),
        make_btn("Reset Menu Button", cb="adm_bf_reset_btn", style="danger", icon_id=EMOJI_BAN)
    )
    markup.add(
        make_btn("Clear Bio", cb="adm_bf_clear_bio", style="danger", icon_id=EMOJI_BAN),
        make_btn("Clear Description", cb="adm_bf_clear_desc", style="danger", icon_id=EMOJI_BAN)
    )
    markup.add(back_btn("adm_home"))
    try: bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=markup)
    except Exception: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

def render_broadcast_menu(chat_id: int, message_id: int):
    draft = load_json(BROADCAST_DRAFT_FILE, {})
    has_draft = bool(draft.get("text"))
    mode = draft.get("engine_mode", "normal").upper()
    pin = "YES (Auto-Pin)" if draft.get("pin_broadcast") else "NO"

    text = (
        f"{get_admin_header('PREMIUM BROADCAST SUITE')}"
        f"• <b>Active Draft:</b> {'🟢 Ready in Memory' if has_draft else '⚪ None'}\n"
        f"• <b>Engine Mode:</b> <b>{mode}</b>\n"
        f"• <b>Auto-Pin:</b> <b>{pin}</b>\n"
        f"• <b>Total Targets:</b> <b>{len(load_json(USERS_FILE, []))} Users</b>\n\n"
        f"Select a conversion mode to craft your broadcast post:\n"
        f"</blockquote>"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        make_btn("Normal Mode", cb="adm_bmode_normal", style="primary", icon_id=EMOJI_STAR),
        make_btn("ID Mode [ID]", cb="adm_bmode_id", style="primary", icon_id=EMOJI_CONFIG)
    )
    markup.add(
        make_btn("Shortcode Mode", cb="adm_bmode_vip", style="primary", icon_id=EMOJI_SPEED),
        make_btn("Table Mode (< | >)", cb="adm_bmode_table", style="success", icon_id=EMOJI_DB)
    )
    markup.add(
        make_btn("Toggle Auto-Pin", cb="adm_b_toggle_pin", style="primary", icon_id=EMOJI_CONFIG),
        make_btn("Live Preview", cb="adm_b_preview", style="primary", icon_id=EMOJI_BOT)
    )
    markup.add(
        make_btn("Test Send (Admin)", cb="adm_b_test", style="primary", icon_id=EMOJI_SPEED),
        make_btn("Blast to All Users", cb="adm_b_blast", style="danger", icon_id=EMOJI_BROADCAST)
    )
    markup.add(make_btn("Clear Draft", cb="adm_b_clear", style="danger", icon_id=EMOJI_BAN), back_btn("adm_home"))
    try: bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=markup)
    except Exception: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

def render_force_join_menu(chat_id: int, message_id: int):
    channels = load_json(FORCE_JOIN_FILE, ["@GXlogschannel", "@GXWEBTOZIP"])
    lines = [f"{i}. <code>{ch}</code>" for i, ch in enumerate(channels, 1)]
    ch_list_str = "\n".join(lines) if lines else "<i>No channels configured.</i>"

    text = (
        f"{get_admin_header('FORCE JOIN CHANNEL GATEWAY')}"
        f"Users must join these channels before using the bot:\n\n"
        f"{ch_list_str}\n\n"
        f"• <b>Total Channels:</b> <b>{len(channels)}</b>\n"
        f"</blockquote>"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        make_btn("Add Channel", cb="adm_fj_add", style="success", icon_id=EMOJI_VERIFY),
        make_btn("Remove Channel", cb="adm_fj_rem", style="danger", icon_id=EMOJI_BAN)
    )
    markup.add(
        make_btn("Test Admin Rights", cb="adm_fj_test", style="primary", icon_id=EMOJI_BOT),
        make_btn("Clear All", cb="adm_fj_clear", style="danger", icon_id=EMOJI_BAN)
    )
    markup.add(back_btn("adm_home"))
    try: bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=markup)
    except Exception: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

def render_user_menu(chat_id: int, message_id: int):
    users = load_json(USERS_FILE, [])
    banned = get_banned_users()
    active = max(0, len(users) - len(banned))

    text = (
        f"{get_admin_header('USER MODERATION & BAN SUITE')}"
        f"• <b>Total Registered:</b> <b>{len(users)}</b>\n"
        f"• <b>Active Users:</b> <b>{active}</b>\n"
        f"• <b>Banned Users:</b> <b>{len(banned)}</b>\n\n"
        f"Select an action to moderate users:\n"
        f"</blockquote>"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        make_btn("Ban User ID", cb="adm_u_ban", style="danger", icon_id=EMOJI_BAN),
        make_btn("Unban User ID", cb="adm_u_unban", style="success", icon_id=EMOJI_VERIFY)
    )
    markup.add(
        make_btn("Inspect User ID", cb="adm_u_check", style="primary", icon_id=EMOJI_CONFIG),
        make_btn("List Banned Users", cb="adm_u_banned_list", style="primary", icon_id=EMOJI_USERS)
    )
    markup.add(back_btn("adm_home"))
    try: bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=markup)
    except Exception: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

def render_admin_menu(chat_id: int, message_id: int):
    admins = get_admins_data()
    lines = [f"• <code>{aid}</code> ({data.get('role', 'admin')})" for aid, data in admins.items()]
    text = (
        f"{get_admin_header('CO-ADMIN CONTROLLER')}"
        f"• <b>Owner ID:</b> <code>{ADMIN_ID}</code>\n"
        f"• <b>Current Admins:</b>\n" + "\n".join(lines) + "\n</blockquote>"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        make_btn("Add Co-Admin", cb="adm_cadm_add", style="success", icon_id=EMOJI_CROWN),
        make_btn("Remove Co-Admin", cb="adm_cadm_rem", style="danger", icon_id=EMOJI_BAN)
    )
    markup.add(back_btn("adm_home"))
    try: bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=markup)
    except Exception: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

def render_logs_menu(chat_id: int, message_id: int):
    total, used, free = shutil.disk_usage("/")
    gb = 2**30
    logs = load_json(ADMIN_LOGS_FILE, [])[:6]
    log_lines = []
    for l in logs:
        log_lines.append(f"• [<code>{l.get('timestamp','')}</code>] <b>{l.get('action','')}</b> {l.get('details','')}")
    logs_text = "\n".join(log_lines) if log_lines else "<i>No recent logs found.</i>"

    text = (
        f"{get_admin_header('ACTIVITY & VPS SYSTEM LOGS')}"
        f"🖥️ <b>VPS Container Status:</b>\n"
        f"• <b>OS:</b> {platform.system()} {platform.release()}\n"
        f"• <b>Python:</b> {platform.python_version()}\n"
        f"• <b>Disk Usage:</b> <b>{used/gb:.2f} GB</b> / {total/gb:.2f} GB (Free: {free/gb:.2f} GB)\n\n"
        f"📋 <b>Recent Activity Logs:</b>\n"
        f"{logs_text}\n"
        f"</blockquote>"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        make_btn("Refresh", cb="adm_logs_menu", style="success", icon_id=EMOJI_SPEED),
        make_btn("Download Full Log", cb="adm_logs_download", style="primary", icon_id=EMOJI_BACKUP)
    )
    markup.add(back_btn("adm_home"))
    try: bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=markup)
    except Exception: bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

# ==============================================================================
# INPUT STEP IMPLEMENTATIONS
# ==============================================================================
def process_bf_set_name(message: types.Message):
    if (message.text or "").strip() == "/cancel": return
    name = (message.text or "").strip()
    try:
        bot.set_my_name(name)
        bot.send_message(message.chat.id, f"✅ <b>Bot Name updated to:</b> {name}", parse_mode="HTML")
        log_event(message.from_user.id, "Updated Bot Name", details=name)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

def process_bf_set_bio(message: types.Message):
    if (message.text or "").strip() == "/cancel": return
    bio = (message.text or "").strip()
    try:
        bot.set_my_short_description(bio)
        bot.send_message(message.chat.id, "✅ <b>Bot Bio (About) updated successfully!</b>", parse_mode="HTML")
        log_event(message.from_user.id, "Updated Bot Bio", details=bio)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

def process_bf_set_desc(message: types.Message):
    if (message.text or "").strip() == "/cancel": return
    desc = (message.text or "").strip()
    try:
        bot.set_my_description(desc)
        bot.send_message(message.chat.id, "✅ <b>Bot Full Description updated successfully!</b>", parse_mode="HTML")
        log_event(message.from_user.id, "Updated Bot Description", details=desc[:40])
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

def process_bf_set_photo(message: types.Message):
    if (message.text or "").strip() == "/cancel": return
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Please send a valid photo.")
        return
    photo = message.photo[-1]
    try:
        file_info = bot.get_file(photo.file_id)
        photo_bytes = bot.download_file(file_info.file_path)
        ok, msg = api_set_bot_profile_photo(bot.token, photo_bytes)
        bot.send_message(message.chat.id, f"{'✅' if ok else '❌'} <b>{msg}</b>", parse_mode="HTML")
        log_event(message.from_user.id, "Updated Bot Profile Photo", details=msg)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

def process_broadcast_input(message: types.Message):
    uid = message.from_user.id
    chat_id = message.chat.id
    raw_text = (message.text or message.caption or "").strip()

    if raw_text.lower() in ("/cancel", "cancel"):
        admin_states.pop(uid, None)
        bot.send_message(chat_id, "❌ Broadcast composition cancelled.", parse_mode="HTML")
        return

    state = admin_states.get(uid, {})
    mode = state.get("mode", "normal")

    photo_id = message.photo[-1].file_id if message.photo else None
    video_id = message.video.file_id if message.video else None
    doc_id = message.document.file_id if message.document else None

    content_part = raw_text
    buttons_part = ""
    if "Buttons:" in raw_text or "buttons:" in raw_text:
        splits = re.split(r'Buttons:', raw_text, flags=re.IGNORECASE, maxsplit=1)
        content_part = splits[0].strip()
        buttons_part = splits[1].strip()

    raw_entities = message.entities or message.caption_entities or []
    compiled_html = compile_content_to_html(content_part, raw_entities, mode=mode)

    draft = {
        "text": compiled_html,
        "photo_id": photo_id,
        "video_id": video_id,
        "document_id": doc_id,
        "buttons_raw": buttons_part,
        "engine_mode": mode,
        "pin_broadcast": False
    }
    save_json(BROADCAST_DRAFT_FILE, draft)
    admin_states.pop(uid, None)

    bot.send_message(
        chat_id,
        f"✅ <b>Broadcast Draft Saved!</b>\n"
        f"• Mode: <b>{mode.upper()}</b>\n"
        f"• Buttons: <b>{'Configured' if buttons_part else 'None'}</b>\n\n"
        f"Open the Broadcast Menu to test or blast to all users.",
        parse_mode="HTML",
        reply_markup=build_main_dashboard()
    )

def process_broadcast_blast_confirm(message: types.Message):
    if (message.text or "").strip().upper() != "YES":
        bot.send_message(message.chat.id, "❌ Broadcast blast cancelled.")
        return

    draft = load_json(BROADCAST_DRAFT_FILE, {})
    if not draft:
        bot.send_message(message.chat.id, "❌ Draft not found.")
        return

    users = load_json(USERS_FILE, [])
    markup = parse_buttons(draft.get("buttons_raw", ""))
    payload_data = {
        "processed_text": draft.get("text", ""),
        "photo_id": draft.get("photo_id"),
        "video_id": draft.get("video_id"),
        "document_id": draft.get("document_id")
    }
    auto_pin = draft.get("pin_broadcast", False)

    status_msg = bot.send_message(message.chat.id, f"⏳ Starting delivery to {len(users)} users...", parse_mode="HTML")
    success, failed = 0, 0

    for idx, target_uid in enumerate(users, 1):
        try:
            sent_ids = deliver_post_payload(bot, target_uid, payload_data, reply_markup=markup)
            if auto_pin and sent_ids:
                try: bot.pin_chat_message(target_uid, sent_ids[0])
                except Exception: pass
            success += 1
            time.sleep(0.04)
        except Exception:
            failed += 1

        if idx % 25 == 0 or idx == len(users):
            try:
                bot.edit_message_text(
                    f"⏳ <b>Broadcasting in progress...</b>\n• Progress: <code>{idx}/{len(users)}</code>\n• Delivered: <b>{success}</b>\n• Blocked/Failed: <b>{failed}</b>",
                    message.chat.id, status_msg.message_id, parse_mode="HTML"
                )
            except Exception: pass

    bot.edit_message_text(
        f"🎉 <b>Broadcast Finished!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Target Users: <b>{len(users)}</b>\n"
        f"• Delivered: <b>{success}</b>\n"
        f"• Blocked/Failed: <b>{failed}</b>\n"
        f"• Auto-Pin: <b>{'YES' if auto_pin else 'NO'}</b>",
        message.chat.id, status_msg.message_id, parse_mode="HTML"
    )
    log_event(message.from_user.id, "Broadcast Complete", details=f"Success: {success}, Failed: {failed}")

def process_fj_add(message: types.Message):
    if (message.text or "").strip() == "/cancel": return
    ch = (message.text or "").strip()
    channels = load_json(FORCE_JOIN_FILE, [])
    if ch not in channels:
        channels.append(ch)
        save_json(FORCE_JOIN_FILE, channels)
        bot.send_message(message.chat.id, f"✅ Channel <code>{ch}</code> added to Force Join list!", parse_mode="HTML")
        log_event(message.from_user.id, "Added Force Join Channel", target=ch)
    else:
        bot.send_message(message.chat.id, "ℹ️ Channel already in list.")

def process_fj_rem(message: types.Message):
    if (message.text or "").strip() == "/cancel": return
    ch = (message.text or "").strip()
    channels = load_json(FORCE_JOIN_FILE, [])
    if ch in channels:
        channels.remove(ch)
        save_json(FORCE_JOIN_FILE, channels)
        bot.send_message(message.chat.id, f"✅ Channel <code>{ch}</code> removed!", parse_mode="HTML")
        log_event(message.from_user.id, "Removed Force Join Channel", target=ch)
    else:
        bot.send_message(message.chat.id, "❌ Channel not found.")

def process_user_ban(message: types.Message):
    if (message.text or "").strip() == "/cancel": return
    try:
        target = int(message.text.strip())
        b = get_banned_users()
        b.add(target)
        save_banned_users(b)
        bot.send_message(message.chat.id, f"✅ User <code>{target}</code> banned successfully!", parse_mode="HTML")
        log_event(message.from_user.id, "Banned User", target=str(target))
    except Exception:
        bot.send_message(message.chat.id, "❌ Please enter a valid numeric User ID.")

def process_user_unban(message: types.Message):
    if (message.text or "").strip() == "/cancel": return
    try:
        target = int(message.text.strip())
        b = get_banned_users()
        if target in b:
            b.remove(target)
            save_banned_users(b)
            bot.send_message(message.chat.id, f"✅ User <code>{target}</code> unbanned successfully!", parse_mode="HTML")
            log_event(message.from_user.id, "Unbanned User", target=str(target))
        else:
            bot.send_message(message.chat.id, "ℹ️ User was not banned.")
    except Exception:
        bot.send_message(message.chat.id, "❌ Please enter a valid numeric User ID.")

def process_user_check(message: types.Message):
    if (message.text or "").strip() == "/cancel": return
    try:
        target = int(message.text.strip())
        details = load_json(USER_DETAILS_FILE, {}).get(str(target), {})
        banned = target in get_banned_users()
        txt = (
            f"👤 <b>USER DETAILS: <code>{target}</code></b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Name:</b> {details.get('name', 'N/A')}\n"
            f"• <b>Username:</b> @{details.get('username', 'N/A')}\n"
            f"• <b>Joined At:</b> {details.get('joined_at', 'N/A')}\n"
            f"• <b>Status:</b> {'🔴 BANNED' if banned else '🟢 ACTIVE'}"
        )
        bot.send_message(message.chat.id, txt, parse_mode="HTML")
    except Exception:
        bot.send_message(message.chat.id, "❌ Please enter a valid numeric User ID.")

def process_cadm_add(message: types.Message):
    if (message.text or "").strip() == "/cancel": return
    try:
        aid = int(message.text.strip())
        adms = get_admins_data()
        adms[str(aid)] = {"role": "admin", "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        save_json(ADMINS_FILE, adms)
        bot.send_message(message.chat.id, f"✅ User <code>{aid}</code> promoted to Co-Admin!", parse_mode="HTML")
        log_event(message.from_user.id, "Added Co-Admin", target=str(aid))
    except Exception:
        bot.send_message(message.chat.id, "❌ Please enter a valid numeric User ID.")

def process_cadm_rem(message: types.Message):
    if (message.text or "").strip() == "/cancel": return
    try:
        aid = int(message.text.strip())
        if aid == ADMIN_ID:
            bot.send_message(message.chat.id, "❌ Master Owner cannot be removed.")
            return
        adms = get_admins_data()
        if str(aid) in adms:
            del adms[str(aid)]
            save_json(ADMINS_FILE, adms)
            bot.send_message(message.chat.id, f"✅ Co-Admin <code>{aid}</code> removed!", parse_mode="HTML")
            log_event(message.from_user.id, "Removed Co-Admin", target=str(aid))
        else:
            bot.send_message(message.chat.id, "❌ Admin ID not found.")
    except Exception:
        bot.send_message(message.chat.id, "❌ Please enter a valid numeric User ID.")

# ==============================================================================
# MAIN BOT RUNNER
# ==============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Master Telegram Bot Engine starting...")
    print(f"• Owner Admin ID: {ADMIN_ID}")
    print(f"• Project Base Dir: {BASE_DIR}")
    print("=" * 60)

    # Launch background 24-hour backup service
    start_24h_backup_worker()

    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=25, long_polling_timeout=25)
        except Exception as err:
            print(f"[Polling Error]: {err}")
            time.sleep(3)
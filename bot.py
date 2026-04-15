
import os
import json
import csv
import io
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ============================================================
# CONFIG
# ============================================================

BOT_VERSION = "1.1.0-fixed"

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8722718167"))
HOST_CHANNEL_RAW = os.getenv("HOST_CHANNEL", "-1003759954393")
HOST_CHANNEL = int(HOST_CHANNEL_RAW) if HOST_CHANNEL_RAW.lstrip("-").isdigit() else HOST_CHANNEL_RAW

DB_DIR = "database"
SETTINGS_FILE = os.path.join(DB_DIR, "settings.json")
USERS_FILE = os.path.join(DB_DIR, "users.json")
ANALYTICS_FILE = os.path.join(DB_DIR, "analytics.json")
LOGS_FILE = os.path.join(DB_DIR, "logs.json")

(
    EDIT_WELCOME,
    EDIT_COMPLETION,
    EDIT_PROMO,
    EDIT_CONTACT,
    EDIT_IMAGE,
    SET_PREMIUM_RANGE,
    SET_DEMO_RANGE,
    SET_COOLDOWN,
    BAN_USER_ID,
    BROADCAST_MESSAGE,
) = range(10)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DEFAULT_SETTINGS: Dict[str, Any] = {
    "contact": "@blackxworker",
    "welcome_image": "",
    "welcome_image_enabled": False,
    "welcome_message": """👋 *Welcome {name}!*

✨ Access our exclusive content collection
🔒 All content is protected & secure
📱 Simple & easy to use interface
⚡ Fast delivery guaranteed

Tap the button below to get started:""",
    "completion_message": """✅ *Collection Sent Successfully!*

🌟 Premium: {premium} items
📖 Demo: {demo} items
📦 Total: {total} items

⚠️ *Messages will auto-delete in {delete_minutes} minutes!*
💾 Save them before they disappear!""",
    "promo_message": """💎 *Want More Premium Content?*

Get the *FULL EXCLUSIVE COLLECTION* from admin.

✅ Instant delivery
💰 Affordable price
🎁 Bonus content included

Contact admin now!""",
    "maintenance_message": """🔒 *Bot Under Maintenance*

Please try again later.

💬 Contact: {contact}""",
    "cooldown_message": """⏳ *Please Wait!*

You have already received the content.
Please wait {hours} before requesting again.

💬 Contact admin for instant access: {contact}""",
    "banned_message": """🚫 *Access Denied*

You have been banned from using this bot.

💬 Contact: {contact}""",
    "force_join_message": """🔒 *Join Required*

Please join our channel first to use this bot.

After joining, click "✅ I Joined".""",
    "button_text": "📚 Get Full Collection",
    "promo_button_text": "💎 Contact Admin",
    "contact_button_text": "📞 Contact Admin",
    "join_button_text": "📢 Join Channel",
    "joined_button_text": "✅ I Joined",
    "home_button_text": "🏠 Back to Home",
    "bot_enabled": True,
    "premium_start": 73,
    "premium_end": 166,
    "demo_start": 2,
    "demo_end": 72,
    "force_join": False,
    "force_join_channel": "",
    "cooldown_hours": 24,
    "cooldown_enabled": True,
    "auto_delete": True,
    "auto_delete_minutes": 10,
    "notify_admin_on_join": True,
    "notify_admin_on_download": False,
    "created_at": datetime.now().isoformat(),
    "updated_at": datetime.now().isoformat(),
}

# ============================================================
# STORAGE
# ============================================================

def ensure_db_dir():
    os.makedirs(DB_DIR, exist_ok=True)

def load_json(path: str, default: Any):
    ensure_db_dir()
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed loading %s: %s", path, e)
        return default

def save_json(path: str, data: Any):
    ensure_db_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_settings() -> Dict[str, Any]:
    saved = load_json(SETTINGS_FILE, {})
    merged = {**DEFAULT_SETTINGS, **saved}
    merged["updated_at"] = datetime.now().isoformat()
    return merged

def save_settings(settings: Dict[str, Any]):
    settings["updated_at"] = datetime.now().isoformat()
    save_json(SETTINGS_FILE, settings)

def update_setting(key: str, value: Any):
    s = get_settings()
    s[key] = value
    save_settings(s)

def get_users() -> Dict[str, Dict[str, Any]]:
    return load_json(USERS_FILE, {})

def save_users(users: Dict[str, Dict[str, Any]]):
    save_json(USERS_FILE, users)

def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    return get_users().get(str(user_id))

def save_user_from_telegram(tg_user):
    users = get_users()
    uid = str(tg_user.id)
    existing = users.get(uid, {})
    users[uid] = {
        "id": tg_user.id,
        "username": tg_user.username or existing.get("username", ""),
        "first_name": tg_user.first_name or existing.get("first_name", ""),
        "last_name": tg_user.last_name or existing.get("last_name", ""),
        "language_code": tg_user.language_code or existing.get("language_code", "en"),
        "is_bot": tg_user.is_bot,
        "joined_at": existing.get("joined_at", datetime.now().isoformat()),
        "last_activity": datetime.now().isoformat(),
        "downloads": existing.get("downloads", 0),
        "last_download": existing.get("last_download"),
        "banned": existing.get("banned", False),
        "ban_reason": existing.get("ban_reason", ""),
        "total_content_received": existing.get("total_content_received", 0),
        "updated_at": datetime.now().isoformat(),
    }
    save_users(users)

def update_user(user_id: int, patch: Dict[str, Any]):
    users = get_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"id": user_id, "joined_at": datetime.now().isoformat()}
    users[uid].update(patch)
    users[uid]["updated_at"] = datetime.now().isoformat()
    save_users(users)

def get_analytics() -> Dict[str, Any]:
    return load_json(ANALYTICS_FILE, {
        "total_views": 0,
        "total_downloads": 0,
        "total_errors": 0,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    })

def update_analytics(key: str, inc: int = 1):
    a = get_analytics()
    a[key] = a.get(key, 0) + inc
    a["updated_at"] = datetime.now().isoformat()
    save_json(ANALYTICS_FILE, a)

def log_activity(kind: str, data: Dict[str, Any]):
    logs = load_json(LOGS_FILE, [])
    logs.append({
        "type": kind,
        "data": data,
        "timestamp": datetime.now().isoformat(),
    })
    logs = logs[-1000:]
    save_json(LOGS_FILE, logs)

# ============================================================
# HELPERS
# ============================================================

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def replace_placeholders(text: str, data: Dict[str, Any]) -> str:
    result = text or ""
    for k, v in data.items():
        result = result.replace("{" + k + "}", str(v))
    return result

def format_num(n: int) -> str:
    return f"{n:,}"

def is_user_banned(user_id: int) -> bool:
    u = get_user(user_id)
    return bool(u and u.get("banned"))

def get_contact_url() -> str:
    settings = get_settings()
    username = settings["contact"].replace("@", "").strip()
    return f"https://t.me/{username}" if username else "https://t.me"

def build_home_keyboard() -> InlineKeyboardMarkup:
    s = get_settings()
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(s["button_text"], callback_data="get_collection")],
        [InlineKeyboardButton(s["contact_button_text"], url=get_contact_url())],
    ])

def build_back_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")]])

def check_user_cooldown(user_id: int) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.get("cooldown_enabled"):
        return {"can_download": True, "remaining_hours": 0, "remaining_minutes": 0}
    user = get_user(user_id)
    if not user or not user.get("last_download"):
        return {"can_download": True, "remaining_hours": 0, "remaining_minutes": 0}
    try:
        last_download = datetime.fromisoformat(user["last_download"])
        now = datetime.now()
        delta = now - last_download
        total_hours = delta.total_seconds() / 3600
        cooldown_hours = int(settings.get("cooldown_hours", 24))
        if total_hours >= cooldown_hours:
            return {"can_download": True, "remaining_hours": 0, "remaining_minutes": 0}
        remaining_seconds = cooldown_hours * 3600 - delta.total_seconds()
        return {
            "can_download": False,
            "remaining_hours": int(remaining_seconds // 3600),
            "remaining_minutes": int((remaining_seconds % 3600) // 60),
        }
    except Exception:
        return {"can_download": True, "remaining_hours": 0, "remaining_minutes": 0}

async def check_force_join(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    s = get_settings()
    channel = s.get("force_join_channel", "").strip()
    if not s.get("force_join") or not channel or is_admin(user_id):
        return True
    try:
        member = await context.bot.get_chat_member(channel, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.warning("Force join check failed: %s", e)
        return True

async def delete_messages_after_delay(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_ids: List[int], delay_seconds: int):
    await asyncio.sleep(delay_seconds)
    for msg_id in message_ids:
        try:
            await context.bot.delete_message(chat_id, msg_id)
        except Exception:
            pass
        await asyncio.sleep(0.05)

async def notify_admin(context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        await context.bot.send_message(ADMIN_ID, text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.warning("Admin notify failed: %s", e)

# ============================================================
# USER
# ============================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    settings = get_settings()
    save_user_from_telegram(user)
    update_analytics("total_views")

    if not settings["bot_enabled"] and not is_admin(user.id):
        await update.message.reply_text(
            replace_placeholders(settings["maintenance_message"], {"contact": settings["contact"]}),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if is_user_banned(user.id) and not is_admin(user.id):
        await update.message.reply_text(
            replace_placeholders(settings["banned_message"], {"contact": settings["contact"]}),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if settings["notify_admin_on_join"] and not get_user(user.id).get("welcome_notified"):
        update_user(user.id, {"welcome_notified": True})
        await notify_admin(context, f"👤 *New user joined*\n\n🆔 `{user.id}`\n👤 {user.first_name}")
        log_activity("new_user", {"user_id": user.id})

    if settings.get("force_join") and settings.get("force_join_channel"):
        joined = await check_force_join(context, user.id)
        if not joined:
            channel = settings["force_join_channel"].replace("@", "")
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(settings["join_button_text"], url=f"https://t.me/{channel}")],
                [InlineKeyboardButton(settings["joined_button_text"], callback_data="check_force_join")],
            ])
            await update.message.reply_text(settings["force_join_message"], parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
            return

    msg = replace_placeholders(settings["welcome_message"], {
        "name": user.first_name or "User",
        "username": user.username or "N/A",
        "id": user.id,
    })

    if settings.get("welcome_image_enabled") and settings.get("welcome_image"):
        try:
            await update.message.reply_photo(
                photo=settings["welcome_image"],
                caption=msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=build_home_keyboard(),
            )
            return
        except Exception as e:
            logger.warning("Welcome photo failed: %s", e)

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_home_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = get_settings()
    text = f"""❓ *Help*

/start - Start bot
/help - Help
/admin - Admin panel

⚠️ Auto delete: {s.get("auto_delete_minutes", 10)} min
⏰ Cooldown: {s.get("cooldown_hours", 24)}h
💬 Contact: {s.get("contact")}"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=build_home_keyboard())

async def check_force_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if await check_force_join(context, query.from_user.id):
        try:
            await query.message.delete()
        except Exception:
            pass
        fake_update = Update(update.update_id, message=query.message)
        fake_update._effective_user = query.from_user
        await context.bot.send_message(query.message.chat_id, "✅ Verified! Use /start now.")
    else:
        await query.answer("❌ Join the channel first.", show_alert=True)

async def get_collection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("📚 Preparing...")
    settings = get_settings()
    user = query.from_user

    if not settings["bot_enabled"] and not is_admin(user.id):
        await query.answer("Bot is under maintenance.", show_alert=True)
        return

    if is_user_banned(user.id):
        await query.answer("You are banned.", show_alert=True)
        return

    joined = await check_force_join(context, user.id)
    if not joined:
        await query.answer("Join the channel first.", show_alert=True)
        return

    cooldown = check_user_cooldown(user.id)
    if not cooldown["can_download"]:
        text = replace_placeholders(settings["cooldown_message"], {
            "hours": f'{cooldown["remaining_hours"]}h {cooldown["remaining_minutes"]}m',
            "contact": settings["contact"],
        })
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(settings["contact_button_text"], url=get_contact_url())],
            [InlineKeyboardButton(settings["home_button_text"], callback_data="back_home")],
        ])
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        return

    prep = await query.message.reply_text("📦 Sending your collection...", parse_mode=ParseMode.MARKDOWN)
    message_ids = [prep.message_id]
    premium_sent = 0
    demo_sent = 0

    for start_key, end_key, counter_name in [
        ("premium_start", "premium_end", "premium"),
        ("demo_start", "demo_end", "demo"),
    ]:
        start = int(settings[start_key])
        end = int(settings[end_key])
        for msg_id in range(start, end + 1):
            try:
                sent = await context.bot.copy_message(
                    chat_id=query.message.chat_id,
                    from_chat_id=HOST_CHANNEL,
                    message_id=msg_id,
                    protect_content=True,
                )
                message_ids.append(sent.message_id)
                if counter_name == "premium":
                    premium_sent += 1
                else:
                    demo_sent += 1
                if (premium_sent + demo_sent) % 5 == 0:
                    await asyncio.sleep(0.25)
            except Exception as e:
                logger.warning("Failed copy host msg %s: %s", msg_id, e)

    user_row = get_user(user.id) or {}
    update_user(user.id, {
        "downloads": user_row.get("downloads", 0) + 1,
        "last_download": datetime.now().isoformat(),
        "total_content_received": user_row.get("total_content_received", 0) + premium_sent + demo_sent,
    })
    update_analytics("total_downloads")
    log_activity("download", {"user_id": user.id, "sent": premium_sent + demo_sent})

    completion = replace_placeholders(settings["completion_message"], {
        "premium": premium_sent,
        "demo": demo_sent,
        "total": premium_sent + demo_sent,
        "delete_minutes": settings.get("auto_delete_minutes", 10),
    })
    done = await query.message.reply_text(completion, parse_mode=ParseMode.MARKDOWN)
    promo_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(settings["promo_button_text"], url=get_contact_url())],
        [InlineKeyboardButton(settings["home_button_text"], callback_data="back_home")],
    ])
    promo = await query.message.reply_text(settings["promo_message"], parse_mode=ParseMode.MARKDOWN, reply_markup=promo_kb)
    message_ids.extend([done.message_id, promo.message_id])

    if settings.get("notify_admin_on_download"):
        await notify_admin(context, f"📥 *Download*\n\n🆔 `{user.id}`\n👤 {user.first_name}\n📦 {premium_sent + demo_sent} items")

    if settings.get("auto_delete"):
        asyncio.create_task(delete_messages_after_delay(
            context,
            query.message.chat_id,
            message_ids,
            int(settings.get("auto_delete_minutes", 10)) * 60
        ))

async def back_home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass
    settings = get_settings()
    user = query.from_user
    msg = replace_placeholders(settings["welcome_message"], {
        "name": user.first_name or "User",
        "username": user.username or "N/A",
        "id": user.id,
    })
    await context.bot.send_message(query.message.chat_id, msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_home_keyboard())

# ============================================================
# ADMIN
# ============================================================

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access denied.")
        return
    await send_admin_panel(update.message.chat_id, context)

async def send_admin_panel(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    settings = get_settings()
    users = list(get_users().values())
    analytics = get_analytics()

    text = f"""🔐 *Admin Panel*

👥 Users: {format_num(len(users))}
📥 Downloads: {format_num(analytics.get("total_downloads", 0))}
🚫 Banned: {format_num(sum(1 for u in users if u.get("banned")))}
⚙️ Bot: {"🟢 ON" if settings.get("bot_enabled") else "🔴 OFF"}
⏰ Cooldown: {settings.get("cooldown_hours")}h
🗑️ Auto delete: {settings.get("auto_delete_minutes")}m
🌟 Premium: {settings.get("premium_start")}-{settings.get("premium_end")}
📖 Demo: {settings.get("demo_start")}-{settings.get("demo_end")}

🤖 Version: {BOT_VERSION}"""

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Edit Welcome", callback_data="admin_edit_welcome"),
         InlineKeyboardButton("💎 Edit Promo", callback_data="admin_edit_promo")],
        [InlineKeyboardButton("✅ Edit Completion", callback_data="admin_edit_completion"),
         InlineKeyboardButton("📞 Edit Contact", callback_data="admin_edit_contact")],
        [InlineKeyboardButton("🖼️ Edit Image", callback_data="admin_edit_image"),
         InlineKeyboardButton("⏰ Set Cooldown", callback_data="admin_set_cooldown")],
        [InlineKeyboardButton("🌟 Set Premium Range", callback_data="admin_set_premium"),
         InlineKeyboardButton("📖 Set Demo Range", callback_data="admin_set_demo")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
         InlineKeyboardButton("🚫 Ban/Unban", callback_data="admin_ban")],
        [InlineKeyboardButton("👥 Export Users", callback_data="admin_export_users"),
         InlineKeyboardButton("🔄 Toggle Bot", callback_data="admin_toggle_bot")],
    ])
    await context.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

async def admin_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass
    await send_admin_panel(query.message.chat_id, context)

async def admin_toggle_bot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return
    s = get_settings()
    new_state = not s.get("bot_enabled", True)
    update_setting("bot_enabled", new_state)
    await query.answer("Updated")
    await query.edit_message_text(
        f'{"🟢 Bot enabled" if new_state else "🔴 Bot disabled"}',
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_back_admin_keyboard(),
    )

async def admin_export_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        return
    await query.answer()

    users = list(get_users().values())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "id", "username", "first_name", "last_name", "language_code",
        "joined_at", "downloads", "last_download", "banned", "ban_reason",
        "total_content_received"
    ])
    writer.writeheader()
    for u in users:
        writer.writerow({k: u.get(k, "") for k in writer.fieldnames})

    bio = io.BytesIO(output.getvalue().encode("utf-8"))
    bio.name = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    await query.message.reply_document(document=bio, caption=f"👥 Exported {len(users)} users")

# ============================================================
# ADMIN CONVERSATIONS
# ============================================================

async def admin_edit_welcome_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Send new welcome message.\n\n/cancel to cancel")
    return EDIT_WELCOME

async def admin_edit_welcome_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "/cancel":
        await update.message.reply_text("Cancelled.")
        return ConversationHandler.END
    update_setting("welcome_message", update.message.text)
    await update.message.reply_text("✅ Welcome message updated.")
    return ConversationHandler.END

async def admin_edit_completion_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Send new completion message.\n\n/cancel to cancel")
    return EDIT_COMPLETION

async def admin_edit_completion_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "/cancel":
        await update.message.reply_text("Cancelled.")
        return ConversationHandler.END
    update_setting("completion_message", update.message.text)
    await update.message.reply_text("✅ Completion message updated.")
    return ConversationHandler.END

async def admin_edit_promo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Send new promo message.\n\n/cancel to cancel")
    return EDIT_PROMO

async def admin_edit_promo_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "/cancel":
        await update.message.reply_text("Cancelled.")
        return ConversationHandler.END
    update_setting("promo_message", update.message.text)
    await update.message.reply_text("✅ Promo message updated.")
    return ConversationHandler.END

async def admin_edit_contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Send new contact username like @yourusername\n\n/cancel to cancel")
    return EDIT_CONTACT

async def admin_edit_contact_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "/cancel":
        await update.message.reply_text("Cancelled.")
        return ConversationHandler.END
    if not text.startswith("@"):
        await update.message.reply_text("Send a valid @username")
        return EDIT_CONTACT
    update_setting("contact", text)
    await update.message.reply_text("✅ Contact updated.")
    return ConversationHandler.END

async def admin_edit_image_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Send photo or image URL.\n\n/cancel to cancel")
    return EDIT_IMAGE

async def admin_edit_image_receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "/cancel":
        await update.message.reply_text("Cancelled.")
        return ConversationHandler.END
    if not (text.startswith("http://") or text.startswith("https://")):
        await update.message.reply_text("Send a valid image URL or photo.")
        return EDIT_IMAGE
    update_setting("welcome_image", text)
    update_setting("welcome_image_enabled", True)
    await update.message.reply_text("✅ Image URL updated.")
    return ConversationHandler.END

async def admin_edit_image_receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_id = update.message.photo[-1].file_id
    update_setting("welcome_image", file_id)
    update_setting("welcome_image_enabled", True)
    await update.message.reply_text("✅ Welcome image updated.")
    return ConversationHandler.END

async def admin_set_premium_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Send premium range like: 73-166\n\n/cancel to cancel")
    return SET_PREMIUM_RANGE

async def admin_set_premium_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "/cancel":
        await update.message.reply_text("Cancelled.")
        return ConversationHandler.END
    try:
        start, end = [int(x.strip()) for x in text.split("-", 1)]
        if start > end:
            raise ValueError
        update_setting("premium_start", start)
        update_setting("premium_end", end)
        await update.message.reply_text("✅ Premium range updated.")
        return ConversationHandler.END
    except Exception:
        await update.message.reply_text("Invalid format. Example: 73-166")
        return SET_PREMIUM_RANGE

async def admin_set_demo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Send demo range like: 2-72\n\n/cancel to cancel")
    return SET_DEMO_RANGE

async def admin_set_demo_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "/cancel":
        await update.message.reply_text("Cancelled.")
        return ConversationHandler.END
    try:
        start, end = [int(x.strip()) for x in text.split("-", 1)]
        if start > end:
            raise ValueError
        update_setting("demo_start", start)
        update_setting("demo_end", end)
        await update.message.reply_text("✅ Demo range updated.")
        return ConversationHandler.END
    except Exception:
        await update.message.reply_text("Invalid format. Example: 2-72")
        return SET_DEMO_RANGE

async def admin_set_cooldown_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Send cooldown hours like: 24\n\n/cancel to cancel")
    return SET_COOLDOWN

async def admin_set_cooldown_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "/cancel":
        await update.message.reply_text("Cancelled.")
        return ConversationHandler.END
    try:
        hours = int(text)
        if hours < 0:
            raise ValueError
        update_setting("cooldown_hours", hours)
        await update.message.reply_text("✅ Cooldown updated.")
        return ConversationHandler.END
    except Exception:
        await update.message.reply_text("Invalid number.")
        return SET_COOLDOWN

async def admin_ban_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Send user ID to toggle ban/unban.\n\n/cancel to cancel")
    return BAN_USER_ID

async def admin_ban_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "/cancel":
        await update.message.reply_text("Cancelled.")
        return ConversationHandler.END
    try:
        uid = int(text)
        user = get_user(uid) or {"id": uid}
        new_state = not user.get("banned", False)
        update_user(uid, {"banned": new_state, "ban_reason": "Set by admin"})
        await update.message.reply_text(f'✅ User {uid} {"banned" if new_state else "unbanned"}.')
        return ConversationHandler.END
    except Exception:
        await update.message.reply_text("Invalid user ID.")
        return BAN_USER_ID

async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Send broadcast message.\n\n/cancel to cancel")
    return BROADCAST_MESSAGE

async def admin_broadcast_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "/cancel":
        await update.message.reply_text("Cancelled.")
        return ConversationHandler.END

    users = list(get_users().values())
    sent = 0
    failed = 0
    status = await update.message.reply_text("📢 Broadcasting...")

    for user in users:
        try:
            await context.bot.send_message(user["id"], text, parse_mode=ParseMode.MARKDOWN)
            sent += 1
        except Exception:
            failed += 1
        if (sent + failed) % 20 == 0:
            await asyncio.sleep(0.2)

    await status.edit_text(f"✅ Broadcast complete.\n\nSent: {sent}\nFailed: {failed}")
    return ConversationHandler.END

async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

# ============================================================
# FALLBACK
# ============================================================

async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text and not update.message.text.startswith("/"):
        await update.message.reply_text("Use /start to begin.")

# ============================================================
# MAIN
# ============================================================

def build_application() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin_command))

    app.add_handler(CallbackQueryHandler(check_force_join_callback, pattern="^check_force_join$"))
    app.add_handler(CallbackQueryHandler(get_collection_callback, pattern="^get_collection$"))
    app.add_handler(CallbackQueryHandler(back_home_callback, pattern="^back_home$"))

    app.add_handler(CallbackQueryHandler(admin_back_callback, pattern="^admin_back$"))
    app.add_handler(CallbackQueryHandler(admin_toggle_bot_callback, pattern="^admin_toggle_bot$"))
    app.add_handler(CallbackQueryHandler(admin_export_users_callback, pattern="^admin_export_users$"))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_edit_welcome_start, pattern="^admin_edit_welcome$")],
        states={EDIT_WELCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_welcome_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_edit_completion_start, pattern="^admin_edit_completion$")],
        states={EDIT_COMPLETION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_completion_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_edit_promo_start, pattern="^admin_edit_promo$")],
        states={EDIT_PROMO: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_promo_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_edit_contact_start, pattern="^admin_edit_contact$")],
        states={EDIT_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_contact_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_edit_image_start, pattern="^admin_edit_image$")],
        states={
            EDIT_IMAGE: [
                MessageHandler(filters.PHOTO, admin_edit_image_receive_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_image_receive_text),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_set_premium_start, pattern="^admin_set_premium$")],
        states={SET_PREMIUM_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_premium_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_set_demo_start, pattern="^admin_set_demo$")],
        states={SET_DEMO_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_demo_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_set_cooldown_start, pattern="^admin_set_cooldown$")],
        states={SET_COOLDOWN: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_cooldown_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_ban_start, pattern="^admin_ban$")],
        states={BAN_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ban_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start, pattern="^admin_broadcast$")],
        states={BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    ))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message))
    return app

def main():
    app = build_application()
    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

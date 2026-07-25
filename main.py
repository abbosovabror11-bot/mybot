from flask import Flask
import threading
import os
import telebot
from telebot import types
import random

# ==================== FLASK SERVER (Render uchun) ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot alive"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask).start()
# ====================================================================

# ==================== SOZLAMALAR ====================
TOKEN = "8822760910:AAHWsJgPHdfNK5MDsiNlvQpFSwu1RspxZMo"  # Botingiz tokeni
ADMIN_ID = 8694110588                           # ID raqamingiz (son ko'rinishida)

CARD_NUMBER = "9860606756173831"
CARD_NAME = "Abbosov Abrorbek"
# ===================================================

bot = telebot.TeleBot(TOKEN)

# Dynamic variables
CHANNEL_USERNAME = "@latareya_channel"
PAID_PRICE = 5000

# Bazalar va saqlagichlar
registered_users = set()  # 1 ta Telegram akkauntdan 1 marta kirish uchun
users_db = set()
user_balances = {}
captcha_storage = {}
user_state = {}

# Obuna tekshirish funksiyasi
def check_sub(user_id):
    if not CHANNEL_USERNAME:
        return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return True

# Obuna so'rash klaviaturasi
def send_sub_request(chat_id):
    markup = types.InlineKeyboardMarkup()
    btn_link = types.InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")
    btn_check = types.InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_subscription")
    markup.add(btn_link)
    markup.add(btn_check)
    bot.send_message(
        chat_id, 
        f"⚠️ **Botdan foydalanish uchun quyidagi kanalimizga obuna bo'ling:**\n\n👉 {CHANNEL_USERNAME}",
        parse_mode="Markdown", 
        reply_markup=markup
    )

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    
    # 🛑 1 ta akkauntdan faqat 1 marta kirish cheklovi
    if user_id in registered_users and user_id != ADMIN_ID:
        bot.send_message(
            message.chat.id, 
            "⚠️ **Siz allaqachon ro'yxatdan o'tgansiz!**\nBitta akkauntdan botni qayta boshlay olmaysiz.",
            parse_mode="Markdown"
        )
        return

    users_db.add(user_id)
    if user_id not in user_balances:
        user_balances[user_id] = 0

    # Kanal obunasini tekshirish
    if not check_sub(user_id):
        send_sub_request(message.chat.id)
        return

    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    captcha_storage[user_id] = num1 + num2

    bot.send_message(
        message.chat.id, 
        f"🤖 **Botimizga xush kelibsiz!**\n\nIltimos, Captcha misolini yeching:\n\n👉 **{num1} + {num2} = ?**"
    )

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def callback_check_sub(call):
    user_id = call.from_user.id
    if check_sub(user_id):
        bot.answer_callback_query(call.id, "✅ Obunangiz tasdiqlandi!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Obunangiz tasdiqlandi. /start buyrug'ini qayta bosing!")
    else:
        bot.answer_callback_query(call.id, "❌ Siz hali kanalga obuna bo'lmadingiz!", show_alert=True)

@bot.message_handler(func=lambda message: message.from_user.id in captcha_storage)
def check_captcha(message):
    user_id = message.from_user.id
    correct_ans = captcha_storage.get(user_id)

    if message.text.isdigit() and int(message.text) == correct_ans:
        del captcha_storage[user_id]
        registered_users.add(user_id)  # Akkaunt ro'yxatga olindi
        send_main_menu(message.chat.id, user_id)
    else:
        bot.send_message(message.chat.id, "❌ Noto'g'ri javob. Qayta urinib ko'ring:")

def send_main_menu(chat_id, user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("🎁 Tekin sandiq")
    btn2 = types.KeyboardButton("💎 VIP (Pullik) sandiq")
    btn3 = types.KeyboardButton("💰 Mening balansim")
    btn4 = types.KeyboardButton("➕ Hisobni to'ldirish")
    btn5 = types.KeyboardButton("🎟 Promokod")
    
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    markup.add(btn5)

    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("👨‍💻 Admin Panel"))

    bot.send_message(chat_id, "🎉 Xush kelibsiz! Asosiy menyu:", reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    user_id = message.from_user.id
    text = message.text

    # Obuna tekshiruv (Admin bo'lmasa)
    if user_id != ADMIN_ID and not check_sub(user_id):
        send_sub_request(message.chat.id)
        return

    # Admin: Kanal username o'zgartirish
    if user_state.get(user_id) == "set_channel" and user_id == ADMIN_ID:
        global CHANNEL_USERNAME
        CHANNEL_USERNAME = text.strip()
        user_state[user_id] = None
        bot.send_message(message.chat.id, f"✅ Majburiy obuna kanali o'zgardi:\n👉 **{CHANNEL_USERNAME}**")
        return

    # Admin Panel
    if text == "👨‍💻 Admin Panel" and user_id == ADMIN_ID:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("📢 Kanal Sozlash", "📊 Statistika")
        markup.add("🚪 Menuga qaytish")
        bot.send_message(message.chat.id, f"👨‍💻 **Admin Panel**\n\nHozirgi kanal: {CHANNEL_USERNAME}", reply_markup=markup)
        return

    if text == "📢 Kanal Sozlash" and user_id == ADMIN_ID:
        user_state[user_id] = "set_channel"
        bot.send_message(message.chat.id, "Yangi kanal username'ini kiriting (Masalan: `@kanalim`):")
        return

    if text == "📊 Statistika" and user_id == ADMIN_ID:
        bot.send_message(message.chat.id, f"👥 Jami foydalanuvchilar: {len(users_db)} ta")
        return

    if text == "🚪 Menuga qaytish":
        send_main_menu(message.chat.id, user_id)
        return

    # Asosiy tugmalar
    if text == "💰 Mening balansim":
        bal = user_balances.get(user_id, 0)
        bot.send_message(message.chat.id, f"💰 Sizning balansingiz: {bal} so'm")

    elif text == "🎁 Tekin sandiq":
        prize = random.choice([100, 200, 500, 0, 1000])
        user_balances[user_id] = user_balances.get(user_id, 0) + prize
        bot.send_message(message.chat.id, f"🎁 Tekin sandiqdan sizga **{prize} so'm** yutuq chiqdi!", parse_mode="Markdown")

    elif text == "💎 VIP (Pullik) sandiq":
        bal = user_balances.get(user_id, 0)
        if bal < PAID_PRICE:
            bot.send_message(message.chat.id, f"❌ Balansingizda yetarli pul yo'q!\n\nVIP sandiq narxi: {PAID_PRICE} so'm\nSizda: {bal} so'm")
        else:
            user_balances[user_id] -= PAID_PRICE
            vip_prize = random.choice([10000, 20000, 50000])
            user_balances[user_id] += vip_prize
            bot.send_message(message.chat.id, f"🎉 VIP Sandiq ochildi! Siz **{vip_prize} so'm** yutib oldingiz!", parse_mode="Markdown")

    elif text == "➕ Hisobni to'ldirish":
        bot.send_message(
            message.chat.id, 
            f"💳 Hisobni to'ldirish uchun karta:\n`{CARD_NUMBER}`\nSohibi: {CARD_NAME}\n\nTo'lov qilgach admin bilan bog'laning.", 
            parse_mode="Markdown"
        )

bot.infinity_polling()
        

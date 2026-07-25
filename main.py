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
ADMIN_ID = 8694110588                           # ID raqamingiz

CARD_NUMBER = "9860606756173831"
CARD_NAME = "Abbosov Abrorbek"
# ===================================================

bot = telebot.TeleBot(TOKEN)

CHANNEL_USERNAME = "@latareya_channel"
PAID_PRICE = 5000

# Bazalar
registered_users = set()
users_db = set()
user_balances = {}
captcha_storage = {}
user_state = {}

# Admin tomonidan sozlanadigan quti va sovrinlar bazasi
box_settings = {
    "free_box_prize": "500 so'm",     # Tekin sandiq sovrini
    "vip_box_prize": "20000 so'm",    # VIP sandiq sovrini
    "max_boxes": 10                   # Tanlash uchun sandiqlar soni (masalan, 10 ta)
}

def check_sub(user_id):
    if not CHANNEL_USERNAME:
        return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return True

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
    
    if user_id in registered_users and user_id != ADMIN_ID:
        bot.send_message(
            message.chat.id, 
            "⚠️ **Siz allaqachon ro'yxatdan o'tgansiz!**",
            parse_mode="Markdown"
        )
        return

    users_db.add(user_id)
    if user_id not in user_balances:
        user_balances[user_id] = 0

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
        registered_users.add(user_id)
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

    if user_id != ADMIN_ID and not check_sub(user_id):
        send_sub_request(message.chat.id)
        return

    # --- ADMIN HOLATLARI ---
    state = user_state.get(user_id)
    if user_id == ADMIN_ID:
        if state == "set_channel":
            global CHANNEL_USERNAME
            CHANNEL_USERNAME = text.strip()
            user_state[user_id] = None
            bot.send_message(message.chat.id, f"✅ Kanal o'zgardi: {CHANNEL_USERNAME}")
            return
        elif state == "set_free_prize":
            box_settings["free_box_prize"] = text.strip()
            user_state[user_id] = None
            bot.send_message(message.chat.id, f"✅ Tekin sandiq sovrini yangilandi: {text}")
            return
        elif state == "set_vip_prize":
            box_settings["vip_box_prize"] = text.strip()
            user_state[user_id] = None
            bot.send_message(message.chat.id, f"✅ VIP sandiq sovrini yangilandi: {text}")
            return
        elif state == "set_max_boxes":
            if text.isdigit():
                box_settings["max_boxes"] = int(text)
                user_state[user_id] = None
                bot.send_message(message.chat.id, f"✅ Sandiqlar soni o'zgardi: {text} ta")
            else:
                bot.send_message(message.chat.id, "❌ Faqat raqam kiriting!")
            return

    # Admin Panel menyusi
    if text == "👨‍💻 Admin Panel" and user_id == ADMIN_ID:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("📢 Kanal Sozlash", "📦 Qutilarni sozlash")
        markup.add("📊 Statistika", "🚪 Menuga qaytish")
        bot.send_message(
            message.chat.id, 
            f"👨‍💻 **Admin Panel**\n\n"
            f"📌 Kanal: {CHANNEL_USERNAME}\n"
            f"📦 Sandiqlar soni: {box_settings['max_boxes']} ta\n"
            f"🎁 Tekin sovrin: {box_settings['free_box_prize']}\n"
            f"💎 VIP sovrin: {box_settings['vip_box_prize']}", 
            reply_markup=markup
        )
        return

    if text == "📢 Kanal Sozlash" and user_id == ADMIN_ID:
        user_state[user_id] = "set_channel"
        bot.send_message(message.chat.id, "Yangi kanal username'ini kiriting (Masalan: `@kanalim`):")
        return

    if text == "📦 Qutilarni sozlash" and user_id == ADMIN_ID:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Sandiqlar sonini o'zgartirish", "Tekin sovrinni o'zgartirish")
        markup.add("VIP sovrinni o'zgartirish", "⬅️ Orqaga")
        bot.send_message(message.chat.id, "Qaysi birini o'zgartirmoqchisiz?", reply_markup=markup)
        return

    if text == "Sandiqlar sonini o'zgartirish" and user_id == ADMIN_ID:
        user_state[user_id] = "set_max_boxes"
        bot.send_message(message.chat.id, "Jami sandiqlar sonini raqamda kiriting (Masalan: 10):")
        return

    if text == "Tekin sovrinni o'zgartirish" and user_id == ADMIN_ID:
        user_state[user_id] = "set_free_prize"
        bot.send_message(message.chat.id, "Tekin sandiq ichiga tushadigan sovrinni yozing:")
        return

    if text == "VIP sovrinni o'zgartirish" and user_id == ADMIN_ID:
        user_state[user_id] = "set_vip_prize"
        bot.send_message(message.chat.id, "VIP sandiq ichiga tushadigan sovrinni yozing:")
        return

    if text == "⬅️ Orqaga" and user_id == ADMIN_ID:
        send_main_menu(message.chat.id, user_id)
        return

    if text == "📊 Statistika" and user_id == ADMIN_ID:
        bot.send_message(message.chat.id, f"👥 Jami foydalanuvchilar: {len(users_db)} ta")
        return

    if text == "🚪 Menuga qaytish":
        send_main_menu(message.chat.id, user_id)
        return

    # --- TEKIN SANDIQ (Raqam tanlash) ---
    if text == "🎁 Tekin sandiq":
        markup = types.InlineKeyboardMarkup(row_width=5)
        buttons = []
        for i in range(1, box_settings["max_boxes"] + 1):
            buttons.append(types.InlineKeyboardButton(f"📦 {i}", callback_data=f"free_box_{i}"))
        markup.add(*buttons)
        bot.send_message(message.chat.id, "🎁 O'zingizga yoqqan raqamdagi tekin sandiqni tanlang:", reply_markup=markup)

    # --- VIP SANDIQ (Pullik - Raqam tanlash) ---
    elif text == "💎 VIP (Pullik) sandiq":
        bal = user_balances.get(user_id, 0)
        if bal < PAID_PRICE:
            bot.send_message(message.chat.id, f"❌ Balansingizda yetarli pul yo'q!\n\nVIP sandiq narxi: {PAID_PRICE} so'm\nSizda: {bal} so'm")
        else:
            markup = types.InlineKeyboardMarkup(row_width=5)
            buttons = []
            for i in range(1, box_settings["max_boxes"] + 1):
                buttons.append(types.InlineKeyboardButton(f"💎 {i}", callback_data=f"vip_box_{i}"))
            markup.add(*buttons)
            bot.send_message(message.chat.id, f"💎 VIP sandiq narxi: {PAID_PRICE} so'm.\nO'zingizga yoqqan raqamni tanlang:", reply_markup=markup)

    elif text == "💰 Mening balansim":
        bal = user_balances.get(user_id, 0)
        bot.send_message(message.chat.id, f"💰 Sizning balansingiz: {bal} so'm")

    elif text == "➕ Hisobni to'ldirish":
        bot.send_message(
            message.chat.id, 
            f"💳 Hisobni to'ldirish uchun karta:\n`{CARD_NUMBER}`\nSohibi: {CARD_NAME}\n\nTo'lov qilgach admin bilan bog'laning.", 
            parse_mode="Markdown"
        )

# --- SANDIQNI BOSGANDA ISHLaydigan FUNKSIYA ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("free_box_") or call.data.startswith("vip_box_"))
def open_box_callback(call):
    user_id = call.from_user.id
    data = call.data

    if data.startswith("free_box_"):
        box_num = data.split("_")[2]
        prize = box_settings["free_box_prize"]
        bot.answer_callback_query(call.id, f"🎁 {box_num}-sandiq ochildi!")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🎉 **{box_num}-sandiq** ochildi!\n\nSizga tushgan sovrin: **{prize}**",
            parse_mode="Markdown"
        )

    elif data.startswith("vip_box_"):
        box_num = data.split("_")[2]
        bal = user_balances.get(user_id, 0)
        
        if bal < PAID_PRICE:
            bot.answer_callback_query(call.id, "❌ Balansingiz yetmadi!", show_alert=True)
            return

        user_balances[user_id] -= PAID_PRICE
        prize = box_settings["vip_box_prize"]
        bot.answer_callback_query(call.id, f"💎 {box_num}-VIP sandiq ochildi!")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🎉 **{box_num}-VIP sandiq** ochildi!\n\nSiz yutib oldingiz: **{prize}**",
            parse_mode="Markdown"
        )

bot.infinity_polling()

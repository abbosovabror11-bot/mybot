from flask import Flask
import threading
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot alive"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask).start()

import telebot
from telebot import types
import random

# ⚠️ BOSHIRIQDA FAQAT 2 TA SOZLAMANI SOZLAYSUR:
TOKEN = "8609443477:AAEbM-IFJ9Zn_ILkuQi5DZHB2etPqyDv-ps"  # BotFather'dan olingan token
ADMIN_ID = 8694110588           # Telegram ID'ingiz

CARD_NUMBER = "9860606756173831"  # Karta raqamingiz
CARD_NAME = "Abbosov Abrorbek"           # Karta egasi

bot = telebot.TeleBot(TOKEN)

# Boshlang'ich o'zgaruvchilar (Dinamik)
CHANNEL_USERNAME = "@latareya_channel"  # Admin paneldan o'zgartirsa bo'ladi
MAX_NUMBERS = 100
PAID_PRICE = 5000  # VIP sandiq narxi

FREE_PRIZES = {}
PAID_PRIZES = {}
PROMO_CODES = {}   # {code: amount}

users_db = set()
user_balances = {}
captcha_storage = {}
user_state = {}

def check_sub(user_id):
    if not CHANNEL_USERNAME or CHANNEL_USERNAME == "@kanalingiz_usernamesi":
        return True # Kanal sozlangan bo'lmasa tekshirmaydi
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return False

def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🎁 Tekin sandiq", "💎 VIP (Pullik) sandiq")
    markup.row("💰 Mening balansim", "➕ Hisobni to'ldirish")
    markup.row("🎟 Promokod", "🚪 Menuga qaytish")
    if user_id == ADMIN_ID:
        markup.row("👨‍💻 Admin Panel")
    return markup

# --- START BUYRUG'I ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    users_db.add(user_id)
    if user_id not in user_balances:
        user_balances[user_id] = 0

    if not check_sub(user_id):
        markup = types.InlineKeyboardMarkup()
        btn_channel = types.InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")
        btn_check = types.InlineKeyboardButton("🔄 Tekshirish", callback_data="check")
        markup.add(btn_channel, btn_check)
        bot.send_message(message.chat.id, f"⚠️ Botdan foydalanish uchun {CHANNEL_USERNAME} kanalimizga obuna bo'ling!", reply_markup=markup)
        return

    if user_id not in captcha_storage or not captcha_storage[user_id]['passed']:
        num1, num2 = random.randint(1, 10), random.randint(1, 10)
        captcha_storage[user_id] = {'answer': num1 + num2, 'passed': False}
        bot.send_message(message.chat.id, f"🤖 **Bot emasligingizni tasdiqlang:**\n\nMisolni yeching: **{num1} + {num2} = ?**", parse_mode="Markdown")
        return

    bot.send_message(message.chat.id, "👋 **Xush kelibsiz!** Kerakli bo'limni tanlang:", reply_markup=main_keyboard(user_id), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check")
def callback_check(call):
    if check_sub(call.from_user.id):
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        start(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Siz hali kanalga obuna bo'lmadingiz!", show_alert=True)

# --- INLINE TUGMALAR (ADMIN CHEK TASDIQLASHI) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(("app_", "rej_")))
def handle_payment_approval(call):
    action, u_id, amount = call.data.split("_")
    u_id, amount = int(u_id), int(amount)

    if action == "app":
        user_balances[u_id] = user_balances.get(u_id, 0) + amount
        bot.edit_message_caption(caption=call.message.caption + f"\n\n✅ **TO'LOV TASDIQLANDI!** (+{amount} so'm)", chat_id=call.message.chat.id, message_id=call.message.message_id)
        try: bot.send_message(u_id, f"🎉 Hisobingiz **{amount} so'm**ga to'ldirildi!\nHozirgi balansingiz: **{user_balances[u_id]} so'm**")
        except: pass
    elif action == "rej":
        bot.edit_message_caption(caption=call.message.caption + "\n\n❌ **TO'LOV RAD ETILDI!**", chat_id=call.message.chat.id, message_id=call.message.message_id)
        try: bot.send_message(u_id, "❌ To'lovingiz rad etildi! Chekni tekshirib qayta yuboring.")
        except: pass

# --- CHEK RASMINI USHLASH ---
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    if user_state.get(user_id, {}).get("action") == "wait_receipt":
        amount = user_state[user_id]["amount"]
        photo_id = message.photo[-1].file_id

        markup = types.InlineKeyboardMarkup()
        btn_app = types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"app_{user_id}_{amount}")
        btn_rej = types.InlineKeyboardButton("❌ Rad etish", callback_data=f"rej_{user_id}_{amount}")
        markup.add(btn_app, btn_rej)

        bot.send_photo(
            ADMIN_ID, photo_id,
            caption=f"💳 **YANGI TO'LOV CHEKI!**\n\n👤 Foydalanuvchi: {message.from_user.first_name}\n🆔 ID: `{user_id}`\n💰 Summa: **{amount} so'm**",
            reply_markup=markup, parse_mode="Markdown"
        )
        bot.send_message(message.chat.id, "📥 Chek qabul qilindi! Admin tekshiruvidan so'ng balansingizga pul o'tkaziladi.")
        user_state[user_id] = None

# --- BARCHA MATNLARNI USHLASH ---
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    global CHANNEL_USERNAME
    user_id = message.from_user.id
    text = message.text

    # Captcha
    if user_id in captcha_storage and not captcha_storage[user_id]['passed']:
        if text.isdigit() and int(text) == captcha_storage[user_id]['answer']:
            captcha_storage[user_id]['passed'] = True
            bot.send_message(message.chat.id, "🎉 Captcha to'g'ri!", reply_markup=main_keyboard(user_id))
        else:
            bot.send_message(message.chat.id, "❌ Javob xato! /start bosib qayta urinib ko'ring.")
        return

    # Foydalanuvchi menyusi
    if text == "💰 Mening balansim":
        bal = user_balances.get(user_id, 0)
        bot.send_message(message.chat.id, f"💳 Sizning balansingiz: **{bal} so'm**", parse_mode="Markdown")
        return

    elif text == "🎟 Promokod":
        user_state[user_id] = {"action": "use_promo"}
        bot.send_message(message.chat.id, "🎟 Maxsus promokodingizni kiriting:")
        return

    elif text == "➕ Hisobni to'ldirish":
        user_state[user_id] = {"action": "wait_amount"}
        bot.send_message(message.chat.id, "💵 Qancha summa to'ldirmoqchisiz? (Masalan: `10000`):", parse_mode="Markdown")
        return

    elif text == "🎁 Tekin sandiq":
        user_state[user_id] = {"action": "choose_free"}
        bot.send_message(message.chat.id, f"🎲 Tekin sandiq ochish uchun **1 dan {MAX_NUMBERS} gacha** son yozing:", parse_mode="Markdown")
        return

    elif text == "💎 VIP (Pullik) sandiq":
        bal = user_balances.get(user_id, 0)
        if bal < PAID_PRICE:
            bot.send_message(message.chat.id, f"❌ Balansingizda yetarli pul yo'q!\n\nVIP sandiq narxi: **{PAID_PRICE} so'm**\nSizda: **{bal} so'm**", parse_mode="Markdown")
        else:
            user_state[user_id] = {"action": "choose_paid"}
            bot.send_message(message.chat.id, f"💎 VIP Sandiq narxi: **{PAID_PRICE} so'm**.\n\n**1 dan {MAX_NUMBERS} gacha** son yozing:", parse_mode="Markdown")
        return

    elif text == "👨‍💻 Admin Panel" and user_id == ADMIN_ID:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("🎁 Tekin yutuq", "💎 VIP yutuq")
        markup.row("📢 Kanal Sozlash", "🎟 Promokod Yaratish")
        markup.row("📊 Statistika", "🚪 Menuga qaytish")
        bot.send_message(message.chat.id, f"👨‍💻 **Admin Panel:**\nHozirgi kanal: **{CHANNEL_USERNAME}**", reply_markup=markup, parse_mode="Markdown")
        return

    elif text == "🚪 Menuga qaytish":
        bot.send_message(message.chat.id, "Asosiy menyu:", reply_markup=main_keyboard(user_id))
        return

    # --- PROMOKODNI ISHLATISH (FOYDALANUVCHI) ---
    if user_state.get(user_id, {}).get("action") == "use_promo":
        code = text.strip()
        if code in PROMO_CODES:
            reward = PROMO_CODES[code]
            user_balances[user_id] = user_balances.get(user_id, 0) + reward
            del PROMO_CODES[code]  # Promokod 1 marta ishlatiladi
            bot.send_message(message.chat.id, f"🎉 Muvaffaqiyatli! Balansingizga **+{reward} so'm** qo'shildi!", parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "❌ Bunday promokod mavjud emas yoki allaqachon ishlatilgan!")
        user_state[user_id] = None
        return

    # --- BALANS TO'LDIRISH (SUMMA VA CHEK) ---
    if user_state.get(user_id, {}).get("action") == "wait_amount":
        if text.isdigit() and int(text) >= 1000:
            amount = int(text)
            user_state[user_id] = {"action": "wait_receipt", "amount": amount}
            msg = f"💳 **To'lov ma'lumotlari:**\n\n🔹 Karta raqam: `{CARD_NUMBER}`\n🔹 Egasi: **{CARD_NAME}**\n💰 Summa: **{amount} so'm**\n\n⚠️ To'lov qilib, **chek skrinshotini** botga yuboring!"
            bot.send_message(message.chat.id, msg, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "❌ Kamida 1000 so'm kiriting!")
        return

    # --- ADMIN AMALLARI ---
    if user_id == ADMIN_ID:
        if text == "📢 Kanal Sozlash":
            user_state[user_id] = {"action": "set_channel"}
            bot.send_message(message.chat.id, "Yangi kanal username-ini yuboring (Masalan: `@mychannel`):")
            return

        elif text == "🎟 Promokod Yaratish":
            user_state[user_id] = {"action": "create_promo"}
            bot.send_message(message.chat.id, "Promokod va summasini yozing:\n\nMasalan: `OMAD2026 5000`", parse_mode="Markdown")
            return

        elif text == "🎁 Tekin yutuq":
            user_state[user_id] = {"action": "add_free_prize"}
            bot.send_message(message.chat.id, "Format: `7 1000 som`", parse_mode="Markdown")
            return

        elif text == "💎 VIP yutuq":
            user_state[user_id] = {"action": "add_paid_prize"}
            bot.send_message(message.chat.id, "Format: `10 Telegram Premium`", parse_mode="Markdown")
            return

        elif text == "📊 Statistika":
            bot.send_message(message.chat.id, f"📊 **STATISTIKA:**\n👥 A'zolar: {len(users_db)} ta\n🎟 Faol promokodlar: {len(PROMO_CODES)} ta")
            return

        # Admin kiritgan ma'lumotlarni saqlash
        act = user_state.get(user_id, {}).get("action")
        
        if act == "set_channel":
            CHANNEL_USERNAME = text.strip()
            bot.send_message(message.chat.id, f"✅ Kanal muvaffaqiyatli **{CHANNEL_USERNAME}** qilib o'zgartirildi!")
            user_state[user_id] = None
            return

        elif act == "create_promo":
            try:
                p = text.split(" ")
                code, amount = p[0], int(p[1])
                PROMO_CODES[code] = amount
                bot.send_message(message.chat.id, f"✅ Promokod yaratildi!\n\n🎟 Kod: `{code}`\n💰 Summa: **{amount} so'm**", parse_mode="Markdown")
            except:
                bot.send_message(message.chat.id, "❌ Xato format! Masalan: `OMAD2026 5000`")
            user_state[user_id] = None
            return

        elif act == "add_free_prize":
            try:
                p = text.split(" ", 1)
                FREE_PRIZES[int(p[0])] = p[1]
                bot.send_message(message.chat.id, f"✅ Tekin {p[0]}-sandiqqa '{p[1]}' qo'shildi!")
            except: bot.send_message(message.chat.id, "❌ Xato format!")
            user_state[user_id] = None
            return

        elif act == "add_paid_prize":
            try:
                p = text.split(" ", 1)
                PAID_PRIZES[int(p[0])] = p[1]
                bot.send_message(message.chat.id, f"✅ VIP {p[0]}-sandiqqa '{p[1]}' qo'shildi!")
            except: bot.send_message(message.chat.id, "❌ Xato format!")
            user_state[user_id] = None
            return

    # --- SANDIQ TANLASH ---
    if text.isdigit():
        val = int(text)
        act = user_state.get(user_id, {}).get("action")

        if act == "choose_free":
            win = FREE_PRIZES.get(val, "🥲 Afsuski, bu sandiq bo'sh!")
            bot.send_message(message.chat.id, f"🎯 Tekin {val}-sandiq ochildi!\n\nNatija: **{win}**", parse_mode="Markdown")
            user_state[user_id] = None

        elif act == "choose_paid":
            if user_balances.get(user_id, 0) >= PAID_PRICE:
                user_balances[user_id] -= PAID_PRICE
                win = PAID_PRIZES.get(val, "🥲 VIP sandiq bo'sh chiqdi!")
                bot.send_message(message.chat.id, f"💎 VIP {val}-sandiq ochildi!\n\nNatija: **{win}**\n💰 Qolgan balans: **{user_balances[user_id]} so'm**", parse_mode="Markdown")
            else:
                bot.send_message(message.chat.id, "❌ Balans yetarli emas!")
            user_state[user_id] = None

bot.infinity_polling()

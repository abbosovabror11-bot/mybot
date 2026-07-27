from flask import Flask
import threading
import os
import telebot
from telebot import types
import random
import time
import sqlite3
from datetime import datetime, timedelta

# ==================== FLASK SERVER ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot alive"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask).start()
# ====================================================

# ==================== SOZLAMALAR ====================
TOKEN = "8630740028:AAGeLn8RLQczuX75cAay1S3VCRl8omXLHeA"
ADMIN_ID = 8694110588
CHANNEL_ID = "@ovozbattleofficial" # Promokod tashlanadigan kanal username yoki ID si

CARD_NUMBER = "9860606756173831"
CARD_NAME = "Abbosov Abrorbek"
# ===================================================

bot = telebot.TeleBot(TOKEN)

forced_channels = []
PAID_PRICE = 5000
DAILY_BONUS = 200     

captcha_storage = {}
user_state = {}
topup_amounts = {}
last_daily_bonus = {}
vip_cooldowns = {}      

free_box_prizes = {} 
vip_box_prizes = { 5: "10000 so'm", 10: "50000 so'm" }
promocodes = {} # { "KOD": {"amount": 1000, "limit": 3, "used_count": 0, "msg_id": None, "channel_id": None} }

# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, joined_date TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, prize TEXT, box_info TEXT, date TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS used_promos (user_id INTEGER, code TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS user_opened_free (user_id INTEGER PRIMARY KEY, box_num INTEGER, prize TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS global_opened_free_boxes (box_num INTEGER PRIMARY KEY, user_id INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS vip_opened_boxes (user_id INTEGER, box_num INTEGER, prize TEXT, PRIMARY KEY (user_id, box_num))')
    cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect('bot_database.db', check_same_thread=False)

def get_max_boxes(box_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (box_type,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return int(row[0])
    else:
        default_val = 10
        set_max_boxes(box_type, default_val)
        return default_val

def set_max_boxes(box_type, val):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (box_type, str(val)))
    conn.commit()
    conn.close()

def get_user_balance(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    else:
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO users (user_id, balance, joined_date) VALUES (?, 0, ?)', (user_id, date_str))
        conn.commit()
        conn.close()
        return 0

def update_user_balance(user_id, amount):
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, balance, joined_date) VALUES (?, 0, ?)', (user_id, date_str))
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def add_history(user_id, prize, box_info):
    conn = get_db_connection()
    cursor = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('INSERT INTO history (user_id, prize, box_info, date) VALUES (?, ?, ?, ?)', (user_id, prize, box_info, date_str))
    conn.commit()
    conn.close()
# ==================================================

def check_user_sub(user_id):
    if not forced_channels:
        return True, None
    for ch in forced_channels:
        try:
            member = bot.get_chat_member(ch["id"], user_id)
            if member.status not in ['creator', 'administrator', 'member', 'restricted']:
                return False, ch
        except Exception:
            return False, ch
    return True, None

def send_sub_request(chat_id):
    markup = types.InlineKeyboardMarkup()
    for ch in forced_channels:
        markup.add(types.InlineKeyboardButton(f"📢 {ch.get('title', 'Kanal')}", url=ch["link"]))
    markup.add(types.InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_subscription"))
    bot.send_message(chat_id, "⚠️ Botdan foydalanish uchun homiy kanallarga obuna bo'ling:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    
    # Parametrli start (masalan: /start promo_KOD)
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("promo_"):
        code = args[1].replace("promo_", "").upper()
        handle_promo_activation(message, user_id, code)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    exists = cursor.fetchone()
    conn.close()

    if not exists and user_id != ADMIN_ID:
        is_subbed, _ = check_user_sub(user_id)
        if not is_subbed:
            send_sub_request(message.chat.id)
            return

    if not exists:
        update_user_balance(user_id, 0)
        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        captcha_storage[user_id] = num1 + num2
        bot.send_message(message.chat.id, f"🤖 Xush kelibsiz!\n\nCaptcha misolini yeching:\n👉 **{num1} + {num2} = ?**", parse_mode="Markdown")
    else:
        send_main_menu(message.chat.id, user_id)

def handle_promo_activation(message, user_id, code):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM used_promos WHERE user_id = ? AND code = ?', (user_id, code))
    already_used = cursor.fetchone()
    conn.close()

    if code in promocodes:
        p_info = promocodes[code]
        if already_used:
            bot.send_message(message.chat.id, "❌ Bu promokondan foylangansiz!")
        elif p_info["used_count"] >= p_info["limit"]:
            bot.send_message(message.chat.id, "❌ Bu promokod tugagan!")
        else:
            p_info["used_count"] += 1
            amt = p_info["amount"]
            update_user_balance(user_id, amt)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO used_promos (user_id, code) VALUES (?, ?)', (user_id, code))
            conn.commit()
            conn.close()
            
            add_history(user_id, f"{amt} so'm", f"Promokod ({code})")
            bot.send_message(message.chat.id, f"🎉 Tabriklaymiz! Promokod muvaffaqiyatli ishlatildi va balansga **{amt} so'm** qo'shildi!", parse_mode="Markdown")

            # Kanaldagi xabarni yangilash
            update_channel_promo_message(code)

            # Adminga xabar yuborish
            user_name = f"@{message.from_user.username}" if message.from_user.username else f"ID: {user_id}"
            try:
                bot.send_message(ADMIN_ID, f"🔔 **Yangi promokod ishlatildi!**\n\n👤 Foydalanuvchi: {user_name} (`{user_id}`)\n🔑 Kod: `{code}`\n💰 Miqdor: {amt} so'm\n📊 Limit: {p_info['used_count']}/{p_info['limit']}", parse_mode="Markdown")
            except:
                pass

            if p_info["used_count"] >= p_info["limit"]:
                try:
                    bot.send_message(ADMIN_ID, f"🚨 **DIQQAT!** `{code}` promokodi limiti to'liq tugadi ({p_info['limit']}/{p_info['limit']}).", parse_mode="Markdown")
                except:
                    pass
    else:
        bot.send_message(message.chat.id, "❌ Bunday promokod topilmadi yoki eskirgan!")
    
    send_main_menu(message.chat.id, user_id)

def update_channel_promo_message(code):
    p_info = promocodes.get(code)
    if not p_info or not p_info.get("msg_id"):
        return
    
    msg_id = p_info["msg_id"]
    used = p_info["used_count"]
    limit = p_info["limit"]
    amt = p_info["amount"]

    if used >= limit:
        text = f"🎁 **PROMOKOD TUGADI!**\n\n🔑 Promo: `{code}`\n💰 Qiymati: {amt} so'm\n👥 Limit: {limit}/{limit} ❌"
        markup = None
    else:
        text = f"🎁 **YANGI PROMOKOD!**\n\n🔑 Promo: `{code}`\n💰 Qiymati: {amt} so'm\n👥 Limit: {used}/{limit} ✅"
        markup = types.InlineKeyboardMarkup()
        bot_username = bot.get_me().username
        markup.add(types.InlineKeyboardButton("🎁 Promokodni ishlatish", url=f"https://t.me/{bot_username}?start=promo_{code}"))

    try:
        bot.edit_message_text(text=text, chat_id=CHANNEL_ID, message_id=msg_id, reply_markup=markup, parse_mode="Markdown")
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def callback_check_sub(call):
    user_id = call.from_user.id
    is_subbed, _ = check_user_sub(user_id)
    if is_subbed:
        bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        captcha_storage[user_id] = num1 + num2
        bot.send_message(call.message.chat.id, f"✅ Tasdiqlandi!\n\nCaptcha misolini yeching:\n👉 **{num1} + {num2} = ?**", parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "❌ Hali hamma kanalga obuna bo'lmadingiz!", show_alert=True)

@bot.message_handler(func=lambda message: message.from_user.id in captcha_storage)
def check_captcha(message):
    user_id = message.from_user.id
    correct_ans = captcha_storage.get(user_id)
    if message.text.isdigit() and int(message.text) == correct_ans:
        del captcha_storage[user_id]
        send_main_menu(message.chat.id, user_id)
    else:
        bot.send_message(message.chat.id, "❌ Noto'g'ri javob. Qayta urinib ko'ring:")

def send_main_menu(chat_id, user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🎁 Tekin sandiq"), types.KeyboardButton("💎 VIP (Pullik) sandiq"))
    markup.add(types.KeyboardButton("💰 Mening balansim"), types.KeyboardButton("➕ Hisobni to'ldirish"))
    markup.add(types.KeyboardButton("🎟 Promokod"), types.KeyboardButton("🎁 Kundalik bonus"))
    markup.add(types.KeyboardButton("📜 Mening yutuqlarim"))
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("👨‍💻 Admin Panel"))
    bot.send_message(chat_id, "🎉 Asosiy menyu:", reply_markup=markup)

def send_admin_panel(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📢 Kanal Sozlash", "📋 Kanallar ro'yxati")
    markup.add("📦 Qutilarni sozlash", "💎 VIP narxini o'zgartirish")
    markup.add("🎟 Promokod qo'shish", "🎁 Kunlik bonusni o'zgartirish")
    markup.add("👤 Foydalanuvchini boshqarish", "📢 Xabar yuborish (Rassilka)")
    markup.add("🔄 Tekin sandiqlarni yangilash")
    markup.add("📊 To'liq Statistika", "🚪 Menuga qaytish")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM user_opened_free')
    opened_free_count = cursor.fetchone()[0]
    conn.close()

    free_max = get_max_boxes("free_max_boxes")
    vip_max = get_max_boxes("vip_max_boxes")

    bot.send_message(
        chat_id, 
        f"👨‍💻 **Admin Panel**\n\n👥 Jami foydalanuvchilar: {total_users} ta\n"
        f"📦 Tekin quti ochganlar: {opened_free_count} kishi\n"
        f"💎 VIP qutilar: {vip_max} ta\n"
        f"💎 VIP narxi: {PAID_PRICE} so'm", 
        reply_markup=markup, 
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    user_id = message.from_user.id
    text = message.text
    state = user_state.get(user_id)

    if user_id == ADMIN_ID:
        if text == "🔄 Tekin sandiqlarni yangilash":
            user_state[user_id] = None
            global free_box_prizes
            free_box_prizes.clear()
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_opened_free')
            cursor.execute('DELETE FROM global_opened_free_boxes')
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, "✅ Tekin sandiqlar tarixi tozalandi! Endi hamma yana 1 tadan tekin quti ocha oladi.")
            send_admin_panel(message.chat.id)
            return

        elif state == "set_channel":
            user_state[user_id] = None
            parts = text.split("|")
            ch_id = parts[0].strip()
            ch_link = parts[1].strip() if len(parts) > 1 else f"https://t.me/{ch_id.replace('@', '')}"
            ch_title = parts[2].strip() if len(parts) > 2 else ch_id
            try:
                chat_info = bot.get_chat(ch_id)
                ch_title = chat_info.title or ch_title
                forced_channels.append({"id": ch_id, "link": ch_link, "title": ch_title})
                bot.send_message(message.chat.id, f"✅ Kanal qo'shildi: {ch_title}")
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Xatolik: {e}")
            send_admin_panel(message.chat.id)
            return

        elif state == "set_vip_price":
            global PAID_PRICE
            user_state[user_id] = None
            if text.isdigit():
                PAID_PRICE = int(text)
                bot.send_message(message.chat.id, f"✅ VIP narxi {PAID_PRICE} so'm qilindi!")
            else:
                bot.send_message(message.chat.id, "❌ Faqat raqam kiriting.")
            send_admin_panel(message.chat.id)
            return

        elif state == "set_daily_bonus":
            global DAILY_BONUS
            user_state[user_id] = None
            if text.isdigit():
                DAILY_BONUS = int(text)
                bot.send_message(message.chat.id, f"✅ Kunlik bonus {DAILY_BONUS} so'm qilindi!")
            else:
                bot.send_message(message.chat.id, "❌ Faqat raqam kiriting.")
            send_admin_panel(message.chat.id)
            return

        elif state == "add_promo_code":
            user_state[user_id] = None
            parts = text.split()
            if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
                code_name = parts[0].upper()
                amt = int(parts[1])
                lim = int(parts[2])
                
                promocodes[code_name] = {"amount": amt, "limit": lim, "used_count": 0, "msg_id": None}
                
                # Kanalga avtomatik yuborish va tugma qo'shish
                try:
                    bot_username = bot.get_me().username
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🎁 Promokodni ishlatish", url=f"https://t.me/{bot_username}?start=promo_{code_name}"))
                    
                    sent_msg = bot.send_message(
                        CHANNEL_ID, 
                        f"🎁 **YANGI PROMOKOD!**\n\n🔑 Promo: `{code_name}`\n💰 Qiymati: {amt} so'm\n👥 Limit: 0/{lim} ✅", 
                        reply_markup=markup, 
                        parse_mode="Markdown"
                    )
                    promocodes[code_name]["msg_id"] = sent_msg.message_id
                    bot.send_message(message.chat.id, f"✅ Promokod muvaffaqiyatli yaratildi va kanalga tashlandi!")
                except Exception as e:
                    bot.send_message(message.chat.id, f"✅ Promokod bazaga qo'shildi, lekin kanalga yuborishda xatolik: {e}")
            else:
                bot.send_message(message.chat.id, "❌ Noto'g'ri format! Masalan: `BONUS 1000 3`", parse_mode="Markdown")
            send_admin_panel(message.chat.id)
            return

        elif state == "broadcast_message":
            user_state[user_id] = None
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users')
            all_uids = cursor.fetchall()
            conn.close()
            success = 0
            for row in all_uids:
                try:
                    bot.send_message(row[0], text)
                    success += 1
                except:
                    pass
            bot.send_message(message.chat.id, f"✅ Xabar {success} ta kishiga yuborildi!")
            send_admin_panel(message.chat.id)
            return

        elif state == "manage_user_id":
            if text.isdigit():
                target_uid = int(text)
                user_state[user_id] = {"state": "manage_user_action", "target": target_uid}
                bot.send_message(message.chat.id, f"Foydalanuvchi ID: {target_uid}\nQancha pul qo'shasiz yoki ayirasiz?:", parse_mode="Markdown")
            else:
                user_state[user_id] = None
                bot.send_message(message.chat.id, "❌ Faqat raqamli ID kiriting.")
                send_admin_panel(message.chat.id)
            return

        elif isinstance(state, dict) and state.get("state") == "manage_user_action":
            target_uid = state.get("target")
            user_state[user_id] = None
            if text.lstrip('-').isdigit():
                amount = int(text)
                update_user_balance(target_uid, amount)
                new_bal = get_user_balance(target_uid)
                bot.send_message(message.chat.id, f"✅ Balans o'zgartirildi. Yangi balans: {new_bal} so'm")
            else:
                bot.send_message(message.chat.id, "❌ Noto'g'ri qiymat!")
            send_admin_panel(message.chat.id)
            return

        elif state and state.startswith("set_free_box_"):
            box_num = int(state.split("_")[3])
            free_box_prizes[box_num] = text.strip()
            user_state[user_id] = None
            bot.send_message(message.chat.id, f"✅ Tekin quti ({box_num}) sovrini saqlandi.")
            send_admin_panel(message.chat.id)
            return

        elif state and state.startswith("set_vip_box_"):
            box_num = int(state.split("_")[3])
            vip_box_prizes[box_num] = text.strip()
            user_state[user_id] = None
            bot.send_message(message.chat.id, f"✅ VIP quti ({box_num}) sovrini saqlandi.")
            send_admin_panel(message.chat.id)
            return

        elif state == "set_free_max_boxes":
            user_state[user_id] = None
            if text.isdigit():
                set_max_boxes("free_max_boxes", int(text))
                bot.send_message(message.chat.id, f"✅ Tekin sandiqlar soni {text} ta qilindi.")
            else:
                bot.send_message(message.chat.id, "❌ Noto'g'ri format!")
            send_admin_panel(message.chat.id)
            return

        elif state == "set_vip_max_boxes":
            user_state[user_id] = None
            if text.isdigit():
                set_max_boxes("vip_max_boxes", int(text))
                bot.send_message(message.chat.id, f"✅ VIP sandiqlar soni {text} ta qilindi.")
            else:
                bot.send_message(message.chat.id, "❌ Noto'g'ri format!")
            send_admin_panel(message.chat.id)
            return

    # Foydalanuvchi buyruqlari
    if text == "💰 Mening balansim":
        user_state[user_id] = None
        bot.send_message(message.chat.id, f"💰 Balansingiz: {get_user_balance(user_id)} so'm")
        return

    elif text == "🎟 Promokod":
        user_state[user_id] = "waiting_promocode"
        bot.send_message(message.chat.id, "🎟 Promokodni kiriting:")
        return

    elif text == "📜 Mening yutuqlarim":
        user_state[user_id] = None
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT prize, box_info, date FROM history WHERE user_id = ? ORDER BY id DESC LIMIT 10', (user_id,))
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            bot.send_message(message.chat.id, "📜 Yutuqlar tarixi bo'sh.")
        else:
            text_hist = "📜 **Oxirgi yutuqlaringiz:**\n\n"
            for r in rows:
                text_hist += f"🎁 Sovrin: **{r[0]}**\n📦 Quti: {r[1]}\n⏰ Vaqt: {r[2]}\n-------------------\n"
            bot.send_message(message.chat.id, text_hist, parse_mode="Markdown")
        return

    elif text == "🎁 Kundalik bonus":
        user_state[user_id] = None
        current_time = time.time()
        last_time = last_daily_bonus.get(user_id, 0)
        if current_time - last_time < 86400:
            rem = int(86400 - (current_time - last_time))
            bot.send_message(message.chat.id, f"⏳ Bonusni olgansiz! Keyingi bonus: {rem // 3600} soatdan keyin.")
        else:
            last_daily_bonus[user_id] = current_time
            update_user_balance(user_id, DAILY_BONUS)
            add_history(user_id, f"{DAILY_BONUS} so'm", "Kunlik bonus")
            bot.send_message(message.chat.id, f"🎉 Tabriklaymiz! **{DAILY_BONUS} so'm** qo'shildi! 💰", parse_mode="Markdown")
        return

    elif text == "🎁 Tekin sandiq":
        user_state[user_id] = None
        free_max = get_max_boxes("free_max_boxes")
        markup = types.InlineKeyboardMarkup(row_width=5)
        buttons = []
        for i in range(1, free_max + 1):
            buttons.append(types.InlineKeyboardButton(f"📦 {i}", callback_data=f"free_box_{i}"))
        markup.add(*buttons)
        bot.send_message(message.chat.id, f"🎁 Tekin sandiqlar (Har bir foydalanuvchi faqat 1 ta ocha oladi):", reply_markup=markup)
        return

    elif text == "💎 VIP (Pullik) sandiq":
        user_state[user_id] = None
        bal = get_user_balance(user_id)
        if bal < PAID_PRICE:
            bot.send_message(message.chat.id, f"❌ Balans yetarli emas! VIP narxi: {PAID_PRICE} so'm")
        else:
            vip_max = get_max_boxes("vip_max_boxes")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT box_num, prize FROM vip_opened_boxes WHERE user_id = ?', (user_id,))
            vip_opened = cursor.fetchall()
            conn.close()
            vip_dict = {row[0]: row[1] for row in vip_opened}

            markup = types.InlineKeyboardMarkup(row_width=5)
            buttons = []
            for i in range(1, vip_max + 1):
                if i in vip_dict:
                    buttons.append(types.InlineKeyboardButton(f"🔒 {i}", callback_data="vip_opened_empty"))
                else:
                    buttons.append(types.InlineKeyboardButton(f"💎 {i}", callback_data=f"vip_box_{i}"))
            markup.add(*buttons)
            bot.send_message(message.chat.id, f"💎 VIP sandiqlar (Jami: {vip_max} ta):", reply_markup=markup)
        return

    elif text == "➕ Hisobni to'ldirish":
        user_state[user_id] = "waiting_topup_amount"
        bot.send_message(message.chat.id, f"💳 Karta: `{CARD_NUMBER}`\nEgasi: {CARD_NAME}\n\nQancha summa tashlaganingizni yozing:", parse_mode="Markdown")
        return

    if state == "waiting_promocode":
        code = text.strip().upper()
        user_state[user_id] = None
        handle_promo_activation(message, user_id, code)
        return

    if state == "waiting_topup_amount":
        if text.isdigit():
            topup_amounts[user_id] = int(text)
            user_state[user_id] = "waiting_topup_screen"
            bot.send_message(message.chat.id, "📸 Endi to'lov cheki skrinshotini yuboring:")
        else:
            user_state[user_id] = None
            bot.send_message(message.chat.id, "❌ Bekor qilindi.")
        return

    # Admin Tugmalari
    if text == "👨‍💻 Admin Panel" and user_id == ADMIN_ID:
        user_state[user_id] = None
        send_admin_panel(message.chat.id)
        return

    if text == "📢 Kanal Sozlash" and user_id == ADMIN_ID:
        user_state[user_id] = "set_channel"
        bot.send_message(message.chat.id, "🔗 Kanal username yoki ID sini yuboring:")
        return

    if text == "📋 Kanallar ro'yxati" and user_id == ADMIN_ID:
        if not forced_channels:
            bot.send_message(message.chat.id, "📭 Kanallar yo'q.")
        else:
            markup = types.InlineKeyboardMarkup()
            for idx, ch in enumerate(forced_channels):
                markup.add(types.InlineKeyboardButton(f"❌ O'chirish: {ch['title']}", callback_data=f"del_ch_{idx}"))
            bot.send_message(message.chat.id, "📋 Kanallar:", reply_markup=markup)
        return

    if text == "💎 VIP narxini o'zgartirish" and user_id == ADMIN_ID:
        user_state[user_id] = "set_vip_price"
        bot.send_message(message.chat.id, f"Hozirgi VIP narx: {PAID_PRICE} so'm. Yangisini kiriting:")
        return

    if text == "🎁 Kunlik bonusni o'zgartirish" and user_id == ADMIN_ID:
        user_state[user_id] = "set_daily_bonus"
        bot.send_message(message.chat.id, f"Hozirgi kunlik bonus: {DAILY_BONUS} so'm. Yangisini kiriting:")
        return

    if text == "🎟 Promokod qo'shish" and user_id == ADMIN_ID:
        user_state[user_id] = "add_promo_code"
        bot.send_message(message.chat.id, "Format: `BONUS 1000 3` (Kod, Summa, Limit)", parse_mode="Markdown")
        return

    if text == "👤 Foydalanuvchini boshqarish" and user_id == ADMIN_ID:
        user_state[user_id] = "manage_user_id"
        bot.send_message(message.chat.id, "Foydalanuvchining Telegram ID raqamini kiriting:")
        return

    if text == "📢 Xabar yuborish (Rassilka)" and user_id == ADMIN_ID:
        user_state[user_id] = "broadcast_message"
        bot.send_message(message.chat.id, "Barchaga yuboriladigan xabarni yozing:")
        return

    if text == "📦 Qutilarni sozlash" and user_id == ADMIN_ID:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Tekin qutilarga sovrin qo'shish", "VIP qutilarga sovrin qo'shish")
        markup.add("Tekin qutilar sonini o'zgartirish", "VIP qutilar sonini o'zgartirish")
        markup.add("⬅️ Orqaga")
        bot.send_message(message.chat.id, "Qaysi birini sozlaysiz?", reply_markup=markup)
        return

    if text == "Tekin qutilar sonini o'zgartirish" and user_id == ADMIN_ID:
        user_state[user_id] = "set_free_max_boxes"
        curr = get_max_boxes("free_max_boxes")
        bot.send_message(message.chat.id, f"Hozirgi tekin qutilar soni: {curr} ta. Yangi sonini kiriting:")
        return

    if text == "VIP qutilar sonini o'zgartirish" and user_id == ADMIN_ID:
        user_state[user_id] = "set_vip_max_boxes"
        curr = get_max_boxes("vip_max_boxes")
        bot.send_message(message.chat.id, f"Hozirgi VIP qutilar soni: {curr} ta. Yangi sonini kiriting:")
        return

    if text == "Tekin qutilarga sovrin qo'shish" and user_id == ADMIN_ID:
        free_max = get_max_boxes("free_max_boxes")
        markup = types.InlineKeyboardMarkup(row_width=5)
        btns = [types.InlineKeyboardButton(f"Quti {i}", callback_data=f"cfg_free_{i}") for i in range(1, free_max + 1)]
        markup.add(*btns)
        bot.send_message(message.chat.id, "Qaysi tekin qutiga sovrin yozasiz?", reply_markup=markup)
        return

    if text == "VIP qutilarga sovrin qo'shish" and user_id == ADMIN_ID:
        vip_max = get_max_boxes("vip_max_boxes")
        markup = types.InlineKeyboardMarkup(row_width=5)
        btns = [types.InlineKeyboardButton(f"VIP {i}", callback_data=f"cfg_vip_{i}") for i in range(1, vip_max + 1)]
        markup.add(*btns)
        bot.send_message(message.chat.id, "Qaysi VIP qutiga sovrin yozasiz?", reply_markup=markup)
        return

    if text == "⬅️ Orqaga" and user_id == ADMIN_ID:
        user_state[user_id] = None
        send_admin_panel(message.chat.id)
        return

    if text == "📊 To'liq Statistika" and user_id == ADMIN_ID:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Jami foydalanuvchilar va balanslar
        cursor.execute('SELECT COUNT(*), SUM(balance) FROM users')
        u_count, total_bal = cursor.fetchone()
        total_bal = total_bal if total_bal else 0

        # Aktivlik (1 kun, 7 kun, 1 oy)
        now = datetime.now()
        d_1 = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        d_7 = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        d_30 = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute('SELECT COUNT(*) FROM users WHERE joined_date >= ?', (d_1,))
        day_1_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM users WHERE joined_date >= ?', (d_7,))
        day_7_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM users WHERE joined_date >= ?', (d_30,))
        day_30_count = cursor.fetchone()[0]

        # Sovrin yutganlar soni (Gift)
        cursor.execute('SELECT COUNT(DISTINCT user_id) FROM history WHERE prize != "Bo\'sh"')
        gift_winners_count = cursor.fetchone()[0]

        # Foydalanuvchilarning balansi ro'yxati (eng ko'p puli bor 5 tasi)
        cursor.execute('SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 5')
        top_users = cursor.fetchall()

        conn.close()

        stat_text = (
            f"📊 **Kengaytirilgan Statistika**\n\n"
            f"👥 Jami foydalanuvchilar: {u_count} ta\n"
            f"💰 Jami balanslar: {total_bal} so'm\n\n"
            f"📈 **Kirib kelganlar (Aktivlik):**\n"
            f"• Oxirgi 1 kunda: {day_1_count} ta\n"
            f"• Oxirgi 7 kunda: {day_7_count} ta\n"
            f"• Oxirgi 1 oyda: {day_30_count} ta\n\n"
            f"🎁 Sovrin (Gift) yutib olganlar: {gift_winners_count} kishi\n\n"
            f"🏆 **Eng ko'p puli bor TOP foydalanuvchilar:**\n"
        )
        for idx, tu in enumerate(top_users, 1):
            stat_text += f"{idx}. ID: `{tu[0]}` — {tu[1]} so'm\n"

        bot.send_message(message.chat.id, stat_text, parse_mode="Markdown")
        return

    if text == "🚪 Menuga qaytish":
        user_state[user_id] = None
        send_main_menu(message.chat.id, user_id)
        return

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    if user_state.get(user_id) == "waiting_topup_screen":
        amount = topup_amounts.get(user_id, 0)
        photo_id = message.photo[-1].file_id
        user_state[user_id] = None
        if user_id in topup_amounts:
            del topup_amounts[user_id]

        bot.send_message(message.chat.id, "✅ Chekingiz adminga yuborildi!")
        admin_markup = types.InlineKeyboardMarkup()
        admin_markup.add(types.InlineKeyboardButton("➕ Tasdiqlash", callback_data=f"approve_topup_{user_id}_{amount}"))
        try:
            bot.send_photo(ADMIN_ID, photo_id, caption=f"To'lov cheki!\nID: {user_id}\nSumma: {amount} so'm", reply_markup=admin_markup)
        except:
            pass

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    username = f"@{call.from_user.username}" if call.from_user.username else f"ID: {user_id}"

    if data == "vip_opened_empty":
        bot.answer_callback_query(call.id, "❌ Bu quti allaqachon ochilgan!", show_alert=True)
        return

    if data.startswith("del_ch_") and user_id == ADMIN_ID:
        idx = int(data.split("_")[2])
        if 0 <= idx < len(forced_channels):
            removed = forced_channels.pop(idx)
            bot.answer_callback_query(call.id, f"✅ O'chirildi: {removed['title']}")
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="✅ O'chirildi.")
        return

    if data.startswith("cfg_free_") and user_id == ADMIN_ID:
        box_num = data.split("_")[2]
        user_state[user_id] = f"set_free_box_{box_num}"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"Tekin quti ({box_num}) uchun sovrin yozing:")
        return

    if data.startswith("cfg_vip_") and user_id == ADMIN_ID:
        box_num = data.split("_")[2]
        user_state[user_id] = f"set_vip_box_{box_num}"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"VIP quti ({box_num}) uchun sovrin yozing:")
        return

    if data.startswith("approve_topup_") and user_id == ADMIN_ID:
        parts = data.split("_")
        target_uid = int(parts[2])
        amount = int(parts[3])
        update_user_balance(target_uid, amount)
        add_history(target_uid, f"{amount} so'm", "Hisobni to'ldirish")
        bot.answer_callback_query(call.id, "✅ Tasdiqlandi!")
        try:
            bot.edit_message_caption(caption=call.message.caption + "\n\n[TASDIQLANDI]", chat_id=call.message.chat.id, message_id=call.message.message_id)
        except:
            pass
        bot.send_message(target_uid, f"🎉 To'lovingiz tasdiqlandi! Balansga **{amount} so'm** qo'shildi.", parse_mode="Markdown")
        return

    if data.startswith("free_box_"):
        box_num = int(data.split("_")[2])
        free_max = get_max_boxes("free_max_boxes")
        
        if box_num > free_max:
            bot.answer_callback_query(call.id, "❌ Bu quti hozirda mavjud emas!", show_alert=True)
            return

        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT box_num FROM user_opened_free WHERE user_id = ?', (user_id,))
        user_opened = cursor.fetchone()

        if user_opened:
            conn.close()
            bot.answer_callback_query(call.id, "❌ Siz allaqachon tekin sandiq ochgansiz!", show_alert=True)
            return

        cursor.execute('SELECT user_id FROM global_opened_free_boxes WHERE box_num = ?', (box_num,))
        box_taken = cursor.fetchone()

        if box_taken:
            conn.close()
            bot.answer_callback_query(call.id, "❌ Bu qutini allaqachon boshqa foydalanuvchi ochib bo'lgan!", show_alert=True)
            return

        prize = free_box_prizes.get(box_num)
        prize_text = prize if prize else "Bo'sh"

        cursor.execute('INSERT INTO user_opened_free (user_id, box_num, prize) VALUES (?, ?, ?)', (user_id, box_num, prize_text))
        cursor.execute('INSERT INTO global_opened_free_boxes (box_num, user_id) VALUES (?, ?)', (box_num, user_id))
        conn.commit()
        conn.close()

        if prize:
            add_history(user_id, prize, f"{box_num}-tekin sandiq")
            bot.answer_callback_query(call.id, "🎉 Yutdingiz!")
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"🎉 **{box_num}-sandiq** yutug'i: **{prize}**", parse_mode="Markdown")
            try:
                bot.send_message(ADMIN_ID, f"🎁 Yutuq: {username} - {prize} ({box_num}-tekin)", parse_mode="Markdown")
            except:
                pass
        else:
            add_history(user_id, "Bo'sh", f"{box_num}-tekin sandiq")
            bot.answer_callback_query(call.id, "Bo'sh chiqdi 😢", show_alert=True)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"📦 **{box_num}-sandiq** bo'sh chiqdi 🍀", parse_mode="Markdown")

    elif data.startswith("vip_box_"):
        box_num = int(data.split("_")[2])
        vip_max = get_max_boxes("vip_max_boxes")
        
        if box_num > vip_max:
            bot.answer_callback_query(call.id, "❌ Bu VIP quti hozirda mavjud emas!", show_alert=True)
            return

        current_time = time.time()
        last_vip_time = vip_cooldowns.get(user_id, 0)
        if current_time - last_vip_time < 5:
            bot.answer_callback_query(call.id, "⏳ Biroz kuting!", show_alert=True)
            return

        bal = get_user_balance(user_id)
        if bal < PAID_PRICE:
            bot.answer_callback_query(call.id, "❌ Balans yetmadi!", show_alert=True)
            return

        update_user_balance(user_id, -PAID_PRICE)
        vip_cooldowns[user_id] = time.time()

        prize = vip_box_prizes.get(box_num)
        prize_text = prize if prize else "Bo'sh"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO vip_opened_boxes (user_id, box_num, prize) VALUES (?, ?, ?)', (user_id, box_num, prize_text))
        conn.commit()
        conn.close()

        if prize:
            add_history(user_id, prize, f"{box_num}-VIP sandiq")
            bot.answer_callback_query(call.id, "💎 VIP yutuq!")
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"🎉 **{box_num}-VIP sandiq** yutug'i: **{prize}**", parse_mode="Markdown")
            try:
                bot.send_message(ADMIN_ID, f"💎 VIP Yutuq: {username} - {prize} ({box_num}-VIP)", parse_mode="Markdown")
            except:
                pass
        else:
            add_history(user_id, "Bo'sh", f"{box_num}-VIP sandiq")
            bot.answer_callback_query(call.id, "Bo'sh VIP sandiq 😢", show_alert=True)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"💎 **{box_num}-VIP sandiq** bo'sh chiqdi 🍀", parse_mode="Markdown")

bot.infinity_polling()

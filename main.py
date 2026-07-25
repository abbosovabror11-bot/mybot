from flask import Flask
import threading
import os
import telebot
from telebot import types
import random
import time
import sqlite3

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
TOKEN = "8630740028:AAGeLn8RLQczuX75cAay1S3VCRl8omXLHeA"  # Botingiz tokeni
ADMIN_ID = 8694110588                           # ID raqamingiz

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

free_box_prizes = { 3: "500 so'm", 7: "1000 so'm" }
vip_box_prizes = { 5: "10000 so'm", 10: "50000 so'm" }
box_settings = { "max_boxes": 10 }
promocodes = { "START2026": {"amount": 1000, "limit": 10, "used_count": 0} }

# ==================== DATABASE (MA'LUMOTLAR BAZASI) ====================
def init_db():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            prize TEXT,
            box_info TEXT,
            date TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS used_promos (
            user_id INTEGER,
            code TEXT
        )
    ''')
    # Tekin qutilar uchun global jadval (hamma uchun umumiy)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_opened_boxes (
            box_num INTEGER PRIMARY KEY,
            prize TEXT,
            opened_by INTEGER
        )
    ''')
    # VIP qutilar uchun har bir foydalanuvchiga alohida jadval
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vip_opened_boxes (
            user_id INTEGER,
            box_num INTEGER,
            prize TEXT,
            PRIMARY KEY (user_id, box_num)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect('bot_database.db', check_same_thread=False)

def get_user_balance(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)', (user_id,))
        conn.commit()
        conn.close()
        return 0

def update_user_balance(user_id, amount):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)', (user_id,))
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def add_history(user_id, prize, box_info):
    conn = get_db_connection()
    cursor = conn.cursor()
    date_str = time.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('INSERT INTO history (user_id, prize, box_info, date) VALUES (?, ?, ?, ?)', (user_id, prize, box_info, date_str))
    conn.commit()
    conn.close()
# ======================================================================

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
        markup.add(types.InlineKeyboardButton(f"📢 {ch.get('title', 'Kanalga o\'tish')}", url=ch["link"]))
    markup.add(types.InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_subscription"))
    bot.send_message(
        chat_id, 
        "⚠️ **Botdan foydalanish uchun quyidagi homiy kanallarga obuna bo'ling:**",
        parse_mode="Markdown", 
        reply_markup=markup
    )

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    
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

        bot.send_message(
            message.chat.id, 
            f"🤖 **Botimizga xush kelibsiz!**\n\nIltimos, Captcha misolini yeching:\n\n👉 **{num1} + {num2} = ?**"
        )
    else:
        send_main_menu(message.chat.id, user_id)

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
        
        bot.send_message(
            call.message.chat.id, 
            f"✅ Tasdiqlandi!\n\nIltimos, Captcha misolini yeching:\n\n👉 **{num1} + {num2} = ?**"
        )
    else:
        bot.answer_callback_query(call.id, "❌ Siz hali hamma homiy kanalga obuna bo'lmadingiz!", show_alert=True)

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
    btn1 = types.KeyboardButton("🎁 Tekin sandiq")
    btn2 = types.KeyboardButton("💎 VIP (Pullik) sandiq")
    btn3 = types.KeyboardButton("💰 Mening balansim")
    btn4 = types.KeyboardButton("➕ Hisobni to'ldirish")
    btn5 = types.KeyboardButton("🎟 Promokod")
    btn6 = types.KeyboardButton("🎁 Kundalik bonus")
    btn7 = types.KeyboardButton("📜 Mening yutuqlarim")
    
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    markup.add(btn5, btn6)
    markup.add(btn7)

    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("👨‍💻 Admin Panel"))

    bot.send_message(chat_id, "🎉 Xush kelibsiz! Asosiy menyu:", reply_markup=markup)

def send_admin_panel(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📢 Kanal Sozlash", "📋 Kanallar ro'yxati")
    markup.add("📦 Qutilarni sozlash", "💎 VIP narxini o'zgartirish")
    markup.add("🎟 Promokod qo'shish", "🎁 Kunlik bonusni o'zgartirish")
    markup.add("👤 Foydalanuvchini boshqarish", "📢 Xabar yuborish (Rassilka)")
    markup.add("📊 Statistika", "🚪 Menuga qaytish")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    conn.close()

    channels_count = len(forced_channels)
    bot.send_message(
        chat_id, 
        f"👨‍💻 **Admin Panel**\n\n"
        f"👥 Jami foydalanuvchilar: {total_users} ta\n"
        f"📌 Jami sandiqlar: {box_settings['max_boxes']} ta\n"
        f"💎 VIP narxi: {PAID_PRICE} so'm\n"
        f"🎁 Kunlik bonus: {DAILY_BONUS} so'm\n"
        f"📢 Homiy kanallar: {channels_count} ta", 
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    user_id = message.from_user.id
    text = message.text
    state = user_state.get(user_id)

    if user_id == ADMIN_ID:
        if state == "set_channel":
            user_state[user_id] = None
            parts = text.split("|")
            ch_id = parts[0].strip()
            ch_link = parts[1].strip() if len(parts) > 1 else f"https://t.me/{ch_id.replace('@', '')}"
            ch_title = parts[2].strip() if len(parts) > 2 else ch_id
            
            try:
                chat_info = bot.get_chat(ch_id)
                ch_title = chat_info.title or ch_title
                forced_channels.append({"id": ch_id, "link": ch_link, "title": ch_title})
                bot.send_message(message.chat.id, f"✅ Homiy kanal qo'shildi!\nNomi: {ch_title}")
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Xatolik! Xatolik: {e}")
            send_admin_panel(message.chat.id)
            return

        elif state == "set_vip_price":
            global PAID_PRICE
            user_state[user_id] = None
            if text.isdigit():
                PAID_PRICE = int(text)
                bot.send_message(message.chat.id, f"✅ VIP sandiq narxi {PAID_PRICE} so'm qilindi!")
            else:
                bot.send_message(message.chat.id, "❌ Faqat raqam kiritilmadi.")
            send_admin_panel(message.chat.id)
            return

        elif state == "set_daily_bonus":
            global DAILY_BONUS
            user_state[user_id] = None
            if text.isdigit():
                DAILY_BONUS = int(text)
                bot.send_message(message.chat.id, f"✅ Kunlik bonus miqdori **{DAILY_BONUS} so'm** qilindi!", parse_mode="Markdown")
            else:
                bot.send_message(message.chat.id, "❌ Faqat raqam kiritilmadi.")
            send_admin_panel(message.chat.id)
            return

        elif state == "add_promo_code":
            user_state[user_id] = None
            parts = text.split()
            if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
                code_name = parts[0].upper()
                code_amt = int(parts[1])
                code_limit = int(parts[2])
                promocodes[code_name] = {"amount": code_amt, "limit": code_limit, "used_count": 0}
                bot.send_message(message.chat.id, f"✅ Promokod qo'shildi!\n🎟 Kod: {code_name}\n💵 Summa: {code_amt} so'm\n👥 Limit: {code_limit} ta odam")
            else:
                bot.send_message(message.chat.id, "❌ Noto'g'ri format!")
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
            bot.send_message(message.chat.id, f"✅ Xabar {success} ta foydalanuvchiga yuborildi!")
            send_admin_panel(message.chat.id)
            return

        elif state == "manage_user_id":
            if text.isdigit():
                target_uid = int(text)
                user_state[user_id] = {"state": "manage_user_action", "target": target_uid}
                bot.send_message(message.chat.id, f"Foydalanuvchi ID: {target_uid}\n\nQancha pul qo'shmoqchisiz yoki ayirmoqchisiz? (Masalan: `1000` yoki `-500`):")
            else:
                user_state[user_id] = None
                bot.send_message(message.chat.id, "❌ Faqat raqamli ID kiritilishi kerak.", parse_mode="Markdown")
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
                try:
                    bot.send_message(target_uid, f"🔔 Admin tomonidan balansingizga **{amount} so'm** ta'sir qilindi. Balans: {new_bal} so'm", parse_mode="Markdown")
                except:
                    pass
            else:
                bot.send_message(message.chat.id, "❌ Noto'g'ri qiymat kiritildi!")
            send_admin_panel(message.chat.id)
            return

        elif state and state.startswith("set_free_box_"):
            box_num = int(state.split("_")[3])
            free_box_prizes[box_num] = text.strip()
            user_state[user_id] = None
            bot.send_message(message.chat.id, f"✅ Tekin sandiq ({box_num}) sovrini saqlandi.")
            send_admin_panel(message.chat.id)
            return

        elif state and state.startswith("set_vip_box_"):
            box_num = int(state.split("_")[3])
            vip_box_prizes[box_num] = text.strip()
            user_state[user_id] = None
            bot.send_message(message.chat.id, f"✅ VIP sandiq ({box_num}) sovrini saqlandi.")
            send_admin_panel(message.chat.id)
            return

        elif state == "set_max_boxes":
            user_state[user_id] = None
            if text.isdigit():
                box_settings["max_boxes"] = int(text)
                bot.send_message(message.chat.id, f"✅ Jami sandiqlar soni {text} ta bo'ldi.")
            else:
                bot.send_message(message.chat.id, "❌ Noto'g'ri format!")
            send_admin_panel(message.chat.id)
            return

    if text == "💰 Mening balansim":
        user_state[user_id] = None
        bal = get_user_balance(user_id)
        bot.send_message(message.chat.id, f"💰 Sizning balansingiz: {bal} so'm")
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
            bot.send_message(message.chat.id, "📜 Sizda hozircha yutuqlar tarixi mavjud emas.")
        else:
            text_hist = "📜 **Sizning oxirgi yutuqlaringiz:**\n\n"
            for r in rows:
                text_hist += f"🎁 Sovrin: **{r[0]}**\n📦 Quti: {r[1]}\n⏰ Vaqt: {r[2]}\n-------------------\n"
            bot.send_message(message.chat.id, text_hist, parse_mode="Markdown")
        return

    elif text == "🎁 Kundalik bonus":
        user_state[user_id] = None
        current_time = time.time()
        last_time = last_daily_bonus.get(user_id, 0)
        
        if current_time - last_time < 86400:
            remaining = int(86400 - (current_time - last_time))
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            bot.send_message(message.chat.id, f"⏳ Siz kundalik bonusni olgansiz!\nKeyingi bonus: **{hours} soat {minutes} daqiqa**dan keyin.", parse_mode="Markdown")
        else:
            last_daily_bonus[user_id] = current_time
            update_user_balance(user_id, DAILY_BONUS)
            add_history(user_id, f"{DAILY_BONUS} so'm", "Kundalik bonus")
            bot.send_message(message.chat.id, f"🎉 Tabriklaymiz! Kunlik bonus sifatida **{DAILY_BONUS} so'm** qo'shildi! 💰", parse_mode="Markdown")
        return

    elif text == "🎁 Tekin sandiq":
        user_state[user_id] = None
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT box_num, prize FROM global_opened_boxes')
        opened_rows = cursor.fetchall()
        conn.close()
        
        opened_dict = {row[0]: row[1] for row in opened_rows}

        markup = types.InlineKeyboardMarkup(row_width=5)
        buttons = []
        for i in range(1, box_settings["max_boxes"] + 1):
            if i in opened_dict:
                p = opened_dict[i]
                if p != "Bo'sh":
                    buttons.append(types.InlineKeyboardButton(f"✅ {i}", callback_data=f"opened_box_info_{p}"))
                else:
                    buttons.append(types.InlineKeyboardButton(f"❌ {i}", callback_data="opened_box_empty"))
            else:
                buttons.append(types.InlineKeyboardButton(f"📦 {i}", callback_data=f"free_box_{i}"))
        markup.add(*buttons)
        bot.send_message(message.chat.id, f"🎁 Tekin sandiqlar (Jami: {box_settings['max_boxes']} ta):\nO'zingizga yoqqan raqamni tanlang (Har birini 1 marta ochish mumkin):", reply_markup=markup)
        return

    elif text == "💎 VIP (Pullik) sandiq":
        user_state[user_id] = None
        bal = get_user_balance(user_id)
        if bal < PAID_PRICE:
            bot.send_message(message.chat.id, f"❌ Balansingizda yetarli pul yo'q!\n\nVIP sandiq narxi: {PAID_PRICE} so'm\nSizda: {bal} so'm")
        else:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT box_num, prize FROM vip_opened_boxes WHERE user_id = ?', (user_id,))
            vip_opened = cursor.fetchall()
            conn.close()

            vip_dict = {row[0]: row[1] for row in vip_opened}

            markup = types.InlineKeyboardMarkup(row_width=5)
            buttons = []
            for i in range(1, box_settings["max_boxes"] + 1):
                if i in vip_dict:
                    p = vip_dict[i]
                    if p != "Bo'sh":
                        buttons.append(types.InlineKeyboardButton(f"✅ {i}", callback_data=f"vip_opened_info_{p}"))
                    else:
                        buttons.append(types.InlineKeyboardButton(f"❌ {i}", callback_data="vip_opened_empty"))
                else:
                    buttons.append(types.InlineKeyboardButton(f"💎 {i}", callback_data=f"vip_box_{i}"))
            markup.add(*buttons)
            bot.send_message(message.chat.id, f"💎 VIP sandiq narxi: {PAID_PRICE} so'm.\n(Ochish oralig'i: 5 soniya). O'zingizga yoqqan raqamni tanlang:", reply_markup=markup)
        return

    elif text == "➕ Hisobni to'ldirish":
        user_state[user_id] = "waiting_topup_amount"
        bot.send_message(
            message.chat.id, 
            f"💳 Hisobni to'ldirish uchun karta:\n`{CARD_NUMBER}`\nSohibi: {CARD_NAME}\n\n"
            f"Kartaga pul o'tkazgach, **qancha summa tashlaganingizni raqamda yozib yuboring** (masalan: `5000`):", 
            parse_mode="Markdown"
        )
        return

    if state == "waiting_promocode":
        code = text.strip().upper()
        user_state[user_id] = None
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM used_promos WHERE user_id = ? AND code = ?', (user_id, code))
        already_used = cursor.fetchone()
        conn.close()

        if code in promocodes:
            promo_info = promocodes[code]
            if already_used:
                bot.send_message(message.chat.id, "❌ Siz bu promokoddan allaqachon foylangansiz!")
            elif promo_info["used_count"] >= promo_info["limit"]:
                bot.send_message(message.chat.id, "❌ Kechirasiz, bu promokodning limiti tugagan!")
            else:
                promo_info["used_count"] += 1
                amt = promo_info["amount"]
                update_user_balance(user_id, amt)
                
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('INSERT INTO used_promos (user_id, code) VALUES (?, ?)', (user_id, code))
                conn.commit()
                conn.close()

                add_history(user_id, f"{amt} so'm", f"Promokod ({code})")
                bot.send_message(message.chat.id, f"🎉 Tabriklaymiz! Promokod faollashtirildi.\nBalansingizga **{amt} so'm** qo'shildi! 💰", parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "❌ Bunday promokod mavjud emas yoki eskirgan!")
        return

    if state == "waiting_topup_amount":
        if text.isdigit():
            topup_amounts[user_id] = int(text)
            user_state[user_id] = "waiting_topup_screen"
            bot.send_message(message.chat.id, "📸 Endi to'lov cheki (skrinshot) rasmini yuboring:")
        else:
            user_state[user_id] = None
            bot.send_message(message.chat.id, "❌ Noto'g'ri format, bekor qilindi.")
        return

    if text == "👨‍💻 Admin Panel" and user_id == ADMIN_ID:
        user_state[user_id] = None
        send_admin_panel(message.chat.id)
        return

    if text == "📢 Kanal Sozlash" and user_id == ADMIN_ID:
        user_state[user_id] = "set_channel"
        bot.send_message(message.chat.id, "🔗 Kanalning username yoki ID sini yuboring:", parse_mode="Markdown")
        return

    if text == "📋 Kanallar ro'yxati" and user_id == ADMIN_ID:
        if not forced_channels:
            bot.send_message(message.chat.id, "📭 Hozircha homiy kanallar yo'q.")
        else:
            markup = types.InlineKeyboardMarkup()
            for idx, ch in enumerate(forced_channels):
                markup.add(types.InlineKeyboardButton(f"❌ O'chirish: {ch['title']}", callback_data=f"del_ch_{idx}"))
            bot.send_message(message.chat.id, "📋 Homiy kanallar ro'yxati:", reply_markup=markup)
        return

    if text == "💎 VIP narxini o'zgartirish" and user_id == ADMIN_ID:
        user_state[user_id] = "set_vip_price"
        bot.send_message(message.chat.id, f"Hozirgi VIP narx: {PAID_PRICE} so'm. Yangi narxni kiriting:")
        return

    if text == "🎁 Kunlik bonusni o'zgartirish" and user_id == ADMIN_ID:
        user_state[user_id] = "set_daily_bonus"
        bot.send_message(message.chat.id, f"Hozirgi kunlik bonus: {DAILY_BONUS} so'm. Yangi summani kiriting:")
        return

    if text == "🎟 Promokod qo'shish" and user_id == ADMIN_ID:
        user_state[user_id] = "add_promo_code"
        bot.send_message(message.chat.id, "Masalan: `BONUS 5000 15`", parse_mode="Markdown")
        return

    if text == "👤 Foydalanuvchini boshqarish" and user_id == ADMIN_ID:
        user_state[user_id] = "manage_user_id"
        bot.send_message(message.chat.id, "Foydalanuvchining Telegram ID raqamini kiriting:")
        return

    if text == "📢 Xabar yuborish (Rassilka)" and user_id == ADMIN_ID:
        user_state[user_id] = "broadcast_message"
        bot.send_message(message.chat.id, "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yozing:")
        return

    if text == "📦 Qutilarni sozlash" and user_id == ADMIN_ID:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Tekin qutilarga sovrin qo'shish", "VIP qutilarga sovrin qo'shish")
        markup.add("Sandiqlar sonini o'zgartirish", "⬅️ Orqaga")
        bot.send_message(message.chat.id, "Qaysi birini sozlaysiz?", reply_markup=markup)
        return

    if text == "Sandiqlar sonini o'zgartirish" and user_id == ADMIN_ID:
        user_state[user_id] = "set_max_boxes"
        bot.send_message(message.chat.id, "Jami sandiqlar sonini kiriting:")
        return

    if text == "Tekin qutilarga sovrin qo'shish" and user_id == ADMIN_ID:
        markup = types.InlineKeyboardMarkup(row_width=5)
        btns = [types.InlineKeyboardButton(f"Quti {i}", callback_data=f"cfg_free_{i}") for i in range(1, box_settings["max_boxes"]+1)]
        markup.add(*btns)
        bot.send_message(message.chat.id, "Qaysi tekin qutiga sovrin yozasiz?", reply_markup=markup)
        return

    if text == "VIP qutilarga sovrin qo'shish" and user_id == ADMIN_ID:
        markup = types.InlineKeyboardMarkup(row_width=5)
        btns = [types.InlineKeyboardButton(f"Quti {i}", callback_data=f"cfg_vip_{i}") for i in range(1, box_settings["max_boxes"]+1)]
        markup.add(*btns)
        bot.send_message(message.chat.id, "Qaysi VIP qutiga sovrin yozasiz?", reply_markup=markup)
        return

    if text == "⬅️ Orqaga" and user_id == ADMIN_ID:
        send_admin_panel(message.chat.id)
        return

    if text == "📊 Statistika" and user_id == ADMIN_ID:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        tot = cursor.fetchone()[0]
        conn.close()
        bot.send_message(message.chat.id, f"👥 Jami foydalanuvchilar: {tot} ta")
        return

    if text == "🚪 Menuga qaytish":
        user_state[user_id] = None
        send_main_menu(message.chat.id, user_id)
        return

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    state_info = user_state.get(user_id)

    if state_info == "waiting_topup_screen":
        amount = topup_amounts.get(user_id, 0)
        photo_id = message.photo[-1].file_id
        
        user_state[user_id] = None
        if user_id in topup_amounts:
            del topup_amounts[user_id]

        bot.send_message(message.chat.id, "✅ Chekingiz adminga yuborildi!")

        admin_markup = types.InlineKeyboardMarkup()
        admin_markup.add(types.InlineKeyboardButton("➕ Balansni tasdiqlash", callback_data=f"approve_topup_{user_id}_{amount}"))
        
        try:
            bot.send_photo(
                ADMIN_ID,
                photo_id,
                caption=f"Yangi to'lov cheki!\n\nFoydalanuvchi ID: {user_id}\nSumma: {amount} so'm",
                reply_markup=admin_markup
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Xatolik: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    username = f"@{call.from_user.username}" if call.from_user.username else f"ID: {user_id}"

    if data == "opened_box_empty" or data == "vip_opened_empty":
        bot.answer_callback_query(call.id, "❌ Bu quti allaqachon ochilgan va bo'sh chiqqan!", show_alert=True)
        return

    if data.startswith("opened_box_info_") or data.startswith("vip_opened_info_"):
        prize_name = data.split("_", 3)[3]
        bot.answer_callback_query(call.id, f"✅ Bu quti ochilgan! Yutuq: {prize_name}", show_alert=True)
        return

    if data.startswith("del_ch_") and user_id == ADMIN_ID:
        idx = int(data.split("_")[2])
        if 0 <= idx < len(forced_channels):
            removed = forced_channels.pop(idx)
            bot.answer_callback_query(call.id, f"✅ O'chirildi: {removed['title']}")
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="✅ Kanal olib tashlandi.")
        return

    if data.startswith("cfg_free_") and user_id == ADMIN_ID:
        box_num = data.split("_")[2]
        user_state[user_id] = f"set_free_box_{box_num}"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"Tekin quti ({box_num}) sovrinini yozing:")
        return

    if data.startswith("cfg_vip_") and user_id == ADMIN_ID:
        box_num = data.split("_")[2]
        user_state[user_id] = f"set_vip_box_{box_num}"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"VIP quti ({box_num}) sovrinini yozing:")
        return

    if data.startswith("approve_topup_") and user_id == ADMIN_ID:
        parts = data.split("_")
        target_user_id = int(parts[2])
        amount = int(parts[3])

        update_user_balance(target_user_id, amount)
        add_history(target_user_id, f"{amount} so'm", "Hisobni to'ldirish")

        bot.answer_callback_query(call.id, "✅ Tasdiqlandi!")
        try:
            bot.edit_message_caption(
                caption=call.message.caption + "\n\n[TASDIQLANDI VA BALANSGA QO'SHILDI]",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
        except:
            pass
        bot.send_message(target_user_id, f"🎉 Tabriklaymiz! To'lovingiz tasdiqlandi va balansingizga **{amount} so'm** qo'shildi.", parse_mode="Markdown")
        return

    if data.startswith("free_box_"):
        box_num = int(data.split("_")[2])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM global_opened_boxes WHERE box_num = ?', (box_num,))
        already_opened = cursor.fetchone()
        conn.close()

        if already_opened:
            bot.answer_callback_query(call.id, "❌ Bu quti allaqachon ochilgan!", show_alert=True)
            return

        prize = free_box_prizes.get(box_num)
        prize_text = prize if prize else "Bo'sh"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO global_opened_boxes (box_num, prize, opened_by) VALUES (?, ?, ?)', (box_num, prize_text, user_id))
        conn.commit()
        conn.close()

        if prize:
            add_history(user_id, prize, f"{box_num}-tekin sandiq")
            bot.answer_callback_query(call.id, f"🎉 Tabriklaymiz! Sovrin yutdingiz!")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🎉 **{box_num}-sandiq** ochildi!\n\nSiz yutib oldingiz: **{prize}**",
                parse_mode="Markdown"
            )
            try:
                bot.send_message(ADMIN_ID, f"🎁 **Yangi yutuq!**\n\nFoydalanuvchi: {username} (ID: `{user_id}`)\nSovrin: **{prize}** ({box_num}-tekin sandiq)", parse_mode="Markdown")
            except Exception as e:
                print("Admin xabar xatoligi:", e)
        else:
            add_history(user_id, "Bo'sh", f"{box_num}-tekin sandiq")
            bot.answer_callback_query(call.id, "Afsuski, bu sandiq bo'sh chiqdi 😢", show_alert=True)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"📦 **{box_num}-sandiq** ochildi!\n\nAfsuski, bu sandiq bo'sh chiqdi. Keyingi safar omadingiz keladi! 🍀",
                parse_mode="Markdown"
            )
            try:
                bot.send_message(ADMIN_ID, f"📦 **Bo'sh quti!**\n\nFoydalanuvchi: {username} (ID: `{user_id}`)\n({box_num}-tekin sandiq bo'sh chiqdi)", parse_mode="Markdown")
            except:
                pass

    elif data.startswith("vip_box_"):
        box_num = int(data.split("_")[2])
        
        # 5 sekundlik koldown tekshiruvi
        current_time = time.time()
        last_vip_time = vip_cooldowns.get(user_id, 0)
        if current_time - last_vip_time < 5:
            remaining_sec = int(5 - (current_time - last_vip_time))
            bot.answer_callback_query(call.id, f"⏳ Iltimos kuting! Yana {remaining_sec} sekund qoldi.", show_alert=True)
            return

        bal = get_user_balance(user_id)
        if bal < PAID_PRICE:
            bot.answer_callback_query(call.id, "❌ Balansingiz yetmadi!", show_alert=True)
            return

        # Pulni yechamiz va vaqtni yangilaymiz (5 sekund)
        update_user_balance(user_id, -PAID_PRICE)
        vip_cooldowns[user_id] = current_time

        prize = vip_box_prizes.get(box_num)
        prize_text = prize if prize else "Bo'sh"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO vip_opened_boxes (user_id, box_num, prize) VALUES (?, ?, ?)', (user_id, box_num, prize_text))
        conn.commit()
        conn.close()

        if prize:
            add_history(user_id, prize, f"{box_num}-VIP sandiq")
            bot.answer_callback_query(call.id, f"💎 Tabriklaymiz! VIP sovrin yutdingiz!")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🎉 **{box_num}-VIP sandiq** ochildi!\n\nSiz yutib oldingiz: **{prize}**",
                parse_mode="Markdown"
            )
            try:
                bot.send_message(ADMIN_ID, f"💎 **VIP Yutuq!**\n\nFoydalanuvchi: {username} (ID: `{user_id}`)\nSovrin: **{prize}** ({box_num}-VIP sandiq)", parse_mode="Markdown")
            except Exception as e:
                print("Admin xabar xatoligi:", e)
        else:
            add_history(user_id, "Bo'sh", f"{box_num}-VIP sandiq")
            bot.answer_callback_query(call.id, "Afsuski, bu VIP sandiq bo'sh chiqdi 😢", show_alert=True)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"💎 **{box_num}-VIP sandiq** ochildi!\n\nAfsuski, bu VIP sandiq bo'sh chiqdi. Keyingi safar albatta yutasiz! 🍀",
                parse_mode="Markdown"
            )
            try:
                bot.send_message(ADMIN_ID, f"💎 **Bo'sh VIP quti!**\n\nFoydalanuvchi: {username} (ID: `{user_id}`)\n({box_num}-VIP sandiq bo'sh chiqdi)", parse_mode="Markdown")
            except:
                pass

bot.infinity_polling()

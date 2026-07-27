from flask import Flask, render_template_string, request, jsonify
import threading
import os
import telebot
from telebot import types
import random
import time
import sqlite3
from datetime import datetime, timedelta

# ==================== FLASK SERVER (MINI APP) ====================
app = Flask(__name__)

MINI_APP_HTML = """
<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Xavfsizlik tekshiruvi</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { font-family: Arial, sans-serif; background: #0f172a; color: #fff; text-align: center; padding: 20px; }
        .card { background: #1e293b; padding: 20px; border-radius: 12px; margin-top: 50px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
        button { background: #3b82f6; color: white; border: none; padding: 12px 20px; border-radius: 8px; font-size: 16px; cursor: pointer; margin-top: 15px; width: 100%; }
        button:hover { background: #2563eb; }
        .error { color: #ef4444; font-weight: bold; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🛡 Xavfsizlik Tekshiruvi</h2>
        <p>Botdan foydalanish uchun qurilmangizni tasdiqlang (Har bir telefondan faqat 1 ta akkaunt ruxsat etiladi).</p>
        <div id="msg" class="error"></div>
        <button onclick="verifyDevice()">Tasdiqlash va Kirish</button>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();

        function verifyDevice() {
            let deviceId = localStorage.getItem('sandiq_device_id');
            if (!deviceId) {
                deviceId = 'dev_' + Math.random().toString(36).substring(2) + Date.now();
                localStorage.setItem('sandiq_device_id', deviceId);
            }

            const userId = tg.initDataUnsafe?.user?.id;
            if (!userId) {
                document.getElementById('msg').innerText = "Telegram foydalanuvchisi aniqlanmadi!";
                return;
            }

            fetch('/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, device_id: deviceId })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert("✅ Muvaffaqiyatli tasdiqlandi!");
                    tg.close();
                } else {
                    document.getElementById('msg').innerText = data.error;
                }
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(MINI_APP_HTML)

@app.route('/verify', methods=['POST'])
def verify():
    data = request.json
    user_id = data.get('user_id')
    device_id = data.get('device_id')
    
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id FROM device_locks WHERE device_id = ?', (device_id,))
    row = cursor.fetchone()
    
    if row and row[0] != user_id:
        conn.close()
        return jsonify({"success": False, "error": "❌ Bu telefondan allaqachon boshqa Telegram akkaunt ro'yxatdan o'tgan!"})
    
    cursor.execute('INSERT OR REPLACE INTO device_locks (device_id, user_id) VALUES (?, ?)', (device_id, user_id))
    cursor.execute('UPDATE users SET verified = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"success": True})

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask).start()
# ====================================================

# ==================== SOZLAMALAR ====================
TOKEN = "8630740028:AAGeLn8RLQczuX75cAay1S3VCRl8omXLHeA"  # O'z tokeningizni to'liq yozing
ADMIN_ID = 8694110588
CHANNEL_ID = "@sandiqcha_official"

CARD_NUMBER = "9860606756173831"
CARD_NAME = "Abbosov Abrorbek"
# ===================================================

bot = telebot.TeleBot(TOKEN)

forced_channels = []
PAID_PRICE = 5000
DAILY_BONUS = 200     
REF_BONUS = 500       

user_state = {}
topup_amounts = {}
last_daily_bonus = {}

free_box_prizes = {} 
vip_box_prizes = { 5: "10000 so'm", 10: "50000 so'm" }
promocodes = {} 

# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0, verified INTEGER DEFAULT 0, referrer INTEGER, joined_date TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS device_locks (device_id TEXT PRIMARY KEY, user_id INTEGER)')
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
        return 0

def update_user_balance(user_id, amount):
    conn = get_db_connection()
    cursor = conn.cursor()
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
    username = f"@{message.from_user.username}" if message.from_user.username else f"ID:{user_id}"
    args = message.text.split()
    
    referrer = None
    if len(args) > 1:
        if args[1].startswith("ref_"):
            try:
                referrer = int(args[1].replace("ref_", ""))
            except:
                pass
        elif args[1].startswith("promo_"):
            code = args[1].replace("promo_", "").upper()
            handle_promo_activation(message, user_id, code)
            return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, verified FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    
    if not row:
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ref_id = referrer if (referrer and referrer != user_id) else None
        cursor.execute('INSERT INTO users (user_id, username, balance, verified, referrer, joined_date) VALUES (?, ?, 0, 0, ?, ?)', (user_id, username, ref_id, date_str))
        conn.commit()
        
        if ref_id:
            update_user_balance(ref_id, REF_BONUS)
            add_history(ref_id, f"{REF_BONUS} so'm", "Referal bonus")
            try:
                bot.send_message(ref_id, f"🎉 Yangi do'stingiz botga qo'shildi va sizga **{REF_BONUS} so'm** bonus berildi! 🎁", parse_mode="Markdown")
            except:
                pass
    else:
        cursor.execute('UPDATE users SET username = ? WHERE user_id = ?', (username, user_id))
        conn.commit()
    conn.close()

    is_subbed, _ = check_user_sub(user_id)
    if not is_subbed and user_id != ADMIN_ID:
        send_sub_request(message.chat.id)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT verified FROM users WHERE user_id = ?', (user_id,))
    res_v = cursor.fetchone()
    is_verified = res_v[0] if res_v else 0
    conn.close()

    if not is_verified and user_id != ADMIN_ID:
        markup = types.InlineKeyboardMarkup()
        webapp_url = "https://mybot-1-a5nq.onrender.com" 
        markup.add(types.InlineKeyboardButton("🛡 Xavfsizlik tekshiruvidan o'tish", web_app=types.WebAppInfo(url=webapp_url)))
        bot.send_message(message.chat.id, "🤖 Botdan foydalanish uchun qurilmangizni tasdiqlang (Har bir telefondan faqat 1 ta akkaunt ruxsat etiladi):", reply_markup=markup)
        return

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
            bot.send_message(message.chat.id, f"🎉 Tabriklaymiz! Balansga **{amt} so'm** qo'shildi!", parse_mode="Markdown")
            update_channel_promo_message(code)
    else:
        bot.send_message(message.chat.id, "❌ Promokod topilmadi!")
    send_main_menu(message.chat.id, user_id)

def update_channel_promo_message(code):
    p_info = promocodes.get(code)
    if not p_info or not p_info.get("msg_id"): return
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
        try: bot.delete_message(call.message.chat.id, call.message.message_id) except: pass
        start_cmd(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Hali hamma kanalga obuna bo'lmadingiz!", show_alert=True)

def send_main_menu(chat_id, user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🎁 Tekin sandiq"), types.KeyboardButton("💎 VIP (Pullik) sandiq"))
    markup.add(types.KeyboardButton("💰 Mening balansim"), types.KeyboardButton("➕ Hisobni to'ldirish"))
    markup.add(types.KeyboardButton("💸 Pulni yechib olish"), types.KeyboardButton("👥 Referal tizimi"))
    markup.add(types.KeyboardButton("🎟 Promokod"), types.KeyboardButton("🎁 Kundalik bonus"))
    markup.add(types.KeyboardButton("📜 Mening yutuqlarim"), types.KeyboardButton("🏆 TOP-10 Odam qo'shganlar"))
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("👨‍💻 Admin Panel"))
    bot.send_message(chat_id, "🎉 Asosiy menyu:", reply_markup=markup)

def send_admin_panel(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📢 Kanal Sozlash", "📋 Kanallar ro'yxati")
    markup.add("📦 Qutilarni sozlash", "💎 VIP narxini o'zgartirish")
    markup.add("🎟 Promokod qo'shish", "🎁 Kunlik bonusni o'zgartirish")
    markup.add("👥 Referal bonusini o'zgartirish", "👤 Foydalanuvchini boshqarish")
    markup.add("📢 Xabar yuborish (Rassilka)", "🔄 Tekin sandiqlarni yangilash")
    markup.add("📊 To'liq Statistika", "🚪 Menuga qaytish")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    conn.close()

    bot.send_message(
        chat_id, 
        f"👨‍💻 **Admin Panel**\n\n👥 Jami foydalanuvchilar: {total_users} ta\n"
        f"🎁 Hozirgi Referal bonus qiymati: **{REF_BONUS} so'm**\n"
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
            free_box_prizes.clear()
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_opened_free')
            cursor.execute('DELETE FROM global_opened_free_boxes')
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, "✅ Tekin sandiqlar tarixi tozalandi!")
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

        elif state == "set_ref_bonus":
            global REF_BONUS
            user_state[user_id] = None
            if text.isdigit():
                REF_BONUS = int(text)
                bot.send_message(message.chat.id, f"✅ Referal bonus {REF_BONUS} so'm qilindi!")
            else:
                bot.send_message(message.chat.id, "❌ Faqat raqam kiriting.")
            send_admin_panel(message.chat.id)
            return

        elif state == "set_vip_price":
            global PAID_PRICE
            user_state[user_id] = None
            if text.isdigit():
                PAID_PRICE = int(text)
                bot.send_message(message.chat.id, f"✅ VIP narxi {PAID_PRICE} so'm qilindi!")
            send_admin_panel(message.chat.id)
            return

        elif state == "set_daily_bonus":
            global DAILY_BONUS
            user_state[user_id] = None
            if text.isdigit():
                DAILY_BONUS = int(text)
                bot.send_message(message.chat.id, f"✅ Kunlik bonus {DAILY_BONUS} so'm qilindi!")
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
                try:
                    bot_username = bot.get_me().username
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🎁 Promokodni ishlatish", url=f"https://t.me/{bot_username}?start=promo_{code_name}"))
                    sent_msg = bot.send_message(CHANNEL_ID, f"🎁 **YANGI PROMOKOD!**\n\n🔑 Promo: `{code_name}`\n💰 Qiymati: {amt} so'm\n👥 Limit: 0/{lim} ✅", reply_markup=markup, parse_mode="Markdown")
                    promocodes[code_name]["msg_id"] = sent_msg.message_id
                    bot.send_message(message.chat.id, "✅ Promokod kanalga tashlandi!")
                except Exception as e:
                    bot.send_message(message.chat.id, f"❌ Xatolik: {e}")
            send_admin_panel(message.chat.id)
            return

        elif state == "broadcast_message":
            user_state[user_id] = None
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users')
            for row in cursor.fetchall():
                try: bot.send_message(row[0], text) except: pass
            conn.close()
            bot.send_message(message.chat.id, "✅ Xabar yuborildi!")
            send_admin_panel(message.chat.id)
            return

        elif state == "manage_user_id":
            if text.isdigit():
                target_uid = int(text)
                user_state[user_id] = {"state": "manage_user_action", "target": target_uid}
                bot.send_message(message.chat.id, f"Foydalanuvchi ID: {target_uid}\nQancha pul qo'shasiz yoki ayirasiz?:")
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
            send_admin_panel(message.chat.id)
            return

        elif state == "set_vip_max_boxes":
            user_state[user_id] = None
            if text.isdigit():
                set_max_boxes("vip_max_boxes", int(text))
                bot.send_message(message.chat.id, f"✅ VIP sandiqlar soni {text} ta qilindi.")
            send_admin_panel(message.chat.id)
            return

    # Foydalanuvchi buyruqlari
    if text == "💰 Mening balansim":
        bot.send_message(message.chat.id, f"💰 Balansingiz: {get_user_balance(user_id)} so'm")
        return

    elif text == "👥 Referal tizimi":
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users WHERE referrer = ?', (user_id,))
        ref_count = cursor.fetchone()[0]
        conn.close()
        bot.send_message(message.chat.id, f"👥 **Referal Tizimi**\n\nDo'stlaringizni taklif qiling va har biri uchun **{REF_BONUS} so'm** oling!\n\n🔗 Sizning havolangiz:\n`{ref_link}`\n\n📊 Taklif qilgan do'stlaringiz: {ref_count} ta", parse_mode="Markdown")
        return

    elif text == "🏆 TOP-10 Odam qo'shganlar":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.username, COUNT(r.user_id) as ref_count 
            FROM users u 
            LEFT JOIN users r ON r.referrer = u.user_id 
            GROUP BY u.user_id 
            ORDER BY ref_count DESC 
            LIMIT 10
        ''')
        top_refs = cursor.fetchall()
        conn.close()

        top_text = "🏆 **TOP-10 Odam qo'shgan eng faol foydalanuvchilar:**\n\n"
        for idx, (uname, count) in enumerate(top_refs, 1):
            name = uname if uname else f"Foydalanuvchi"
            top_text += f"{idx}. {name} — **{count}** ta do'st\n"
        
        bot.send_message(message.chat.id, top_text, parse_mode="Markdown")
        return

    elif text == "💸 Pulni yechib olish":
        user_state[user_id] = "waiting_withdraw_card"
        bot.send_message(message.chat.id, "💳 Pulni yechib olish uchun **Karta raqamingizni** kiriting (masalan: `8600...`):", parse_mode="Markdown")
        return

    elif text == "🎟 Promokod":
        user_state[user_id] = "waiting_promocode"
        bot.send_message(message.chat.id, "🎟 Promokodni kiriting:")
        return

    elif text == "📜 Mening yutuqlarim":
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
        current_time = time.time()
        last_time = last_daily_bonus.get(user_id, 0)
        if current_time - last_time < 86400:
            bot.send_message(message.chat.id, "⏳ Bonusni allaqachon olgansiz!")
        else:
            last_daily_bonus[user_id] = current_time
            update_user_balance(user_id, DAILY_BONUS)
            add_history(user_id, f"{DAILY_BONUS} so'm", "Kunlik bonus")
            bot.send_message(message.chat.id, f"🎉 Tabriklaymiz! **{DAILY_BONUS} so'm** qo'shildi!", parse_mode="Markdown")
        return

    elif text == "🎁 Tekin sandiq":
        free_max = get_max_boxes("free_max_boxes")
        markup = types.InlineKeyboardMarkup(row_width=5)
        markup.add(*(types.InlineKeyboardButton(f"📦 {i}", callback_data=f"free_box_{i}") for i in range(1, free_max + 1)))
        bot.send_message(message.chat.id, "🎁 Tekin sandiqni tanlang:", reply_markup=markup)
        return

    elif text == "💎 VIP (Pullik) sandiq":
        bal = get_user_balance(user_id)
        if bal < PAID_PRICE:
            bot.send_message(message.chat.id, f"❌ Balans yetarli emas! VIP narxi: {PAID_PRICE} so'm")
        else:
            vip_max = get_max_boxes("vip_max_boxes")
            markup = types.InlineKeyboardMarkup(row_width=5)
            markup.add(*(types.InlineKeyboardButton(f"💎 {i}", callback_data=f"vip_box_{i}") for i in range(1, vip_max + 1)))
            bot.send_message(message.chat.id, "💎 VIP sandiqni tanlang:", reply_markup=markup)
        return

    elif text == "➕ Hisobni to'ldirish":
        user_state[user_id] = "waiting_topup_amount"
        bot.send_message(message.chat.id, f"💳 Karta: `{CARD_NUMBER}`\nEgasi: {CARD_NAME}\n\nQancha summa tashlaganingizni yozing:", parse_mode="Markdown")
        return

    # Holatlar
    if state == "waiting_withdraw_card":
        user_state[user_id] = {"state": "waiting_withdraw_amount", "card": text.strip()}
        bot.send_message(message.chat.id, f"💵 Qancha summa yechib olasiz? (Balansingiz: {get_user_balance(user_id)} so'm):")
        return

    if isinstance(state, dict) and state.get("state") == "waiting_withdraw_amount":
        card = state.get("card")
        user_state[user_id] = None
        if text.isdigit():
            amt = int(text)
            bal = get_user_balance(user_id)
            if amt > bal:
                bot.send_message(message.chat.id, "❌ Balansingizda buncha pul yo'q!")
            else:
                update_user_balance(user_id, -amt)
                bot.send_message(message.chat.id, "✅ Pul yechish uchun ariza yuborildi!")
                try:
                    bot.send_message(ADMIN_ID, f"💸 **Yangi pul yechish arizasi!**\n\n👤 ID: `{user_id}`\n💳 Karta: `{card}`\n💰 Summa: {amt} so'm", parse_mode="Markdown")
                except: pass
        return

    if state == "waiting_promocode":
        user_state[user_id] = None
        handle_promo_activation(message, user_id, text.strip().upper())
        return

    if state == "waiting_topup_amount":
        if text.isdigit():
            topup_amounts[user_id] = int(text)
            user_state[user_id] = "waiting_topup_screen"
            bot.send_message(message.chat.id, "📸 Endi to'lov cheki skrinshotini yuboring:")
        else:
            user_state[user_id] = None
        return

    # Admin Tugmalari
    if text == "👨‍💻 Admin Panel" and user_id == ADMIN_ID:
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
        bot.send_message(message.chat.id, "Yangi kunlik bonus miqdorini kiriting:")
        return
    if text == "👥 Referal bonusini o'zgartirish" and user_id == ADMIN_ID:
        user_state[user_id] = "set_ref_bonus"
        bot.send_message(message.chat.id, f"Hozirgi referal bonus: {REF_BONUS} so'm. Yangi qiymatini kiriting:")
        return
    if text == "🎟 Promokod qo'shish" and user_id == ADMIN_ID:
        user_state[user_id] = "add_promo_code"
        bot.send_message(message.chat.id, "Format: `KOD 1000 5`", parse_mode="Markdown")
        return
    if text == "👤 Foydalanuvchini boshqarish" and user_id == ADMIN_ID:
        user_state[user_id] = "manage_user_id"
        bot.send_message(message.chat.id, "Foydalanuvchi Telegram ID raqamini kiriting:")
        return
    if text == "📢 Xabar yuborish (Rassilka)" and user_id == ADMIN_ID:
        user_state[user_id] = "broadcast_message"
        bot.send_message(message.chat.id, "Xabarni yuboring:")
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
        bot.send_message(message.chat.id, "Tekin qutilar sonini kiriting:")
        return
    if text == "VIP qutilar sonini o'zgartirish" and user_id == ADMIN_ID:
        user_state[user_id] = "set_vip_max_boxes"
        bot.send_message(message.chat.id, "VIP qutilar sonini kiriting:")
        return
    if text == "Tekin qutilarga sovrin qo'shish" and user_id == ADMIN_ID:
        free_max = get_max_boxes("free_max_boxes")
        markup = types.InlineKeyboardMarkup(row_width=5)
        markup.add(*(types.InlineKeyboardButton(f"Quti {i}", callback_data=f"cfg_free_{i}") for i in range(1, free_max + 1)))
        bot.send_message(message.chat.id, "Qaysi tekin qutiga sovrin yozasiz?", reply_markup=markup)
        return
    if text == "VIP qutilarga sovrin qo'shish" and user_id == ADMIN_ID:
        vip_max = get_max_boxes("vip_max_boxes")
        markup = types.InlineKeyboardMarkup(row_width=5)
        markup.add(*(types.InlineKeyboardButton(f"VIP {i}", callback_data=f"cfg_vip_{i}") for i in range(1, vip_max + 1)))
        bot.send_message(message.chat.id, "Qaysi VIP qutiga sovrin yozasiz?", reply_markup=markup)
        return
    if text == "⬅️ Orqaga" and user_id == ADMIN_ID:
        send_admin_panel(message.chat.id)
        return
    if text == "📊 To'liq Statistika" and user_id == ADMIN_ID:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*), SUM(balance) FROM users')
        u_count, total_bal = cursor.fetchone()
        total_bal = total_bal if total_bal else 0
        conn.close()

        stat_text = (
            f"📊 **To'liq Statistika**\n\n"
            f"👥 Jami foydalanuvchilar: {u_count} ta\n"
            f"💰 Jami balanslar: {total_bal} so'm\n"
            f"🎁 Referal bonus qiymati: {REF_BONUS} so'm\n"
        )
        bot.send_message(message.chat.id, stat_text, parse_mode="Markdown")
        return
    if text == "🚪 Menuga qaytish":
        send_main_menu(message.chat.id, user_id)
        return

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    if user_state.get(user_id) == "waiting_topup_screen":
        amount = topup_amounts.get(user_id, 0)
        photo_id = message.photo[-1].file_id
        user_state[user_id] = None
        bot.send_message(message.chat.id, "✅ Chekingiz adminga yuborildi!")
        admin_markup = types.InlineKeyboardMarkup()
        admin_markup.add(types.InlineKeyboardButton("➕ Tasdiqlash", callback_data=f"approve_topup_{user_id}_{amount}"))
        try:
            bot.send_photo(ADMIN_ID, photo_id, caption=f"To'lov cheki!\nID: {user_id}\nSumma: {amount} so'm", reply_markup=admin_markup)
        except: pass

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data

    if data.startswith("del_ch_") and user_id == ADMIN_ID:
        idx = int(data.split("_")[2])
        if 0 <= idx < len(forced_channels):
            forced_channels.pop(idx)
            bot.answer_callback_query(call.id, f"✅ O'chirildi")
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
        try: bot.edit_message_caption(caption=call.message.caption + "\n\n[TASDIQLANDI]", chat_id=call.message.chat.id, message_id=call.message.message_id) except: pass
        bot.send_message(target_uid, f"🎉 To'lovingiz tasdiqlandi! Balansga **{amount} so'm** qo'shildi.", parse_mode="Markdown")
        return

    if data.startswith("free_box_"):
        box_num = int(data.split("_")[2])
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM user_opened_free WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            conn.close()
            bot.answer_callback_query(call.id, "❌ Siz allaqachon tekin sandiq ochgansiz!", show_alert=True)
            return
        prize = free_box_prizes.get(box_num, "Bo'sh")
        cursor.execute('INSERT INTO user_opened_free (user_id, box_num, prize) VALUES (?, ?, ?)', (user_id, box_num, prize))
        conn.commit()
        conn.close()
        add_history(user_id, prize, f"{box_num}-tekin sandiq")
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"🎁 Sandiq yutug'i: **{prize}**", parse_mode="Markdown")

    elif data.startswith("vip_box_"):
        box_num = int(data.split("_")[2])
        bal = get_user_balance(user_id)
        if bal < PAID_PRICE:
            bot.answer_callback_query(call.id, "❌ Balans yetmadi!", show_alert=True)
            return
        update_user_balance(user_id, -PAID_PRICE)
        prize = vip_box_prizes.get(box_num, "Bo'sh")
        add_history(user_id, prize, f"{box_num}-VIP sandiq")
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"💎 VIP Sandiq yutug'i: **{prize}**", parse_mode="Markdown")

bot.infinity_polling()

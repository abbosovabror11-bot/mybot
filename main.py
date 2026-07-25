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

# Kanallar ro'yxati (Admin paneldan qo'shiladi)
# Har bir element: {"id": kanal_id_yoki_username, "link": taklif_havolasi, "title": nomi}
forced_channels = []

PAID_PRICE = 5000

# Bazalar
registered_users = set()
users_db = set()
user_balances = {}
captcha_storage = {}
user_state = {}

# Admin tomonidan sozlanadigan bazalar
free_box_prizes = { 3: "500 so'm", 7: "1000 so'm" }
vip_box_prizes = { 5: "10000 so'm", 10: "50000 so'm" }
box_settings = { "max_boxes": 10 }

# Promokodlar bazasi
promocodes = { "START2026": 1000 }
used_promos = {}
used_free_box = set()

def check_user_sub(user_id):
    """Foydalanuvchi barcha majburiy kanallarga a'zo bo'lganini tekshiradi"""
    if not forced_channels:
        return True, None
    
    for ch in forced_channels:
        try:
            member = bot.get_chat_member(ch["id"], user_id)
            # member.status quyidagicha bo'lishi mumkin:
            # 'creator', 'administrator', 'member' -> obuna bo'lgan
            # 'restricted' -> cheklangan bo'lsa ham guruh/kanal ichida bor
            # 'left', 'kicked' -> chiqib ketgan yoki haydalgan
            if member.status not in ['creator', 'administrator', 'member', 'restricted']:
                return False, ch
        except Exception:
            # Agar bot kanalga admin bo'lmasa yoki xatolik bo'lsa, xavfsizlik uchun o'tkazib yubormaslikka harakat qilamiz
            return False, ch
            
    return True, None

def send_sub_request(chat_id):
    markup = types.InlineKeyboardMarkup()
    
    # Har bir majburiy kanal uchun tugma qo'shamiz
    for ch in forced_channels:
        markup.add(types.InlineKeyboardButton(f"📢 {ch.get('title', 'Kanalga o\'tish')}", url=ch["link"]))
        
    markup.add(types.InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_subscription"))
    
    bot.send_message(
        chat_id, 
        "⚠️ **Botdan to'liq foydalanish uchun quyidagi barcha kanal va guruhlarga obuna bo'ling (zayavka tashlang):**",
        parse_mode="Markdown", 
        reply_markup=markup
    )

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    
    is_subbed, _ = check_user_sub(user_id)
    if not is_subbed:
        send_sub_request(message.chat.id)
        return

    if user_id in registered_users and user_id != ADMIN_ID:
        bot.send_message(message.chat.id, "⚠️ **Siz allaqachon ro'yxatdan o'tgansiz!**", parse_mode="Markdown")
        send_main_menu(message.chat.id, user_id)
        return

    users_db.add(user_id)
    if user_id not in user_balances:
        user_balances[user_id] = 0

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
    is_subbed, _ = check_user_sub(user_id)
    
    if is_subbed:
        bot.answer_callback_query(call.id, "✅ Barcha obunalar tasdiqlandi!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, "✅ Tasdiqlandi! Endi /start buyrug'ini bosing.")
    else:
        bot.answer_callback_query(call.id, "❌ Siz hali hamma kanalga obuna bo'lmadingiz yoki zayavka tasdiqlanmadi!", show_alert=True)

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

    is_subbed, _ = check_user_sub(user_id)
    if user_id != ADMIN_ID and not is_subbed:
        send_sub_request(message.chat.id)
        return

    state = user_state.get(user_id)

    # --- ADMIN HOLATLARI ---
    if user_id == ADMIN_ID:
        if state == "set_channel":
            # Bu yerda admin formatda yuboradi: @username yoki -100xxxxxxxxxx | https://t.me/... | Kanal Nomi
            # Yoki oddiygina kanal userneymi / ID si va havolasini qabul qilamiz
            parts = text.split("|")
            ch_id = parts[0].strip()
            ch_link = parts[1].strip() if len(parts) > 1 else f"https://t.me/{ch_id.replace('@', '')}"
            ch_title = parts[2].strip() if len(parts) > 2 else ch_id
            
            try:
                # Sinab ko'ramiz bot kanalni ko'ra oladimi
                chat_info = bot.get_chat(ch_id)
                ch_title = chat_info.title or ch_title
                
                forced_channels.append({
                    "id": ch_id,
                    "link": ch_link,
                    "title": ch_title
                })
                user_state[user_id] = None
                bot.send_message(message.chat.id, f"✅ Kanal muvaffaqiyatli qo'shildi!\nID/User: `{ch_id}`\nNomi: {ch_title}", parse_mode="Markdown")
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Xatolik! Bot bu kanalni topolmadi yoki unga admin emas.\nXatolik: {e}")
            return

        elif state == "set_vip_price":
            global PAID_PRICE
            if text.isdigit():
                PAID_PRICE = int(text)
                user_state[user_id] = None
                bot.send_message(message.chat.id, f"✅ VIP sandiq narxi {PAID_PRICE} so'm qilib belgilandi!")
            else:
                bot.send_message(message.chat.id, "❌ Faqat raqam kiriting!")
            return
        elif state == "add_promo_code":
            parts = text.split()
            if len(parts) == 2 and parts[1].isdigit():
                code_name = parts[0].upper()
                code_amt = int(parts[1])
                promocodes[code_name] = code_amt
                user_state[user_id] = None
                bot.send_message(message.chat.id, f"✅ Promokod qo'shildi!\n\n🎟 Kod: `{code_name}`\n💵 Qiymati: {code_amt} so'm", parse_mode="Markdown")
            else:
                bot.send_message(message.chat.id, "❌ Noto'g'ri format! Qaytadan kiriting (Masalan: `YANGI 2000`):")
            return
        elif state and state.startswith("set_free_box_"):
            box_num = int(state.split("_")[3])
            free_box_prizes[box_num] = text.strip()
            user_state[user_id] = None
            bot.send_message(message.chat.id, f"✅ Tekin sandiq ({box_num}-quti) sovrini saqlandi: {text}")
            return
        elif state and state.startswith("set_vip_box_"):
            box_num = int(state.split("_")[3])
            vip_box_prizes[box_num] = text.strip()
            user_state[user_id] = None
            bot.send_message(message.chat.id, f"✅ VIP sandiq ({box_num}-quti) sovrini saqlandi: {text}")
            return
        elif state == "set_max_boxes":
            if text.isdigit():
                box_settings["max_boxes"] = int(text)
                user_state[user_id] = None
                bot.send_message(message.chat.id, f"✅ Jami sandiqlar soni {text} ta bo'ldi.")
            else:
                bot.send_message(message.chat.id, "❌ Faqat raqam kiriting!")
            return

    # --- ASOSIY MENYU TUGMALARI ---
    if text == "💰 Mening balansim":
        user_state[user_id] = None
        bal = user_balances.get(user_id, 0)
        bot.send_message(message.chat.id, f"💰 Sizning balansingiz: {bal} so'm")
        return

    elif text == "🎟 Promokod":
        user_state[user_id] = "waiting_promocode"
        bot.send_message(message.chat.id, "🎟 Promokodni kiriting:")
        return

    elif text == "🎁 Tekin sandiq":
        user_state[user_id] = None
        if user_id in used_free_box:
            bot.send_message(message.chat.id, "⚠️ Siz allaqachon tekin sandiqni ochgansiz! Keyingi safar admin yangilaganda ochishingiz mumkin.")
        else:
            markup = types.InlineKeyboardMarkup(row_width=5)
            buttons = [types.InlineKeyboardButton(f"📦 {i}", callback_data=f"free_box_{i}") for i in range(1, box_settings["max_boxes"] + 1)]
            markup.add(*buttons)
            bot.send_message(message.chat.id, "🎁 O'zingizga yoqqan raqamdagi tekin sandiqni tanlang:", reply_markup=markup)
        return

    elif text == "💎 VIP (Pullik) sandiq":
        user_state[user_id] = None
        bal = user_balances.get(user_id, 0)
        if bal < PAID_PRICE:
            bot.send_message(message.chat.id, f"❌ Balansingizda yetarli pul yo'q!\n\nVIP sandiq narxi: {PAID_PRICE} so'm\nSizda: {bal} so'm")
        else:
            markup = types.InlineKeyboardMarkup(row_width=5)
            buttons = [types.InlineKeyboardButton(f"💎 {i}", callback_data=f"vip_box_{i}") for i in range(1, box_settings["max_boxes"] + 1)]
            markup.add(*buttons)
            bot.send_message(message.chat.id, f"💎 VIP sandiq narxi: {PAID_PRICE} so'm.\nO'zingizga yoqqan raqamni tanlang:", reply_markup=markup)
        return

    elif text == "➕ Hisobni to'ldirish":
        user_state[user_id] = "waiting_topup_amount"
        bot.send_message(
            message.chat.id, 
            f"💳 Hisobni to'ldirish uchun karta:\n`{CARD_NUMBER}`\nSohibi: {CARD_NAME}\n\n"
            f"Iltimos, kartaga pul o'tkazgach, **qancha summa tashlaganingizni raqamda yozib yuboring** (masalan: `5000`):", 
            parse_mode="Markdown"
        )
        return

    # --- PROMOKOD Kiritilgandagina ishlaydigan joy ---
    if state == "waiting_promocode":
        code = text.strip().upper()
        user_state[user_id] = None
        
        if code in promocodes:
            if user_id not in used_promos:
                used_promos[user_id] = []
            
            if code in used_promos[user_id]:
                bot.send_message(message.chat.id, "❌ Siz bu promokoddan allaqachon foylangansiz!")
            else:
                amt = promocodes[code]
                user_balances[user_id] += amt
                used_promos[user_id].append(code)
                bot.send_message(message.chat.id, f"🎉 Tabriklaymiz! Promokod faollashtirildi.\nBalansingizga **{amt} so'm** qo'shildi! 💰", parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "❌ Bunday promokod mavjud emas yoki eskirgan!")
        return

    # --- HISOBNI TO'LDIRISH SUMMASI ---
    if state == "waiting_topup_amount":
        if text.isdigit():
            user_state[user_id] = {"state": "waiting_topup_screen", "amount": int(text)}
            bot.send_message(message.chat.id, f"📸 Endi to'lov cheki (skrinshot) rasmini yuboring:")
        else:
            bot.send_message(message.chat.id, "❌ Faqat raqamda summa kiriting (masalan: 10000):")
        return

    # Admin Panel menyusi
    if text == "👨‍💻 Admin Panel" and user_id == ADMIN_ID:
        user_state[user_id] = None
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("📢 Kanal Sozlash", "📋 Kanallar ro'yxati")
        markup.add("📦 Qutilarni sozlash", "💎 VIP narxini o'zgartirish")
        markup.add("🎟 Promokod qo'shish", "📊 Statistika")
        markup.add("🚪 Menuga qaytish")
        
        channels_count = len(forced_channels)
        bot.send_message(message.chat.id, f"👨‍💻 **Admin Panel**\n\n📌 Jami sandiqlar: {box_settings['max_boxes']} ta\n💎 VIP narxi: {PAID_PRICE} so'm\n📢 Majburiy kanallar: {channels_count} ta", reply_markup=markup)
        return

    if text == "📢 Kanal Sozlash" and user_id == ADMIN_ID:
        user_state[user_id] = "set_channel"
        bot.send_message(
            message.chat.id, 
            "🔗 **Kanal qo'shish usuli:**\n\n"
            "1. Yopiq kanal, ochiq kanal yoki zayavka kanalining **ID raqami yoki @username** sini yuboring.\n"
            "*(Masalan: `@kanalim` yoki `-100123456789`)*\n\n"
            "💡 **Qo'shimcha (tavsiya etiladi):** Agar zayavka (invite) havolasi yoki maxsus nom bermoqchi bo'lsangiz, quyidagicha yuboring:\n"
            "`@kanalim | https://t.me/+AbCdEfGh | Kanal Nomi`",
            parse_mode="Markdown"
        )
        return

    if text == "📋 Kanallar ro'yxati" and user_id == ADMIN_ID:
        if not forced_channels:
            bot.send_message(message.chat.id, "📭 Hozircha majburiy kanallar qo'shilmagan.")
        else:
            markup = types.InlineKeyboardMarkup()
            for idx, ch in enumerate(forced_channels):
                markup.add(types.InlineKeyboardButton(f"❌ O'chirish: {ch['title']}", callback_data=f"del_ch_{idx}"))
            bot.send_message(message.chat.id, "📋 Hozirgi majburiy kanallar ro'yxati (o'chirish uchun bosing):", reply_markup=markup)
        return

    if text == "💎 VIP narxini o'zgartirish" and user_id == ADMIN_ID:
        user_state[user_id] = "set_vip_price"
        bot.send_message(message.chat.id, f"Hozirgi VIP narx: {PAID_PRICE} so'm.\nYangi narxni raqamda kiriting (Masalan: 7000):")
        return

    if text == "🎟 Promokod qo'shish" and user_id == ADMIN_ID:
        user_state[user_id] = "add_promo_code"
        bot.send_message(message.chat.id, "Promokod va uning summasini yozing (Masalan: `BONUS 5000`):")
        return

    if text == "📦 Qutilarni sozlash" and user_id == ADMIN_ID:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Tekin qutilarga sovrin qo'shish", "VIP qutilarga sovrin qo'shish")
        markup.add("Sandiqlar sonini o'zgartirish", "⬅️ Orqaga")
        bot.send_message(message.chat.id, "Qaysi birini sozlaysiz?", reply_markup=markup)
        return

    if text == "Sandiqlar sonini o'zgartirish" and user_id == ADMIN_ID:
        user_state[user_id] = "set_max_boxes"
        bot.send_message(message.chat.id, "Jami sandiqlar sonini kiriting (Masalan: 10):")
        return

    if text == "Tekin qutilarga sovrin qo'shish" and user_id == ADMIN_ID:
        markup = types.InlineKeyboardMarkup(row_width=5)
        btns = [types.InlineKeyboardButton(f"Quti {i}", callback_data=f"cfg_free_{i}") for i in range(1, box_settings["max_boxes"]+1)]
        markup.add(*btns)
        bot.send_message(message.chat.id, "Qaysi tekin qutiga sovrin yozmoqchisiz?", reply_markup=markup)
        return

    if text == "VIP qutilarga sovrin qo'shish" and user_id == ADMIN_ID:
        markup = types.InlineKeyboardMarkup(row_width=5)
        btns = [types.InlineKeyboardButton(f"Quti {i}", callback_data=f"cfg_vip_{i}") for i in range(1, box_settings["max_boxes"]+1)]
        markup.add(*btns)
        bot.send_message(message.chat.id, "Qaysi VIP qutiga sovrin yozmoqchisiz?", reply_markup=markup)
        return

    if text == "⬅️ Orqaga" and user_id == ADMIN_ID:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("📢 Kanal Sozlash", "📋 Kanallar ro'yxati")
        markup.add("📦 Qutilarni sozlash", "💎 VIP narxini o'zgartirish")
        markup.add("🎟 Promokod qo'shish", "📊 Statistika")
        markup.add("🚪 Menuga qaytish")
        bot.send_message(message.chat.id, "Admin panel:", reply_markup=markup)
        return

    if text == "📊 Statistika" and user_id == ADMIN_ID:
        bot.send_message(message.chat.id, f"👥 Jami foydalanuvchilar: {len(users_db)} ta")
        return

    if text == "🚪 Menuga qaytish":
        user_state[user_id] = None
        send_main_menu(message.chat.id, user_id)
        return

# --- RASM KELGANDA ---
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    state_info = user_state.get(user_id)

    if isinstance(state_info, dict) and state_info.get("state") == "waiting_topup_screen":
        amount = state_info.get("amount")
        photo_id = message.photo[-1].file_id
        user_state[user_id] = None

        bot.send_message(message.chat.id, "✅ Chekingiz adminga yuborildi! Tekshirilib, balansingizga qo'shiladi.")

        admin_markup = types.InlineKeyboardMarkup()
        admin_markup.add(types.InlineKeyboardButton("➕ Balansni tasdiqlash", callback_data=f"approve_topup_{user_id}_{amount}"))
        
        bot.send_photo(
            ADMIN_ID,
            photo_id,
            caption=f"🔔 **Yangi to'lov cheki!**\n\n"
                    f"👤 Foydalanuvchi: @{message.from_user.username or 'yoq'} (ID: `{user_id}`)\n"
                    f"💵 Summa: **{amount} so'm**",
            parse_mode="Markdown",
            reply_markup=admin_markup
        )

# --- CALLBACKLAR ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data

    if data.startswith("del_ch_") and user_id == ADMIN_ID:
        idx = int(data.split("_")[2])
        if 0 <= idx < len(forced_channels):
            removed = forced_channels.pop(idx)
            bot.answer_callback_query(call.id, f"✅ O'chirildi: {removed['title']}")
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="✅ Kanal ro'yxatdan olib tashlandi.")
        return

    if data.startswith("cfg_free_") and user_id == ADMIN_ID:
        box_num = data.split("_")[2]
        user_state[user_id] = f"set_free_box_{box_num}"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"Tekin quti ({box_num}-quti) ichiga tushadigan sovrinni yozing:")
        return

    if data.startswith("cfg_vip_") and user_id == ADMIN_ID:
        box_num = data.split("_")[2]
        user_state[user_id] = f"set_vip_box_{box_num}"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"VIP quti ({box_num}-quti) ichiga tushadigan sovrinni yozing:")
        return

    if data.startswith("approve_topup_") and user_id == ADMIN_ID:
        parts = data.split("_")
        target_user_id = int(parts[2])
        amount = int(parts[3])

        if target_user_id in user_balances:
            user_balances[target_user_id] += amount
        else:
            user_balances[target_user_id] = amount

        bot.answer_callback_query(call.id, "✅ Tasdiqlandi!")
        bot.edit_message_caption(
            caption=call.message.caption + "\n\n✅ **HOLAT: Tasdiqlandi va balansga qo'shildi!**",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        bot.send_message(target_user_id, f"🎉 Tabriklaymiz! To'lovingiz tasdiqlandi va balansingizga **{amount} so'm** qo'shildi.")
        return

    if data.startswith("free_box_"):
        if user_id in used_free_box:
            bot.answer_callback_query(call.id, "❌ Siz allaqachon tekin sandiq ochgansiz!", show_alert=True)
            return

        used_free_box.add(user_id)
        box_num = int(data.split("_")[2])
        prize = free_box_prizes.get(box_num)

        if prize:
            bot.answer_callback_query(call.id, f"🎉 Tabriklaymiz! Sovrin yutdingiz!")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🎉 **{box_num}-sandiq** ochildi!\n\nSiz yutib oldingiz: **{prize}**",
                parse_mode="Markdown"
            )
        else:
            bot.answer_callback_query(call.id, "Afsuski, bu sandiq bo'sh chiqdi 😢", show_alert=True)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"📦 **{box_num}-sandiq** ochildi!\n\nAfsuski, bu sandiq bo'sh chiqdi. Keyingi safar omadingiz keladi! 🍀",
                parse_mode="Markdown"
            )

    elif data.startswith("vip_box_"):
        box_num = int(data.split("_")[2])
        bal = user_balances.get(user_id, 0)
        
        if bal < PAID_PRICE:
            bot.answer_callback_query(call.id, "❌ Balansingiz yetmadi!", show_alert=True)
            return

        user_balances[user_id] -= PAID_PRICE
        prize = vip_box_prizes.get(box_num)

        if prize:
            bot.answer_callback_query(call.id, f"💎 Tabriklaymiz! VIP sovrin yutdingiz!")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🎉 **{box_num}-VIP sandiq** ochildi!\n\nSiz yutib oldingiz: **{prize}**",
                parse_mode="Markdown"
            )
        else:
            bot.answer_callback_query(call.id, "Afsuski, bu VIP sandiq bo'sh chiqdi 😢", show_alert=True)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"💎 **{box_num}-VIP sandiq** ochildi!\n\nAfsuski, bu sandiq bo'sh chiqdi. Keyingi safar albatta yutasiz! 🍀",
                parse_mode="Markdown"
            )

bot.infinity_polling()

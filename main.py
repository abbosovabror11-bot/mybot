from flask import Flask
import threading
import os
import telebot
from telebot import types
import random
import time

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
REF_BONUS = 500       
DAILY_BONUS = 200     

users_db = set()
user_balances = {}
captcha_storage = {}
user_state = {}
topup_amounts = {}
last_daily_bonus = {}

free_box_prizes = { 3: "500 so'm", 7: "1000 so'm" }
vip_box_prizes = { 5: "10000 so'm", 10: "50000 so'm" }
box_settings = { "max_boxes": 10 }

# Promokodlar strukturasi: { "KOD": {"amount": summa, "limit": max_odam, "used_count": 0} }
promocodes = { "START2026": {"amount": 1000, "limit": 10, "used_count": 0} }
used_promos = {}
used_free_box = set()

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
    args = message.text.split()

    is_new_user = user_id not in users_db

    if is_new_user and user_id != ADMIN_ID:
        is_subbed, _ = check_user_sub(user_id)
        if not is_subbed:
            send_sub_request(message.chat.id)
            return

    if is_new_user:
        users_db.add(user_id)
        if user_id not in user_balances:
            user_balances[user_id] = 0

        if len(args) > 1:
            try:
                referrer_id = int(args[1])
                if referrer_id != user_id and referrer_id in users_db:
                    user_balances[referrer_id] = user_balances.get(referrer_id, 0) + REF_BONUS
                    bot.send_message(
                        referrer_id, 
                        f"🎉 **Sizning havolangiz orqali yangi foydalanuvchi qo'shildi!**\nBalansingizga **{REF_BONUS} so'm** qo'shildi! 💰", 
                        parse_mode="Markdown"
                    )
            except ValueError:
                pass

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
    btn6 = types.KeyboardButton("👥 Referal (Do'stlarni taklif qilish)")
    btn7 = types.KeyboardButton("🎁 Kundalik bonus")
    
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    markup.add(btn5, btn6)
    markup.add(btn7)

    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("👨‍💻 Admin Panel"))

    bot.send_message(chat_id, "🎉 Xush kelibsiz! Asosiy menyu:", reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    user_id = message.from_user.id
    text = message.text
    state = user_state.get(user_id)

    if user_id == ADMIN_ID:
        if state == "set_channel":
            parts = text.split("|")
            ch_id = parts[0].strip()
            ch_link = parts[1].strip() if len(parts) > 1 else f"https://t.me/{ch_id.replace('@', '')}"
            ch_title = parts[2].strip() if len(parts) > 2 else ch_id
            
            try:
                chat_info = bot.get_chat(ch_id)
                ch_title = chat_info.title or ch_title
                
                forced_channels.append({
                    "id": ch_id,
                    "link": ch_link,
                    "title": ch_title
                })
                user_state[user_id] = None
                bot.send_message(message.chat.id, f"✅ Homiy kanal qo'shildi!\nNomi: {ch_title}")
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Xatolik! Bot bu kanalni topolmadi yoki unga admin emas.\nXatolik: {e}")
            return

        elif state == "set_vip_price":
            global PAID_PRICE
            if text.isdigit():
                PAID_PRICE = int(text)
                user_state[user_id] = None
                bot.send_message(message.chat.id, f"✅ VIP sandiq narxi {PAID_PRICE} so'm qilindi!")
            else:
                bot.send_message(message.chat.id, "❌ Faqat raqam kiriting!")
            return
        elif state == "add_promo_code":
            parts = text.split()
            if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
                code_name = parts[0].upper()
                code_amt = int(parts[1])
                code_limit = int(parts[2])
                
                promocodes[code_name] = {
                    "amount": code_amt,
                    "limit": code_limit,
                    "used_count": 0
                }
                user_state[user_id] = None
                bot.send_message(message.chat.id, f"✅ Promokod qo'shildi!\n🎟 Kod: {code_name}\n💵 Summa: {code_amt} so'm\n👥 Limit: {code_limit} ta odam")
            else:
                bot.send_message(message.chat.id, "❌ Noto'g'ri format! Masalan shunday yozing:\n`YANGI 2000 15` (Kod Summa Limit)", parse_mode="Markdown")
            return
        elif state == "broadcast_message":
            user_state[user_id] = None
            success = 0
            for uid in users_db:
                try:
                    bot.send_message(uid, text)
                    success += 1
                except:
                    pass
            bot.send_message(message.chat.id, f"✅ Xabar {success} ta foydalanuvchiga yuborildi!")
            return
        elif state == "manage_user_id":
            if text.isdigit():
                target_uid = int(text)
                user_state[user_id] = {"state": "manage_user_action", "target": target_uid}
                bot.send_message(message.chat.id, f"Foydalanuvchi ID: {target_uid}\n\nQancha pul qo'shmoqchisiz yoki ayirmoqchisiz? (Masalan: `1000` yoki `-500`):")
            else:
                bot.send_message(message.chat.id, "❌ Faqat raqamli ID kiriting:")
            return
        elif isinstance(state, dict) and state.get("state") == "manage_user_action":
            target_uid = state.get("target")
            user_state[user_id] = None
            if text.lstrip('-').isdigit():
                amount = int(text)
                if target_uid in user_balances:
                    user_balances[target_uid] += amount
                else:
                    user_balances[target_uid] = amount
                bot.send_message(message.chat.id, f"✅ Foydalanuvchi ({target_uid}) balansi o'zgartirildi. Hozirgi balans: {user_balances[target_uid]} so'm")
                try:
                    bot.send_message(target_uid, f"🔔 Admin tomonidan balansingiz **{amount} so'm** ga o'zgartirildi. Hozirgi balans: {user_balances[target_uid]} so'm", parse_mode="Markdown")
                except:
                    pass
            else:
                bot.send_message(message.chat.id, "❌ Noto'g'ri qiymat kiritildi!")
            return
        elif state and state.startswith("set_free_box_"):
            box_num = int(state.split("_")[3])
            free_box_prizes[box_num] = text.strip()
            user_state[user_id] = None
            bot.send_message(message.chat.id, f"✅ Tekin sandiq ({box_num}) sovrini saqlandi: {text}")
            return
        elif state and state.startswith("set_vip_box_"):
            box_num = int(state.split("_")[3])
            vip_box_prizes[box_num] = text.strip()
            user_state[user_id] = None
            bot.send_message(message.chat.id, f"✅ VIP sandiq ({box_num}) sovrini saqlandi: {text}")
            return
        elif state == "set_max_boxes":
            if text.isdigit():
                box_settings["max_boxes"] = int(text)
                user_state[user_id] = None
                bot.send_message(message.chat.id, f"✅ Jami sandiqlar soni {text} ta bo'ldi.")
            else:
                bot.send_message(message.chat.id, "❌ Faqat raqam kiriting!")
            return

    if text == "💰 Mening balansim":
        user_state[user_id] = None
        bal = user_balances.get(user_id, 0)
        bot.send_message(message.chat.id, f"💰 Sizning balansingiz: {bal} so'm")
        return

    elif text == "🎟 Promokod":
        user_state[user_id] = "waiting_promocode"
        bot.send_message(message.chat.id, "🎟 Promokodni kiriting:")
        return

    elif text == "👥 Referal (Do'stlarni taklif qilish)":
        user_state[user_id] = None
        bot_info = bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        bot.send_message(
            message.chat.id, 
            f"👥 **Do'stlarni taklif qilish va pul ishlash!**\n\n"
            f"Har bir taklif qilgan do'stingiz uchun **{REF_BONUS} so'm** beriladi!\n\n"
            f"Sizning taklif havolangiz:\n`{ref_link}`", 
            parse_mode="Markdown"
        )
        return

    elif text == "🎁 Kundalik bonus":
        user_state[user_id] = None
        current_time = time.time()
        last_time = last_daily_bonus.get(user_id, 0)
        
        if current_time - last_time < 86400:
            remaining = int(86400 - (current_time - last_time))
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            bot.send_message(message.chat.id, f"⏳ Siz kundalik bonusni allaqachon olgansiz!\nKeyingi bonus: **{hours} soat {minutes} daqiqa**dan keyin ochiladi.", parse_mode="Markdown")
        else:
            last_daily_bonus[user_id] = current_time
            user_balances[user_id] = user_balances.get(user_id, 0) + DAILY_BONUS
            bot.send_message(message.chat.id, f"🎉 Tabriklaymiz! Kunlik bonus sifatida balansingizga **{DAILY_BONUS} so'm** qo'shildi! 💰", parse_mode="Markdown")
        return

    elif text == "🎁 Tekin sandiq":
        user_state[user_id] = None
        if user_id in used_free_box:
            bot.send_message(message.chat.id, "⚠️ Siz allaqachon tekin sandiqni ochgansiz!")
        else:
            markup = types.InlineKeyboardMarkup(row_width=5)
            buttons = []
            for i in range(1, box_settings["max_boxes"] + 1):
                # Qaysi biri ochilgani ko'rinib turishi uchun emoji qo'shamiz
                if i in used_free_box: # Yoki umumiy ochilgan qutilar ro'yxatini yuritish mumkin
                    buttons.append(types.InlineKeyboardButton(f"❌ {i}", callback_data=f"opened_box"))
                else:
                    buttons.append(types.InlineKeyboardButton(f"📦 {i}", callback_data=f"free_box_{i}"))
            markup.add(*buttons)
            
            opened_count = len([b for b in range(1, box_settings["max_boxes"]+1) if b in used_free_box]) # Misol uchun
            bot.send_message(message.chat.id, f"🎁 Tekin sandiqlar (Jami: {box_settings['max_boxes']} ta):\nO'zingizga yoqqan raqamni tanlang:", reply_markup=markup)
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

    if state == "waiting_promocode":
        code = text.strip().upper()
        user_state[user_id] = None
        
        if code in promocodes:
            promo_info = promocodes[code]
            if user_id not in used_promos:
                used_promos[user_id] = []
            
            if code in used_promos[user_id]:
                bot.send_message(message.chat.id, "❌ Siz bu promokoddan allaqachon foylangansiz!")
            elif promo_info["used_count"] >= promo_info["limit"]:
                bot.send_message(message.chat.id, "❌ Kechirasiz, bu promokoddan foydalanish limiti tugagan!")
            else:
                promo_info["used_count"] += 1
                amt = promo_info["amount"]
                user_balances[user_id] = user_balances.get(user_id, 0) + amt
                used_promos[user_id].append(code)
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
            bot.send_message(message.chat.id, "❌ Faqat raqamda summa kiriting (masalan: 10000):")
        return

    if text == "👨‍💻 Admin Panel" and user_id == ADMIN_ID:
        user_state[user_id] = None
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("📢 Kanal Sozlash", "📋 Kanallar ro'yxati")
        markup.add("📦 Qutilarni sozlash", "💎 VIP narxini o'zgartirish")
        markup.add("🎟 Promokod qo'shish", "👤 Foydalanuvchini boshqarish")
        markup.add("📢 Xabar yuborish (Rassilka)", "📊 Statistika")
        markup.add("🚪 Menuga qaytish")
        
        channels_count = len(forced_channels)
        bot.send_message(message.chat.id, f"👨‍💻 **Admin Panel**\n\n📌 Jami sandiqlar: {box_settings['max_boxes']} ta\n💎 VIP narxi: {PAID_PRICE} so'm\n📢 Homiy kanallar: {channels_count} ta", reply_markup=markup)
        return

    if text == "📢 Kanal Sozlash" and user_id == ADMIN_ID:
        user_state[user_id] = "set_channel"
        bot.send_message(
            message.chat.id, 
            "🔗 **Homiy kanal qo'shish:**\n\n"
            "Kanalning **ID raqami yoki @username** sini yuboring.\n"
            "*(Masalan: `@kanalim` yoki `-100123456789`)*\n\n"
            "Maxsus havola uchun:\n"
            "`@kanalim | https://t.me/+AbCdEfGh | Kanal Nomi`",
            parse_mode="Markdown"
        )
        return

    if text == "📋 Kanallar ro'yxati" and user_id == ADMIN_ID:
        if not forced_channels:
            bot.send_message(message.chat.id, "📭 Hozircha homiy kanallar qo'shilmagan.")
        else:
            markup = types.InlineKeyboardMarkup()
            for idx, ch in enumerate(forced_channels):
                markup.add(types.InlineKeyboardButton(f"❌ O'chirish: {ch['title']}", callback_data=f"del_ch_{idx}"))
            bot.send_message(message.chat.id, "📋 Hozirgi homiy kanallar ro'yxati:", reply_markup=markup)
        return

    if text == "💎 VIP narxini o'zgartirish" and user_id == ADMIN_ID:
        user_state[user_id] = "set_vip_price"
        bot.send_message(message.chat.id, f"Hozirgi VIP narx: {PAID_PRICE} so'm.\nYangi narxni raqamda kiriting:")
        return

    if text == "🎟 Promokod qo'shish" and user_id == ADMIN_ID:
        user_state[user_id] = "add_promo_code"
        bot.send_message(message.chat.id, "Promokod, summasi va nechta odam ishlatishini yozing:\n*(Masalan: `BONUS 5000 15`)*", parse_mode="Markdown")
        return

    if text == "👤 Foydalanuvchini boshqarish" and user_id == ADMIN_ID:
        user_state[user_id] = "manage_user_id"
        bot.send_message(message.chat.id, "Foydalanuvchining **Telegram ID** raqamini kiriting:")
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
        markup.add("🎟 Promokod qo'shish", "👤 Foydalanuvchini boshqarish")
        markup.add("📢 Xabar yuborish (Rassilka)", "📊 Statistika")
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
            bot.send_message(message.chat.id, f"❌ Xatolik yuz berdi: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    username = f"@{call.from_user.username}" if call.from_user.username else f"ID: {user_id}"

    if data == "opened_box":
        bot.answer_callback_query(call.id, "❌ Bu quti allaqachon ochilgan!", show_alert=True)
        return

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

        if target_user_id in user_balances:
            user_balances[target_user_id] += amount
        else:
            user_balances[target_user_id] = amount

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
            # Adminga yutuq haqida xabar yuborish
            try:
                bot.send_message(ADMIN_ID, f"🎁 **Yangi yutuq!**\n\nFoydalanuvchi: {username} (ID: `{user_id}`)\nSovrin: **{prize}** ({box_num}-tekin sandiq)", parse_mode="Markdown")
            except:
                pass
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
            # Adminga VIP yutuq haqida xabar yuborish
            try:
                bot.send_message(ADMIN_ID, f"💎 **VIP Yutuq!**\n\nFoydalanuvchi: {username} (ID: `{user_id}`)\nSovrin: **{prize}** ({box_num}-VIP sandiq)", parse_mode="Markdown")
            except:
                pass
        else:
            bot.answer_callback_query(call.id, "Afsuski, bu VIP sandiq bo'sh chiqdi 😢", show_alert=True)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"💎 **{box_num}-VIP sandiq** ochildi!\n\nAfsuski, bu VIP sandiq bo'sh chiqdi. Keyingi safar albatta yutasiz! 🍀",
                parse_mode="Markdown"
            )

bot.infinity_polling()

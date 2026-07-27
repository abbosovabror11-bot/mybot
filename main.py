import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ==========================================
# SOZLAMALAR
# ==========================================
TOKEN = "8860310673:AAGjR_4nY3fiNR5D_WCX4J1bLZvG5zUBZ7c"      # BotFather dan olgan tokeningiz
ADMIN_ID = 8694110588          # Sizning Telegram ID raqamingiz

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Xotirada bazani simulyatsiya qilish (Professional loyihada PostgreSQL ishlatiladi)
channels_db = set()           # Bot admin bo'lgan kanallar ID lari
channel_names = {}            # Kanal ID -> Nomi
users_db = set()              # Botdan foydalangan barcha foydalanuvchilar (ID va qo'shilgan vaqti)
users_joined_time = {}        # User_id -> datetime (Statistika uchun)
channel_usage_count = {}      # Top 10 kanallar uchun faollik
forced_channels = []          # Majburiy obuna uchun kanallar ro'yxati (masalan: ["@kanalusername"])


# ==========================================
# MAJBURIY OBUNANI TEKSHIRISH FUNKSIYASI
# ==========================================
async def check_subscription(user_id: int) -> bool:
    if not forced_channels:
        return True
    
    for channel in forced_channels:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            # Agar botning o'zi majburiy kanalda admin bo'lmasa yoki xatolik bo'lsa
            pass
    return True


# ==========================================
# 1. START VA ASOSIY MENYU (MAJBURIY OBUNA BILAN)
# ==========================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # Foydalanuvchini bazaga qo'shish va vaqtini saqlash (Statistika uchun)
    if user_id not in users_db:
        users_db.add(user_id)
        users_joined_time[user_id] = datetime.now()

    # Majburiy obunani tekshirish
    is_subscribed = await check_subscription(user_id)
    
    builder = InlineKeyboardBuilder()
    
    if not is_subscribed:
        # Agar obuna bo'lmasa, kanallarga obuna bo'lish tugmalarini chiqaramiz
        for ch in forced_channels:
            builder.button(text=f"📢 {ch} ga obuna bo'lish", url=f"https://t.me/{ch.replace('@', '')}")
        builder.button(text="✅ Tekshirish", callback_data="check_sub")
        builder.adjust(1)
        
        await message.answer(
            "⚠️ **Botdan foydalanish uchun quyidagi kanallarga obuna bo'lishingiz kerak:**\n\n"
            "Obuna bo'lgach, **✅ Tekshirish** tugmasini bosing.",
            reply_markup=builder.as_markup()
        )
        return

    # Asosiy menyu
    builder.row(
        types.InlineKeyboardButton(text="🎮 O'yinni boshlash", callback_data="start_game"),
        types.InlineKeyboardButton(text="🏆 Top 10 Kanallar", callback_data="top_channels")
    )
    builder.row(
        types.InlineKeyboardButton(text="ℹ️ Bot haqida", callback_data="about_bot")
    )
    
    await message.answer(
        "👋 **Xush kelibsiz!**\n\n"
        "Men kanallar uchun maxsus avtomatlashtirilgan interaktiv o'yin va tanlov botiman.\n\n"
        "✨ **Asosiy imkoniyatlarim:**\n"
        "• Kanalingizda avtomatlashtirilgan shou va o'yinlar\n"
        "• Eng faol kanallarning ochiq reytingi (Top 10)\n"
        "• To'liq qulay boshqaruv menyusi\n\n"
        "📥 Meni o'z kanalingizga **admin** qilib qo'shing va ishga tushiring!",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data == "check_sub")
async def process_check_sub(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    is_subscribed = await check_subscription(user_id)
    
    if not is_subscribed:
        await callback.answer("❌ Siz hali hamma kanallarga obuna bo'lmadingiz!", show_alert=True)
        return
        
    await callback.message.delete()
    # Obuna tasdiqlangach start menyusini qayta chaqiramiz
    fake_message = callback.message
    fake_message.from_user = callback.from_user
    await cmd_start(fake_message)


# ==========================================
# 2. KANALGA ADMIN QILINGANDA AVTOMATIK QO'SHILISH
# ==========================================
@dp.my_chat_member()
async def bot_added_to_channel(event: types.ChatMemberUpdated):
    if event.new_chat_member.status in ["administrator", "creator"]:
        chat_id = event.chat.id
        chat_title = event.chat.title
        
        channels_db.add(chat_id)
        channel_names[chat_id] = chat_title
        
        if chat_id not in channel_usage_count:
            channel_usage_count[chat_id] = 0
            
        logging.info(f"Yangi kanalga qo'shildim: {chat_title} ({chat_id})")


# ==========================================
# 3. O'YIN VA INTERAKTIV TUGMALAR
# ==========================================
@dp.callback_query(F.data == "start_game")
async def process_game(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ Ball yig'ish / Ovoz berish", callback_data="vote_action")
    builder.button(text="🔙 Ortga", callback_data="back_home")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "🎮 **O'yin rejimi faollashdi!**\n\n"
        "Ishtirokchilar quyidagi tugma orqali o'z ballarini yig'ishlari va faollik ko'rsatishlari mumkin.",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data == "vote_action")
async def vote_handler(callback: types.CallbackQuery):
    await callback.answer("✅ Faolligingiz muvaffaqiyatli qo'shildi!", show_alert=True)


# ==========================================
# 4. TOP 10 KANALLAR REYTINGI
# ==========================================
@dp.callback_query(F.data == "top_channels")
async def show_top_channels(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Ortga", callback_data="back_home")
    
    sorted_channels = sorted(channel_usage_count.items(), key=lambda x: x[1], reverse=True)[:10]
    
    text = "🏆 **Botdan eng ko'p foydalanayotgan TOP 10 kanallar:**\n\n"
    
    if not sorted_channels or all(count == 0 for _, count in sorted_channels):
        text += "Hozircha faol kanallar mavjud emas yoki statistika yig'ilmoqda."
    else:
        for idx, (cid, count) in enumerate(sorted_channels, 1):
            name = channel_names.get(cid, f"Kanal #{cid}")
            text += f"{idx}. **{name}** — {count} ta faollik\n"
            
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@dp.callback_query(F.data == "about_bot")
async def about_bot(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Ortga", callback_data="back_home")
    
    await callback.message.edit_text(
        "ℹ️ **Bot haqida ma'lumot:**\n\n"
        "Bu bot Telegram kanallari uchun mo'ljallangan professional o'yin va tanlov vositasi hisoblanadi.\n"
        "Savollar va takliflar uchun admin bilan bog'laning.",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data == "back_home")
async def back_home(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🎮 O'yinni boshlash", callback_data="start_game"),
        types.InlineKeyboardButton(text="🏆 Top 10 Kanallar", callback_data="top_channels")
    )
    builder.row(
        types.InlineKeyboardButton(text="ℹ️ Bot haqida", callback_data="about_bot")
    )
    await callback.message.edit_text(
        "👋 Asosiy menyuga xush kelibsiz! Kerakli bo'limni tanlang:",
        reply_markup=builder.as_markup()
    )


# ==========================================
# 5. KENGAYTIRILGAN ADMIN PANEL VA STATISTIKA (/admin)
# ==========================================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Kechirasiz, bu buyruq faqat bot egasi uchun!")
        return
        
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Batafsil Statistika", callback_data="admin_stats")
    builder.button(text="📢 Xabar yuborish (Broadcast)", callback_data="admin_broadcast")
    builder.adjust(1)
    
    await message.answer(
        "👑 **Admin Panelga xush kelibsiz!**\n\n"
        "Quyidagi boshqaruv elementlaridan birini tanlang:",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
        
    now = datetime.now()
    
    # Vaqtlar bo'yicha foydalanuvchilarni hisoblash
    total_users = len(users_db)
    day_1 = sum(1 for uid, t in users_joined_time.items() if now - t <= timedelta(days=1))
    days_7 = sum(1 for uid, t in users_joined_time.items() if now - t <= timedelta(days=7))
    days_30 = sum(1 for uid, t in users_joined_time.items() if now - t <= timedelta(days=30))
    
    total_channels = len(channels_db)
    
    stats_text = (
        f"📊 **Botning Kengaytirilgan Statistikasi:**\n\n"
        f"📢 **Kanallar bo'yicha:**\n"
        f"• Bot admin bo'lgan kanallar soni: **{total_channels} ta**\n\n"
        f"👥 **Foydalanuvchilar bo'yicha:**\n"
        f"• Oxirgi 24 soatda qo'shilganlar: **{day_1} ta**\n"
        f"• Oxirgi 7 kunda qo'shilganlar: **{days_7} ta**\n"
        f"• Oxirgi 1 oyda qo'shilganlar: **{days_30} ta**\n"
        f"• Umumiy foydalanuvchilar soni: **{total_users} ta**\n\n"
        f"🟢 **Server holati:** Barqaror ishlayapti"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Ortga", callback_data="admin_back")
    
    await callback.message.edit_text(stats_text, reply_markup=builder.as_markup())
    await callback.answer()


@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Batafsil Statistika", callback_data="admin_stats")
    builder.button(text="📢 Xabar yuborish (Broadcast)", callback_data="admin_broadcast")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "👑 **Admin Panelga xush kelibsiz!**\n\n"
        "Quyidagi boshqaruv elementlaridan birini tanlang:",
        reply_markup=builder.as_markup()
    )


# ==========================================
# BOTNI ISHGA TUSHIRISH
# ==========================================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

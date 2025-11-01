# admin_panel.py
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def admin_main_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("👥 Users", callback_data="admin:users"),
        InlineKeyboardButton("⭐ Premium", callback_data="admin:premium"),
        InlineKeyboardButton("📊 Running", callback_data="admin:running"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin:broadcast"),
        InlineKeyboardButton("💾 Backup Now", callback_data="admin:backup"),
        InlineKeyboardButton("♻️ Restart Bot", callback_data="admin:restart"),
    )
    kb.add(InlineKeyboardButton("⬅️ Back", callback_data="back_home"))
    return kb
  

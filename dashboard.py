# dashboard.py
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def user_dashboard_kb(project_name: str):
    kb = InlineKeyboardMarkup(row_width=2)
    # list run/stop for any py file present
    # for simplicity we provide generic buttons; actual run buttons are constructed with run:project:filename
    # In bot we will present file list first; this kb is for quick actions
    kb.add(
        InlineKeyboardButton("▶️ Run", callback_data=f"runquick:{project_name}"),
        InlineKeyboardButton("⏹ Stop", callback_data=f"stopquick:{project_name}")
    )
    kb.add(
        InlineKeyboardButton("🔁 Restart", callback_data=f"restartquick:{project_name}"),
        InlineKeyboardButton("📄 Logs", callback_data=f"logsquick:{project_name}")
    )
    kb.add(
        InlineKeyboardButton("📂 File Manager", callback_data=f"fm:{project_name}"),
        InlineKeyboardButton("⬅️ Back", callback_data="back_home")
    )
    return kb
  

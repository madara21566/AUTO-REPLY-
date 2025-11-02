from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os

def register(app: Client):
    @app.on_callback_query(filters.regex(r"file_manager_(.+)"))
    async def file_manager(client, query):
        project_name = query.data.split("_", 2)[2]
        url = f"{os.getenv('BASE_URL')}/file_manager/{query.from_user.id}/{project_name}"
        await query.message.edit_text(f"Access your file manager here: {url}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"project_{project_name}")]]))
      

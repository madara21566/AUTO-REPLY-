from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def register(app: Client):
    @app.on_message(filters.command("start"))
    async def start(client, message):
        text = """
👋 Welcome to the Python Project Hoster!

I'm your personal bot for securely deploying and managing your Python scripts and applications, right here from Telegram.

━━━━━━━━━━━━━━━━━━━
⚡ Key Features:
🚀 Deploy Instantly — Upload your code as a .zip or .py file and I’ll handle the rest.
📂 Easy Management — Use the built-in web file manager to edit your files live.
🤖 Full Control — Start, stop, restart, and view logs for all your projects.
🪄 Auto Setup — No need for a requirements file; I automatically install everything required!
💾 Backup System — Your project data is automatically backed up every 10 minutes.
━━━━━━━━━━━━━━━━━━━

🆓 Free Tier:
• You can host up to 2 projects.
• Each project runs for 12 hours per session.

⭐ Premium Tier:
• Host up to 10 projects.
• Run your scripts 24/7 nonstop.
• Automatic daily backup retention.

Need more power? You can upgrade to Premium anytime by contacting the bot owner!

━━━━━━━━━━━━━━━━━━━
👇 Get Started Now:
1️⃣ Tap “🆕 New Project” below.
2️⃣ Set your project name.
3️⃣ Upload your Python script (.py) or .zip file.
4️⃣ Control everything from your dashboard!
━━━━━━━━━━━━━━━━━━━
🧑‍💻 Powered by: @MADARAXHEREE  
🔒 Secure • Fast • Easy to Use
"""
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🆕 New Project", callback_data="new_project"),
             InlineKeyboardButton("📂 My Projects", callback_data="my_projects")],
            [InlineKeyboardButton("💬 Help", callback_data="help"),
             InlineKeyboardButton("⭐ Premium", callback_data="premium")]
        ])
        await message.reply(text, reply_markup=buttons)
      

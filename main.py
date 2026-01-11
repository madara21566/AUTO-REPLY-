import os, threading
import psycopg2
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
ApplicationBuilder, CommandHandler,
CallbackQueryHandler, MessageHandler,
ContextTypes, filters
)


import bot_core  # tumhara original script

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
DATABASE_URL = os.environ.get("DATABASE_URL")
PORT = int(os.environ.get("PORT", "10000"))

conn = psycopg2.connect(DATABASE_URL, sslmode="require")
conn.autocommit = True

def init_db():
with conn.cursor() as cur:
cur.execute("""
CREATE TABLE IF NOT EXISTS allowed_users (
user_id BIGINT PRIMARY KEY
);
""")

def is_allowed(uid: int):
if uid == OWNER_ID:
return True
with conn.cursor() as cur:
cur.execute("SELECT 1 FROM allowed_users WHERE user_id=%s", (uid,))
return cur.fetchone() is not None

def db_add(uid: int):
with conn.cursor() as cur:
cur.execute(
"INSERT INTO allowed_users(user_id) VALUES(%s) ON CONFLICT DO NOTHING",
(uid,)
)

def db_remove(uid: int):
with conn.cursor() as cur:
cur.execute("DELETE FROM allowed_users WHERE user_id=%s", (uid,))

def db_list():
with conn.cursor() as cur:
cur.execute("SELECT user_id FROM allowed_users ORDER BY user_id")
return [str(r[0]) for r in cur.fetchall()]


def admin_menu():
return InlineKeyboardMarkup([
[InlineKeyboardButton("➕ Add User", callback_data="admin_add")],
[InlineKeyboardButton("➖ Remove User", callback_data="admin_remove")],
[InlineKeyboardButton("📋 List Users", callback_data="admin_list")],
[InlineKeyboardButton("⬅ Back", callback_data="admin_back")]
])

admin_state = {}

orig_start = bot_core.start
orig_buttons = bot_core.buttons
orig_text = bot_core.handle_text
orig_file = bot_core.handle_file

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
uid = update.effective_user.id
if not is_allowed(uid):
return await update.message.reply_text("⛔ This is a private bot. Please Contact Owner :- @MADARAXHEREE")

if uid == OWNER_ID:  
    await update.message.reply_text(  
        "👑 Admin Access Enabled\n\nSend /admin for control panel"  
    )  

return await orig_start(update, ctx)

async def admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id != OWNER_ID:
return
await update.message.reply_text(
"🔐 Admin Panel",
reply_markup=admin_menu()
)

async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
q = update.callback_query
uid = q.from_user.id
await q.answer()

if not is_allowed(uid):  
    return await q.answer("⛔ Private Bot", show_alert=True)  

if uid == OWNER_ID:  
    if q.data == "admin_add":  
        admin_state[uid] = "add"  
        return await q.message.reply_text("🆔 User ID likh kar bhejo")  

    if q.data == "admin_remove":  
        admin_state[uid] = "remove"  
        return await q.message.reply_text("🆔 User ID likh kar bhejo")  

    if q.data == "admin_list":  
        users = db_list()  
        return await q.message.reply_text(  
            "👥 Allowed Users:\n" + ("\n".join(users) if users else "None")  
        )  

    if q.data == "admin_back":  
        return await q.message.reply_text("⬅ Back")  

return await orig_buttons(update, ctx)

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
uid = update.effective_user.id
txt = update.message.text.strip()

if not is_allowed(uid):  
    return  

if uid == OWNER_ID and admin_state.get(uid):  
    if not txt.isdigit():  
        return await update.message.reply_text("❌ Valid numeric User ID bhejo")  

    target = int(txt)  
    if admin_state[uid] == "add":  
        db_add(target)  
        msg = "✅ User access added"  
    else:  
        db_remove(target)  
        msg = "❌ User access removed"  

    admin_state.pop(uid, None)  
    return await update.message.reply_text(msg, reply_markup=admin_menu())  

return await orig_text(update, ctx)

async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
uid = update.effective_user.id
if not is_allowed(uid):
return
return await orig_file(update, ctx)


flask_app = Flask(name)

@flask_app.route("/")
def home():
return "Bot is running"

def run_flask():
flask_app.run(host="0.0.0.0", port=PORT)

if name == "main":
init_db()

threading.Thread(target=run_flask, daemon=True).start()  

app = ApplicationBuilder().token(BOT_TOKEN).build()  

app.add_handler(CommandHandler("start", start))  
app.add_handler(CommandHandler("admin", admin))  
app.add_handler(CallbackQueryHandler(buttons))  
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))  
app.add_handler(MessageHandler(filters.Document.ALL, handle_file))  

print("🚀 Bot running with Admin Panel + PostgreSQL + Flask")  
app.run_polling()

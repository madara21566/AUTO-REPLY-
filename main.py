import os, threading
import psycopg2
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

# ===== IMPORT ORIGINAL BOT =====
import bot_core  # tumhara original script

# ================= ENV =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
DATABASE_URL = os.environ.get("DATABASE_URL")
PORT = int(os.environ.get("PORT", "10000"))

# ================= DATABASE =================
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

# ================= ADMIN UI =================
def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add User", callback_data="admin_add")],
        [InlineKeyboardButton("➖ Remove User", callback_data="admin_remove")],
        [InlineKeyboardButton("📋 List Users", callback_data="admin_list")],
        [InlineKeyboardButton("⬅ Back", callback_data="admin_back")]
    ])

admin_state = {}

# ================= ORIGINAL HANDLERS =================
orig_start = bot_core.start
orig_buttons = bot_core.buttons
orig_text = bot_core.handle_text
orig_file = bot_core.handle_file

# ================= START =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not is_allowed(uid):
        return await update.message.reply_text(
            "📂💾 *VCF Bot Access*\n"
            "Want my *VCF Converter Bot*?\n"
            "Just DM me anytime — I’ll reply fast!\n\n"
            "📩 "@{os.environ.get("USERNAME")}\n\n"
            "⚡ TXT ⇄ VCF | 🪄 Easy | 🔒 Trusted",
            parse_mode="Markdown"
        )

    # 🔑 OWNER ONLY ADMIN BUTTON
    if uid == OWNER_ID:
        await update.message.reply_text(
            "👑 Owner Mode Active",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 Admin Panel", callback_data="open_admin")]
            ])
        )

    return await orig_start(update, ctx)

# ================= BUTTONS =================
async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()

    if not is_allowed(uid):
        return await q.answer("⛔ Private Bot", show_alert=True)

    # 🔐 OPEN ADMIN PANEL (OWNER ONLY)
    if q.data == "open_admin" and uid == OWNER_ID:
        return await q.message.reply_text(
            "🔐 Admin Panel",
            reply_markup=admin_menu()
        )

    # ----- ADMIN ACTIONS -----
    if uid == OWNER_ID:
        if q.data == "admin_add":
            admin_state[uid] = "add"
            return await q.message.reply_text("🆔 User ID bhejo")

        if q.data == "admin_remove":
            admin_state[uid] = "remove"
            return await q.message.reply_text("🆔 User ID bhejo")

        if q.data == "admin_list":
            users = db_list()
            return await q.message.reply_text(
                "👥 Allowed Users:\n" + ("\n".join(users) if users else "None")
            )

        # ⬅ BACK → PANEL COMPLETELY GONE
        if q.data == "admin_back":
            admin_state.pop(uid, None)
            await q.message.delete()
            return

    return await orig_buttons(update, ctx)

# ================= TEXT =================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    txt = update.message.text.strip()

    if not is_allowed(uid):
        return

    # ----- ADMIN INPUT -----
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

# ================= FILE =================
async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_allowed(uid):
        return
    return await orig_file(update, ctx)

# ================= FLASK =================
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is running"

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

# ================= MAIN =================
if __name__ == "__main__":
    init_db()

    threading.Thread(target=run_flask, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("🚀 Bot running with Inline Admin Panel")
    app.run_polling()

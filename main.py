import os
import threading
import psycopg2
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ===== IMPORT BOTH CORE FILES =====
import bot_core
import bot_coree


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

# SECOND FILE HANDLERS (OPTIONAL)
extra_start = getattr(bot_coree, "start", None)
extra_buttons = getattr(bot_coree, "buttons", None)
extra_text = getattr(bot_coree, "handle_text", None)
extra_file = getattr(bot_coree, "handle_file", None)


# ================= SECURED WRAPPERS =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not is_allowed(uid):
        return await update.message.reply_text (
        "📂💾 *VCF Bot Access*\n"
        "Want my *VCF Converter Bot*?\n"
        "Just DM me anytime — I’ll reply to you fast!\n\n"
        "📩 *Direct Message here:* @MADARAXHEREE\n\n"
        "⚡ Convert TXT ⇄ VCF instantly | 🪄 Easy & Quick | 🔒 Trusted"
        )

    if uid == OWNER_ID:
        await update.message.reply_text(
            "👑 Admin Access Enabled\nSend /admin for control panel"
        )

    # call both cores if needed
    await orig_start(update, ctx)
    if extra_start:
        await extra_start(update, ctx)


async def admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text("🔐 Admin Panel", reply_markup=admin_menu())


async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()

    if not is_allowed(uid):
        return await q.answer("⛔ Private Bot", show_alert=True)

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

        if q.data == "admin_back":
            return await q.message.reply_text("⬅ Back")

    await orig_buttons(update, ctx)
    if extra_buttons:
        await extra_buttons(update, ctx)


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    if not is_allowed(uid):
        return

    if uid == OWNER_ID and admin_state.get(uid):
        if not text.isdigit():
            return await update.message.reply_text("❌ Numeric User ID bhejo")

        target = int(text)

        if admin_state[uid] == "add":
            db_add(target)
            msg = "✅ User Added"
        else:
            db_remove(target)
            msg = "❌ User Removed"

        admin_state.pop(uid, None)
        return await update.message.reply_text(msg, reply_markup=admin_menu())

    await orig_text(update, ctx)
    if extra_text:
        await extra_text(update, ctx)


async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_allowed(uid):
        return

    await orig_file(update, ctx)
    if extra_file:
        await extra_file(update, ctx)


# ================= FLASK =================
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ Bot is running"


def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)


# ================= MAIN =================
if __name__ == "__main__":
    init_db()

    threading.Thread(target=run_flask, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("🚀 Bot running with bot_core + bot_coree + Admin + Flask")
    app.run_polling()

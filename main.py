import os, threading, asyncio
import psycopg2
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

# ================= ORIGINAL BOT =================
import bot_core  # ❗ tumhara original bot (unchanged)

orig_start = bot_core.start
orig_buttons = bot_core.buttons
orig_text = bot_core.handle_text
orig_file = bot_core.handle_file

# ================= ENV =================
BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])
DATABASE_URL = os.environ["DATABASE_URL"]
PORT = int(os.environ.get("PORT", "10000"))

CHANNEL_1_ID = int(os.environ["CHANNEL_1_ID"])
CHANNEL_2_ID = int(os.environ["CHANNEL_2_ID"])
CHANNEL_1_LINK = os.environ["CHANNEL_1_LINK"]
CHANNEL_2_LINK = os.environ["CHANNEL_2_LINK"]

# ================= DB =================
conn = psycopg2.connect(DATABASE_URL, sslmode="require")
conn.autocommit = True

def init_db():
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            expires_at TIMESTAMP,
            warned BOOLEAN DEFAULT FALSE,
            trial_used BOOLEAN DEFAULT FALSE
        );
        """)

# ================= HELPERS =================
def get_user(uid):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT expires_at, warned, trial_used FROM users WHERE user_id=%s",
            (uid,)
        )
        return cur.fetchone()

def is_allowed(uid):
    if uid == OWNER_ID:
        return True
    data = get_user(uid)
    if not data:
        return False
    expires = data[0]
    if expires is None:
        return True
    return datetime.utcnow() < expires

def give_trial(uid):
    with conn.cursor() as cur:
        cur.execute("""
        INSERT INTO users (user_id, expires_at, trial_used)
        VALUES (%s, %s, TRUE)
        ON CONFLICT DO NOTHING
        """, (uid, datetime.utcnow() + timedelta(hours=24)))

def add_permanent(uid):
    with conn.cursor() as cur:
        cur.execute("""
        INSERT INTO users (user_id, expires_at, trial_used)
        VALUES (%s, NULL, TRUE)
        ON CONFLICT (user_id)
        DO UPDATE SET expires_at=NULL
        """, (uid,))

def remove_user(uid):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE user_id=%s", (uid,))

# ================= CHANNEL CHECK =================
async def joined_channels(bot, uid):
    try:
        ok = ["member", "administrator", "creator"]
        m1 = await bot.get_chat_member(CHANNEL_1_ID, uid)
        m2 = await bot.get_chat_member(CHANNEL_2_ID, uid)
        return m1.status in ok and m2.status in ok
    except:
        return False

# ================= START =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    # ✅ ACCESS → ORIGINAL BOT
    if is_allowed(uid):
        return await orig_start(update, ctx)

    # 🚫 TRIAL ALREADY USED
    user = get_user(uid)
    if user and user[2]:
        return await update.message.reply_text(
            "⛔ Free trial already used.\nContact admin for access."
        )

    # 🔐 FORCE JOIN
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Join Channel 1", url=CHANNEL_1_LINK)],
        [InlineKeyboardButton("🔗 Join Channel 2", url=CHANNEL_2_LINK)],
        [InlineKeyboardButton("✅ Continue", callback_data="check_join")]
    ])

    await update.message.reply_text(
        "🔐 *Bot Locked*\n\n"
        "Bot use karne ke liye dono channels join karo\n"
        "Join request bhejne ke baad *Continue* dabao",
        parse_mode="Markdown",
        reply_markup=kb
    )

# ================= ADMIN =================
admin_state = {}

async def admin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Permanent", callback_data="admin_add")],
        [InlineKeyboardButton("➖ Remove User", callback_data="admin_remove")],
        [InlineKeyboardButton("📋 List Users", callback_data="admin_list")]
    ])
    await update.message.reply_text("🔐 Admin Panel", reply_markup=kb)

# ================= BUTTONS =================
async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()

    # ===== CONTINUE =====
    if q.data == "check_join":
        user = get_user(uid)
        if user and user[2]:
            return await q.message.reply_text("❌ Trial already used.")

        if await joined_channels(ctx.bot, uid):
            give_trial(uid)
            return await q.message.reply_text(
                "🎉 *24 HOURS FREE TRIAL ACTIVATED!*",
                parse_mode="Markdown"
            )
        return await q.answer("Join both channels first", show_alert=True)

    # ===== ADMIN =====
    if uid == OWNER_ID:
        if q.data == "admin_add":
            admin_state[uid] = "add"
            return await q.message.reply_text("Send User ID")

        if q.data == "admin_remove":
            admin_state[uid] = "remove"
            return await q.message.reply_text("Send User ID")

        if q.data == "admin_list":
            with conn.cursor() as cur:
                cur.execute("SELECT user_id, expires_at FROM users")
                rows = cur.fetchall()

            if not rows:
                return await q.message.reply_text("No users")

            text = "👥 Users:\n"
            for u, e in rows:
                text += f"{u} → {'PERMANENT' if e is None else e}\n"
            return await q.message.reply_text(text)

    # ✅ ORIGINAL BOT BUTTONS
    return await orig_buttons(update, ctx)

# ================= TEXT =================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    txt = update.message.text.strip()

    # ADMIN INPUT
    if uid == OWNER_ID and uid in admin_state:
        if not txt.isdigit():
            return await update.message.reply_text("Invalid ID")

        target = int(txt)
        action = admin_state.pop(uid)

        if action == "add":
            add_permanent(target)
            return await update.message.reply_text("✅ Permanent access added")

        if action == "remove":
            remove_user(target)
            return await update.message.reply_text("❌ User removed")

    if not is_allowed(uid):
        return

    return await orig_text(update, ctx)

# ================= FILE =================
async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    return await orig_file(update, ctx)

# ================= TRIAL WARNING =================
async def trial_watcher(app):
    while True:
        await asyncio.sleep(300)
        with conn.cursor() as cur:
            cur.execute("""
            SELECT user_id, expires_at FROM users
            WHERE expires_at IS NOT NULL AND warned = FALSE
            """)
            rows = cur.fetchall()

        for uid, exp in rows:
            if exp - datetime.utcnow() <= timedelta(hours=1):
                try:
                    await app.bot.send_message(
                        uid,
                        "⚠️ Trial will expire in 1 hour!"
                    )
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE users SET warned=TRUE WHERE user_id=%s",
                            (uid,)
                        )
                except:
                    pass

# ================= FLASK =================
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot running"

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

# ================= MAIN =================
async def post_init(app):
    asyncio.create_task(trial_watcher(app))

if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("🚀 FINAL BOT RUNNING (bot_core + trial + force join)")
    app.run_polling()

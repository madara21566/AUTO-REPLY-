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

# ================= ENV =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
DATABASE_URL = os.environ.get("DATABASE_URL")
PORT = int(os.environ.get("PORT", "10000"))

CHANNEL_1 = int(os.environ.get("CHANNEL_1"))
CHANNEL_2 = int(os.environ.get("CHANNEL_2"))

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

# ================= ACCESS =================
def get_user(uid):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT expires_at, warned, trial_used FROM users WHERE user_id=%s",
            (uid,)
        )
        return cur.fetchone()

def is_allowed(uid: int):
    if uid == OWNER_ID:
        return True

    data = get_user(uid)
    if not data:
        return False

    expires_at = data[0]
    if expires_at is None:
        return True

    return datetime.utcnow() < expires_at

def give_trial(uid: int):
    with conn.cursor() as cur:
        cur.execute("""
        INSERT INTO users (user_id, expires_at, trial_used)
        VALUES (%s, %s, TRUE)
        ON CONFLICT DO NOTHING
        """, (uid, datetime.utcnow() + timedelta(hours=24)))

def add_permanent(uid: int):
    with conn.cursor() as cur:
        cur.execute("""
        INSERT INTO users (user_id, expires_at, trial_used)
        VALUES (%s, NULL, TRUE)
        ON CONFLICT (user_id)
        DO UPDATE SET expires_at=NULL
        """, (uid,))

def remove_user(uid: int):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE user_id=%s", (uid,))

# ================= CHANNEL CHECK =================
async def joined_channels(bot, uid):
    try:
        ok = ["member", "administrator", "creator"]
        m1 = await bot.get_chat_member(CHANNEL_1, uid)
        m2 = await bot.get_chat_member(CHANNEL_2, uid)
        return m1.status in ok and m2.status in ok
    except:
        return False

# ================= START =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if is_allowed(uid):
        return await update.message.reply_text("✅ Access Granted 🚀")

    user = get_user(uid)
    if user and user[2]:
        return await update.message.reply_text(
            "⛔ Your free trial is over.\n\n"
            "Contact admin for access."
        )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Join Channel 1", url="https://t.me/yourchannel1")],
        [InlineKeyboardButton("🔗 Join Channel 2", url="https://t.me/yourchannel2")],
        [InlineKeyboardButton("✅ Continue", callback_data="check_join")]
    ])

    await update.message.reply_text(
        "🔐 Join both channels to unlock 24h free trial",
        reply_markup=kb
    )

# ================= BUTTONS =================
admin_state = {}

async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()

    # ===== CONTINUE =====
    if q.data == "check_join":
        user = get_user(uid)
        if user and user[2]:
            return await q.message.reply_text(
                "❌ Trial already used.\nContact admin."
            )

        if await joined_channels(ctx.bot, uid):
            give_trial(uid)
            return await q.message.reply_text(
                "🎉 24 HOURS FREE TRIAL STARTED!"
            )
        return await q.answer("Join both channels first", show_alert=True)

    # ===== ADMIN PANEL =====
    if uid == OWNER_ID and q.data == "admin":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Permanent", callback_data="add_perm")],
            [InlineKeyboardButton("➖ Remove User", callback_data="remove_user")],
            [InlineKeyboardButton("📋 User List", callback_data="list_users")]
        ])
        return await q.message.reply_text("🔐 Admin Panel", reply_markup=kb)

    if uid == OWNER_ID:
        admin_state[uid] = q.data
        return await q.message.reply_text("Send User ID")

# ================= TEXT =================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    if uid == OWNER_ID and uid in admin_state:
        if not text.isdigit():
            return await update.message.reply_text("Invalid ID")

        target = int(text)
        action = admin_state.pop(uid)

        if action == "add_perm":
            add_permanent(target)
            return await update.message.reply_text("✅ Permanent access added")

        if action == "remove_user":
            remove_user(target)
            return await update.message.reply_text("❌ User removed")

    if not is_allowed(uid):
        return await update.message.reply_text("⛔ Access denied")

# ================= WARNING SYSTEM =================
async def trial_watcher(app):
    while True:
        await asyncio.sleep(300)
        with conn.cursor() as cur:
            cur.execute("""
            SELECT user_id, expires_at FROM users
            WHERE expires_at IS NOT NULL
            AND warned = FALSE
            """)
            rows = cur.fetchall()

        for uid, exp in rows:
            if exp - datetime.utcnow() <= timedelta(hours=1):
                try:
                    await app.bot.send_message(
                        uid,
                        "⚠️ Your trial will expire in 1 hour!"
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
if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", lambda u,c: buttons(
        type("Q", (), {"callback_query": type("CQ", (), {
            "data":"admin","from_user":u.effective_user,
            "answer":lambda *a,**k:None,
            "message":u.message
        })()}), c
    )))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.job_queue.run_once(lambda _: asyncio.create_task(trial_watcher(app)), 5)

    print("🚀 Bot running with trial warning + admin + retrial block")
    app.run_polling()

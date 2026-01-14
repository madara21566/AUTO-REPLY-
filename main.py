import os
import threading
import time
from datetime import datetime, timedelta

import psycopg2
from flask import Flask
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= ORIGINAL BOT =================
import bot_core

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
        CREATE TABLE IF NOT EXISTS user_access (
            user_id BIGINT PRIMARY KEY,
            trial_start TIMESTAMP,
            trial_end TIMESTAMP,
            trial_used BOOLEAN DEFAULT FALSE,
            is_premium BOOLEAN DEFAULT FALSE,
            temp_access_until TIMESTAMP,
            reminder_sent BOOLEAN DEFAULT FALSE
        );
        """)

def get_user(uid):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM user_access WHERE user_id=%s", (uid,))
        return cur.fetchone()

def start_trial(uid):
    now = datetime.utcnow()
    with conn.cursor() as cur:
        cur.execute("""
        INSERT INTO user_access (user_id, trial_start, trial_end, trial_used)
        VALUES (%s, %s, %s, TRUE)
        ON CONFLICT DO NOTHING
        """, (uid, now, now + timedelta(hours=24)))

def is_allowed(uid):
    if uid == OWNER_ID:
        return True

    user = get_user(uid)
    now = datetime.utcnow()

    if not user:
        start_trial(uid)
        return True

    _, _, trial_end, trial_used, is_premium, temp_until, _ = user

    if is_premium:
        return True

    if temp_until and now <= temp_until:
        return True

    if trial_used and trial_end and now <= trial_end:
        return True

    return False

# ================= UI =================
def premium_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Buy Premium", url="https://t.me/MADARAXHEREE")],
        [InlineKeyboardButton("📊 My Status", callback_data="check_status")]
    ])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏱ Temp Access", callback_data="admin_temp")],
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
    user = get_user(uid)

    if user and not user[4] and user[2] and datetime.utcnow() > user[2]:
        return await update.message.reply_text(
            "❌ *Trial Expired*\n\nPremium lene ke liye 👇",
            reply_markup=premium_button(),
            parse_mode="Markdown"
        )

    if not is_allowed(uid):
        return

    if uid == OWNER_ID:
        await update.message.reply_text(
            "👑 Owner Mode",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 Admin Panel", callback_data="open_admin")]
            ])
        )

    await update.message.reply_text(
        "👋 Welcome!\n\n🎁 *24 Hour FREE Trial Activated*\n\n👇",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 My Status", callback_data="check_status")]
        ]),
        parse_mode="Markdown"
    )

    return await orig_start(update, ctx)

# ================= BUTTONS =================
async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()

    # STATUS
    if q.data == "check_status":
        user = get_user(uid)
        now = datetime.utcnow()

        if uid == OWNER_ID:
            return await q.message.reply_text("👑 Owner – Unlimited Access")

        if not user:
            return await q.message.reply_text("❌ No data")

        _, _, trial_end, trial_used, is_premium, temp_until, _ = user

        if is_premium:
            return await q.message.reply_text("💎 Premium Active")

        if temp_until and now <= temp_until:
            left = temp_until - now
            return await q.message.reply_text(
                f"⏱ Temporary Access\nTime Left: {left.seconds//3600}h"
            )

        if trial_used and trial_end:
            if now <= trial_end:
                left = trial_end - now
                return await q.message.reply_text(
                    f"⏳ Trial Active\n"
                    f"Time Left: {left.seconds//3600}h {left.seconds%3600//60}m",
                    reply_markup=premium_button()
                )
            else:
                return await q.message.reply_text(
                    "❌ Trial Expired",
                    reply_markup=premium_button()
                )

    # ADMIN
    if q.data == "open_admin" and uid == OWNER_ID:
        return await q.message.reply_text("🔐 Admin Panel", reply_markup=admin_menu())

    if q.data == "admin_temp" and uid == OWNER_ID:
        return await q.message.reply_text(
            "Select Temporary Access:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("1 Hour", callback_data="temp_1h")],
                [InlineKeyboardButton("1 Day", callback_data="temp_1d")],
                [InlineKeyboardButton("1 Month", callback_data="temp_1m")]
            ])
        )

    if q.data.startswith("temp_") and uid == OWNER_ID:
        admin_state[uid] = q.data
        return await q.message.reply_text("🆔 User ID bhejo")

    return await orig_buttons(update, ctx)

# ================= TEXT =================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    txt = update.message.text.strip()

    if uid == OWNER_ID and uid in admin_state:
        if not txt.isdigit():
            return await update.message.reply_text("❌ Valid User ID")

        target = int(txt)
        now = datetime.utcnow()

        if admin_state[uid] == "temp_1h":
            until = now + timedelta(hours=1)
        elif admin_state[uid] == "temp_1d":
            until = now + timedelta(days=1)
        else:
            until = now + timedelta(days=30)

        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO user_access (user_id, temp_access_until)
            VALUES (%s, %s)
            ON CONFLICT (user_id)
            DO UPDATE SET temp_access_until = EXCLUDED.temp_access_until
            """, (target, until))

        admin_state.pop(uid)
        return await update.message.reply_text("✅ Temporary Access Granted")

    if not is_allowed(uid):
        return

    return await orig_text(update, ctx)

# ================= FILE =================
async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    return await orig_file(update, ctx)

# ================= TRIAL REMINDER THREAD =================
def trial_reminder_loop(app):
    while True:
        time.sleep(600)
        now = datetime.utcnow()

        with conn.cursor() as cur:
            cur.execute("""
            SELECT user_id, trial_end FROM user_access
            WHERE is_premium=FALSE
              AND trial_used=TRUE
              AND reminder_sent=FALSE
            """)
            users = cur.fetchall()

        for uid, trial_end in users:
            if not trial_end:
                continue

            remaining = (trial_end - now).total_seconds()
            if 3500 <= remaining <= 3600:
                try:
                    app.bot.send_message(
                        chat_id=uid,
                        text="⏰ Trial ending in 1 hour!\n\nBuy premium 👇",
                        reply_markup=premium_button(),
                        parse_mode="Markdown"
                    )
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE user_access SET reminder_sent=TRUE WHERE user_id=%s",
                            (uid,)
                        )
                except:
                    pass

# ================= FLASK =================
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot Running"

def run_flask():
    flask_app.run("0.0.0.0", PORT)

# ================= MAIN =================
if __name__ == "__main__":
    init_db()

    threading.Thread(target=run_flask, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    # ✅ BACKGROUND REMINDER (RENDER SAFE)
    threading.Thread(
        target=trial_reminder_loop,
        args=(app,),
        daemon=True
    ).start()

    print("🚀 BOT RUNNING (FINAL)")
    app.run_polling()

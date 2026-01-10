import os
import io
import sys
import time
import threading
import traceback
import sqlite3
import datetime
from typing import Optional, List, Tuple

import NIKALLLLLLL

from flask import Flask, render_template_string, request, jsonify
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============ UPTIME ============
START_TIME = datetime.datetime.now()

def format_uptime():
    delta = datetime.datetime.now() - START_TIME
    h, r = divmod(delta.seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h:02}:{m:02}:{s:02}"

def uptime_seconds():
    return int((datetime.datetime.now() - START_TIME).total_seconds())

# ============ CONFIG ============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
APP_PORT = int(os.environ.get("PORT", "8080"))
DB_FILE = "bot_stats.db"
ERROR_LOG = "bot_errors.log"

# ============ DB ============
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT,
            timestamp TEXT
        )
        """)

def log_action(uid, uname, action):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO logs (user_id, username, action, timestamp) VALUES (?,?,?,?)",
            (uid, uname or "N/A", action, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )

# ============ IMPORT BOT LOGIC ============
from NIKALLLLLLL import (
    start, set_filename, set_contact_name, set_limit, set_start,
    set_vcf_start, set_country_code, set_group_number,
    make_vcf_command, merge_command, done_merge,
    handle_document, handle_text,
    reset_settings, my_settings, txt2vcf, vcf2txt
)

# ============ TELEGRAM ============
application = Application.builder().token(BOT_TOKEN).build()
tg_bot = Bot(BOT_TOKEN)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = traceback.format_exc()
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(err + "\n")

application.add_error_handler(error_handler)

# === COMMANDS (NO ACCESS CHECK) ===
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("mysettings", my_settings))
application.add_handler(CommandHandler("reset", reset_settings))
application.add_handler(CommandHandler("setfilename", set_filename))
application.add_handler(CommandHandler("setcontactname", set_contact_name))
application.add_handler(CommandHandler("setlimit", set_limit))
application.add_handler(CommandHandler("setstart", set_start))
application.add_handler(CommandHandler("setvcfstart", set_vcf_start))
application.add_handler(CommandHandler("setcountrycode", set_country_code))
application.add_handler(CommandHandler("setgroup", set_group_number))
application.add_handler(CommandHandler("makevcf", make_vcf_command))
application.add_handler(CommandHandler("merge", merge_command))
application.add_handler(CommandHandler("done", done_merge))
application.add_handler(CommandHandler("txt2vcf", txt2vcf))
application.add_handler(CommandHandler("vcf2txt", vcf2txt))

application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

# ============ FLASK DASHBOARD ============
flask_app = Flask(__name__)

@flask_app.route("/")
def dashboard():
    return "GOD MADARA BOT IS RUNNING 🚀"

@flask_app.route("/api/stats")
def stats():
    with sqlite3.connect(DB_FILE) as c:
        users = c.execute("SELECT COUNT(DISTINCT user_id) FROM logs").fetchone()[0]
        actions = c.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    return jsonify({
        "users": users,
        "actions": actions,
        "uptime": format_uptime()
    })

def run_flask():
    flask_app.run(host="0.0.0.0", port=APP_PORT)

# ============ RUN ============
if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()
    print("BOT STARTED")
    application.run_polling()

import os
import sys
import time
import sqlite3
import threading
import datetime
import traceback

from flask import Flask, request, redirect, session, render_template_string, jsonify
from telegram import Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

import NIKALLLLLLL
from NIKALLLLLLL import (
    start, handle_document, handle_text
)

# ================= CONFIG =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
PORT = int(os.environ.get("PORT", "8080"))

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

DB_FILE = "bot.db"
ERROR_LOG = "errors.log"

# ================= INIT =================
app = Flask(__name__)
app.secret_key = "madara-secret"

bot = Bot(BOT_TOKEN)
application = Application.builder().token(BOT_TOKEN).build()

START_TIME = datetime.datetime.now()

# ================= DATABASE =================
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            added_on TEXT,
            expires_on TEXT
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            time TEXT
        )
        """)

        conn.commit()

# ================= AUTH =================
def is_authorized(user_id):
    if user_id == OWNER_ID:
        return True

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT 1 FROM users
            WHERE user_id=?
            AND (expires_on IS NULL OR expires_on > ?)
        """, (user_id, now))
        return c.fetchone() is not None

# ================= CLEANUP =================
def cleanup_expired_users():
    while True:
        try:
            with sqlite3.connect(DB_FILE) as conn:
                c = conn.cursor()
                c.execute("""
                    DELETE FROM users
                    WHERE expires_on IS NOT NULL
                    AND expires_on <= datetime('now')
                """)
                conn.commit()
        except Exception as e:
            with open(ERROR_LOG, "a") as f:
                f.write(f"{datetime.datetime.utcnow()} cleanup error {e}\n")

        time.sleep(6 * 60 * 60)  # every 6 hours

# ================= TELEGRAM GUARD =================
def protected(handler):
    async def wrapper(update, context):
        user_id = update.effective_user.id
        if not is_authorized(user_id):
            await update.message.reply_text("❌ Access denied. Contact owner.")
            return
        return await handler(update, context)
    return wrapper

# ================= TELEGRAM =================
application.add_handler(CommandHandler("start", protected(start)))
application.add_handler(MessageHandler(filters.Document.ALL, protected(handle_document)))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, protected(handle_text)))

async def error_handler(update, context):
    err = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
    with open(ERROR_LOG, "a") as f:
        f.write(err + "\n")

application.add_error_handler(error_handler)

# ================= ADMIN AUTH =================
def admin_logged_in():
    return session.get("admin") == True

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if (
            request.form["username"] == ADMIN_USERNAME
            and request.form["password"] == ADMIN_PASSWORD
        ):
            session["admin"] = True
            return redirect("/admin")
        return "Invalid login"

    return """
    <h3>Admin Login</h3>
    <form method="post">
      <input name="username"><br>
      <input name="password" type="password"><br>
      <button>Login</button>
    </form>
    """

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/admin/login")

# ================= ADMIN PANEL =================
@app.route("/admin")
def admin_panel():
    if not admin_logged_in():
        return redirect("/admin/login")

    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, expires_on FROM users")
        users = c.fetchall()

    return render_template_string("""
    <h2>👑 OWNER ADMIN PANEL</h2>

    <h3>Add User</h3>
    <form action="/admin/add" method="post">
      <input name="user_id" placeholder="User ID">
      <input name="days" placeholder="Days (0=life)">
      <button>Add</button>
    </form>

    <h3>Broadcast</h3>
    <form action="/admin/broadcast" method="post" enctype="multipart/form-data">
      <textarea name="msg"></textarea><br>
      <input type="file" name="file"><br>
      <button>Send</button>
    </form>

    <h3>Users</h3>
    <ul>
    {% for u in users %}
      <li>{{u[0]}} | {{u[1] or 'Lifetime'}}
      <a href="/admin/remove/{{u[0]}}">❌</a></li>
    {% endfor %}
    </ul>

    <a href="/admin/logout">Logout</a>
    """, users=users)

@app.route("/admin/add", methods=["POST"])
def admin_add():
    if not admin_logged_in():
        return redirect("/admin/login")

    uid = int(request.form["user_id"])
    days = int(request.form.get("days", 0))

    expires = None
    if days > 0:
        expires = (datetime.datetime.now() +
                   datetime.timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO users VALUES (?, ?, ?)
        """, (uid,
              datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              expires))
        conn.commit()

    return redirect("/admin")

@app.route("/admin/remove/<int:uid>")
def admin_remove(uid):
    if not admin_logged_in():
        return redirect("/admin/login")

    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE user_id=?", (uid,))
        conn.commit()

    return redirect("/admin")

@app.route("/admin/broadcast", methods=["POST"])
def admin_broadcast():
    if not admin_logged_in():
        return redirect("/admin/login")

    msg = request.form.get("msg")
    file = request.files.get("file")

    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT user_id FROM users
            WHERE expires_on IS NULL OR expires_on > datetime('now')
        """)
        users = c.fetchall()

    for (uid,) in users:
        try:
            if msg:
                bot.send_message(uid, msg)
            if file:
                file.stream.seek(0)
                bot.send_document(uid, file)
        except:
            pass

    return redirect("/admin")

# ================= RUN =================
if __name__ == "__main__":
    init_db()

    threading.Thread(target=cleanup_expired_users, daemon=True).start()
    threading.Thread(target=lambda: app.run("0.0.0.0", PORT), daemon=True).start()

    print("Bot running...")
    application.run_polling()

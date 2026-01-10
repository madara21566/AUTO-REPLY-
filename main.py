import os, re, threading
import psycopg2
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# ================== ENV ==================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
DATABASE_URL = os.environ.get("DATABASE_URL")
PORT = int(os.environ.get("PORT", "10000"))

# ================== DB ==================
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

# ================= SETTINGS =================
DEFAULT_SETTINGS = {
    "file_name": "Contacts",
    "contact_name": "Contact",
    "limit": 100,
    "contact_start": 1,
    "vcf_start": 1,
    "country_code": "",
    "group_number": None,
}

user_settings = {}
user_state = {}
merge_queue = {}

def settings(uid):
    user_settings.setdefault(uid, DEFAULT_SETTINGS.copy())
    return user_settings[uid]

def state(uid):
    user_state.setdefault(uid, {"mode": None, "step": None})
    return user_state[uid]

# ================= HELPERS =================
def extract_txt(path):
    return re.findall(r"\d{7,}", open(path, "r", errors="ignore").read())

def extract_vcf(path):
    nums = []
    for l in open(path, "r", errors="ignore"):
        if l.startswith("TEL"):
            n = re.sub(r"\D", "", l)
            if len(n) >= 7:
                nums.append(n)
    return nums

def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def make_vcf(numbers, cfg, index):
    start = cfg["contact_start"] + index * cfg["limit"]
    out = ""
    for i, n in enumerate(numbers, start=start):
        name = f"{cfg['contact_name']}{str(i).zfill(3)}"
        num = f"{cfg['country_code']}{n}" if cfg["country_code"] else n
        out += f"BEGIN:VCARD\nVERSION:3.0\nFN:{name}\nTEL:{num}\nEND:VCARD\n"
    fname = f"{cfg['file_name']}_{cfg['vcf_start'] + index}.vcf"
    open(fname, "w").write(out)
    return fname

# ================= UI =================
def main_menu(uid):
    kb = [
        [InlineKeyboardButton("⚡ MAKE VCF", callback_data="quick_vcf")],
        [InlineKeyboardButton("📇 Generate VCF", callback_data="gen")],
        [InlineKeyboardButton("🔁 TXT → VCF", callback_data="txt2vcf"),
         InlineKeyboardButton("🔄 VCF → TXT", callback_data="vcf2txt")],
        [InlineKeyboardButton("🧩 Merge Files", callback_data="merge")],
    ]
    if uid == OWNER_ID:
        kb.append([InlineKeyboardButton("🔐 Access Panel", callback_data="access")])
    return InlineKeyboardMarkup(kb)

def access_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add User", callback_data="add_user")],
        [InlineKeyboardButton("➖ Remove User", callback_data="remove_user")],
        [InlineKeyboardButton("📋 List Users", callback_data="list_user")],
        [InlineKeyboardButton("⬅ Back", callback_data="back")]
    ])

# ================= START =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_allowed(uid):
        return await update.message.reply_text("⛔ Private Bot")
    await update.message.reply_text(
        "👋 Welcome to VCF Manager Bot",
        reply_markup=main_menu(uid)
    )

# ================= BUTTONS =================
async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()

    if not is_allowed(uid):
        return await q.answer("⛔ Private", show_alert=True)

    st = state(uid)

    if q.data == "access" and uid == OWNER_ID:
        return await q.message.reply_text("🔐 Access Panel", reply_markup=access_menu())

    if q.data == "add_user":
        st["mode"] = "add_user"
        return await q.message.reply_text("User ka message forward karo")

    if q.data == "remove_user":
        st["mode"] = "remove_user"
        return await q.message.reply_text("User ka message forward karo")

    if q.data == "list_user":
        users = db_list()
        return await q.message.reply_text("👥 Users:\n" + ("\n".join(users) if users else "None"))

    if q.data == "back":
        return await q.message.reply_text("⬅ Back", reply_markup=main_menu(uid))

# ================= TEXT =================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_allowed(uid):
        return

    st = state(uid)

    if st.get("mode") in ("add_user", "remove_user") and uid == OWNER_ID:
        target = update.message.forward_from.id
        if st["mode"] == "add_user":
            db_add(target)
            msg = "✅ Access Added"
        else:
            db_remove(target)
            msg = "❌ Access Removed"
        st["mode"] = None
        return await update.message.reply_text(msg, reply_markup=access_menu())

# ================= FILE =================
async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_allowed(uid):
        return

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

    threading.Thread(target=run_flask).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("🚀 Bot running with PostgreSQL + Flask")
    app.run_polling()

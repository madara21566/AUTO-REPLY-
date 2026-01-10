import os
import re
import traceback
import pandas as pd
from datetime import datetime
import threading

from flask import Flask
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ================== WEB SERVER (RENDER KEEP ALIVE) ==================
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "✅ VCF Bot is running 24/7 (Render Free)"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# ================== CONFIG ==================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 7640327597

ALLOWED_USERS = [
    7856502907, 7950732287, 8128934569, 5849097477,
    7640327597, 7669357884, 7118726445, 7043391463, 8047407478
]

# ================== DEFAULTS ==================
DEFAULT_FILE_NAME = "Contacts"
DEFAULT_CONTACT_NAME = "Contact"
DEFAULT_LIMIT = 100

# ================== USER DATA ==================
user_settings = {}
user_state = {}   # { user_id: {"mode":None,"setting":None} }
merge_data = {}

# ================== HELPERS ==================
def is_authorized(user_id):
    return user_id in ALLOWED_USERS

def get_state(user_id):
    if user_id not in user_state:
        user_state[user_id] = {"mode": None, "setting": None}
    return user_state[user_id]

def get_settings(user_id):
    if user_id not in user_settings:
        user_settings[user_id] = {
            "file_name": DEFAULT_FILE_NAME,
            "contact_name": DEFAULT_CONTACT_NAME,
            "limit": DEFAULT_LIMIT,
            "country_code": "",
        }
    return user_settings[user_id]

def generate_vcf(numbers, filename, cname, code=""):
    vcf = ""
    for i, num in enumerate(numbers, start=1):
        name = f"{cname}{str(i).zfill(3)}"
        final = f"{code}{num}" if code else num
        vcf += (
            "BEGIN:VCARD\n"
            "VERSION:3.0\n"
            f"FN:{name}\n"
            f"TEL;TYPE=CELL:{final}\n"
            "END:VCARD\n"
        )
    path = f"{filename}.vcf"
    with open(path, "w", encoding="utf-8") as f:
        f.write(vcf)
    return path

def extract_vcf(path):
    nums = set()
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("TEL"):
                n = re.sub(r"[^0-9]", "", line)
                if len(n) >= 7:
                    nums.add(n)
    return nums

def extract_txt(path):
    nums = set()
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for l in f:
            nums.update(re.findall(r"\d{7,}", l))
    return nums

# ================== UI ==================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Make VCF", callback_data="make")],
        [
            InlineKeyboardButton("🔁 TXT → VCF", callback_data="txt2vcf"),
            InlineKeyboardButton("🔄 VCF → TXT", callback_data="vcf2txt"),
        ],
        [InlineKeyboardButton("🧩 Merge Files", callback_data="merge")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("📊 My Settings", callback_data="mysettings")],
    ])

def settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 File Name", callback_data="set_file")],
        [InlineKeyboardButton("👤 Contact Name", callback_data="set_contact")],
        [InlineKeyboardButton("📊 Per VCF Limit", callback_data="set_limit")],
        [InlineKeyboardButton("🌍 Country Code", callback_data="set_country")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")],
    ])

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ Access denied")
        return
    await update.message.reply_text(
        "👋 *Welcome to VCF Maker Bot*\n\n"
        "👉 Buttons use karo, sab simple hai 🙂",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

# ================== BUTTON HANDLER ==================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    state = get_state(uid)

    if q.data == "make":
        state["mode"] = "make"
        state["setting"] = None
        await q.message.reply_text("📤 Numbers ya file bhejo")

    elif q.data == "txt2vcf":
        state["mode"] = "txt2vcf"
        await q.message.reply_text("📂 TXT file bhejo")

    elif q.data == "vcf2txt":
        state["mode"] = "vcf2txt"
        await q.message.reply_text("📂 VCF file bhejo")

    elif q.data == "merge":
        state["mode"] = "merge"
        merge_data[uid] = []
        await q.message.reply_text(
            "📥 Files bhejo (TXT/VCF)\n"
            "Sab bhejne ke baad *DONE* likho",
            parse_mode="Markdown"
        )

    elif q.data == "settings":
        await q.message.reply_text("⚙️ Settings", reply_markup=settings_menu())

    elif q.data == "set_file":
        state["setting"] = "file_name"
        await q.message.reply_text("✏️ File name bhejo\nExample: Contacts, Friends")

    elif q.data == "set_contact":
        state["setting"] = "contact_name"
        await q.message.reply_text("✏️ Contact name bhejo\nExample: User")

    elif q.data == "set_limit":
        state["setting"] = "limit"
        await q.message.reply_text("✏️ Per VCF limit bhejo\nExample: 100")

    elif q.data == "set_country":
        state["setting"] = "country_code"
        await q.message.reply_text("✏️ Country code bhejo\nExample: +91")

    elif q.data == "mysettings":
        s = get_settings(uid)
        await q.message.reply_text(
            f"📊 *Your Settings*\n"
            f"📂 File: `{s['file_name']}`\n"
            f"👤 Contact: `{s['contact_name']}`\n"
            f"📊 Limit: `{s['limit']}`\n"
            f"🌍 Code: `{s['country_code']}`",
            parse_mode="Markdown"
        )

    elif q.data == "back":
        await q.message.reply_text("⬅️ Main Menu", reply_markup=main_menu())

# ================== TEXT ==================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_authorized(uid):
        return

    state = get_state(uid)
    settings = get_settings(uid)
    text = update.message.text.strip()

    # SETTINGS INPUT
    if state["setting"]:
        key = state["setting"]
        if key == "limit" and not text.isdigit():
            await update.message.reply_text("❌ Limit number hona chahiye")
            return
        settings[key] = int(text) if key == "limit" else text
        state["setting"] = None
        await update.message.reply_text("✅ Setting updated")
        return

    # MERGE DONE
    if state["mode"] == "merge" and text.lower() == "done":
        all_nums = set()
        for p in merge_data.get(uid, []):
            if os.path.exists(p):
                if p.endswith(".vcf"):
                    all_nums.update(extract_vcf(p))
                elif p.endswith(".txt"):
                    all_nums.update(extract_txt(p))
                os.remove(p)

        out = generate_vcf(
            all_nums,
            settings["file_name"],
            settings["contact_name"],
            settings["country_code"]
        )
        await update.message.reply_document(open(out, "rb"))
        os.remove(out)

        merge_data.pop(uid, None)
        state["mode"] = None
        return

    # NORMAL NUMBERS
    nums = re.findall(r"\d{7,}", text)
    if nums:
        out = generate_vcf(
            nums,
            settings["file_name"],
            settings["contact_name"],
            settings["country_code"]
        )
        await update.message.reply_document(open(out, "rb"))
        os.remove(out)

# ================== FILE ==================
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_authorized(uid):
        return

    state = get_state(uid)
    settings = get_settings(uid)

    doc = update.message.document
    path = f"{doc.file_unique_id}_{doc.file_name}"
    await (await context.bot.get_file(doc.file_id)).download_to_drive(path)

    try:
        if state["mode"] == "merge":
            merge_data[uid].append(path)
            await update.message.reply_text("📥 File added, aur bhejo ya DONE likho")
            return

        if path.endswith(".vcf"):
            nums = extract_vcf(path)
        elif path.endswith(".txt"):
            nums = extract_txt(path)
        elif path.endswith(".csv"):
            nums = pd.read_csv(path).iloc[:, 0].astype(str).tolist()
        elif path.endswith(".xlsx"):
            nums = pd.read_excel(path).iloc[:, 0].astype(str).tolist()
        else:
            await update.message.reply_text("❌ Unsupported file")
            return

        out = generate_vcf(
            nums,
            settings["file_name"],
            settings["contact_name"],
            settings["country_code"]
        )
        await update.message.reply_document(open(out, "rb"))
        os.remove(out)

    finally:
        if state["mode"] != "merge" and os.path.exists(path):
            os.remove(path)

# ================== ERROR ==================
async def error_handler(update, context):
    err = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
    with open("bot_errors.log", "a") as f:
        f.write(err)
    try:
        await context.bot.send_message(OWNER_ID, err[:4000])
    except:
        pass

# ================== MAIN ==================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_error_handler(error_handler)
    print("🚀 Bot running (FINAL FIXED)")
    app.run_polling()

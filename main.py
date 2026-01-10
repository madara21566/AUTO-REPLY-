import os, re, asyncio
import pandas as pd
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.request import HTTPXRequest

# ================= CONFIG =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
APP_URL = os.environ.get("APP_URL")

# ================= DEFAULT SETTINGS =================
DEFAULT_SETTINGS = {
    "file_name": "Contacts",
    "contact_name": "Contact",
    "limit": 100,
    "start_index": 1,
    "vcf_start": 1,
    "country_code": "",
    "group_start": None,
}

user_settings = {}
user_state = {}
merge_files = {}
rename_files = {}
rename_contacts = {}

# ================= FLASK =================
app = Flask(__name__)

@app.route("/")
def home():
    return "VCF Bot Running"

# ================= HELPERS =================
def settings(uid):
    user_settings.setdefault(uid, DEFAULT_SETTINGS.copy())
    return user_settings[uid]

def state(uid):
    user_state.setdefault(uid, {"mode": None, "step": None})
    return user_state[uid]

def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def extract_numbers_from_vcf(path):
    nums = []
    with open(path, "r", errors="ignore") as f:
        for line in f:
            if line.startswith("TEL"):
                n = re.sub(r"\D", "", line)
                if len(n) >= 7:
                    nums.append(n)
    return nums

def extract_numbers_from_txt(path):
    nums = []
    with open(path, "r", errors="ignore") as f:
        for l in f:
            nums += re.findall(r"\d{7,}", l)
    return nums

def make_vcf(numbers, cfg, index):
    start = cfg["start_index"] + index * cfg["limit"]
    out = ""
    for i, n in enumerate(numbers, start=start):
        name = f"{cfg['contact_name']}{str(i).zfill(3)}"
        num = f"{cfg['country_code']}{n}" if cfg["country_code"] else n
        out += f"BEGIN:VCARD\nVERSION:3.0\nFN:{name}\nTEL;TYPE=CELL:{num}\nEND:VCARD\n"
    fname = f"{cfg['file_name']}_{cfg['vcf_start'] + index}.vcf"
    open(fname, "w").write(out)
    return fname

# ================= UI =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📇 Generate VCF", callback_data="gen")],
        [InlineKeyboardButton("🔁 TXT → VCF", callback_data="txt2vcf"),
         InlineKeyboardButton("🔄 VCF → TXT", callback_data="vcf2txt")],
        [InlineKeyboardButton("🧩 Merge Files", callback_data="merge")],
        [InlineKeyboardButton("✏️ Rename VCF Files", callback_data="rename_files")],
        [InlineKeyboardButton("✏️ Rename Contacts", callback_data="rename_contacts")],
        [InlineKeyboardButton("📊 My Settings", callback_data="mysettings")],
        [InlineKeyboardButton("♻️ Reset", callback_data="reset")]
    ])

# ================= HANDLERS =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to VCF Generator Bot\nChoose option 👇",
        reply_markup=main_menu()
    )

async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    st = state(uid)

    st["mode"] = q.data
    st["step"] = None

    messages = {
        "gen": "📤 Send numbers",
        "txt2vcf": "📂 Send TXT file",
        "vcf2txt": "📂 Send VCF file",
        "merge": "📥 Send files, then type DONE",
        "rename_files": "📂 Send VCF files to rename",
        "rename_contacts": "📂 Send VCF files",
        "mysettings": None,
        "reset": None,
    }

    if q.data == "mysettings":
        cfg = settings(uid)
        return await q.message.reply_text(
            f"📂 File name: {cfg['file_name']}\n"
            f"👤 Contact name: {cfg['contact_name']}\n"
            f"📊 Limit: {cfg['limit']}\n"
            f"🔢 Start index: {cfg['start_index']}\n"
            f"📄 VCF start: {cfg['vcf_start']}\n"
            f"🌍 Country code: {cfg['country_code'] or 'None'}"
        )

    if q.data == "reset":
        user_settings[uid] = DEFAULT_SETTINGS.copy()
        merge_files.pop(uid, None)
        rename_files.pop(uid, None)
        rename_contacts.pop(uid, None)
        return await q.message.reply_text("♻️ Reset done")

    await q.message.reply_text(messages[q.data])

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = state(uid)
    cfg = settings(uid)
    txt = update.message.text.strip()

    if st["mode"] == "merge" and txt.lower() == "done":
        nums = []
        for f in merge_files.get(uid, []):
            nums += extract_numbers_from_vcf(f) if f.endswith(".vcf") else extract_numbers_from_txt(f)
            os.remove(f)
        for i, c in enumerate(chunk(nums, cfg["limit"])):
            f = make_vcf(c, cfg, i)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)
        merge_files.pop(uid, None)
        st["mode"] = None
        return

    if st["mode"] == "rename_files":
        rename_files[uid] = txt
        for i, f in enumerate(rename_files.get("files", []), start=1):
            new = f"{txt}_{i}.vcf"
            os.rename(f, new)
            await update.message.reply_document(open(new, "rb"))
            os.remove(new)
        st["mode"] = None
        return

    numbers = re.findall(r"\d{7,}", txt)
    if numbers:
        for i, c in enumerate(chunk(numbers, cfg["limit"])):
            f = make_vcf(c, cfg, i)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)

async def file_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = state(uid)
    cfg = settings(uid)

    doc = update.message.document
    path = doc.file_name
    await (await ctx.bot.get_file(doc.file_id)).download_to_drive(path)

    if st["mode"] == "merge":
        merge_files.setdefault(uid, []).append(path)
        return await update.message.reply_text("Added")

    if st["mode"] == "rename_files":
        rename_files.setdefault("files", []).append(path)
        return await update.message.reply_text("File received, now send new name")

    if st["mode"] == "rename_contacts":
        rename_contacts.setdefault(uid, []).append(path)
        return await update.message.reply_text("Now send new contact name")

    if st["mode"] == "vcf2txt":
        nums = extract_numbers_from_vcf(path)
        out = "numbers.txt"
        open(out, "w").write("\n".join(nums))
        await update.message.reply_document(open(out, "rb"))
        os.remove(out)
        os.remove(path)
        return

    nums = extract_numbers_from_txt(path)
    for i, c in enumerate(chunk(nums, cfg["limit"])):
        f = make_vcf(c, cfg, i)
        await update.message.reply_document(open(f, "rb"))
        os.remove(f)
    os.remove(path)

# ================= TELEGRAM APP =================
request_client = HTTPXRequest()
application = ApplicationBuilder().token(BOT_TOKEN).request(request_client).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(buttons))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
application.add_handler(MessageHandler(filters.Document.ALL, file_handler))

asyncio.get_event_loop().run_until_complete(application.initialize())
asyncio.get_event_loop().run_until_complete(application.start())

# ================= WEBHOOK =================
@app.route("/webhook", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "ok"

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

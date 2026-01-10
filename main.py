import os, re, asyncio, traceback
import pandas as pd
from flask import Flask, request
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
from telegram.request import HTTPXRequest

# ================= CONFIG =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
APP_URL = os.environ.get("APP_URL")

# ====== OPEN FOR ALL (NO AUTH ISSUE) ======
def auth(uid): 
    return True

# ================= DEFAULT SETTINGS =================
DEFAULT_SETTINGS = {
    "file_name": "Contacts",
    "contact_name": "Contact",
    "limit": 100,
    "start_index": None,
    "vcf_start": None,
    "country_code": None,
    "group_start": None,
}

user_settings = {}
user_state = {}
merge_files = {}

# ================= FLASK =================
app = Flask(__name__)

@app.route("/")
def home():
    return "VCF Bot is running"

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

def extract_vcf(path):
    nums = set()
    with open(path, "r", errors="ignore") as f:
        for l in f:
            if l.startswith("TEL"):
                n = re.sub(r"\D", "", l)
                if len(n) >= 7:
                    nums.add(n)
    return nums

def extract_txt(path):
    nums = set()
    with open(path, "r", errors="ignore") as f:
        for l in f:
            nums.update(re.findall(r"\d{7,}", l))
    return nums

def make_vcf(nums, cfg, idx):
    start = (cfg["start_index"] or 1) + idx * cfg["limit"]
    out = ""
    for i, n in enumerate(nums, start=start):
        name = f"{cfg['contact_name']}{str(i).zfill(3)}"
        if cfg["group_start"] is not None:
            name += f" (Group {cfg['group_start'] + idx})"
        num = f"{cfg['country_code']}{n}" if cfg["country_code"] else n
        out += (
            "BEGIN:VCARD\n"
            "VERSION:3.0\n"
            f"FN:{name}\n"
            f"TEL;TYPE=CELL:{num}\n"
            "END:VCARD\n"
        )
    vnum = (cfg["vcf_start"] or 1) + idx
    fname = f"{cfg['file_name']}_{vnum}.vcf"
    with open(fname, "w") as f:
        f.write(out)
    return fname

# ================= UI =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📇 Generate VCF", callback_data="gen")],
        [InlineKeyboardButton("🔁 TXT → VCF", callback_data="txt2vcf"),
         InlineKeyboardButton("🔄 VCF → TXT", callback_data="vcf2txt")],
        [InlineKeyboardButton("🧩 Merge Files", callback_data="merge")],
        [InlineKeyboardButton("📊 My Settings", callback_data="mysettings")],
        [InlineKeyboardButton("♻️ Reset", callback_data="reset")],
    ])

def gen_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 Set File Name", callback_data="set_file")],
        [InlineKeyboardButton("👤 Set Contact Name", callback_data="set_contact")],
        [InlineKeyboardButton("📊 Set Limit", callback_data="set_limit")],
        [InlineKeyboardButton("🔢 Contact Start", callback_data="set_start")],
        [InlineKeyboardButton("📄 VCF Start", callback_data="set_vcf")],
        [InlineKeyboardButton("🌍 Country Code", callback_data="set_country")],
        [InlineKeyboardButton("📑 Group Number", callback_data="set_group")],
        [InlineKeyboardButton("✅ Done", callback_data="gen_done")],
    ])

# ================= HANDLERS =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to VCF Generator Bot",
        reply_markup=main_menu()
    )

async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    st = state(uid)
    cfg = settings(uid)

    if q.data == "gen":
        st["mode"] = "gen"
        st["step"] = None
        return await q.message.reply_text(
            "⚙️ Set details first",
            reply_markup=gen_menu()
        )

    if q.data in ["txt2vcf", "vcf2txt"]:
        st["mode"] = q.data
        return await q.message.reply_text("📂 Send file")

    if q.data == "merge":
        st["mode"] = "merge"
        merge_files[uid] = []
        return await q.message.reply_text("📥 Send files, then type DONE")

    if q.data.startswith("set_"):
        st["step"] = q.data
        prompts = {
            "set_file": "Send file name",
            "set_contact": "Send contact name",
            "set_limit": "Send limit",
            "set_start": "Send contact start",
            "set_vcf": "Send vcf start",
            "set_country": "Send country code (+91)",
            "set_group": "Send group number",
        }
        return await q.message.reply_text(prompts[q.data])

    if q.data == "gen_done":
        st["step"] = None
        return await q.message.reply_text("📤 Now send numbers or file")

    if q.data == "mysettings":
        return await q.message.reply_text(
            f"📂 File name: {cfg['file_name']}\n"
            f"👤 Contact name: {cfg['contact_name']}\n"
            f"📊 Limit: {cfg['limit']}\n"
            f"🔢 Start index: {cfg['start_index'] or 'Not set'}\n"
            f"📄 VCF start: {cfg['vcf_start'] or 'Not set'}\n"
            f"🌍 Country code: {cfg['country_code'] or 'None'}\n"
            f"📑 Group start: {cfg['group_start'] or 'Not set'}"
        )

    if q.data == "reset":
        user_settings[uid] = DEFAULT_SETTINGS.copy()
        user_state[uid] = {"mode": None, "step": None}
        merge_files.pop(uid, None)
        return await q.message.reply_text("♻️ Reset done")

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = state(uid)
    cfg = settings(uid)
    txt = update.message.text.strip()

    if st["step"]:
        keymap = {
            "set_file": "file_name",
            "set_contact": "contact_name",
            "set_limit": "limit",
            "set_start": "start_index",
            "set_vcf": "vcf_start",
            "set_country": "country_code",
            "set_group": "group_start",
        }
        key = keymap[st["step"]]
        cfg[key] = int(txt) if txt.isdigit() else txt
        st["step"] = None
        return await update.message.reply_text(f"✅ {key} set")

    if st["mode"] == "merge" and txt.lower() == "done":
        nums = set()
        for p in merge_files.get(uid, []):
            nums |= extract_vcf(p) if p.endswith(".vcf") else extract_txt(p)
            os.remove(p)
        for i, c in enumerate(chunk(list(nums), cfg["limit"])):
            f = make_vcf(c, cfg, i)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)
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

    nums = []
    if path.endswith(".vcf"):
        nums = list(extract_vcf(path))
    elif path.endswith(".txt"):
        nums = list(extract_txt(path))

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

# 🔥 REQUIRED FOR WEBHOOK (FIX)
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

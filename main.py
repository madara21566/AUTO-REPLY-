    import os, re, traceback
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
OWNER_ID = 7640327597

ALLOWED_USERS = {
    7856502907,7950732287,8128934569,5849097477,
    7640327597,7669357884,7118726445,7043391463,8047407478
}

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

# ================= FLASK APP =================
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ VCF Bot Webhook Running"

# ================= HELPERS =================
def auth(uid): 
    return uid in ALLOWED_USERS

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
    nums=set()
    with open(path,"r",errors="ignore") as f:
        for l in f:
            if l.startswith("TEL"):
                n=re.sub(r"\D","",l)
                if len(n)>=7: nums.add(n)
    return nums

def extract_txt(path):
    nums=set()
    with open(path,"r",errors="ignore") as f:
        for l in f:
            nums.update(re.findall(r"\d{7,}",l))
    return nums

def make_vcf(nums, cfg, idx):
    start = (cfg["start_index"] or 1) + (idx * cfg["limit"])
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
        [InlineKeyboardButton("♻️ Reset Settings", callback_data="reset")]
    ])

def gen_settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 Set File Name", callback_data="set_file")],
        [InlineKeyboardButton("👤 Set Contact Name", callback_data="set_contact")],
        [InlineKeyboardButton("📊 Set VCF Per Limit", callback_data="set_limit")],
        [InlineKeyboardButton("🔢 Set Contact Number Start", callback_data="set_start")],
        [InlineKeyboardButton("📄 Set VCF Number Start", callback_data="set_vcf")],
        [InlineKeyboardButton("🌍 Set Country Code", callback_data="set_country")],
        [InlineKeyboardButton("📑 Set Group Number", callback_data="set_group")],
        [InlineKeyboardButton("✅ Done", callback_data="gen_done")]
    ])

# ================= BOT HANDLERS =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not auth(uid):
        return await update.message.reply_text("❌ Access denied")
    await update.message.reply_text(
        "👋 Welcome to VCF Generator Bot\n\nChoose an option below 👇",
        reply_markup=main_menu()
    )

async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    st = state(uid)
    cfg = settings(uid)

    # ===== MAIN MODES =====
    if q.data == "gen":
        st["mode"] = "generate"
        st["step"] = None
        return await q.message.reply_text(
            "⚙️ Please set details first",
            reply_markup=gen_settings_menu()
        )

    if q.data in ["txt2vcf", "vcf2txt"]:
        st["mode"] = q.data
        return await q.message.reply_text("📂 Send the file")

    if q.data == "merge":
        st["mode"] = "merge_files"
        merge_files[uid] = []
        return await q.message.reply_text("📥 Send TXT / VCF files")

    # ===== SETTINGS BUTTONS =====
    if q.data.startswith("set_"):
        st["step"] = q.data
        prompts = {
            "set_file": "✏️ Send your file name",
            "set_contact": "✏️ Send your contact name",
            "set_limit": "✏️ Send VCF per limit (number)",
            "set_start": "✏️ Send contact number start",
            "set_vcf": "✏️ Send VCF file number start",
            "set_country": "✏️ Send country code (Example: +91)",
            "set_group": "✏️ Send group number"
        }
        return await q.message.reply_text(prompts[q.data])

    if q.data == "gen_done":
        st["step"] = None
        return await q.message.reply_text(
            "📤 Now send numbers or file\n"
            "Example:\n3838376362 8283736272"
        )

    # ===== MY SETTINGS =====
    if q.data == "mysettings":
        msg = (
            "📊 Your Current Settings\n\n"
            f"📂 File name: {cfg['file_name']}\n"
            f"👤 Contact name: {cfg['contact_name']}\n"
            f"📊 Limit: {cfg['limit']}\n"
            f"🔢 Start index: {cfg['start_index'] if cfg['start_index'] is not None else 'Not set'}\n"
            f"📄 VCF start: {cfg['vcf_start'] if cfg['vcf_start'] is not None else 'Not set'}\n"
            f"🌍 Country code: {cfg['country_code'] if cfg['country_code'] else 'None'}\n"
            f"📑 Group start: {cfg['group_start'] if cfg['group_start'] is not None else 'Not set'}"
        )
        return await q.message.reply_text(msg)

    # ===== RESET =====
    if q.data == "reset":
        user_settings[uid] = DEFAULT_SETTINGS.copy()
        user_state[uid] = {"mode": None, "step": None}
        merge_files.pop(uid, None)
        return await q.message.reply_text("♻️ All settings reset successfully ✅")

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not auth(uid):
        return

    st = state(uid)
    cfg = settings(uid)
    text = update.message.text.strip()

    # ===== SETTING INPUT =====
    if st["step"]:
        key_map = {
            "set_file": "file_name",
            "set_contact": "contact_name",
            "set_limit": "limit",
            "set_start": "start_index",
            "set_vcf": "vcf_start",
            "set_country": "country_code",
            "set_group": "group_start"
        }
        key = key_map[st["step"]]
        cfg[key] = int(text) if key in ["limit","start_index","vcf_start","group_start"] and text.isdigit() else text
        st["step"] = None
        return await update.message.reply_text(f"✅ Your {key.replace('_',' ')} is set")

    # ===== MERGE DONE =====
    if st["mode"] == "merge_files" and text.lower() == "done":
        nums=set()
        for p in merge_files.get(uid, []):
            if os.path.exists(p):
                nums |= extract_vcf(p) if p.endswith(".vcf") else extract_txt(p)
                os.remove(p)
        for i, c in enumerate(chunk(list(nums), cfg["limit"])):
            f = make_vcf(c, cfg, i)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)
        merge_files.pop(uid, None)
        st["mode"] = None
        return

    # ===== NUMBER INPUT =====
    numbers = re.findall(r"\d{7,}", text)
    if numbers:
        for i, c in enumerate(chunk(numbers, cfg["limit"])):
            f = make_vcf(c, cfg, i)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)

async def file_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not auth(uid):
        return

    st = state(uid)
    cfg = settings(uid)
    doc = update.message.document
    path = f"{doc.file_unique_id}_{doc.file_name}"
    await (await ctx.bot.get_file(doc.file_id)).download_to_drive(path)

    try:
        if st["mode"] == "merge_files":
            merge_files[uid].append(path)
            return await update.message.reply_text("📥 File added. Type DONE when finished.")

        if path.endswith(".vcf"):
            nums = list(extract_vcf(path))
        elif path.endswith(".txt"):
            nums = list(extract_txt(path))
        elif path.endswith(".csv"):
            nums = pd.read_csv(path).iloc[:,0].astype(str).tolist()
        elif path.endswith(".xlsx"):
            nums = pd.read_excel(path).iloc[:,0].astype(str).tolist()
        else:
            return await update.message.reply_text("❌ Unsupported file")

        for i, c in enumerate(chunk(nums, cfg["limit"])):
            f = make_vcf(c, cfg, i)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)
    finally:
        if st["mode"] != "merge_files" and os.path.exists(path):
            os.remove(path)

async def error_handler(update, ctx):
    err = "".join(traceback.format_exception(None, ctx.error, ctx.error.__traceback__))
    with open("bot_errors.log", "a") as f:
        f.write(err)
    try:
        await ctx.bot.send_message(OWNER_ID, err[:4000])
    except:
        pass

# ================= TELEGRAM APP =================
request_client = HTTPXRequest(connect_timeout=30, read_timeout=30, write_timeout=30)
application = ApplicationBuilder().token(BOT_TOKEN).request(request_client).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(buttons))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
application.add_handler(MessageHandler(filters.Document.ALL, file_handler))
application.add_error_handler(error_handler)

# ================= WEBHOOK =================
@app.route("/webhook", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "ok"

@app.before_first_request
def set_webhook():
    application.bot.set_webhook(f"{APP_URL}/webhook")

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

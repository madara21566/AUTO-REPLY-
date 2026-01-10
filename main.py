import os
import re
import traceback

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

# ================= CONFIG =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# ================= DEFAULT SETTINGS =================
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
rename_files_queue = {}
rename_contacts_queue = {}

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

def extract_txt(path):
    nums = []
    with open(path, "r", errors="ignore") as f:
        for l in f:
            nums += re.findall(r"\d{7,}", l)
    return nums

def extract_vcf(path):
    nums = []
    with open(path, "r", errors="ignore") as f:
        for l in f:
            if l.startswith("TEL"):
                n = re.sub(r"\D", "", l)
                if len(n) >= 7:
                    nums.append(n)
    return nums

def make_vcf(numbers, cfg, index):
    start = cfg["contact_start"] + index * cfg["limit"]
    out = ""

    for i, n in enumerate(numbers, start=start):
        name = f"{cfg['contact_name']}{str(i).zfill(3)}"
        if cfg["group_number"] is not None:
            name += f" (Group {cfg['group_number'] + index})"
        num = f"{cfg['country_code']}{n}" if cfg["country_code"] else n

        out += (
            "BEGIN:VCARD\n"
            "VERSION:3.0\n"
            f"FN:{name}\n"
            f"TEL;TYPE=CELL:{num}\n"
            "END:VCARD\n"
        )

    fname = f"{cfg['file_name']}_{cfg['vcf_start'] + index}.vcf"
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
        [InlineKeyboardButton("✏️ Rename VCF Files", callback_data="rename_files")],
        [InlineKeyboardButton("✏️ Rename Contacts", callback_data="rename_contacts")],
        [InlineKeyboardButton("📊 My Settings", callback_data="mysettings")],
        [InlineKeyboardButton("♻️ Reset", callback_data="reset")],
    ])

def gen_settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 Set File Name", callback_data="set_file")],
        [InlineKeyboardButton("👤 Set Contact Name", callback_data="set_contact")],
        [InlineKeyboardButton("📊 Set Limit", callback_data="set_limit")],
        [InlineKeyboardButton("🔢 Contact Start", callback_data="set_contact_start")],
        [InlineKeyboardButton("📄 VCF Start", callback_data="set_vcf_start")],
        [InlineKeyboardButton("🌍 Country Code", callback_data="set_country")],
        [InlineKeyboardButton("📑 Group Number", callback_data="set_group")],
        [InlineKeyboardButton("✅ Done", callback_data="gen_done")],
    ])

# ================= START =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to VCF Manager Bot\n\nSelect an option below 👇",
        reply_markup=main_menu()
    )

# ================= BUTTON HANDLER =================
async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    st = state(uid)
    cfg = settings(uid)

    # RESET ANY PREVIOUS STEP
    if q.data in ["gen", "txt2vcf", "vcf2txt", "merge", "rename_files", "rename_contacts"]:
        st["step"] = None

    if q.data == "gen":
        st["mode"] = "gen"
        return await q.message.reply_text(
            "⚙️ Please set details first",
            reply_markup=gen_settings_menu()
        )

    if q.data.startswith("set_"):
        st["step"] = q.data
        prompts = {
            "set_file": "✏️ Send file name",
            "set_contact": "✏️ Send contact name",
            "set_limit": "✏️ Send limit",
            "set_contact_start": "✏️ Send contact start number",
            "set_vcf_start": "✏️ Send VCF start number",
            "set_country": "✏️ Send country code (example +91)",
            "set_group": "✏️ Send group number",
        }
        return await q.message.reply_text(prompts[q.data])

    if q.data == "gen_done":
        st["mode"] = "gen"
        st["step"] = None
        return await q.message.reply_text(
            "📤 Now send numbers or TXT file\n\nExample:\n9876543210 9123456789"
        )

    if q.data == "txt2vcf":
        st["mode"] = "txt2vcf"
        return await q.message.reply_text("📂 Send TXT file")

    if q.data == "vcf2txt":
        st["mode"] = "vcf2txt"
        return await q.message.reply_text("📂 Send VCF file")

    if q.data == "merge":
        st["mode"] = "merge"
        merge_queue[uid] = []
        return await q.message.reply_text("📥 Send TXT / VCF files\nType DONE when finished")

    if q.data == "rename_files":
        st["mode"] = "rename_files"
        rename_files_queue[uid] = []
        return await q.message.reply_text("📂 Send VCF files to rename")

    if q.data == "rename_contacts":
        st["mode"] = "rename_contacts"
        rename_contacts_queue[uid] = {"files": []}
        return await q.message.reply_text("📂 Send VCF files (rename contacts)")

    if q.data == "mysettings":
        return await q.message.reply_text(
            f"📂 File name: {cfg['file_name']}\n"
            f"👤 Contact name: {cfg['contact_name']}\n"
            f"📊 Limit: {cfg['limit']}\n"
            f"🔢 Contact start: {cfg['contact_start']}\n"
            f"📄 VCF start: {cfg['vcf_start']}\n"
            f"🌍 Country code: {cfg['country_code'] or 'None'}\n"
            f"📑 Group number: {cfg['group_number'] or 'Not set'}"
        )

    if q.data == "reset":
        user_settings[uid] = DEFAULT_SETTINGS.copy()
        user_state[uid] = {"mode": None, "step": None}
        merge_queue.pop(uid, None)
        rename_files_queue.pop(uid, None)
        rename_contacts_queue.pop(uid, None)
        return await q.message.reply_text(
            "♻️ All settings reset\n\nChoose option 👇",
            reply_markup=main_menu()
        )

# ================= TEXT HANDLER =================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = state(uid)
    cfg = settings(uid)
    txt = update.message.text.strip()

    # SETTING INPUT
    if st["step"]:
        mapping = {
            "set_file": "file_name",
            "set_contact": "contact_name",
            "set_limit": "limit",
            "set_contact_start": "contact_start",
            "set_vcf_start": "vcf_start",
            "set_country": "country_code",
            "set_group": "group_number",
        }
        key = mapping[st["step"]]
        cfg[key] = int(txt) if txt.isdigit() else txt
        st["step"] = None
        return await update.message.reply_text(f"✅ {key.replace('_',' ')} set")

    # MERGE DONE
    if st["mode"] == "merge" and txt.lower() == "done":
        nums = []
        for f in merge_queue.get(uid, []):
            nums += extract_vcf(f) if f.endswith(".vcf") else extract_txt(f)
            os.remove(f)

        for i, c in enumerate(chunk(nums, cfg["limit"])):
            f = make_vcf(c, cfg, i)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)

        st["mode"] = None
        merge_queue.pop(uid, None)

        return await update.message.reply_text(
            "✅ Files merged successfully\n\nChoose next option 👇",
            reply_markup=main_menu()
        )

    # GENERATE VIA TEXT
    if st["mode"] == "gen":
        numbers = re.findall(r"\d{7,}", txt)
        if not numbers:
            return await update.message.reply_text("❌ No numbers found")

        for i, c in enumerate(chunk(numbers, cfg["limit"])):
            f = make_vcf(c, cfg, i)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)

        st["mode"] = None

        return await update.message.reply_text(
            "✅ VCF generated successfully\n\nChoose next option 👇",
            reply_markup=main_menu()
        )

# ================= FILE HANDLER =================
async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = state(uid)
    cfg = settings(uid)

    doc = update.message.document
    path = doc.file_name
    await (await ctx.bot.get_file(doc.file_id)).download_to_drive(path)

    # 🔥 PRIORITY: GENERATE VCF
    if st["mode"] == "gen":
        nums = extract_txt(path) if path.endswith(".txt") else extract_vcf(path)

        for i, c in enumerate(chunk(nums, cfg["limit"])):
            f = make_vcf(c, cfg, i)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)

        os.remove(path)
        st["mode"] = None

        return await update.message.reply_text(
            "✅ VCF generated successfully\n\nChoose next option 👇",
            reply_markup=main_menu()
        )

    if st["mode"] == "txt2vcf":
        nums = extract_txt(path)
        for i, c in enumerate(chunk(nums, cfg["limit"])):
            f = make_vcf(c, cfg, i)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)
        os.remove(path)
        st["mode"] = None
        return

    if st["mode"] == "vcf2txt":
        nums = extract_vcf(path)
        out = "numbers.txt"
        open(out, "w").write("\n".join(nums))
        await update.message.reply_document(open(out, "rb"))
        os.remove(out)
        os.remove(path)
        st["mode"] = None
        return

    if st["mode"] == "merge":
        merge_queue.setdefault(uid, []).append(path)
        return await update.message.reply_text("📥 File added")

# ================= ERROR =================
async def error_handler(update, ctx):
    err = "".join(traceback.format_exception(None, ctx.error, ctx.error.__traceback__))
    print(err)

# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_error_handler(error_handler)

    print("🚀 Bot running (polling)")
    app.run_polling()

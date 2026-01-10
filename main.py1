import os, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

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
rename_files_queue = {}
rename_contacts_queue = {}

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
        if cfg["group_number"] is not None:
            name += f" (Group {cfg['group_number']})"
        num = f"{cfg['country_code']}{n}" if cfg["country_code"] else n
        out += (
            "BEGIN:VCARD\nVERSION:3.0\n"
            f"FN:{name}\nTEL;TYPE=CELL:{num}\nEND:VCARD\n"
        )
    fname = f"{cfg['file_name']}_{cfg['vcf_start'] + index}.vcf"
    open(fname, "w").write(out)
    return fname

def rename_contacts_inside(path, new_name, start):
    out, idx = "", start
    for l in open(path, "r", errors="ignore"):
        if l.startswith("FN:"):
            out += f"FN:{new_name}{str(idx).zfill(3)}\n"
            idx += 1
        else:
            out += l
    open(path, "w").write(out)

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

def gen_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 Set File Name", callback_data="gen_file")],
        [InlineKeyboardButton("👤 Set Contact Name", callback_data="gen_contact")],
        [InlineKeyboardButton("📊 Set Limit", callback_data="gen_limit")],
        [InlineKeyboardButton("🔢 Contact Start", callback_data="gen_contact_start")],
        [InlineKeyboardButton("📄 VCF Start", callback_data="gen_vcf_start")],
        [InlineKeyboardButton("🌍 Country Code", callback_data="gen_cc")],
        [InlineKeyboardButton("📑 Group Number", callback_data="gen_group")],
        [InlineKeyboardButton("✅ Done", callback_data="gen_done")],
    ])

# ================= START =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to VCF Manager Bot\nChoose option 👇",
        reply_markup=main_menu()
    )

# ================= BUTTONS =================
async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    st = state(uid)
    cfg = settings(uid)
    st["step"] = None

    if q.data == "gen":
        st["mode"] = "gen"
        return await q.message.reply_text("⚙️ Generate VCF Settings 👇", reply_markup=gen_menu())

    mapping = {
        "gen_file": ("file", "📂 Send file name"),
        "gen_contact": ("contact", "👤 Send contact name"),
        "gen_limit": ("limit", "📊 Send VCF limit"),
        "gen_contact_start": ("contact_start", "🔢 Send contact start number"),
        "gen_vcf_start": ("vcf_start", "📄 Send VCF start number"),
        "gen_cc": ("cc", "🌍 Send country code or 0"),
        "gen_group": ("group", "📑 Send group number"),
    }
    if q.data in mapping:
        st["step"], msg = mapping[q.data]
        return await q.message.reply_text(msg)

    if q.data == "gen_done":
        st["step"] = "waiting_input"
        return await q.message.reply_text("📤 Send numbers or TXT file")

    if q.data == "txt2vcf":
        st["mode"] = "txt2vcf"
        return await q.message.reply_text("📂 Send TXT file")

    if q.data == "vcf2txt":
        st["mode"] = "vcf2txt"
        return await q.message.reply_text("📂 Send VCF file")

    if q.data == "merge":
        st["mode"] = "merge"
        merge_queue[uid] = []
        return await q.message.reply_text("📥 Send files, type DONE")

    if q.data == "rename_files":
        st["mode"] = "rename_files"
        rename_files_queue[uid] = []
        return await q.message.reply_text("📂 Send VCF files")

    if q.data == "rename_contacts":
        st["mode"] = "rename_contacts"
        rename_contacts_queue[uid] = {"files": []}
        return await q.message.reply_text("📂 Send VCF files")

    if q.data == "mysettings":
        return await q.message.reply_text(
            f"📂 File: {cfg['file_name']}\n"
            f"👤 Contact: {cfg['contact_name']}\n"
            f"📊 Limit: {cfg['limit']}\n"
            f"🔢 Start: {cfg['contact_start']}\n"
            f"📄 VCF Start: {cfg['vcf_start']}\n"
            f"🌍 Code: {cfg['country_code'] or 'None'}\n"
            f"📑 Group: {cfg['group_number'] or 'Not set'}"
        )

    if q.data == "reset":
        user_settings[uid] = DEFAULT_SETTINGS.copy()
        user_state[uid] = {"mode": None, "step": None}
        merge_queue.pop(uid, None)
        rename_files_queue.pop(uid, None)
        rename_contacts_queue.pop(uid, None)
        return await q.message.reply_text("♻️ Reset done", reply_markup=main_menu())

# ================= TEXT =================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = state(uid)
    cfg = settings(uid)
    txt = update.message.text.strip()

    if st["mode"] == "gen" and st["step"] and st["step"] != "waiting_input":
        key_map = {
            "file": "file_name",
            "contact": "contact_name",
            "limit": "limit",
            "contact_start": "contact_start",
            "vcf_start": "vcf_start",
            "cc": "country_code",
            "group": "group_number",
        }
        key = key_map[st["step"]]
        cfg[key] = int(txt) if txt.isdigit() else txt
        st["step"] = None
        return await update.message.reply_text("✅ Setting saved")

    if st["mode"] == "merge" and txt.lower() == "done":
        nums = set()
        for f in merge_queue[uid]:
            nums.update(extract_vcf(f) if f.endswith(".vcf") else extract_txt(f))
            os.remove(f)
        f = make_vcf(list(nums), cfg, 0)
        await update.message.reply_document(open(f, "rb"))
        os.remove(f)
        st["mode"] = None
        return await update.message.reply_text("✅ Files merged", reply_markup=main_menu())

    if st["mode"] == "rename_files":
        for i, f in enumerate(rename_files_queue[uid], 1):
            nf = f"{txt}_{i}.vcf"
            os.rename(f, nf)
            await update.message.reply_document(open(nf, "rb"))
            os.remove(nf)
        st["mode"] = None
        return await update.message.reply_text("✅ Files renamed", reply_markup=main_menu())

    if st["mode"] == "rename_contacts":
        data = rename_contacts_queue[uid]
        if "name" not in data:
            data["name"] = txt
            return await update.message.reply_text("🔢 Send start number")
        start = int(txt)
        for f in data["files"]:
            rename_contacts_inside(f, data["name"], start)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)
        st["mode"] = None
        return await update.message.reply_text("✅ Contacts renamed", reply_markup=main_menu())

    if st["mode"] == "gen" and st["step"] == "waiting_input":
        nums = re.findall(r"\d{7,}", txt)
        for i, c in enumerate(chunk(nums, cfg["limit"])):
            f = make_vcf(c, cfg, i)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)
        st["mode"] = st["step"] = None
        return await update.message.reply_text("✅ VCF generated", reply_markup=main_menu())

# ================= FILE =================
async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = state(uid)
    cfg = settings(uid)

    doc = update.message.document
    path = doc.file_name
    await (await ctx.bot.get_file(doc.file_id)).download_to_drive(path)

    if st["mode"] == "gen" and st["step"] == "waiting_input":
        nums = extract_txt(path)
        for i, c in enumerate(chunk(nums, cfg["limit"])):
            f = make_vcf(c, cfg, i)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)
        os.remove(path)
        st["mode"] = st["step"] = None
        return await update.message.reply_text("✅ VCF generated", reply_markup=main_menu())

    if st["mode"] == "txt2vcf":
        nums = extract_txt(path)
        f = make_vcf(nums, cfg, 0)
        await update.message.reply_document(open(f, "rb"))
        os.remove(f); os.remove(path)
        st["mode"] = None
        return await update.message.reply_text("✅ TXT → VCF done", reply_markup=main_menu())

    if st["mode"] == "vcf2txt":
        nums = extract_vcf(path)
        out = "numbers.txt"
        open(out, "w").write("\n".join(nums))
        await update.message.reply_document(open(out, "rb"))
        os.remove(out); os.remove(path)
        st["mode"] = None
        return await update.message.reply_text("✅ VCF → TXT done", reply_markup=main_menu())

    if st["mode"] == "merge":
        merge_queue[uid].append(path)
        return await update.message.reply_text("📥 File added")

    if st["mode"] == "rename_files":
        rename_files_queue[uid].append(path)
        return await update.message.reply_text("✏️ Send new file name")

    if st["mode"] == "rename_contacts":
        rename_contacts_queue[uid]["files"].append(path)
        return await update.message.reply_text("✏️ Send new contact name")

# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    print("🚀 Bot running (polling)")
    app.run_polling()

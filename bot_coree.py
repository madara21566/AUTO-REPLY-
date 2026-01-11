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
}

user_settings = {}
user_state = {}
merge_queue = {}
rename_files_queue = {}
rename_contacts_queue = {}
split_queue = {}

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

def make_vcf(numbers, cfg, index, limit):
    start = cfg["contact_start"] + index * limit
    out = ""
    for i, n in enumerate(numbers, start=start):
        name = f"{cfg['contact_name']}{str(i).zfill(3)}"
        num = f"{cfg['country_code']}{n}" if cfg["country_code"] else n
        out += (
            "BEGIN:VCARD\nVERSION:3.0\n"
            f"FN:{name}\nTEL;TYPE=CELL:{num}\nEND:VCARD\n"
        )
    fname = f"{cfg['file_name']}_{index+1}.vcf"
    open(fname, "w").write(out)
    return fname

def rename_contacts_inside(path, new_name, start=1):
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
        [InlineKeyboardButton("✂️ Split VCF", callback_data="split_vcf")],
        [InlineKeyboardButton("📝 Rename VCF File", callback_data="rename_files")],
        [InlineKeyboardButton("👤 Rename Contacts", callback_data="rename_contacts")],
        [InlineKeyboardButton("📊 File Count", callback_data="file_count")],
        [InlineKeyboardButton("♻️ Reset", callback_data="reset")],
    ])

# ================= START =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "",
        reply_markup=main_menu()
    )

# ================= BUTTONS =================
async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    st = state(uid)

    if q.data == "split_vcf":
        st["mode"] = "split"
        st["step"] = "file"
        return await q.message.reply_text("📂 Send VCF file")

    if q.data == "rename_files":
        st["mode"] = "rename_files"
        rename_files_queue[uid] = []
        return await q.message.reply_text("📂 Send VCF file")

    if q.data == "rename_contacts":
        st["mode"] = "rename_contacts"
        rename_contacts_queue[uid] = []
        return await q.message.reply_text("📂 Send VCF file")

    if q.data == "file_count":
        st["mode"] = "file_count"
        return await q.message.reply_text("📂 Send VCF or TXT file")

    if q.data == "reset":
        user_state[uid] = {"mode": None, "step": None}
        return await q.message.reply_text("♻️ Reset done", reply_markup=main_menu())

# ================= TEXT =================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = state(uid)

    if st["mode"] == "split" and st["step"] == "limit":
        if not update.message.text.isdigit():
            return await update.message.reply_text("❌ Send valid number")
        split_queue[uid]["limit"] = int(update.message.text)
        st["step"] = "process"

        nums = split_queue[uid]["nums"]
        cfg = settings(uid)
        limit = split_queue[uid]["limit"]

        for i, part in enumerate(chunk(nums, limit)):
            f = make_vcf(part, cfg, i, limit)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)

        os.remove(split_queue[uid]["file"])
        st["mode"] = None
        return await update.message.reply_text("✅ Split done", reply_markup=main_menu())

    if st["mode"] == "rename_files":
        new = update.message.text + ".vcf"
        for f in rename_files_queue[uid]:
            os.rename(f, new)
            await update.message.reply_document(open(new, "rb"))
            os.remove(new)
        st["mode"] = None
        return await update.message.reply_text("✅ File renamed", reply_markup=main_menu())

    if st["mode"] == "rename_contacts":
        for f in rename_contacts_queue[uid]:
            rename_contacts_inside(f, update.message.text)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)
        st["mode"] = None
        return await update.message.reply_text("✅ Contacts renamed", reply_markup=main_menu())

# ================= FILE =================
async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = state(uid)

    doc = update.message.document
    path = doc.file_name
    await (await ctx.bot.get_file(doc.file_id)).download_to_drive(path)

    if st["mode"] == "split" and st["step"] == "file":
        nums = extract_vcf(path)
        split_queue[uid] = {"file": path, "nums": nums}
        st["step"] = "limit"
        return await update.message.reply_text("✏️ 1 file me kitne contacts chahiye?")

    if st["mode"] == "rename_files":
        rename_files_queue[uid].append(path)
        return await update.message.reply_text("✏️ Send new file name")

    if st["mode"] == "rename_contacts":
        rename_contacts_queue[uid].append(path)
        return await update.message.reply_text("✏️ Send new contact name")

    if st["mode"] == "file_count":
        if path.endswith(".vcf"):
            total = len(extract_vcf(path))
            kind = "VCF"
        else:
            total = len(extract_txt(path))
            kind = "TXT"

        await update.message.reply_text(
            f"📊 File Analysis\n\n"
            f"📄 File: {path}\n"
            f"🔢 Total Numbers: {total}\n"
            f"📁 Type: {kind}"
        )
        os.remove(path)
        st["mode"] = None
        return await update.message.reply_text("✅ Done", reply_markup=main_menu())

# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    print("🚀 Bot running")
    app.run_polling()

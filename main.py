import os
import re
import pandas as pd
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
    "start_index": 1,
    "vcf_start": 1,
    "country_code": "",
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

def extract_vcf(path):
    nums = []
    with open(path, "r", errors="ignore") as f:
        for line in f:
            if line.startswith("TEL"):
                n = re.sub(r"\D", "", line)
                if len(n) >= 7:
                    nums.append(n)
    return nums

def extract_txt(path):
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

def rename_contacts_in_vcf(path, new_name, start_index):
    out = ""
    idx = start_index
    with open(path, "r", errors="ignore") as f:
        for line in f:
            if line.startswith("FN:"):
                out += f"FN:{new_name}{str(idx).zfill(3)}\n"
                idx += 1
            else:
                out += line
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

# ================= START =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to VCF Bot\n\nChoose an option 👇",
        reply_markup=main_menu()
    )

# ================= BUTTON HANDLER =================
async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    st = state(uid)

    st["mode"] = q.data
    st["step"] = None

    messages = {
        "gen": "📤 Send numbers or file",
        "txt2vcf": "📂 Send TXT file",
        "vcf2txt": "📂 Send VCF file",
        "merge": "📥 Send files, then type DONE",
        "rename_files": "📂 Send VCF files to rename",
        "rename_contacts": "📂 Send VCF files (contacts rename)",
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
        merge_queue.pop(uid, None)
        rename_files_queue.pop(uid, None)
        rename_contacts_queue.pop(uid, None)
        return await q.message.reply_text("♻️ Reset done")

    await q.message.reply_text(messages[q.data])

# ================= TEXT HANDLER =================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = state(uid)
    cfg = settings(uid)
    txt = update.message.text.strip()

    if st["mode"] == "merge" and txt.lower() == "done":
        nums = []
        for f in merge_queue.get(uid, []):
            nums += extract_vcf(f) if f.endswith(".vcf") else extract_txt(f)
            os.remove(f)

        for i, c in enumerate(chunk(nums, cfg["limit"])):
            f = make_vcf(c, cfg, i)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)

        merge_queue.pop(uid, None)
        st["mode"] = None
        return

    if st["mode"] == "rename_files":
        new_name = txt
        for i, f in enumerate(rename_files_queue.get(uid, []), start=1):
            new = f"{new_name}_{i}.vcf"
            os.rename(f, new)
            await update.message.reply_document(open(new, "rb"))
            os.remove(new)
        rename_files_queue.pop(uid, None)
        st["mode"] = None
        return

    if st["mode"] == "rename_contacts":
        rename_contacts_queue[uid]["name"] = txt
        await update.message.reply_text("Send start number (example: 1)")
        st["step"] = "contact_start"
        return

    if st["step"] == "contact_start":
        start_idx = int(txt)
        data = rename_contacts_queue.get(uid)
        for f in data["files"]:
            rename_contacts_in_vcf(f, data["name"], start_idx)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)
        rename_contacts_queue.pop(uid, None)
        st["mode"] = None
        st["step"] = None
        return

    numbers = re.findall(r"\d{7,}", txt)
    if numbers:
        for i, c in enumerate(chunk(numbers, cfg["limit"])):
            f = make_vcf(c, cfg, i)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)

# ================= FILE HANDLER =================
async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = state(uid)
    cfg = settings(uid)

    doc = update.message.document
    path = doc.file_name
    await (await ctx.bot.get_file(doc.file_id)).download_to_drive(path)

    if st["mode"] == "merge":
        merge_queue.setdefault(uid, []).append(path)
        return await update.message.reply_text("Added")

    if st["mode"] == "rename_files":
        rename_files_queue.setdefault(uid, []).append(path)
        return await update.message.reply_text("Send new file name")

    if st["mode"] == "rename_contacts":
        rename_contacts_queue.setdefault(uid, {"files": []})["files"].append(path)
        return await update.message.reply_text("Send new contact name")

    if st["mode"] == "vcf2txt":
        nums = extract_vcf(path)
        out = "numbers.txt"
        open(out, "w").write("\n".join(nums))
        await update.message.reply_document(open(out, "rb"))
        os.remove(out)
        os.remove(path)
        return

    nums = extract_txt(path)
    for i, c in enumerate(chunk(nums, cfg["limit"])):
        f = make_vcf(c, cfg, i)
        await update.message.reply_document(open(f, "rb"))
        os.remove(f)
    os.remove(path)

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

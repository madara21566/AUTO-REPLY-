import os
import re
import traceback

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
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
    with open(path, "r", errors="ignore") as f:
        return re.findall(r"\d{7,}", f.read())

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
            "BEGIN:VCARD\nVERSION:3.0\n"
            f"FN:{name}\nTEL;TYPE=CELL:{num}\nEND:VCARD\n"
        )

    fname = f"{cfg['file_name']}_{cfg['vcf_start'] + index}.vcf"
    with open(fname, "w") as f:
        f.write(out)
    return fname

def rename_contacts_inside(path, new_name, start):
    out, idx = "", start
    with open(path, "r", errors="ignore") as f:
        for l in f:
            if l.startswith("FN:"):
                out += f"FN:{new_name}{str(idx).zfill(3)}\n"
                idx += 1
            else:
                out += l
    with open(path, "w") as f:
        f.write(out)

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
        "👋 Welcome to VCF Manager Bot\n\nChoose option 👇",
        reply_markup=main_menu()
    )

# ================= BUTTONS =================
async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    st = state(uid)
    cfg = settings(uid)

    if q.data == "txt2vcf":
        st["mode"] = "txt2vcf"
        return await q.message.reply_text("📂 Send TXT file")

    if q.data == "vcf2txt":
        st["mode"] = "vcf2txt"
        return await q.message.reply_text("📂 Send VCF file")

    if q.data == "merge":
        st["mode"] = "merge"
        merge_queue[uid] = []
        return await q.message.reply_text("📥 Send TXT/VCF files\nType DONE when finished")

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
            f"📂 File: {cfg['file_name']}\n👤 Contact: {cfg['contact_name']}\n"
            f"📊 Limit: {cfg['limit']}\n🔢 Start: {cfg['contact_start']}\n"
            f"📄 VCF Start: {cfg['vcf_start']}\n🌍 Code: {cfg['country_code'] or 'None'}"
        )

    if q.data == "reset":
        user_settings[uid] = DEFAULT_SETTINGS.copy()
        user_state[uid] = {"mode": None, "step": None}
        return await q.message.reply_text("♻️ Reset done", reply_markup=main_menu())

# ================= TEXT =================
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = state(uid)
    cfg = settings(uid)
    txt = update.message.text.strip()

    # MERGE DONE
    if st["mode"] == "merge" and txt.lower() == "done":
        nums = set()
        for f in merge_queue.get(uid, []):
            nums.update(extract_vcf(f) if f.endswith(".vcf") else extract_txt(f))
            os.remove(f)

        merged = make_vcf(list(nums), cfg, 0)
        await update.message.reply_document(open(merged, "rb"))
        os.remove(merged)

        st["mode"] = None
        return await update.message.reply_text("✅ Files merged", reply_markup=main_menu())

    # RENAME FILES NAME INPUT
    if st["mode"] == "rename_files":
        new = txt
        for i, f in enumerate(rename_files_queue[uid], 1):
            nf = f"{new}_{i}.vcf"
            os.rename(f, nf)
            await update.message.reply_document(open(nf, "rb"))
            os.remove(nf)
        st["mode"] = None
        return await update.message.reply_text("✅ Files renamed", reply_markup=main_menu())

    # RENAME CONTACTS STEPS
    if st["mode"] == "rename_contacts":
        data = rename_contacts_queue[uid]
        if "name" not in data:
            data["name"] = txt
            return await update.message.reply_text("🔢 Send contact start number")
        else:
            start = int(txt)
            for f in data["files"]:
                rename_contacts_inside(f, data["name"], start)
                await update.message.reply_document(open(f, "rb"))
                os.remove(f)
            st["mode"] = None
            return await update.message.reply_text("✅ Contacts renamed", reply_markup=main_menu())

# ================= FILE =================
async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = state(uid)
    cfg = settings(uid)

    doc = update.message.document
    path = doc.file_name
    await (await ctx.bot.get_file(doc.file_id)).download_to_drive(path)

    # TXT → VCF
    if st["mode"] == "txt2vcf":
        nums = extract_txt(path)
        for i, c in enumerate(chunk(nums, cfg["limit"])):
            f = make_vcf(c, cfg, i)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)
        os.remove(path)
        st["mode"] = None
        return await update.message.reply_text("✅ TXT → VCF done", reply_markup=main_menu())

    # VCF → TXT
    if st["mode"] == "vcf2txt":
        nums = extract_vcf(path)
        out = "numbers.txt"
        with open(out, "w") as f:
            f.write("\n".join(nums))
        await update.message.reply_document(open(out, "rb"))
        os.remove(out)
        os.remove(path)
        st["mode"] = None
        return await update.message.reply_text("✅ VCF → TXT done", reply_markup=main_menu())

    # MERGE ADD
    if st["mode"] == "merge":
        merge_queue[uid].append(path)
        return await update.message.reply_text("📥 File added")

    # RENAME FILE QUEUE
    if st["mode"] == "rename_files":
        rename_files_queue[uid].append(path)
        return await update.message.reply_text("✏️ Send new file name")

    # RENAME CONTACT QUEUE
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
    print("🚀 Bot running")
    app.run_polling()

import os, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

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
split_queue = {}

def settings(uid):
    user_settings.setdefault(uid, DEFAULT_SETTINGS.copy())
    return user_settings[uid]

def state(uid):
    user_state.setdefault(uid, {"mode": None, "step": None})
    return user_state[uid]

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

def make_vcf(numbers, cfg, index, custom_limit=None):
    limit = custom_limit if custom_limit else cfg["limit"]
    start = cfg["contact_start"] + index * limit
    out = ""
    for i, n in enumerate(numbers, start=start):
        name = f"{cfg['contact_name']}{str(i).zfill(3)}"
        if cfg.get("group_number") is not None:
            name += f" (Group {cfg['group_number']})"
        num = f"{cfg['country_code']}{n}" if cfg["country_code"] else n
        out += (
            "BEGIN:VCARD\nVERSION:3.0\n"
            f"FN:{name}\nTEL;TYPE=CELL:{num}\nEND:VCARD\n"
        )
    fname = f"{cfg['file_name']}_{cfg['vcf_start'] + index}.vcf"
    with open(fname, "w") as f:
        f.write(out)
    return fname

def rename_contacts_inside(path, new_name, start=1):
    out, idx = "", start
    for l in open(path, "r", errors="ignore"):
        if l.startswith("FN:"):
            out += f"FN:{new_name}{str(idx).zfill(3)}\n"
            idx += 1
        else:
            out += l
    with open(path, "w") as f:
        f.write(out)


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ QUICK VCF", callback_data="quick_vcf"),
         InlineKeyboardButton("📇 GENERATE VCF", callback_data="gen")],
        [InlineKeyboardButton("✂️ SPLIT VCF", callback_data="split_vcf"),
         InlineKeyboardButton("🧩 MERGE FILES", callback_data="merge")],
        [InlineKeyboardButton("🔁 TXT → VCF", callback_data="txt2vcf"),
         InlineKeyboardButton("🔄 VCF → TXT", callback_data="vcf2txt")],
        [InlineKeyboardButton("📝 RENAME FILE", callback_data="rename_files"),
         InlineKeyboardButton("👤 RENAME CONTACT", callback_data="rename_contacts")],
        [InlineKeyboardButton("📊 FILE COUNT", callback_data="file_count"),
         InlineKeyboardButton("⚙️ MY SETTINGS", callback_data="mysettings")],
        [InlineKeyboardButton("♻️ RESET ALL", callback_data="reset")],
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


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Advance VCF Manager\nChoose an option below:",
        reply_markup=main_menu()
    )


async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    st = state(uid)
    cfg = settings(uid)

    if q.data == "quick_vcf":
        st.clear()
        st["mode"] = "quick"
        st["step"] = "file"
        return await q.message.reply_text("📂 Send VCF file name")

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

    if q.data == "split_vcf":
        st["mode"] = "split"
        st["step"] = "file"
        return await q.message.reply_text("📂 Send VCF file to split")

    if q.data == "txt2vcf":
        st["mode"] = "txt2vcf"
        return await q.message.reply_text("📂 Send TXT file")

    if q.data == "vcf2txt":
        st["mode"] = "vcf2txt"
        return await q.message.reply_text("📂 Send VCF file")

    if q.data == "merge":
        st["mode"] = "merge"
        merge_queue[uid] = []
        return await q.message.reply_text("📥 Send files, type DONE when finished")

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

    if q.data == "mysettings":
        return await q.message.reply_text(
            f"📊 **Current Settings**\n\n"
            f"📂 File Name: {cfg['file_name']}\n"
            f"👤 Contact Name: {cfg['contact_name']}\n"
            f"📊 Limit: {cfg['limit']}\n"
            f"🔢 Contact Start: {cfg['contact_start']}\n"
            f"📄 VCF Start: {cfg['vcf_start']}\n"
            f"🌍 Country Code: {cfg['country_code'] or 'None'}\n"
            f"📑 Group: {cfg['group_number'] or 'Not set'}"
        )

    if q.data == "reset":
        user_settings[uid] = DEFAULT_SETTINGS.copy()
        user_state[uid] = {"mode": None, "step": None}
        return await q.message.reply_text("♻️ Reset done", reply_markup=main_menu())


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = state(uid)
    cfg = settings(uid)
    txt = update.message.text.strip()

    # Split Limit Handle
    if st["mode"] == "split" and st["step"] == "limit":
        if not txt.isdigit():
            return await update.message.reply_text("❌ Send valid number")
        
        limit = int(txt)
        nums = split_queue[uid]["nums"]
        path = split_queue[uid]["file"]
        
        for i, part in enumerate(chunk(nums, limit)):
            f = make_vcf(part, cfg, i, custom_limit=limit)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)
        
        if os.path.exists(path): os.remove(path)
        st["mode"] = None
        return await update.message.reply_text("✅ Split done", reply_markup=main_menu())

    # Quick VCF Flow
    if st.get("mode") == "quick":
        if st["step"] == "file":
            st["file"] = txt
            st["step"] = "contact"
            return await update.message.reply_text("👤 Send contact name")
        if st["step"] == "contact":
            st["contact"] = txt
            st["step"] = "numbers"
            return await update.message.reply_text("📤 Send numbers (space or new line)")
        if st["step"] == "numbers":
            nums = re.findall(r"\d{7,}", txt)
            out = ""
            for i, n in enumerate(nums, 1):
                out += f"BEGIN:VCARD\nVERSION:3.0\nFN:{st['contact']}{str(i).zfill(3)}\nTEL;TYPE=CELL:{n}\nEND:VCARD\n"
            fname = f"{st['file']}.vcf"
            with open(fname, "w") as f: f.write(out)
            await update.message.reply_document(open(fname, "rb"))
            os.remove(fname)
            st.clear()
            return await update.message.reply_text("✅ VCF generated", reply_markup=main_menu())

    # Settings Input
    if st["mode"] == "gen" and st["step"] and st["step"] != "waiting_input":
        key_map = {"file": "file_name", "contact": "contact_name", "limit": "limit", 
                   "contact_start": "contact_start", "vcf_start": "vcf_start", "cc": "country_code", "group": "group_number"}
        key = key_map[st["step"]]
        cfg[key] = int(txt) if txt.isdigit() else txt
        st["step"] = None
        return await update.message.reply_text("✅ Setting saved")

    # Merge Done
    if st["mode"] == "merge" and txt.lower() == "done":
        nums = set()
        for f in merge_queue[uid]:
            nums.update(extract_vcf(f) if f.endswith(".vcf") else extract_txt(f))
            if os.path.exists(f): os.remove(f)
        f = make_vcf(list(nums), cfg, 0)
        await update.message.reply_document(open(f, "rb"))
        os.remove(f)
        st["mode"] = None
        return await update.message.reply_text("✅ Files merged", reply_markup=main_menu())

    # Rename Operations
    if st["mode"] == "rename_files":
        new = txt + ".vcf"
        for f in rename_files_queue[uid]:
            if os.path.exists(f):
                os.rename(f, new)
                await update.message.reply_document(open(new, "rb"))
                os.remove(new)
        st["mode"] = None
        return await update.message.reply_text("✅ File renamed", reply_markup=main_menu())

    if st["mode"] == "rename_contacts":
        for f in rename_contacts_queue[uid]:
            if os.path.exists(f):
                rename_contacts_inside(f, txt)
                await update.message.reply_document(open(f, "rb"))
                os.remove(f)
        st["mode"] = None
        return await update.message.reply_text("✅ Contacts renamed", reply_markup=main_menu())


async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = state(uid)
    cfg = settings(uid)
    doc = update.message.document
    path = doc.file_name
    await (await ctx.bot.get_file(doc.file_id)).download_to_drive(path)

    if st["mode"] == "split" and st["step"] == "file":
        nums = extract_vcf(path)
        split_queue[uid] = {"file": path, "nums": nums}
        st["step"] = "limit"
        return await update.message.reply_text("✏️ 1 file me kitne contacts chahiye?")

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
        out = f"{path}.txt"
        with open(out, "w") as f: f.write("\n".join(nums))
        await update.message.reply_document(open(out, "rb"))
        os.remove(out); os.remove(path)
        st["mode"] = None
        return await update.message.reply_text("✅ VCF → TXT done", reply_markup=main_menu())

    if st["mode"] == "merge":
        merge_queue[uid].append(path)
        return await update.message.reply_text("📥 File added. Send more or type DONE")

    if st["mode"] == "rename_files":
        rename_files_queue[uid].append(path)
        return await update.message.reply_text("✏️ Send new file name")

    if st["mode"] == "rename_contacts":
        rename_contacts_queue[uid].append(path)
        return await update.message.reply_text("✏️ Send new contact name")

    if st["mode"] == "file_count":
        total = len(extract_vcf(path)) if path.endswith(".vcf") else len(extract_txt(path))
        kind = "VCF" if path.endswith(".vcf") else "TXT"
        await update.message.reply_text(f"📊 **File Analysis**\n\n📄 File: {path}\n🔢 Total Numbers: {total}\n📁 Type: {kind}")
        os.remove(path)
        st["mode"] = None
        return await update.message.reply_text("✅ Done", reply_markup=main_menu())


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    print("🚀 All-in-One Bot running")
    app.run_polling()
      

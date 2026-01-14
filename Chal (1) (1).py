import os, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# 🔑 Bot Token
BOT_TOKEN = "8247588556:AAHy41QOlh0G90n5RQLHX7-6UaQHYTFQZrc"

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
split_queue = {}
rename_queue = {}
quick_vcf_data = {} # For Looping Feature
vcf_editor_data = {} # For Edit Feature

def settings(uid):
    user_settings.setdefault(uid, DEFAULT_SETTINGS.copy())
    return user_settings[uid]

def state(uid):
    user_state.setdefault(uid, {"mode": None, "step": None})
    return user_state[uid]

# ================= HELPERS =================

def extract_txt(path):
    # Added Automatic Duplicate Remover using dict.fromkeys
    nums = re.findall(r"\d{7,}", open(path, "r", errors="ignore").read())
    return list(dict.fromkeys(nums))

def extract_vcf(path):
    # Added Automatic Duplicate Remover
    nums = []
    for l in open(path, "r", errors="ignore"):
        if l.startswith("TEL"):
            n = re.sub(r"\D", "", l)
            if len(n) >= 7:
                nums.append(n)
    return list(dict.fromkeys(nums))

def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def make_vcf(numbers, cfg, index, custom_limit=None):
    limit = custom_limit if custom_limit else cfg["limit"]
    start = cfg["contact_start"] + index * limit
    out = ""
    for i, n in enumerate(numbers, start=start):
        # Sequential Name Logic: Name 001 format
        name = f"{cfg['contact_name']}{str(i).zfill(3)}"
        if cfg.get("group_number"):
            name += f" ({cfg['group_number']})"
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

# ================= UI =================

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ QUICK VCF (LOOP)", callback_data="quick_vcf"),
         InlineKeyboardButton("📝 NAME GENERATOR", callback_data="name_gen")],
        [InlineKeyboardButton("🛠️ VCF EDITOR", callback_data="vcf_editor"),
         InlineKeyboardButton("📇 GENERATE VCF", callback_data="gen")],
        [InlineKeyboardButton("✂️ SPLIT VCF", callback_data="split_vcf"),
         InlineKeyboardButton("🧩 MERGE FILES", callback_data="merge")],
        [InlineKeyboardButton("🔁 TXT TO VCF", callback_data="txt2vcf"),
         InlineKeyboardButton("🔄 VCF TO TXT", callback_data="vcf2txt")],
        [InlineKeyboardButton("📝 RENAME FILE", callback_data="rename_files"),
         InlineKeyboardButton("👤 RENAME CONTACT", callback_data="rename_contacts")],
        [InlineKeyboardButton("📊 FILE COUNT", callback_data="file_count"),
         InlineKeyboardButton("⚙️ MY SETTINGS", callback_data="mysettings")],
        [InlineKeyboardButton("♻️ RESET ALL", callback_data="reset")],
    ])

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 BACK TO MENU", callback_data="main_menu")]])

async def show_summary(msg, cfg):
    text = (
        "📊 SUMMARY:\n"
        "━━━━━━━━━━━━\n"
        "📂 VCF FILE NAME: {}\n"
        "👤 CONTACT NAME: {}\n"
        "📊 PER VCF LIMIT: {}\n"
        "🔢 START: {}\n"
        "📄 VCF START: {}\n"
        "🌍 CODE: {}\n"
        "📑 GROUP: {}\n"
    ).format(
        cfg['file_name'], cfg['contact_name'], cfg['limit'],
        cfg['contact_start'], cfg['vcf_start'],
        cfg['country_code'] or 'NONE', cfg['group_number'] or 'NONE'
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ DONE", callback_data="gen_done")],
        [InlineKeyboardButton("🔄 RESTART", callback_data="gen")],
        [InlineKeyboardButton("🔙 BACK", callback_data="main_menu")]
    ])
    if hasattr(msg, 'edit_text'):
        await msg.edit_text(text, reply_markup=kb)
    else:
        await msg.reply_text(text, reply_markup=kb)

# ================= HANDLERS =================

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or "User"
    username = f"@{user.username}" if user.username else "Not set"

    text = (
        f"✨✨ *WELCOME TO VCF MANAGER PRO* ✨✨\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 *User Name:* {name}\n"
        f"🔖 *Username:* {username}\n"
        f"🆔 *User ID:* `{user.id}`\n\n"
        f"🚀 *What this bot can do?*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📇 Generate VCF files from TXT\n"
        f"✂️ Split large VCF files\n"
        f"🧩 Merge multiple files\n"
        f"♻️ Remove duplicate numbers\n"
        f"📝 Rename contacts & files\n"
        f"⚡ Quick VCF & Name Generator\n\n"
        f"💡 *How to start?*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👉 Choose an option from the menu below\n"
        f"👉 Upload your file and follow instructions\n\n"
        f"⚠️ *Note:*\n"
        f"• Do not upload fake or invalid numbers\n"
        f"• Processing speed depends on file size\n\n"
        f"✅ *Ready to begin?*\n"
        f"👇 Select an option below"
    )

    await update.message.reply_text(
        text,
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    st, cfg = state(uid), settings(uid)

    if q.data == "main_menu":
        st.clear()
        return await q.message.edit_text("👋 CHOOSE AN OPTION:", reply_markup=main_menu())

    # --- NEW: Quick VCF Looping Actions ---
    elif q.data == "add_more_quick":
        st["step"] = "contact"
        await q.message.edit_text("👤 ENTER NEXT CONTACT NAME:")

    elif q.data == "finish_quick":
        f_name = st.get("file", "QuickVCF")
        out = ""
        # Combine all looped data into one file
        for entry in quick_vcf_data[uid]:
            c_name = entry['contact']
            for i, n in enumerate(entry['nums'], start=1):
                out += f"BEGIN:VCARD\nVERSION:3.0\nFN:{c_name}{str(i).zfill(3)}\nTEL;TYPE=CELL:{n}\nEND:VCARD\n"

        path = f"{f_name}.vcf"
        with open(path, "w") as x: x.write(out)
        await q.message.reply_document(open(path, "rb"))
        os.remove(path); st.clear(); quick_vcf_data.pop(uid, None)
        await q.message.reply_text("✅ ALL CONTACTS SAVED IN ONE VCF.", reply_markup=main_menu())

    # --- NEW: VCF Editor Actions ---
    elif q.data == "vcf_editor":
        st.update({"mode": "editor", "step": "file"})
        await q.message.edit_text("📂 SEND VCF FILE TO EDIT (ADD/REMOVE CONTACTS):", reply_markup=back_kb())

    elif q.data.startswith("edit_"):
        action = q.data.split("_")[1]
        st["step"] = f"do_{action}"
        msg = "✍️ SEND NUMBERS TO ADD (Text format):" if action == "add" else "🗑️ SEND THE EXACT NUMBER TO REMOVE:"
        await q.message.edit_text(msg)

    # --- Existing Actions ---
    elif q.data == "gen":
        st.update({"mode": "gen", "step": "file_name"})
        await q.message.edit_text("⌨️ ENTER VCF FILE NAME:", reply_markup=back_kb())

    elif q.data == "gen_done":
        st["step"] = "waiting_input"
        await q.message.edit_text("✅ SETTINGS SAVED. SEND TXT FILE NOW.", reply_markup=back_kb())

    elif q.data == "split_vcf":
        st.update({"mode": "split", "step": "file"})
        await q.message.edit_text("📂 SEND VCF OR TXT FILE TO SPLIT:", reply_markup=back_kb())

    elif q.data == "merge":
        st["mode"], merge_queue[uid] = "merge", []
        await q.message.edit_text("📥 SEND FILES AND TYPE DONE WHEN FINISHED.", reply_markup=back_kb())

    elif q.data == "rename_files":
        st.update({"mode": "rename_files", "step": "file"})
        rename_queue[uid] = []
        await q.message.edit_text("📂 SEND VCF FILE TO RENAME:", reply_markup=back_kb())

    elif q.data == "rename_contacts":
        st.update({"mode": "rename_contacts", "step": "file"})
        rename_queue[uid] = []
        await q.message.edit_text("📂 SEND VCF FILE TO RENAME CONTACTS:", reply_markup=back_kb())

    elif q.data.startswith("merge_as_"):
        fmt = q.data.split("_")[-1]
        nums = []
        for f in merge_queue[uid]:
            nums.extend(extract_vcf(f) if f.endswith(".vcf") else extract_txt(f))
            if os.path.exists(f): os.remove(f)
        nums = list(dict.fromkeys(nums))
        f = make_vcf(nums, cfg, 0) if fmt == "vcf" else "Merged.txt"
        if fmt == "txt":
            with open(f, "w") as x: x.write("\n".join(nums))
        await q.message.reply_document(open(f, "rb"))
        os.remove(f); st.clear()
        await q.message.reply_text("✅ MERGE COMPLETE.", reply_markup=main_menu())

    elif q.data == "quick_vcf":
        st.update({"mode": "quick", "step": "file"})
        quick_vcf_data[uid] = [] # Initialize storage for loop
        await q.message.edit_text("⌨️ ENTER VCF FILE NAME:", reply_markup=back_kb())

    elif q.data == "name_gen":
        st.update({"mode": "name_gen", "step": "name"})
        await q.message.edit_text("✏️ ENTER BASE NAME (e.g. Madara):", reply_markup=back_kb())

    elif q.data == "skip_cc":
        cfg["country_code"] = ""; st["step"] = "group_number"
        await q.message.edit_text("📑 ENTER GROUP NAME OR SKIP:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏩ SKIP", callback_data="skip_group")]]))

    elif q.data == "skip_group":
        cfg["group_number"] = None; await show_summary(q.message, cfg)

    elif q.data in ["txt2vcf", "vcf2txt", "file_count"]:
        st["mode"] = q.data; st["step"] = "file"
        await q.message.edit_text(f"📤 MODE: {q.data.upper()}. SEND FILE:", reply_markup=back_kb())

    elif q.data == "mysettings":
        await show_summary(q.message, cfg)

    elif q.data == "reset":
        user_settings[uid] = DEFAULT_SETTINGS.copy(); st.clear()
        await q.message.edit_text("♻️ RESET COMPLETE.", reply_markup=main_menu())

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st, cfg, txt = state(uid), settings(uid), update.message.text.strip()

    if st["mode"] == "gen":
        if st["step"] == "file_name":
            cfg["file_name"] = txt; st["step"] = "contact_name"; await update.message.reply_text("👤 ENTER CONTACT NAME:")
        elif st["step"] == "contact_name":
            cfg["contact_name"] = txt; st["step"] = "limit"; await update.message.reply_text("📊 ENTER LIMIT:")
        elif st["step"] == "limit":
            cfg["limit"] = int(txt) if txt.isdigit() else 100; st["step"] = "contact_start"; await update.message.reply_text("🔢 ENTER CONTACT START NUMBER:")
        elif st["step"] == "contact_start":
            cfg["contact_start"] = int(txt) if txt.isdigit() else 1; st["step"] = "vcf_start"; await update.message.reply_text("📄 ENTER VCF START NUMBER:")
        elif st["step"] == "vcf_start":
            cfg["vcf_start"] = int(txt) if txt.isdigit() else 1; st["step"] = "country_code"
            await update.message.reply_text("🌍 ENTER COUNTRY CODE:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏩ SKIP", callback_data="skip_cc")]]))
        elif st["step"] == "country_code":
            cfg["country_code"] = txt; st["step"] = "group_number"
            await update.message.reply_text("📑 ENTER GROUP NAME:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏩ SKIP", callback_data="skip_group")]]))
        elif st["step"] == "group_number":
            cfg["group_number"] = txt; await show_summary(update.message, cfg)

    elif st["mode"] == "split" and st["step"] == "limit":
        if txt.isdigit():
            limit = int(txt)
            nums, path = split_queue[uid]["nums"], split_queue[uid]["file"]
            for i, p in enumerate(chunk(nums, limit)):
                f = make_vcf(p, cfg, i, custom_limit=limit)
                await update.message.reply_document(open(f, "rb")); os.remove(f)
            if os.path.exists(path): os.remove(path)
            st.clear(); await update.message.reply_text("✅ SPLIT DONE.", reply_markup=main_menu())

    elif st["mode"] == "merge" and txt.lower() == "done":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📄 GET VCF", callback_data="merge_as_vcf"), InlineKeyboardButton("📝 GET TXT", callback_data="merge_as_txt")]])
        await update.message.reply_text("📋 CHOOSE FORMAT:", reply_markup=kb)

    elif st["mode"] == "rename_files" and st["step"] == "name":
        for f in rename_queue[uid]:
            new_path = f"{txt}.vcf"
            os.rename(f, new_path)
            await update.message.reply_document(open(new_path, "rb"))
            os.remove(new_path)
        st.clear(); await update.message.reply_text("✅ FILE RENAMED.", reply_markup=main_menu())

    elif st["mode"] == "rename_contacts" and st["step"] == "name":
        for f in rename_queue[uid]:
            rename_contacts_inside(f, txt)
            await update.message.reply_document(open(f, "rb"))
            os.remove(f)
        st.clear(); await update.message.reply_text("✅ CONTACTS RENAMED.", reply_markup=main_menu())

    # --- NEW: Quick VCF Loop Logic ---
    elif st["mode"] == "quick":
        if st["step"] == "file":
            st["file"] = txt; st["step"] = "contact"; await update.message.reply_text("👤 ENTER CONTACT NAME:")
        elif st["step"] == "contact":
            st["contact"] = txt; st["step"] = "numbers"; await update.message.reply_text(f"📤 SEND NUMBERS FOR {txt}:")
        elif st["step"] == "numbers":
            raw_nums = re.findall(r"\d{7,}", txt)
            nums = list(dict.fromkeys(raw_nums)) # Remove Duplicates
            quick_vcf_data[uid].append({"contact": st["contact"], "nums": nums})

            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ ADD MORE CONTACTS", callback_data="add_more_quick")],
                [InlineKeyboardButton("⏩ SKIP & GENERATE VCF", callback_data="finish_quick")]
            ])
            await update.message.reply_text(f"✅ {len(nums)} numbers added. Aur contacts add karne hain?", reply_markup=kb)

    # --- NEW: Name Generator Logic ---
    elif st["mode"] == "name_gen":
        if st["step"] == "name":
            st["base_name"] = txt; st["step"] = "count"
            await update.message.reply_text("🔢 HOW MANY NAMES? (e.g. 50):")
        elif st["step"] == "count":
            if txt.isdigit():
                count = int(txt)
                base = st["base_name"]
                # HTML code tag for easy copy
                res = "\n".join([f"<code>{base} {i+1}</code>" for i in range(count)])
                await update.message.reply_text(f"📝 **GENERATED LIST:**\n\n{res}", parse_mode="HTML")
                st.clear(); await update.message.reply_text("✅ DONE.", reply_markup=main_menu())

    # --- NEW: VCF Editor Logic ---
    elif st["mode"] == "editor_action":
        path = vcf_editor_data[uid]
        if st["step"] == "do_add":
            nums = list(dict.fromkeys(re.findall(r"\d{7,}", txt)))
            old_content = open(path, "r").read()
            # Generate new entries
            new_v = "".join([f"BEGIN:VCARD\nVERSION:3.0\nFN:Added{str(i+1).zfill(3)}\nTEL;TYPE=CELL:{n}\nEND:VCARD\n" for i, n in enumerate(nums)])
            with open(path, "a") as f: f.write(new_v)
            await update.message.reply_document(open(path, "rb"))
        elif st["step"] == "do_remove":
            target = re.sub(r"\D", "", txt)
            cards = open(path, "r").read().split("END:VCARD\n")
            # Filter out cards containing the number
            new_cards = [c for c in cards if target not in c and "BEGIN:VCARD" in c]
            with open(path, "w") as f: f.write("END:VCARD\n".join(new_cards) + "END:VCARD\n")
            await update.message.reply_document(open(path, "rb"))
        os.remove(path); st.clear(); await update.message.reply_text("✅ EDITOR COMPLETE.", reply_markup=main_menu())

async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st, cfg, doc = state(uid), settings(uid), update.message.document
    path = doc.file_name
    await (await ctx.bot.get_file(doc.file_id)).download_to_drive(path)

    if st["mode"] == "split":
        nums = extract_vcf(path) if path.endswith(".vcf") else extract_txt(path)
        split_queue[uid] = {"file": path, "nums": nums}; st["step"] = "limit"
        await update.message.reply_text(f"📊 TOTAL NUMBERS: {len(nums)}. ENTER LIMIT PER FILE:")

    elif st["mode"] in ["rename_files", "rename_contacts"]:
        rename_queue[uid].append(path)
        st["step"] = "name"
        prompt = "NEW VCF FILE NAME" if st["mode"] == "rename_files" else "NEW CONTACT NAME"
        await update.message.reply_text(f"✏️ ENTER {prompt}:")

    elif st["mode"] == "gen" and st["step"] == "waiting_input":
        nums = extract_txt(path)
        for i, c in enumerate(chunk(nums, cfg["limit"])):
            f = make_vcf(c, cfg, i); await update.message.reply_document(open(f, "rb")); os.remove(f)
        os.remove(path); st.clear(); await update.message.reply_text("✅ PROCESS COMPLETE.", reply_markup=main_menu())

    elif st["mode"] == "txt2vcf":
        cfg["file_name"] = os.path.splitext(path)[0]
        f = make_vcf(extract_txt(path), cfg, 0); await update.message.reply_document(open(f, "rb"))
        os.remove(f); os.remove(path); st.clear(); await update.message.reply_text("✅ CONVERSION DONE.", reply_markup=main_menu())

    elif st["mode"] == "vcf2txt":
        out = f"{os.path.splitext(path)[0]}.txt"
        with open(out, "w") as f: f.write("\n".join(extract_vcf(path)))
        await update.message.reply_document(open(out, "rb")); os.remove(out); os.remove(path); st.clear()
        await update.message.reply_text("✅ CONVERSION DONE.", reply_markup=main_menu())

    elif st["mode"] == "merge":
        merge_queue[uid].append(path); await update.message.reply_text(f"📥 FILE {path} ADDED. SEND MORE OR TYPE DONE.")

    elif st["mode"] == "file_count":
        n = extract_vcf(path) if path.endswith(".vcf") else extract_txt(path)
        await update.message.reply_text(f"📊 NUMBERS FOUND: {len(n)}", reply_markup=main_menu()); os.remove(path); st.clear()

    # --- NEW: Editor File Handling ---
    elif st["mode"] == "editor":
        vcf_editor_data[uid] = path
        st["mode"] = "editor_action"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ ADD CONTACTS", callback_data="edit_add")],
            [InlineKeyboardButton("❌ REMOVE A NUMBER", callback_data="edit_remove")],
            [InlineKeyboardButton("🔙 CANCEL", callback_data="main_menu")]
        ])
        await update.message.reply_text(f"📂 File '{path}' received. Kya karna chahte ho?", reply_markup=kb)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    print("🚀 BOT STARTED SUCCESSFULLY")
    app.run_polling()

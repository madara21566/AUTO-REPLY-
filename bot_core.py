import os
import re
import pandas as pd
import phonenumbers
import asyncio
from phonenumbers import geocoder, carrier
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# 🔑 Bot Token
BOT_TOKEN = "8247588556:AAG850sPcxYDJcvpsu5OhL-Xpr6SBjribrQ"

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
quick_vcf_data = {}
vcf_editor_data = {}
convert_queue = {}

def settings(uid):
    user_settings.setdefault(uid, DEFAULT_SETTINGS.copy())
    return user_settings[uid]

def state(uid):
    user_state.setdefault(uid, {"mode": None, "step": None})
    return user_state[uid]

# ================= HELPERS & ANIMATION =================

async def progress_bar(msg, text):
    """
    Displays a percentage based loading animation.
    Speed increased significantly.
    """
    stages = [
        (20, "■■□□□□□□□□"),
        (50, "■■■■■□□□□□"),
        (80, "■■■■■■■■□□"),
        (100, "■■■■■■■■■■")
    ]

    for percent, bar in stages:
        try:
            await msg.edit_text(
                f"⏳ **{text}...**\n\n"
                f"`[{bar}] {percent}%`",
                parse_mode=ParseMode.MARKDOWN
            )
            await asyncio.sleep(0.1) # FAST SPEED (Reduced from 0.4)
        except:
            pass

def extract_all_numbers(path):
    ext = os.path.splitext(path)[1].lower()
    nums = []
    try:
        if ext == ".vcf":
            with open(path, "r", errors="ignore") as f:
                for line in f:
                    if line.startswith("TEL"):
                        n = re.sub(r"[^\d+]", "", line)
                        if len(n) >= 7: nums.append(n)
        elif ext in [".xlsx", ".xls"]:
            df = pd.read_excel(path, dtype=str)
            text_data = " ".join(df.values.flatten().astype(str))
            nums = re.findall(r"\+?\d{7,}", text_data)
        elif ext == ".csv":
            df = pd.read_csv(path, dtype=str)
            text_data = " ".join(df.values.flatten().astype(str))
            nums = re.findall(r"\+?\d{7,}", text_data)
        else:
            with open(path, "r", errors="ignore") as f:
                nums = re.findall(r"\+?\d{7,}", f.read())
    except Exception as e:
        print(f"Error extracting: {e}")
        return []
    return list(dict.fromkeys(nums))

def detect_primary_country(numbers):
    countries = {}
    for n in numbers[:50]:
        try:
            parse_num = "+" + n if not n.startswith("+") else n
            pn = phonenumbers.parse(parse_num, None)
            region = geocoder.description_for_number(pn, "en")
            if region: countries[region] = countries.get(region, 0) + 1
        except: continue
    if countries: return max(countries, key=countries.get)
    return "Unknown"

def generate_analysis_report(file_name, numbers):
    total = len(numbers)
    unique_set = set(numbers)
    unique_count = len(unique_set)
    duplicates = total - unique_count

    country_stats = {}
    invalid_count = 0
    for n in unique_set:
        try:
            parse_num = "+" + n if not n.startswith("+") else n
            pn = phonenumbers.parse(parse_num, None)
            if phonenumbers.is_valid_number(pn):
                region = geocoder.description_for_number(pn, "en") or "Unknown"
                country_stats[region] = country_stats.get(region, 0) + 1
            else: invalid_count += 1
        except: invalid_count += 1

    country_text = "\n".join([f"  └ {c}: {count}" for c, count in country_stats.items()])
    if not country_text: country_text = "  └ None detected"

    report = (
        f"📊 **FILE ANALYSIS REPORT**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 **File Name:** `{file_name}`\n\n"
        f"📌 **Statistics:**\n"
        f"  ├ 🔢 Total Numbers: `{total}`\n"
        f"  ├ ✅ Unique: `{unique_count}`\n"
        f"  └ ♻️ Duplicates: `{duplicates}`\n\n"
        f"🌍 **Country Breakdown:**\n"
        f"{country_text}\n\n"
        f"⚠️ **Integrity Check:**\n"
        f"  └ ❌ Invalid/Junk: `{invalid_count}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    return report

def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def make_vcf(numbers, cfg, index, custom_limit=None):
    limit = custom_limit if custom_limit else cfg["limit"]
    start = cfg["contact_start"] + index * limit
    out = ""
    for i, n in enumerate(numbers, start=start):
        name = f"{cfg['contact_name']}{str(i).zfill(3)}"
        if cfg.get("group_number"): name += f" ({cfg['group_number']})"
        clean_n = n.replace("+", "")
        prefix = cfg["country_code"] if cfg["country_code"] else "+"
        final_num = f"{prefix}{clean_n}"
        out += f"BEGIN:VCARD\nVERSION:3.0\nFN:{name}\nTEL;TYPE=CELL:{final_num}\nEND:VCARD\n"

    fname = f"{cfg['file_name']}_{cfg['vcf_start'] + index}.vcf"
    with open(fname, "w", encoding="utf-8") as f: f.write(out)
    return fname

# ================= UI & MENUS =================

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📂 FILE ANALYSIS", callback_data="analysis"),
            InlineKeyboardButton("🔄 CONVERTER", callback_data="converter")
        ],
        [
            InlineKeyboardButton("⚡ QUICK VCF", callback_data="quick_vcf"),
            InlineKeyboardButton("📇 PRO GENERATOR", callback_data="gen")
        ],
        [
            InlineKeyboardButton("✂️ SPLIT VCF", callback_data="split_vcf"),
            InlineKeyboardButton("🧩 MERGE FILES", callback_data="merge")
        ],
        [
            InlineKeyboardButton("🛠️ EDITOR", callback_data="vcf_editor"),
            InlineKeyboardButton("📝 NAME MAKER", callback_data="name_gen")
        ],
        [
            InlineKeyboardButton("✏️ RENAME FILE", callback_data="rename_files"),
            InlineKeyboardButton("✏️ RENAME CONTACT", callback_data="rename_contacts")
        ],
        # Removed TXT/VCF Buttons as requested
        [
            InlineKeyboardButton("⚙️ SETTINGS", callback_data="mysettings"),
            InlineKeyboardButton("🗑 RESET", callback_data="reset")
        ]
    ])

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 MAIN MENU", callback_data="main_menu")]])

def cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ CANCEL OPERATION", callback_data="main_menu")]])

def convert_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 TO TXT", callback_data="cv_txt"), InlineKeyboardButton("📇 TO VCF", callback_data="cv_vcf")],
        [InlineKeyboardButton("📊 TO CSV", callback_data="cv_csv"), InlineKeyboardButton("📑 TO XLSX", callback_data="cv_xlsx")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="main_menu")]
    ])

async def show_summary(msg, cfg):
    c_disp = cfg['country_code'] if cfg['country_code'] else "🤖 Auto-Detect"
    g_disp = cfg['group_number'] if cfg['group_number'] else "❌ None"

    text = (
        "⚙️ **CONFIGURATION SUMMARY**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📂 **File Name:** `{cfg['file_name']}`\n"
        f"👤 **Contact Name:** `{cfg['contact_name']}`\n"
        f"📏 **Limit Per File:** `{cfg['limit']}`\n"
        f"🔢 **Start Index:** `{cfg['contact_start']}`\n"
        f"🌍 **Country Code:** `{c_disp}`\n"
        f"🏷 **Group Tag:** `{g_disp}`\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👇 *Does this look correct?*"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ CONFIRM & START", callback_data="gen_done")],
        [InlineKeyboardButton("✏️ EDIT SETTINGS", callback_data="gen")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="main_menu")]
    ])
    if hasattr(msg, 'edit_text'):
        await msg.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else:
        await msg.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

# ================= HANDLERS =================

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"🌟 **ULTIMATE VCF MANAGER PRO** 🌟\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👋 **Greetings, {user.first_name}!**\n"
        f"Welcome to the most advanced contact management bot.\n\n"
        f"🚀 **Core Capabilities:**\n"
        f"  💎 **Smart Conversion** (TXT, VCF, XLS, CSV)\n"
        f"  💎 **Pro Generation** (Auto + Prefixing)\n"
        f"  💎 **Split & Merge** Large Files\n"
        f"  💎 **Detailed Analytics** & Reporting\n\n"
        f"👇 **Select a tool from the dashboard below:**"
    )
    await update.message.reply_text(text, reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)

async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    st, cfg = state(uid), settings(uid)

    if q.data == "main_menu":
        st.clear()
        if uid in merge_queue: merge_queue.pop(uid)
        await q.message.edit_text("🤖 **MAIN MENU**\nSelect an option to proceed:", reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)

    # --- Analysis Feature ---
    elif q.data == "analysis":
        st.update({"mode": "analysis", "step": "file"})
        await q.message.edit_text("🧐 **FILE ANALYSIS MODE**\n\nPlease upload any file (TXT, VCF, CSV, XLSX) to generate a report.", reply_markup=cancel_kb(), parse_mode=ParseMode.MARKDOWN)

    # --- Converter Feature ---
    elif q.data == "converter":
        st.update({"mode": "converter", "step": "file"})
        await q.message.edit_text("🔄 **UNIVERSAL CONVERTER**\n\nPlease upload a file (TXT, VCF, CSV, XLSX) you wish to convert.", reply_markup=cancel_kb(), parse_mode=ParseMode.MARKDOWN)

    elif q.data.startswith("cv_"):
        target_fmt = q.data.split("_")[1]
        path = convert_queue.get(uid)
        if not path: return await q.message.reply_text("❌ Session expired. Please upload the file again.", reply_markup=main_menu())

        # ANIMATION
        proc_msg = await q.message.edit_text("⏳ **Initializing Conversion...**", parse_mode=ParseMode.MARKDOWN)
        await progress_bar(proc_msg, "Converting File")

        try:
            nums = extract_all_numbers(path)
            out_file = f"Converted_{os.path.basename(path).split('.')[0]}.{target_fmt}"

            if target_fmt == "vcf":
                temp_cfg = DEFAULT_SETTINGS.copy()
                temp_cfg["file_name"] = "Converted"
                out_file = make_vcf(nums, temp_cfg, 0, custom_limit=len(nums))
            elif target_fmt == "txt":
                formatted = ["+" + n.replace("+","") for n in nums]
                with open(out_file, "w") as f: f.write("\n".join(formatted))
            elif target_fmt == "csv":
                formatted = ["+" + n.replace("+","") for n in nums]
                df = pd.DataFrame(formatted, columns=["Mobile Number"])
                df.to_csv(out_file, index=False)
            elif target_fmt == "xlsx":
                formatted = ["+" + n.replace("+","") for n in nums]
                df = pd.DataFrame(formatted, columns=["Mobile Number"])
                df.to_excel(out_file, index=False)

            await proc_msg.delete()
            await q.message.reply_document(open(out_file, "rb"), caption=f"✅ **Conversion Successful!**", parse_mode=ParseMode.MARKDOWN)
            os.remove(out_file); os.remove(path); st.clear()
            await q.message.reply_text("🔄 Would you like to convert another file?", reply_markup=main_menu())
        except Exception as e:
            await proc_msg.delete()
            await q.message.reply_text(f"❌ Error Occurred: {e}", reply_markup=main_menu())

    # --- Quick VCF ---
    elif q.data == "quick_vcf":
        st.update({"mode": "quick", "step": "file"})
        quick_vcf_data[uid] = []
        await q.message.edit_text("⚡ **QUICK VCF MODE**\n\n⌨️ Please enter a **Filename** for your VCF:", reply_markup=cancel_kb(), parse_mode=ParseMode.MARKDOWN)

    elif q.data == "add_more_quick":
        st["step"] = "contact"
        await q.message.edit_text("👤 Please enter the **Next Contact Name**:", parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_kb())

    elif q.data == "finish_quick":
        f_name = st.get("file", "QuickVCF")

        proc_msg = await q.message.reply_text("⏳ **Preparing...**", parse_mode=ParseMode.MARKDOWN)
        await progress_bar(proc_msg, "Generating VCF")

        out = ""
        total_nums = 0
        for entry in quick_vcf_data[uid]:
            c_name = entry['contact']
            for i, n in enumerate(entry['nums'], start=1):
                clean_n = "+" + n.replace("+", "")
                out += f"BEGIN:VCARD\nVERSION:3.0\nFN:{c_name}{str(i).zfill(3)}\nTEL;TYPE=CELL:{clean_n}\nEND:VCARD\n"
                total_nums += 1

        path = f"{f_name}.vcf"
        with open(path, "w", encoding="utf-8") as x: x.write(out)

        await proc_msg.delete()
        await q.message.reply_document(open(path, "rb"), caption=f"✅ **Task Completed!**\nTotal Contacts: {total_nums}", parse_mode=ParseMode.MARKDOWN)
        os.remove(path); st.clear(); quick_vcf_data.pop(uid, None)
        await q.message.reply_text("🏠 Return to Menu:", reply_markup=main_menu())

    # --- VCF Editor ---
    elif q.data == "vcf_editor":
        st.update({"mode": "editor", "step": "file"})
        await q.message.edit_text("🛠️ **EDITOR MODE**\n\nPlease upload the VCF file you wish to modify.", reply_markup=cancel_kb(), parse_mode=ParseMode.MARKDOWN)

    elif q.data.startswith("edit_"):
        action = q.data.split("_")[1]
        st["step"] = f"do_{action}"
        msg = "✍️ **Please send the Numbers to ADD:**" if action == "add" else "🗑️ **Please send the Number to REMOVE:**"
        await q.message.edit_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_kb())

    # --- Generation Flow ---
    elif q.data == "gen":
        st.update({"mode": "gen", "step": "file_name"})
        await q.message.edit_text("📇 **PRO GENERATOR SETUP**\n\n⌨️ Enter **File Name**:", reply_markup=cancel_kb(), parse_mode=ParseMode.MARKDOWN)

    elif q.data == "gen_done":
        st["step"] = "waiting_input"
        await q.message.edit_text("🔒 **Configuration Locked.**\n\n📂 **Please upload your file now.**\n(Supported: TXT, VCF, CSV, XLSX)", reply_markup=cancel_kb(), parse_mode=ParseMode.MARKDOWN)

    elif q.data == "skip_cc":
        cfg["country_code"] = ""
        st["step"] = "group_number"
        await q.message.edit_text("📑 Enter **Group Name** (or Skip):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏩ SKIP", callback_data="skip_group"), InlineKeyboardButton("❌ CANCEL", callback_data="main_menu")]]), parse_mode=ParseMode.MARKDOWN)

    elif q.data == "skip_group":
        cfg["group_number"] = None; await show_summary(q.message, cfg)

    # --- Name Generator ---
    elif q.data == "name_gen":
        st.update({"mode": "name_gen", "step": "name"})
        await q.message.edit_text("📝 **NAME GENERATOR**\n\n✏️ Enter the Base Name (e.g. `Client`):", reply_markup=cancel_kb(), parse_mode=ParseMode.MARKDOWN)

    # --- Universal Handlers ---
    elif q.data in ["split_vcf", "merge", "rename_files", "rename_contacts", "mysettings", "reset"]:
        if q.data == "merge": merge_queue[uid] = []
        elif q.data in ["rename_files", "rename_contacts"]: rename_queue[uid] = []

        target_mode = "split" if q.data == "split_vcf" else q.data
        st["mode"] = target_mode

        if q.data == "mysettings":
            await show_summary(q.message, cfg)
        elif q.data == "reset":
            user_settings[uid] = DEFAULT_SETTINGS.copy(); st.clear()
            await q.message.edit_text("♻️ **All settings have been reset to default.**", reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)
        else:
            st["step"] = "file" if q.data != "merge" else "collect"
            prompts = {
                "split_vcf": "✂️ **SPLIT VCF**\nPlease upload the VCF/TXT file to split:",
                "rename_files": "📝 **RENAME FILE**\nPlease upload the VCF file:",
                "rename_contacts": "👤 **RENAME CONTACT**\nPlease upload the VCF file:",
                "merge": "🧩 **MERGE MODE**\nSend files one by one. Type 'DONE' when finished."
            }
            await q.message.edit_text(prompts.get(q.data, "Send File:"), reply_markup=cancel_kb(), parse_mode=ParseMode.MARKDOWN)

    elif q.data.startswith("merge_as_"):
        fmt = q.data.split("_")[-1]

        proc_msg = await q.message.reply_text("⏳ **Initializing...**", parse_mode=ParseMode.MARKDOWN)
        await progress_bar(proc_msg, "Merging Files")

        try:
            nums = []
            for f in merge_queue[uid]:
                nums.extend(extract_all_numbers(f))
                if os.path.exists(f): os.remove(f)
            nums = list(dict.fromkeys(nums))

            f_name = "Merged_File"
            if fmt == "vcf":
                out_f = make_vcf(nums, cfg, 0, custom_limit=len(nums))
            else:
                out_f = f"{f_name}.txt"
                with open(out_f, "w") as x: x.write("\n".join(["+"+n.replace("+","") for n in nums]))

            await proc_msg.delete()
            await q.message.reply_document(open(out_f, "rb"), caption="✅ **Merge Successful!**", parse_mode=ParseMode.MARKDOWN)
            os.remove(out_f); st.clear()
            await q.message.reply_text("🏠 Main Menu:", reply_markup=main_menu())
        except Exception as e:
            await proc_msg.delete()
            await q.message.reply_text(f"❌ Error: {e}", reply_markup=main_menu())

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st, cfg, txt = state(uid), settings(uid), update.message.text.strip()

    # GEN MODE INPUTS
    if st["mode"] == "gen":
        if st["step"] == "file_name":
            cfg["file_name"] = txt; st["step"] = "contact_name"
            await update.message.reply_text("👤 Enter **Contact Name**:", parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_kb())
        elif st["step"] == "contact_name":
            cfg["contact_name"] = txt; st["step"] = "limit"
            await update.message.reply_text("📊 Enter **Limit Per File** (e.g. 100):", parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_kb())
        elif st["step"] == "limit":
            cfg["limit"] = int(txt) if txt.isdigit() else 100; st["step"] = "contact_start"
            await update.message.reply_text("🔢 Enter **Start Number** (e.g. 1):", parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_kb())
        elif st["step"] == "contact_start":
            cfg["contact_start"] = int(txt) if txt.isdigit() else 1; st["step"] = "vcf_start"
            await update.message.reply_text("📄 Enter **VCF File Start Index**:", parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_kb())
        elif st["step"] == "vcf_start":
            cfg["vcf_start"] = int(txt) if txt.isdigit() else 1; st["step"] = "country_code"
            await update.message.reply_text("🌍 Enter **Country Code** (e.g. +91) or Skip:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏩ AUTO DETECT", callback_data="skip_cc"), InlineKeyboardButton("❌ CANCEL", callback_data="main_menu")]]), parse_mode=ParseMode.MARKDOWN)
        elif st["step"] == "country_code":
            cfg["country_code"] = txt if txt.startswith("+") else f"+{txt}"; st["step"] = "group_number"
            await update.message.reply_text("📑 Enter **Group Name**:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏩ SKIP", callback_data="skip_group"), InlineKeyboardButton("❌ CANCEL", callback_data="main_menu")]]), parse_mode=ParseMode.MARKDOWN)
        elif st["step"] == "group_number":
            cfg["group_number"] = txt; await show_summary(update.message, cfg)

    elif st["mode"] == "split" and st["step"] == "limit":
        if txt.isdigit():
            limit = int(txt)
            nums, path = split_queue[uid]["nums"], split_queue[uid]["file"]

            proc_msg = await update.message.reply_text(f"⏳ **Starting...**", parse_mode=ParseMode.MARKDOWN)
            await progress_bar(proc_msg, "Splitting Files")

            for i, p in enumerate(chunk(nums, limit)):
                f = make_vcf(p, cfg, i, custom_limit=limit)
                await update.message.reply_document(open(f, "rb")); os.remove(f)
            if os.path.exists(path): os.remove(path)

            await proc_msg.delete()
            st.clear(); await update.message.reply_text("✅ **Splitting Completed.**", reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)

    elif st["mode"] == "merge" and txt.lower() == "done":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 AS VCF", callback_data="merge_as_vcf"), InlineKeyboardButton("📝 AS TXT", callback_data="merge_as_txt")],
            [InlineKeyboardButton("❌ CANCEL", callback_data="main_menu")]
        ])
        await update.message.reply_text("📋 **Merge Ready.** Choose Output Format:", reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    elif st["mode"] == "quick" and st["step"] == "file":
        st["file"] = txt; st["step"] = "contact"
        await update.message.reply_text("👤 Enter **Contact Name**:", parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_kb())
    elif st["mode"] == "quick" and st["step"] == "contact":
        st["contact"] = txt; st["step"] = "numbers"
        await update.message.reply_text(f"📤 Paste Numbers for **'{txt}'**:", parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_kb())
    elif st["mode"] == "quick" and st["step"] == "numbers":
        raw_nums = re.findall(r"\d{7,}", txt)
        quick_vcf_data[uid].append({"contact": st["contact"], "nums": list(set(raw_nums))})
        await update.message.reply_text(f"✅ Added {len(set(raw_nums))} numbers.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ ADD MORE", callback_data="add_more_quick"), InlineKeyboardButton("🏁 FINISH", callback_data="finish_quick"), InlineKeyboardButton("❌ CANCEL", callback_data="main_menu")]]))

    elif st["mode"] == "name_gen":
        if st["step"] == "name":
            st["base_name"] = txt; st["step"] = "count"
            await update.message.reply_text("🔢 How many names?", parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_kb())
        elif st["step"] == "count":
            if txt.isdigit():
                proc_msg = await update.message.reply_text("⏳ **Generating...**", parse_mode=ParseMode.MARKDOWN)
                await progress_bar(proc_msg, "Creating List")

                count = int(txt)
                base = st["base_name"]
                content = "\n".join([f"{base} {i+1}" for i in range(count)])

                await proc_msg.delete()

                if len(content) > 4000:
                    with open("names.txt", "w") as f: f.write(content)
                    await update.message.reply_document(open("names.txt", "rb"), caption="✅ List too long, sent as file.")
                    os.remove("names.txt")
                else:
                    await update.message.reply_text(f"📝 **GENERATED LIST:**\n\n```\n{content}\n```", parse_mode=ParseMode.MARKDOWN)
                st.clear(); await update.message.reply_text("✅ **Task Done.**", reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)

    elif st["mode"] == "editor_action":
        path = vcf_editor_data[uid]
        proc_msg = await update.message.reply_text("⏳ **Processing...**", parse_mode=ParseMode.MARKDOWN)
        await progress_bar(proc_msg, "Applying Edits")

        if st["step"] == "do_add":
            nums = list(dict.fromkeys(re.findall(r"\d{7,}", txt)))
            new_v = "".join([f"BEGIN:VCARD\nVERSION:3.0\nFN:Added{str(i+1).zfill(3)}\nTEL;TYPE=CELL:+{n.replace('+','')}\nEND:VCARD\n" for i, n in enumerate(nums)])
            with open(path, "a") as f: f.write(new_v)
            await proc_msg.delete()
            await update.message.reply_document(open(path, "rb"), caption="✅ **Contacts Added**", parse_mode=ParseMode.MARKDOWN)
        elif st["step"] == "do_remove":
            target = re.sub(r"\D", "", txt)
            with open(path, "r") as f: content = f.read()
            cards = content.split("END:VCARD\n")
            new_cards = [c for c in cards if target not in c and "BEGIN:VCARD" in c]
            with open(path, "w") as f: f.write("END:VCARD\n".join(new_cards) + "END:VCARD\n")
            await proc_msg.delete()
            await update.message.reply_document(open(path, "rb"), caption="✅ **Number Removed**", parse_mode=ParseMode.MARKDOWN)
        os.remove(path); st.clear(); await update.message.reply_text("✅ **Edit Finished.**", reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)

    elif st["mode"] in ["rename_files", "rename_contacts"] and st["step"] == "name":
        if uid not in rename_queue or not rename_queue[uid]:
             await update.message.reply_text("❌ No file found.", reply_markup=main_menu())
             return

        proc_msg = await update.message.reply_text("⏳ **Renaming...**", parse_mode=ParseMode.MARKDOWN)
        await progress_bar(proc_msg, "Processing Files")

        for f in rename_queue[uid]:
            if st["mode"] == "rename_files":
                new_path = f"{txt}.vcf"
                os.rename(f, new_path)
                await update.message.reply_document(open(new_path, "rb"))
                os.remove(new_path)
            else:
                out, idx = "", 1
                with open(f, "r") as r:
                    for line in r:
                        if line.startswith("FN:"):
                            out += f"FN:{txt}{str(idx).zfill(3)}\n"; idx+=1
                        else: out += line
                with open(f, "w") as w: w.write(out)
                await update.message.reply_document(open(f, "rb"))
                os.remove(f)

        await proc_msg.delete()
        st.clear(); await update.message.reply_text("✅ **Rename Complete.**", reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)

async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st, cfg, doc = state(uid), settings(uid), update.message.document
    path = doc.file_name
    file_obj = await ctx.bot.get_file(doc.file_id)
    await file_obj.download_to_drive(path)

    if st["mode"] == "analysis":
        proc_msg = await update.message.reply_text("⏳ **Analyzing...**", parse_mode=ParseMode.MARKDOWN)
        await progress_bar(proc_msg, "Scanning File")

        nums = extract_all_numbers(path)
        report = generate_analysis_report(path, nums)
        await proc_msg.delete()
        await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu())
        os.remove(path); st.clear()

    elif st["mode"] == "converter":
        convert_queue[uid] = path
        st["step"] = "format"
        await update.message.reply_text("📂 **File Received.** Choose output format:", reply_markup=convert_kb(), parse_mode=ParseMode.MARKDOWN)

    elif st["mode"] == "split":
        nums = extract_all_numbers(path)
        split_queue[uid] = {"file": path, "nums": nums}; st["step"] = "limit"
        await update.message.reply_text(f"📊 Found **{len(nums)}** numbers.\nEnter limit per file:", parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_kb())

    elif st["mode"] == "gen" and st["step"] == "waiting_input":
        proc_msg = await update.message.reply_text("⚙️ **Processing...**", parse_mode=ParseMode.MARKDOWN)
        await progress_bar(proc_msg, "Generating Files")

        nums = extract_all_numbers(path)
        detected_country = "Manual"
        if not cfg["country_code"]: detected_country = detect_primary_country(nums)

        generated_files = []
        for i, c in enumerate(chunk(nums, cfg["limit"])):
            f = make_vcf(c, cfg, i)
            await update.message.reply_document(open(f, "rb"))
            generated_files.append(f)

        await proc_msg.delete()

        summary = (
            f"✅ **GENERATION COMPLETE**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📂 File Name: `{cfg['file_name']}`\n"
            f"🔢 Total: `{len(nums)}` | 📁 Files: `{len(generated_files)}`\n"
            f"🌍 Detect: `{detected_country}`\n"
        )
        await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu())
        for f in generated_files: os.remove(f)
        os.remove(path); st.clear()

    elif st["mode"] == "merge":
        merge_queue[uid].append(path)
        await update.message.reply_text(f"📥 **File Added.** Send next or type 'DONE'.", parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_kb())

    elif st["mode"] in ["rename_files", "rename_contacts"]:
        if uid not in rename_queue: rename_queue[uid] = []
        rename_queue[uid].append(path)
        st["step"] = "name"
        prompt = "NEW FILE NAME" if st["mode"] == "rename_files" else "NEW CONTACT NAME"
        await update.message.reply_text(f"✏️ Enter **{prompt}**:", parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_kb())

    elif st["mode"] == "editor":
        vcf_editor_data[uid] = path
        st["mode"] = "editor_action"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ ADD", callback_data="edit_add"), InlineKeyboardButton("❌ REMOVE", callback_data="edit_remove")],
            [InlineKeyboardButton("❌ CANCEL", callback_data="main_menu")]
        ])
        await update.message.reply_text(f"📂 **File Ready.** Select Action:", reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    print("🚀 PRO BOT STARTED WITH PERCENTAGE ANIMATION")
    app.run_polling()

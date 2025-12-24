import os
import re
import pandas as pd
from datetime import datetime
import traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ================= CONFIG =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 7640327597
BOT_START_TIME = datetime.utcnow()

# ================= DEFAULTS =================
default_vcf_name = "Contacts"
default_contact_name = "Contact"
default_limit = 100

# ================= USER DATA =================
user_file_names = {}
user_contact_names = {}
user_limits = {}
user_start_indexes = {}
user_vcf_start_numbers = {}
user_country_codes = {}
user_group_start_numbers = {}
merge_data = {}
conversion_mode = {}
user_input_state = {}

# ================= ERROR HANDLER =================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
    with open("bot_errors.log", "a") as f:
        f.write(err)
    try:
        await context.bot.send_message(OWNER_ID, f"⚠️ ERROR:\n{err[:4000]}")
    except:
        pass

# ================= HELPERS =================
def generate_vcf(numbers, filename="Contacts", cname="Contact",
                 start_index=None, cc="", group=None):
    data = ""
    for i, num in enumerate(numbers, start=start_index or 1):
        name = f"{cname}{str(i).zfill(3)}"
        if group:
            name += f" (Group {group})"
        num = f"{cc}{num}" if cc else num
        data += f"BEGIN:VCARD\nVERSION:3.0\nFN:{name}\nTEL:{num}\nEND:VCARD\n"
    path = f"{filename}.vcf"
    with open(path, "w") as f:
        f.write(data)
    return path

def extract_numbers_from_vcf(path):
    nums = set()
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("TEL"):
                nums.add(re.sub(r"\D", "", line))
    return nums

def extract_numbers_from_txt(path):
    nums = set()
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            nums.update(re.findall(r"\d{7,}", line))
    return nums

# ================= START MENU =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📂 Filename", callback_data="filename"),
         InlineKeyboardButton("👤 Contact", callback_data="contact")],
        [InlineKeyboardButton("📊 Limit", callback_data="limit"),
         InlineKeyboardButton("🔢 Start No.", callback_data="startnum")],
        [InlineKeyboardButton("📄 VCF Start", callback_data="vcfstart"),
         InlineKeyboardButton("🌍 Country Code", callback_data="cc")],
        [InlineKeyboardButton("📑 Group", callback_data="group"),
         InlineKeyboardButton("🛠 Make VCF", callback_data="makevcf")],
        [InlineKeyboardButton("🔀 Merge", callback_data="merge"),
         InlineKeyboardButton("✅ Done", callback_data="done")],
        [InlineKeyboardButton("📝 TXT → VCF", callback_data="txt2vcf"),
         InlineKeyboardButton("📄 VCF → TXT", callback_data="vcf2txt")],
        [InlineKeyboardButton("⚙️ My Settings", callback_data="mysettings"),
         InlineKeyboardButton("♻️ Reset", callback_data="reset")]
    ]

    await update.message.reply_text(
        "☠️ *VCF MAKER BOT – BUTTON MODE* ☠️\n\n👇 Option choose karo:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ================= BUTTON HANDLER =================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    ask = {
        "filename": "📂 Filename bhejo",
        "contact": "👤 Contact name bhejo",
        "limit": "📊 Limit number bhejo",
        "startnum": "🔢 Contact start number bhejo",
        "vcfstart": "📄 VCF start number bhejo",
        "cc": "🌍 Country code bhejo (ex +91)",
        "group": "📑 Group start number bhejo"
    }

    if q.data in ask:
        user_input_state[uid] = q.data
        await q.message.reply_text(ask[q.data])
        return

    if q.data == "makevcf":
        await q.message.reply_text("Example:\nFriends 9876543210 9123456789")
    elif q.data == "merge":
        merge_data[uid] = {"files": [], "filename": "Merged"}
        await q.message.reply_text("📂 Files bhejo\nDone ke liye DONE dabao")
    elif q.data == "done":
        await done_merge(update, context)
    elif q.data == "mysettings":
        await my_settings(update, context)
    elif q.data == "reset":
        await reset_settings(update, context)
    elif q.data == "txt2vcf":
        await txt2vcf(update, context)
    elif q.data == "vcf2txt":
        await vcf2txt(update, context)

# ================= TEXT HANDLER =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    if uid in user_input_state:
        state = user_input_state.pop(uid)
        if state == "filename":
            user_file_names[uid] = text
        elif state == "contact":
            user_contact_names[uid] = text
        elif state == "limit" and text.isdigit():
            user_limits[uid] = int(text)
        elif state == "startnum" and text.isdigit():
            user_start_indexes[uid] = int(text)
        elif state == "vcfstart" and text.isdigit():
            user_vcf_start_numbers[uid] = int(text)
        elif state == "cc":
            user_country_codes[uid] = text
        elif state == "group" and text.isdigit():
            user_group_start_numbers[uid] = int(text)

        await update.message.reply_text("✅ Saved")
        await start(update, context)
        return

    numbers = re.findall(r"\d{7,}", text)
    if numbers:
        await process_numbers(update, context, numbers)

# ================= FILE HANDLER =================
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document
    path = f"{file.file_unique_id}_{file.file_name}"
    await (await context.bot.get_file(file.file_id)).download_to_drive(path)
    uid = update.effective_user.id

    if uid in merge_data:
        merge_data[uid]["files"].append(path)
        await update.message.reply_text("📥 Added")
        return

    if uid in conversion_mode:
        if conversion_mode[uid] == "txt2vcf":
            nums = extract_numbers_from_txt(path)
            out = generate_vcf(list(nums), "Converted")
        else:
            nums = extract_numbers_from_vcf(path)
            out = "Converted.txt"
            with open(out, "w") as f:
                f.write("\n".join(nums))

        await update.message.reply_document(open(out, "rb"))
        os.remove(out)
        os.remove(path)
        conversion_mode.pop(uid)
        return

    if path.endswith(".vcf"):
        nums = extract_numbers_from_vcf(path)
    else:
        nums = extract_numbers_from_txt(path)

    await process_numbers(update, context, list(nums))
    os.remove(path)

# ================= PROCESS =================
async def process_numbers(update, context, numbers):
    uid = update.effective_user.id
    limit = user_limits.get(uid, default_limit)
    fname = user_file_names.get(uid, default_vcf_name)
    cname = user_contact_names.get(uid, default_contact_name)
    cc = user_country_codes.get(uid, "")
    start = user_start_indexes.get(uid)
    vcfstart = user_vcf_start_numbers.get(uid)
    group = user_group_start_numbers.get(uid)

    chunks = [numbers[i:i+limit] for i in range(0, len(numbers), limit)]
    for i, chunk in enumerate(chunks):
        file = generate_vcf(
            chunk,
            f"{fname}_{(vcfstart or 1)+i}",
            cname,
            (start or 1) + i*limit,
            cc,
            (group+i) if group else None
        )
        await update.message.reply_document(open(file, "rb"))
        os.remove(file)

# ================= COMMAND HELPERS =================
async def txt2vcf(update, context):
    conversion_mode[update.effective_user.id] = "txt2vcf"
    await update.message.reply_text("📂 TXT file bhejo")

async def vcf2txt(update, context):
    conversion_mode[update.effective_user.id] = "vcf2txt"
    await update.message.reply_text("📂 VCF file bhejo")

async def my_settings(update, context):
    uid = update.effective_user.id
    await update.message.reply_text(
        f"📂 File: {user_file_names.get(uid, default_vcf_name)}\n"
        f"👤 Contact: {user_contact_names.get(uid, default_contact_name)}\n"
        f"📊 Limit: {user_limits.get(uid, default_limit)}"
    )

async def reset_settings(update, context):
    uid = update.effective_user.id
    for d in [user_file_names, user_contact_names, user_limits,
              user_start_indexes, user_vcf_start_numbers,
              user_country_codes, user_group_start_numbers]:
        d.pop(uid, None)
    await update.message.reply_text("♻️ Reset Done")

async def done_merge(update, context):
    uid = update.effective_user.id
    if uid not in merge_data:
        return
    nums = set()
    for f in merge_data[uid]["files"]:
        if f.endswith(".vcf"):
            nums |= extract_numbers_from_vcf(f)
        else:
            nums |= extract_numbers_from_txt(f)
        os.remove(f)
    out = generate_vcf(list(nums), "Merged")
    await update.message.reply_document(open(out, "rb"))
    os.remove(out)
    merge_data.pop(uid)

# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_error_handler(error_handler)

    print("🚀 BOT RUNNING (BUTTON MODE)")
    app.run_polling()

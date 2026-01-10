import os
import re
import traceback
import pandas as pd
from datetime import datetime

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
OWNER_ID = 7640327597  # owner telegram id

ALLOWED_USERS = [
    7856502907, 7950732287, 8128934569, 5849097477,
    7640327597, 7669357884, 7118726445, 7043391463, 8047407478
]

START_TIME = datetime.utcnow()

# ================= DEFAULTS =================
DEFAULT_FILE_NAME = "Contacts"
DEFAULT_CONTACT_NAME = "Contact"
DEFAULT_LIMIT = 100

# ================= USER DATA =================
user_settings = {}
user_state = {}        # current mode
merge_data = {}        # merge files
conversion_mode = {}  # txt2vcf / vcf2txt


# ================= HELPERS =================
def is_authorized(user_id: int) -> bool:
    return user_id in ALLOWED_USERS


def get_user_settings(user_id: int):
    if user_id not in user_settings:
        user_settings[user_id] = {
            "file_name": DEFAULT_FILE_NAME,
            "contact_name": DEFAULT_CONTACT_NAME,
            "limit": DEFAULT_LIMIT,
            "start_index": None,
            "vcf_start": None,
            "country_code": "",
            "group_start": None,
        }
    return user_settings[user_id]


def generate_vcf(numbers, filename, contact_name,
                 start_index=None, country_code="", group_num=None):
    vcf = ""
    for i, num in enumerate(numbers, start=start_index or 1):
        name = f"{contact_name}{str(i).zfill(3)}"
        if group_num:
            name += f" (Group {group_num})"

        final_num = f"{country_code}{num}" if country_code else num
        vcf += (
            "BEGIN:VCARD\n"
            "VERSION:3.0\n"
            f"FN:{name}\n"
            f"TEL;TYPE=CELL:{final_num}\n"
            "END:VCARD\n"
        )

    path = f"{filename}.vcf"
    with open(path, "w", encoding="utf-8") as f:
        f.write(vcf)
    return path


def extract_numbers_from_vcf(path):
    numbers = set()
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        data = f.read()
    for line in data.splitlines():
        if line.startswith("TEL"):
            num = re.sub(r"[^0-9]", "", line)
            if len(num) >= 7:
                numbers.add(num)
    return numbers


def extract_numbers_from_txt(path):
    numbers = set()
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            found = re.findall(r"\d{7,}", line)
            numbers.update(found)
    return numbers


# ================= UI =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Make VCF", callback_data="make_vcf")],
        [
            InlineKeyboardButton("🔁 TXT → VCF", callback_data="txt2vcf"),
            InlineKeyboardButton("🔄 VCF → TXT", callback_data="vcf2txt"),
        ],
        [InlineKeyboardButton("🧩 Merge Files", callback_data="merge")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("📊 My Settings", callback_data="mysettings")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
    ])


def settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 File Name", callback_data="set_file")],
        [InlineKeyboardButton("👤 Contact Name", callback_data="set_contact")],
        [InlineKeyboardButton("📊 Per VCF Limit", callback_data="set_limit")],
        [InlineKeyboardButton("🔢 Contact Start No.", callback_data="set_start")],
        [InlineKeyboardButton("📄 VCF Start No.", callback_data="set_vcfstart")],
        [InlineKeyboardButton("🌍 Country Code", callback_data="set_country")],
        [InlineKeyboardButton("📑 Group Number", callback_data="set_group")],
        [InlineKeyboardButton("♻️ Reset All", callback_data="reset")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")],
    ])


# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ Access denied. Owner se contact karein.")
        return

    await update.message.reply_text(
        "👋 *Welcome to VCF Maker Bot*\n\n"
        "👉 Neeche buttons se choose karein.\n"
        "Commands yaad rakhne ki zarurat nahi 🙂",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )


# ================= BUTTON HANDLER =================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    settings = get_user_settings(user_id)

    data = query.data

    if data == "make_vcf":
        user_state[user_id] = "make_vcf"
        await query.message.reply_text(
            "📤 *Numbers ya file bhejo*\n"
            "TXT / CSV / XLSX / VCF – sab chalega.",
            parse_mode="Markdown"
        )

    elif data == "txt2vcf":
        user_state[user_id] = "txt2vcf"
        await query.message.reply_text("📂 TXT file bhejo → VCF bana dunga")

    elif data == "vcf2txt":
        user_state[user_id] = "vcf2txt"
        await query.message.reply_text("📂 VCF file bhejo → TXT bana dunga")

    elif data == "merge":
        merge_data[user_id] = []
        user_state[user_id] = "merge"
        await query.message.reply_text(
            "📥 Multiple TXT / VCF bhejo\n"
            "Sab bhejne ke baad *DONE* likho",
            parse_mode="Markdown"
        )

    elif data == "settings":
        await query.message.reply_text("⚙️ *Settings*", reply_markup=settings_menu(), parse_mode="Markdown")

    elif data == "mysettings":
        await query.message.reply_text(
            f"📊 *Your Settings*\n\n"
            f"📂 File Name: `{settings['file_name']}`\n"
            f"👤 Contact Name: `{settings['contact_name']}`\n"
            f"📊 Limit: `{settings['limit']}`\n"
            f"🔢 Contact Start: `{settings['start_index']}`\n"
            f"📄 VCF Start: `{settings['vcf_start']}`\n"
            f"🌍 Country Code: `{settings['country_code']}`\n"
            f"📑 Group Start: `{settings['group_start']}`",
            parse_mode="Markdown"
        )

    elif data == "help":
        await query.message.reply_text(
            "ℹ️ *Help*\n\n"
            "➕ Make VCF → numbers/file se VCF\n"
            "🔁 TXT → VCF → txt convert\n"
            "🔄 VCF → TXT → extract numbers\n"
            "🧩 Merge → multiple files merge\n"
            "⚙️ Settings → customize\n",
            parse_mode="Markdown"
        )

    elif data == "back":
        await query.message.reply_text("⬅️ Main Menu", reply_markup=main_menu())


# ================= TEXT HANDLER =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    text = update.message.text.strip()
    settings = get_user_settings(user_id)

    # MERGE DONE
    if user_state.get(user_id) == "merge" and text.lower() == "done":
        all_numbers = set()
        for path in merge_data.get(user_id, []):
            if path.endswith(".vcf"):
                all_numbers.update(extract_numbers_from_vcf(path))
            elif path.endswith(".txt"):
                all_numbers.update(extract_numbers_from_txt(path))
            os.remove(path)

        out = generate_vcf(
            list(all_numbers),
            settings["file_name"],
            settings["contact_name"],
            settings["start_index"],
            settings["country_code"],
            settings["group_start"]
        )
        await update.message.reply_document(open(out, "rb"))
        os.remove(out)

        merge_data.pop(user_id, None)
        user_state.pop(user_id, None)
        return

    # NORMAL NUMBERS
    numbers = re.findall(r"\d{7,}", text)
    if numbers:
        out = generate_vcf(
            numbers,
            settings["file_name"],
            settings["contact_name"],
            settings["start_index"],
            settings["country_code"],
            settings["group_start"]
        )
        await update.message.reply_document(open(out, "rb"))
        os.remove(out)


# ================= FILE HANDLER =================
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    doc = update.message.document
    path = f"{doc.file_unique_id}_{doc.file_name}"
    await (await context.bot.get_file(doc.file_id)).download_to_drive(path)
    settings = get_user_settings(user_id)
    mode = user_state.get(user_id)

    try:
        if mode == "merge":
            merge_data[user_id].append(path)
            await update.message.reply_text("📥 File added. Aur bhejo ya DONE likho.")
            return

        if mode == "txt2vcf" and path.endswith(".txt"):
            nums = extract_numbers_from_txt(path)
        elif mode == "vcf2txt" and path.endswith(".vcf"):
            nums = extract_numbers_from_vcf(path)
            txt = f"{settings['file_name']}.txt"
            with open(txt, "w") as f:
                f.write("\n".join(nums))
            await update.message.reply_document(open(txt, "rb"))
            os.remove(txt)
            return
        else:
            if path.endswith(".vcf"):
                nums = extract_numbers_from_vcf(path)
            elif path.endswith(".txt"):
                nums = extract_numbers_from_txt(path)
            elif path.endswith(".csv"):
                df = pd.read_csv(path)
                nums = df.iloc[:, 0].astype(str).tolist()
            elif path.endswith(".xlsx"):
                df = pd.read_excel(path)
                nums = df.iloc[:, 0].astype(str).tolist()
            else:
                await update.message.reply_text("❌ Unsupported file")
                return

        out = generate_vcf(
            list(nums),
            settings["file_name"],
            settings["contact_name"],
            settings["start_index"],
            settings["country_code"],
            settings["group_start"]
        )
        await update.message.reply_document(open(out, "rb"))
        os.remove(out)

    finally:
        if os.path.exists(path):
            os.remove(path)


# ================= ERROR =================
async def error_handler(update, context):
    err = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
    with open("bot_errors.log", "a") as f:
        f.write(err)
    try:
        await context.bot.send_message(OWNER_ID, f"⚠️ Bot Error:\n{err[:4000]}")
    except:
        pass


# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_error_handler(error_handler)

    print("🚀 Bot running on Render...")
    app.run_polling()

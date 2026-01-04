import os
import re
import pandas as pd
from datetime import datetime
import traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters
)

# ✅ CONFIGURATION
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOT_USERNAME = os.environ.get("BOT_USERNAME")
OWNER_ID = 7640327597
ALLOWED_USERS = [7856502907,7950732287,8128934569,5849097477,
                 7640327597,7669357884,7118726445,7043391463,8047407478]

def is_authorized(user_id):
    return user_id in ALLOWED_USERS

BOT_START_TIME = datetime.utcnow()

# ✅ DEFAULTS
default_vcf_name = "Contacts"
default_contact_name = "Contact"
default_limit = 100

# ✅ USER SETTINGS
user_file_names = {}
user_contact_names = {}
user_limits = {}
user_start_indexes = {}
user_vcf_start_numbers = {}
user_country_codes = {}
user_group_start_numbers = {}
merge_data = {}
conversion_mode = {}

# ✅ ERROR HANDLER
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error_text = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
    with open("bot_errors.log", "a") as f:
        f.write(f"{datetime.utcnow()} - {error_text}\n\n")
    try:
        await context.bot.send_message(chat_id=OWNER_ID, text=f"⚠️ Bot Error Alert ⚠️\n\n{error_text[:4000]}")
    except Exception:
        pass

# ✅ HELPERS
def generate_vcf(numbers, filename="Contacts", contact_name="Contact", start_index=None, country_code="", group_num=None):
    vcf_data = ""
    for i, num in enumerate(numbers, start=(start_index if start_index else 1)):
        if group_num:
            name = f"{contact_name}{str(i).zfill(3)} (Group {group_num})"
        else:
            name = f"{contact_name}{str(i).zfill(3)}"
        formatted_num = f"{country_code}{num}" if country_code else num
        vcf_data += f"BEGIN:VCARD\nVERSION:3.0\nFN:{name}\nTEL;TYPE=CELL:{formatted_num}\nEND:VCARD\n"
    with open(f"{filename}.vcf", "w") as f:
        f.write(vcf_data)
    return f"{filename}.vcf"

def extract_numbers_from_vcf(file_path):
    numbers = set()
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    for card in content.split('END:VCARD'):
        if 'TEL' in card:
            tel_lines = [line for line in card.splitlines() if line.startswith('TEL')]
            for line in tel_lines:
                number = re.sub(r'[^0-9]', '', line.split(':')[-1].strip())
                if number:
                    numbers.add(number)
    return numbers

def extract_numbers_from_txt(file_path):
    numbers = set()
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            nums = re.findall(r'\d{7,}', line)
            numbers.update(nums)
    return numbers

# ✅ START COMMAND
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    
    if not user_id or not is_authorized(user_id):
        if update.message:
            await update.message.reply_text("❌ Unauthorized. Contact the bot owner.")
        return

    user_name = update.effective_user.first_name
    uptime_duration = datetime.utcnow() - BOT_START_TIME
    days = uptime_duration.days
    hours, rem = divmod(uptime_duration.seconds, 3600)
    minutes, seconds = divmod(rem, 60)

    welcome_text = (
        f"╔═══════════════════════╗\n"
        f"║   🔥 VCF MASTER BOT 🔥   ║\n"
        f"╚═══════════════════════╝\n\n"
        f"👋 Welcome back, {user_name}!\n\n"
        f"⏰ Bot Uptime: {days}d {hours}h {minutes}m\n"
        f"🤖 Status: Online & Ready\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 QUICK ACTIONS\n"
        f"Choose what you want to do:"
    )

    keyboard = [
        [
            InlineKeyboardButton("📥 TXT → VCF", callback_data="txt2vcf"),
            InlineKeyboardButton("📤 VCF → TXT", callback_data="vcf2txt")
        ],
        [
            InlineKeyboardButton("🔗 Merge Files", callback_data="merge"),
            InlineKeyboardButton("⚙️ Settings", callback_data="settings")
        ],
        [
            InlineKeyboardButton("📚 Help Guide", callback_data="help"),
            InlineKeyboardButton("👤 Owner", url="https://madara21566.github.io/GODMADARA-PROFILE/")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup)

# ✅ CALLBACK QUERY HANDLER (FIXED)
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id

    # 🔒 Prevent silent failures
    if not is_authorized(user_id):
        await query.message.reply_text("❌ Unauthorized. Contact the bot owner.")
        return
    
    if query.data == "txt2vcf":
        conversion_mode[user_id] = "txt2vcf"
        await query.message.edit_text(
            "📥 TXT → VCF CONVERTER\n\n"
            "📎 Send me a TXT file containing phone numbers.\n"
            "I'll convert it into a VCF contact file!\n\n"
            "💡 Tip: One number per line works best."
        )
    
    elif query.data == "vcf2txt":
        conversion_mode[user_id] = "vcf2txt"
        await query.message.edit_text(
            "📤 VCF → TXT CONVERTER\n\n"
            "📎 Send me a VCF file.\n"
            "I'll extract all phone numbers into TXT!"
        )
    
    elif query.data == "merge":
        merge_data[user_id] = {"files": [], "filename": "Merged"}
        await query.message.edit_text(
            "🔗 MERGE MODE ACTIVATED\n\n"
            "📁 Send me multiple VCF/TXT files.\n"
            "I'll combine them into one.\n\n"
            "✅ When done, use /done command."
        )
    
    elif query.data == "settings":
        settings_text = (
            "⚙️ YOUR CURRENT SETTINGS\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📂 File Name: {user_file_names.get(user_id, default_vcf_name)}\n"
            f"👤 Contact Name: {user_contact_names.get(user_id, default_contact_name)}\n"
            f"📊 Limit per VCF: {user_limits.get(user_id, default_limit)}\n"
            f"🔢 Start Index: {user_start_indexes.get(user_id, 'Not set')}\n"
            f"📄 VCF Start: {user_vcf_start_numbers.get(user_id, 'Not set')}\n"
            f"🌍 Country Code: {user_country_codes.get(user_id, 'None')}\n"
            f"🔖 Group Start: {user_group_start_numbers.get(user_id, 'Not set')}\n\n"
            "Use commands to modify settings"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Reset All", callback_data="reset_confirm")],
            [InlineKeyboardButton("« Back to Menu", callback_data="back_to_start")]
        ]
        await query.message.edit_text(settings_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "help":
        await query.message.edit_text(
            "📖 COMMAND GUIDE\n\n"
            "Use:\n"
            "/txt2vcf — Convert TXT → VCF\n"
            "/vcf2txt — Convert VCF → TXT\n"
            "/merge — Start file merge\n"
            "/done — Finish merge\n"
            "/mysettings — View settings\n"
            "/reset — Reset settings"
        )
    
    elif query.data == "back_to_start":
        await start(update, context)
    
    elif query.data == "reset_confirm":
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Reset", callback_data="reset_yes"),
                InlineKeyboardButton("❌ Cancel", callback_data="settings")
            ]
        ]
        await query.message.edit_text(
            "⚠️ Confirm reset?\nThis cannot be undone.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == "reset_yes":
        user_file_names.pop(user_id, None)
        user_contact_names.pop(user_id, None)
        user_limits.pop(user_id, None)
        user_start_indexes.pop(user_id, None)
        user_vcf_start_numbers.pop(user_id, None)
        user_country_codes.pop(user_id, None)
        user_group_start_numbers.pop(user_id, None)
        await query.message.edit_text(
            "✅ Settings reset successfully.\nUse /start to continue."
        )

# ✅ TXT2VCF & VCF2TXT COMMANDS
async def txt2vcf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversion_mode[update.effective_user.id] = "txt2vcf"
    if context.args:
        conversion_mode[f"{update.effective_user.id}_name"] = "_".join(context.args)
    await update.message.reply_text(
        "📥 TXT → VCF Mode Enabled\nSend a TXT file now."
    )

async def vcf2txt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversion_mode[update.effective_user.id] = "vcf2txt"
    if context.args:
        conversion_mode[f"{update.effective_user.id}_name"] = "_".join(context.args)
    await update.message.reply_text(
        "📤 VCF → TXT Mode Enabled\nSend a VCF file now."
    )

# ✅ FILE HANDLER
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ You don't have access to use this bot.")
        return

    processing_msg = await update.message.reply_text("⏳ Processing your file...")

    file = update.message.document
    path = f"{file.file_unique_id}_{file.file_name}"
    file_obj = await context.bot.get_file(file.file_id)
    await file_obj.download_to_drive(path)
    user_id = update.effective_user.id

    # Merge mode
    if user_id in merge_data:
        merge_data[user_id]["files"].append(path)
        await processing_msg.edit_text(
            f"✅ File Added\n📁 {file.file_name}\nTotal: {len(merge_data[user_id]['files'])}\n\nSend more or use /done."
        )
        return

    # Conversion modes
    if user_id in conversion_mode:
        mode = conversion_mode[user_id]

        if mode == "txt2vcf" and path.endswith(".txt"):
            numbers = extract_numbers_from_txt(path)
            if numbers:
                filename = conversion_mode.get(f"{user_id}_name", "Converted")
                vcf_path = generate_vcf(list(numbers), filename, "Contact")
                await processing_msg.edit_text("✅ Conversion Successful — Downloading...")
                with open(vcf_path, "rb") as vcf_file:
                    await update.message.reply_document(document=vcf_file)
                os.remove(vcf_path)
            else:
                await processing_msg.edit_text("❌ No valid numbers found.")

        elif mode == "vcf2txt" and path.endswith(".vcf"):
            numbers = extract_numbers_from_vcf(path)
            if numbers:
                filename = conversion_mode.get(f"{user_id}_name", "Converted")
                txt_path = f"{filename}.txt"
                with open(txt_path, "w") as f:
                    f.write("\n".join(numbers))
                await processing_msg.edit_text("✅ Extraction Complete — Downloading...")
                with open(txt_path, "rb") as txt_file:
                    await update.message.reply_document(document=txt_file)
                os.remove(txt_path)
            else:
                await processing_msg.edit_text("❌ No phone numbers found.")

        else:
            await processing_msg.edit_text("❌ Wrong file type for this command.")

        conversion_mode.pop(user_id, None)
        conversion_mode.pop(f"{user_id}_name", None)
        if os.path.exists(path):
            os.remove(path)
        return

    # Normal processing
    try:
        if path.endswith('.csv'):
            df = pd.read_csv(path, encoding='utf-8')
        elif path.endswith('.xlsx'):
            df = pd.read_excel(path)
        elif path.endswith('.txt'):
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            numbers = [''.join(filter(str.isdigit, w)) for w in content.split() if len(w) >= 7]
            df = pd.DataFrame({'Numbers': numbers})
        elif path.endswith('.vcf'):
            numbers = extract_numbers_from_vcf(path)
            df = pd.DataFrame({'Numbers': list(numbers)})
        else:
            await processing_msg.edit_text("❌ Unsupported file type.")
            if os.path.exists(path):
                os.remove(path)
            return
        
        await processing_msg.edit_text("🔄 Generating VCF files...")
        await process_numbers(update, context, df['Numbers'].dropna().astype(str).tolist(), processing_msg)
    except Exception as e:
        await processing_msg.edit_text(f"❌ Error: {str(e)}")
    finally:
        if os.path.exists(path):
            os.remove(path)

# ✅ HANDLE TEXT
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    processing_msg = await update.message.reply_text("🔍 Searching for phone numbers...")
    numbers = [''.join(filter(str.isdigit, w)) for w in update.message.text.split() if len(w) >= 7]
    if numbers:
        await process_numbers(update, context, numbers, processing_msg)
    else:
        await processing_msg.edit_text("❌ No valid phone numbers found.")

# ✅ PROCESS NUMBERS
async def process_numbers(update, context, numbers, status_msg=None):
    user_id = update.effective_user.id
    contact_name = user_contact_names.get(user_id, default_contact_name)
    file_base = user_file_names.get(user_id, default_vcf_name)
    limit = user_limits.get(user_id, default_limit)
    start_index = user_start_indexes.get(user_id, None)
    vcf_num = user_vcf_start_numbers.get(user_id, None)
    country_code = user_country_codes.get(user_id, "")
    custom_group_start = user_group_start_numbers.get(user_id, None)

    numbers = list(dict.fromkeys([n.strip() for n in numbers if n.strip().isdigit()]))
    chunks = [numbers[i:i+limit] for i in range(0, len(numbers), limit)]
    
    if status_msg:
        await status_msg.edit_text(
            f"✅ Processing Complete\n📱 Total: {len(numbers)}\n📦 Files: {len(chunks)}\n⬇️ Sending files..."
        )

    for idx, chunk in enumerate(chunks):
        group_num = (custom_group_start + idx) if custom_group_start else None
        file_suffix = f"{vcf_num+idx}" if vcf_num else f"{idx+1}"
        file_path = generate_vcf(
            chunk,
            f"{file_base}_{file_suffix}",
            contact_name,
            (start_index + idx*limit) if start_index else None,
            country_code,
            group_num
        )
        caption = f"📁 File {idx+1}/{len(chunks)} | 📱 {len(chunk)} contacts"
        with open(file_path, "rb") as vcf_file:
            await update.message.reply_document(document=vcf_file, caption=caption)
        os.remove(file_path)
    
    await update.message.reply_text(
        f"🎉 Done\nGenerated {len(chunks)} VCF file(s)\nUse /start for more options."
    )

# ✅ SETTINGS COMMANDS
async def set_filename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        filename = ' '.join(context.args)
        user_file_names[update.effective_user.id] = filename
        await update.message.reply_text(f"✅ File name updated: {filename}")
    else:
        await update.message.reply_text("❌ Usage: /setfilename NAME")

async def set_contact_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        contact_name = ' '.join(context.args)
        user_contact_names[update.effective_user.id] = contact_name
        await update.message.reply_text(f"✅ Contact name updated: {contact_name}")
    else:
        await update.message.reply_text("❌ Usage: /setcontactname NAME")

async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].isdigit():
        user_limits[update.effective_user.id] = int(context.args[0])
        await update.message.reply_text("✅ Limit updated")
    else:
        await update.message.reply_text("❌ Usage: /setlimit NUMBER")

async def set_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].isdigit():
        user_start_indexes[update.effective_user.id] = int(context.args[0])
        await update.message.reply_text("✅ Start index updated")
    else:
        await update.message.reply_text("❌ Usage: /setstart NUMBER")

async def set_vcf_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].isdigit():
        user_vcf_start_numbers[update.effective_user.id] = int(context.args[0])
        await update.message.reply_text("✅ VCF start number updated")
    else:
        await update.message.reply_text("❌ Usage: /setvcfstart NUMBER")

async def set_country_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        user_country_codes[update.effective_user.id] = context.args[0]
        await update.message.reply_text("✅ Country code set")
    else:
        await update.message.reply_text("❌ Usage: /setcountrycode +91")

async def set_group_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].isdigit():
        user_group_start_numbers[update.effective_user.id] = int(context.args[0])
        await update.message.reply_text("✅ Group number set")
    else:
        await update.message.reply_text("❌ Usage: /setgroup NUMBER")

async def reset_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_file_names.pop(user_id, None)
    user_contact_names.pop(user_id, None)
    user_limits.pop(user_id, None)
    user_start_indexes.pop(user_id, None)
    user_vcf_start_numbers.pop(user_id, None)
    user_country_codes.pop(user_id, None)
    user_group_start_numbers.pop(user_id, None)
    await update.message.reply_text("✅ All settings reset")

async def my_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"⚙️ SETTINGS\n\n"
        f"File: {user_file_names.get(user_id, default_vcf_name)}\n"
        f"Contact: {user_contact_names.get(user_id, default_contact_name)}\n"
        f"Limit: {user_limits.get(user_id, default_limit)}"
    )

# ✅ MERGE COMMANDS
async def merge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    merge_data[user_id] = {"files": [], "filename": "Merged"}
    if context.args:
        merge_data[user_id]["filename"] = "_".join(context.args)
    await update.message.reply_text(
        f"🔗 MERGE MODE ENABLED\nSend files now.\nOutput: {merge_data[user_id]['filename']}.vcf\nUse /done when finished."
    )

async def done_merge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in merge_data or not merge_data[user_id]["files"]:
        await update.message.reply_text("❌ No files added. Use /merge first.")
        return

    processing_msg = await update.message.reply_text("🔄 Merging files...")

    all_numbers = set()
    for file_path in merge_data[user_id]["files"]:
        if file_path.endswith(".vcf"):
            all_numbers.update(extract_numbers_from_vcf(file_path))
        elif file_path.endswith(".txt"):
            all_numbers.update(extract_numbers_from_txt(file_path))

    filename = merge_data[user_id]["filename"]
    vcf_path = generate_vcf(list(all_numbers), filename)
    
    await processing_msg.edit_text("✅ Merge complete — downloading...")
    with open(vcf_path, "rb") as vcf_file:
        await update.message.reply_document(document=vcf_file)
    os.remove(vcf_path)

    for file_path in merge_data[user_id]["files"]:
        if os.path.exists(file_path):
            os.remove(file_path)
    merge_data.pop(user_id, None)

# ✅ MAIN
if __name__ == "__main__":
    application = Application.builder().token(BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setfilename", set_filename))
    application.add_handler(CommandHandler("setcontactname", set_contact_name))
    application.add_handler(CommandHandler("setlimit", set_limit))
    application.add_handler(CommandHandler("setstart", set_start))
    application.add_handler(CommandHandler("setvcfstart", set_vcf_start))
    application.add_handler(CommandHandler("setcountrycode", set_country_code))
    application.add_handler(CommandHandler("setgroup", set_group_number))
    application.add_handler(CommandHandler("reset", reset_settings))
    application.add_handler(CommandHandler("mysettings", my_settings))
    application.add_handler(CommandHandler("makevcf", None))
    application.add_handler(CommandHandler("merge", merge_command))
    application.add_handler(CommandHandler("done", done_merge))
    application.add_handler(CommandHandler("txt2vcf", txt2vcf))
    application.add_handler(CommandHandler("vcf2txt", vcf2txt))

    # Callback Query Handler
    application.add_handler(CallbackQueryHandler(button_callback))

    # Message Handlers
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Error Handler
    application.add_error_handler(error_handler)

    print("🚀 VCF Master Bot is running...")
    application.run_polling()

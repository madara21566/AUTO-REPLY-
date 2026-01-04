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
    ContextTypes,
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

# ✅ ENHANCED START COMMAND WITH BEAUTIFUL UI
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
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
        f"👋 Welcome back, *{user_name}*!\n\n"
        f"⏰ *Bot Uptime:* `{days}d {hours}h {minutes}m`\n"
        f"🤖 *Status:* ✅ Online & Ready\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 *QUICK ACTIONS*\n"
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

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

# ✅ HELP COMMAND WITH BETTER FORMATTING
async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *COMPLETE COMMAND GUIDE*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        "🎨 *CUSTOMIZATION COMMANDS*\n"
        "├ `/setfilename` `[NAME]`\n"
        "│  └ Set output VCF file name\n"
        "│\n"
        "├ `/setcontactname` `[NAME]`\n"
        "│  └ Set contact prefix name\n"
        "│\n"
        "├ `/setlimit` `[NUMBER]`\n"
        "│  └ Contacts per VCF file\n"
        "│\n"
        "├ `/setstart` `[NUMBER]`\n"
        "│  └ Start contact numbering from\n"
        "│\n"
        "├ `/setvcfstart` `[NUMBER]`\n"
        "│  └ Start VCF file numbering from\n"
        "│\n"
        "├ `/setcountrycode` `[+91]`\n"
        "│  └ Add country code to numbers\n"
        "│\n"
        "└ `/setgroup` `[NUMBER]`\n"
        "   └ Add group number to contacts\n\n"
        
        "🔄 *CONVERSION COMMANDS*\n"
        "├ `/txt2vcf` - Convert TXT → VCF\n"
        "├ `/vcf2txt` - Convert VCF → TXT\n"
        "└ `/makevcf` `[Name] [Numbers...]`\n\n"
        
        "🔗 *MERGE COMMANDS*\n"
        "├ `/merge` `[OUTPUT_NAME]`\n"
        "│  └ Start merge mode\n"
        "└ `/done` - Finish merging files\n\n"
        
        "⚙️ *SETTINGS*\n"
        "├ `/mysettings` - View current settings\n"
        "└ `/reset` - Reset all to default\n\n"
        
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *TIP:* Just send files directly!\n"
        "Supported: TXT, CSV, XLSX, VCF"
    )
    
    keyboard = [[InlineKeyboardButton("« Back to Menu", callback_data="back_to_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode="Markdown")

# ✅ SETTINGS MENU
async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    settings_text = (
        "⚙️ *YOUR CURRENT SETTINGS*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📂 *File Name:* `{user_file_names.get(user_id, default_vcf_name)}`\n"
        f"👤 *Contact Name:* `{user_contact_names.get(user_id, default_contact_name)}`\n"
        f"📊 *Limit per VCF:* `{user_limits.get(user_id, default_limit)}`\n"
        f"🔢 *Start Index:* `{user_start_indexes.get(user_id, 'Not set')}`\n"
        f"📄 *VCF Start:* `{user_vcf_start_numbers.get(user_id, 'Not set')}`\n"
        f"🌍 *Country Code:* `{user_country_codes.get(user_id, 'None')}`\n"
        f"🔖 *Group Start:* `{user_group_start_numbers.get(user_id, 'Not set')}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Use commands to modify settings"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Reset All", callback_data="reset_confirm")],
        [InlineKeyboardButton("« Back to Menu", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(settings_text, reply_markup=reply_markup, parse_mode="Markdown")

# ✅ CALLBACK QUERY HANDLER
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    if query.data == "txt2vcf":
        await query.answer()
        conversion_mode[query.from_user.id] = "txt2vcf"
        await query.edit_message_text(
            "📥 *TXT → VCF CONVERTER*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📎 Send me a TXT file containing phone numbers.\n"
            "I'll convert it into a VCF contact file!\n\n"
            "💡 *Tip:* One number per line works best.",
            parse_mode="Markdown"
        )
    
    elif query.data == "vcf2txt":
        await query.answer()
        conversion_mode[query.from_user.id] = "vcf2txt"
        await query.edit_message_text(
            "📤 *VCF → TXT CONVERTER*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📎 Send me a VCF file.\n"
            "I'll extract all phone numbers into TXT!\n\n"
            "⚡ Fast & accurate extraction.",
            parse_mode="Markdown"
        )
    
    elif query.data == "merge":
        await query.answer()
        user_id = query.from_user.id
        merge_data[user_id] = {"files": [], "filename": "Merged"}
        await query.edit_message_text(
            "🔗 *MERGE MODE ACTIVATED*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📁 Send me multiple VCF/TXT files.\n"
            "I'll combine them into one!\n\n"
            "✅ When done, use `/done` command.\n\n"
            "💾 Output: `Merged.vcf`",
            parse_mode="Markdown"
        )
    
    elif query.data == "settings":
        await show_settings_menu(update, context)
    
    elif query.data == "help":
        await show_help(update, context)
    
    elif query.data == "back_to_start":
        await start(update, context)
    
    elif query.data == "reset_confirm":
        await query.answer()
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Reset", callback_data="reset_yes"),
                InlineKeyboardButton("❌ Cancel", callback_data="settings")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⚠️ *CONFIRM RESET*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Are you sure you want to reset all settings to default?\n\n"
            "This action cannot be undone.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    elif query.data == "reset_yes":
        await query.answer()
        user_id = query.from_user.id
        user_file_names.pop(user_id, None)
        user_contact_names.pop(user_id, None)
        user_limits.pop(user_id, None)
        user_start_indexes.pop(user_id, None)
        user_vcf_start_numbers.pop(user_id, None)
        user_country_codes.pop(user_id, None)
        user_group_start_numbers.pop(user_id, None)
        await query.edit_message_text(
            "✅ *SETTINGS RESET SUCCESSFUL*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "All settings have been restored to defaults!\n\n"
            "Use /start to continue.",
            parse_mode="Markdown"
        )

# ✅ TXT2VCF & VCF2TXT
async def txt2vcf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversion_mode[update.effective_user.id] = "txt2vcf"
    if context.args:
        conversion_mode[f"{update.effective_user.id}_name"] = "_".join(context.args)
    
    await update.message.reply_text(
        "📥 *TXT → VCF CONVERTER*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📎 Send me a TXT file with phone numbers.\n\n"
        "✨ Processing will start automatically!",
        parse_mode="Markdown"
    )

async def vcf2txt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversion_mode[update.effective_user.id] = "vcf2txt"
    if context.args:
        conversion_mode[f"{update.effective_user.id}_name"] = "_".join(context.args)
    
    await update.message.reply_text(
        "📤 *VCF → TXT CONVERTER*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📎 Send me a VCF file.\n\n"
        "⚡ Extraction will begin immediately!",
        parse_mode="Markdown"
    )

# ✅ FILE HANDLER WITH BETTER MESSAGES
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ You don't have access to use this bot.")
        return

    # Show processing message
    processing_msg = await update.message.reply_text(
        "⏳ *Processing your file...*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📊 Analyzing data...",
        parse_mode="Markdown"
    )

    file = update.message.document
    path = f"{file.file_unique_id}_{file.file_name}"
    await (await context.bot.get_file(file.file_id)).download_to_drive(path)
    user_id = update.effective_user.id

    # Merge mode
    if user_id in merge_data:
        merge_data[user_id]["files"].append(path)
        await processing_msg.edit_text(
            f"✅ *File Added to Merge Queue*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📁 File: `{file.file_name}`\n"
            f"📦 Total files: `{len(merge_data[user_id]['files'])}`\n\n"
            f"➕ Send more files or use `/done` to merge.",
            parse_mode="Markdown"
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
                
                await processing_msg.edit_text(
                    f"✅ *Conversion Successful!*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📱 Total contacts: `{len(numbers)}`\n"
                    f"📄 File: `{filename}.vcf`\n\n"
                    f"⬇️ Downloading...",
                    parse_mode="Markdown"
                )
                
                await update.message.reply_document(document=open(vcf_path, "rb"))
                os.remove(vcf_path)
            else:
                await processing_msg.edit_text("❌ No valid phone numbers found in the file.")

        elif mode == "vcf2txt" and path.endswith(".vcf"):
            numbers = extract_numbers_from_vcf(path)
            if numbers:
                filename = conversion_mode.get(f"{user_id}_name", "Converted")
                txt_path = f"{filename}.txt"
                with open(txt_path, "w") as f:
                    f.write("\n".join(numbers))
                
                await processing_msg.edit_text(
                    f"✅ *Extraction Successful!*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📱 Total numbers: `{len(numbers)}`\n"
                    f"📄 File: `{filename}.txt`\n\n"
                    f"⬇️ Downloading...",
                    parse_mode="Markdown"
                )
                
                await update.message.reply_document(document=open(txt_path, "rb"))
                os.remove(txt_path)
            else:
                await processing_msg.edit_text("❌ No phone numbers found in the VCF file.")

        else:
            await processing_msg.edit_text("❌ Wrong file type for this command.")

        conversion_mode.pop(user_id, None)
        conversion_mode.pop(f"{user_id}_name", None)
        if os.path.exists(path):
            os.remove(path)
        return

    # Normal file handling
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
            return
        
        await processing_msg.edit_text(
            "🔄 *Generating VCF files...*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⏳ Please wait...",
            parse_mode="Markdown"
        )
        
        await process_numbers(update, context, df['Numbers'].dropna().astype(str).tolist(), processing_msg)
    except Exception as e:
        await processing_msg.edit_text(f"❌ Error processing file: {str(e)}")
    finally:
        if os.path.exists(path):
            os.remove(path)

# ✅ HANDLE TEXT
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    
    processing_msg = await update.message.reply_text(
        "🔍 *Searching for phone numbers...*",
        parse_mode="Markdown"
    )
    
    numbers = [''.join(filter(str.isdigit, w)) for w in update.message.text.split() if len(w) >=7]
    if numbers:
        await process_numbers(update, context, numbers, processing_msg)
    else:
        await processing_msg.edit_text("❌ No valid phone numbers found.")

# ✅ PROCESS NUMBERS WITH BETTER FEEDBACK
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
            f"✅ *Processing Complete!*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📱 Total contacts: `{len(numbers)}`\n"
            f"📦 VCF files: `{len(chunks)}`\n"
            f"📄 Contacts per file: `{limit}`\n\n"
            f"⬇️ Sending files...",
            parse_mode="Markdown"
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
        await update.message.reply_document(
            document=open(file_path, "rb"),
            caption=caption
        )
        os.remove(file_path)
    
    # Final success message
    await update.message.reply_text(
        f"🎉 *All Done!*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ Successfully generated {len(chunks)} VCF file(s)\n"
        f"📱 Total contacts: {len(numbers)}\n\n"
        f"💡 Use /start for more options!",
        parse_mode="Markdown"
    )

# ✅ SETTINGS COMMANDS WITH BETTER FEEDBACK
async def set_filename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        filename = ' '.join(context.args)
        user_file_names[update.effective_user.id] = filename
        await update.message.reply_text(
            f"✅ *File Name Updated*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📂 New name: `{filename}`\n\n"
            f"This will be used for all future VCF files.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Usage: `/setfilename [NAME]`", parse_mode="Markdown")

async def set_contact_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        contact_name = ' '.join(context.args)
        user_contact_names[update.effective_user.id] = contact_name
        await update.message.reply_text(
            f"✅ *Contact Name Updated*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 New prefix: `{contact_name}`\n\n"
            f"Example: `{contact_name}001`, `{contact_name}002`, etc.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Usage: `/setcontactname [NAME]`", parse_mode="Markdown")

async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].isdigit():
        limit = int(context.args[0])
        user_limits[update.effective_user.id] = limit
        await update.message.reply_text(
            f"✅ *Limit Updated*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 Contacts per VCF: `{limit}`\n\n"
            f"Files will be split automatically.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Usage: `/setlimit [NUMBER]`", parse_mode="Markdown")

async def set_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].isdigit():
        start = int(context.args[0])
        user_start_indexes[update.effective_user.id] = start
        await update.message.reply_text(
            f"✅ *Start Index Updated*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔢 Starting from: `{start}`\n\n"
            f"Contact numbering will begin at {start}.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Usage: `/setstart [NUMBER]`", parse_mode="Markdown")

async def set_vcf_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].isdigit():
        vcf_start = int(context.args[0])
        user_vcf_start_numbers[update.effective_user.id] = vcf_start
        await update.message.reply_text(
            f"✅ *VCF Numbering Updated*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📄 Starting from: `{vcf_start}`\n\n"
            f"VCF files will be numbered from {vcf_start}.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Usage: `/setvcfstart [NUMBER]`", parse_mode="Markdown")

async def set_country_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        code = context.args[0]
        user_country_codes[update.effective_user.id] = code
        await update.message.reply_text(
            f"✅ *Country Code Set*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🌍 Code: `{code}`\n\n"
            f"All numbers will be prefixed with {code}.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Usage: `/setcountrycode [+91]`", parse_mode="Markdown")

async def set_group_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].isdigit():
        group_start = int(context.args[0])
        user_group_start_numbers[update.effective_user.id] = group_start
        await update.message.reply_text(
            f"✅ *Group Number Set*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔖 Starting from: `{group_start}`\n\n"
            f"Groups will be numbered from {group_start}.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Usage: `/setgroup [NUMBER]`", parse_mode="Markdown")

async def reset_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_file_names.pop(user_id, None)
    user_contact_names.pop(user_id, None)
    user_limits.pop(user_id, None)
    user_start_indexes.pop(user_id, None)
    user_vcf_start_numbers.pop(user_id, None)
    user_country_codes.pop(user_id, None)
    user_group_start_numbers.pop(user_id, None)
    await update.message.reply_text(
        "✅ *All Settings Reset*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔄 Everything is back to default!\n\n"
        "Use /mysettings to view defaults.",
        parse_mode="Markdown"
    )

async def my_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    settings = (
        "⚙️ *YOUR CURRENT SETTINGS*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📂 *File name:* `{user_file_names.get(user_id, default_vcf_name)}`\n"
        f"👤 *Contact name:* `{user_contact_names.get(user_id, default_contact_name)}`\n"
        f"📊 *Limit:* `{user_limits.get(user_id, default_limit)}`\n"
        f"🔢 *Start index:* `{user_start_indexes.get(user_id, 'Not set')}`\n"
        f"📄 *VCF start:* `{user_vcf_start_numbers.get(user_id, 'Not set')}`\n"
        f"🌍 *Country code:* `{user_country_codes.get(user_id, 'None')}`\n"
        f"🔖 *Group start:* `{user_group_start_numbers.get(user_id, 'Not set')}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 Use /reset to restore defaults"
    )
    await update.message.reply_text(settings, parse_mode="Markdown")

async def make_vcf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ *Invalid Usage*\n\n"
            "📝 Correct format:\n"
            "`/makevcf Name 1234567890 9876543210`",
            parse_mode="Markdown"
        )
        return
    
    contact_name = context.args[0]
    numbers = context.args[1:]
    
    file_path = generate_vcf(numbers, contact_name, contact_name)
    
    await update.message.reply_text(
        f"✅ *VCF Created!*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📱 Contacts: `{len(numbers)}`\n"
        f"📄 Name: `{contact_name}.vcf`",
        parse_mode="Markdown"
    )
    
    await update.message.reply_document(document=open(file_path, "rb"))
    os.remove(file_path)

async def merge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    merge_data[user_id] = {"files": [], "filename": "Merged"}
    if context.args:
        merge_data[user_id]["filename"] = "_".join(context.args)
    
    await update.message.reply_text(
        f"🔗 *MERGE MODE ACTIVATED*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📁 Send me VCF/TXT files to merge\n"
        f"📦 Output: `{merge_data[user_id]['filename']}.vcf`\n\n"
        f"✅ Use `/done` when finished",
        parse_mode="Markdown"
    )

async def done_merge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in merge_data or not merge_data[user_id]["files"]:
        await update.message.reply_text("❌ No files queued for merge.")
        return

    processing_msg = await update.message.reply_text(
        "🔄 *Merging files...*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⏳ Please wait...",
        parse_mode="Markdown"
    )

    all_numbers = set()
    for file_path in merge_data[user_id]["files"]:
        if file_path.endswith(".vcf"):
            all_numbers.update(extract_numbers_from_vcf(file_path))
        elif file_path.endswith(".txt"):
            all_numbers.update(extract_numbers_from_txt(file_path))

    filename = merge_data[user_id]["filename"]
    vcf_path = generate_vcf(list(all_numbers), filename)
    
    await processing_msg.edit_text(
        f"✅ *Merge Complete!*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📁 Files merged: `{len(merge_data[user_id]['files'])}`\n"
        f"📱 Total contacts: `{len(all_numbers)}`\n"
        f"📄 Output: `{filename}.vcf`\n\n"
        f"⬇️ Sending file...",
        parse_mode="Markdown"
    )
    
    await update.message.reply_document(document=open(vcf_path, "rb"))
    os.remove(vcf_path)

    for file_path in merge_data[user_id]["files"]:
        if os.path.exists(file_path):
            os.remove(file_path)
    merge_data.pop(user_id, None)

if __name__ == "__main__":
    from telegram.ext import CallbackQueryHandler
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setfilename", set_filename))
    app.add_handler(CommandHandler("setcontactname", set_contact_name))
    app.add_handler(CommandHandler("setlimit", set_limit))
    app.add_handler(CommandHandler("setstart", set_start))
    app.add_handler(CommandHandler("setvcfstart", set_vcf_start))
    app.add_handler(CommandHandler("setcountrycode", set_country_code))
    app.add_handler(CommandHandler("setgroup", set_group_number))
    app.add_handler(CommandHandler("reset", reset_settings))
    app.add_handler(CommandHandler("mysettings", my_settings))
    app.add_handler(CommandHandler("makevcf", make_vcf_command))
    app.add_handler(CommandHandler("merge", merge_command))
    app.add_handler(CommandHandler("done", done_merge))
    app.add_handler(CommandHandler("txt2vcf", txt2vcf))
    app.add_handler(CommandHandler("vcf2txt", vcf2txt))

    # Callback buttons
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Handlers
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    print("🚀 Bot is running...")
    app.run_polling()

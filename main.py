import os, threading, datetime
import psycopg2
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

# ===== IMPORT ORIGINAL BOT =====
import bot_core

# ================= CONFIGURATION =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
DATABASE_URL = os.environ.get("DATABASE_URL")
PORT = int(os.environ.get("PORT", "10000"))

# 👇 APNE CHANNEL IDs YAHAN DAALO (Ex: -100123456789)
CHANNEL_1_ID = -100123456789  # Replace this
CHANNEL_2_ID = -100987654321  # Replace this
CHANNEL_1_LINK = "https://t.me/YourChannel1"
CHANNEL_2_LINK = "https://t.me/YourChannel2"

# ================= DATABASE =================
conn = psycopg2.connect(DATABASE_URL, sslmode="require")
conn.autocommit = True

def init_db():
    with conn.cursor() as cur:
        # Schema: user_id, expiry_date (NULL means Permanent)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS allowed_users (
            user_id BIGINT PRIMARY KEY,
            expiry_date TIMESTAMP, 
            joined_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

def check_access(uid: int):
    """
    Returns: 'allowed', 'expired', 'new'
    """
    if uid == OWNER_ID: return 'allowed'
    
    with conn.cursor() as cur:
        cur.execute("SELECT expiry_date FROM allowed_users WHERE user_id=%s", (uid,))
        res = cur.fetchone()
        
        if res is None:
            return 'new'
            
        expiry = res[0]
        if expiry is None:
            return 'allowed' # Permanent
            
        if datetime.datetime.now() < expiry:
            return 'allowed' # Valid Trial
        else:
            return 'expired' # Date passed

def db_add_user(uid: int, days=None):
    """
    days=None -> Permanent
    days=1 -> 24 Hours
    """
    expiry = None
    if days:
        expiry = datetime.datetime.now() + datetime.timedelta(days=days)
        
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO allowed_users (user_id, expiry_date) 
            VALUES (%s, %s) 
            ON CONFLICT (user_id) 
            DO UPDATE SET expiry_date = EXCLUDED.expiry_date
        """, (uid, expiry))

def db_remove_user(uid: int):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM allowed_users WHERE user_id=%s", (uid,))

def db_stats():
    with conn.cursor() as cur:
        now = datetime.datetime.now()
        cur.execute("SELECT COUNT(*) FROM allowed_users WHERE expiry_date IS NULL OR expiry_date > %s", (now,))
        active = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM allowed_users WHERE expiry_date < %s", (now,))
        expired = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM allowed_users")
        total = cur.fetchone()[0]
        
        return total, active, expired

def db_get_list(filter_type):
    """
    filter_type: 'active' or 'expired' or 'all'
    """
    with conn.cursor() as cur:
        now = datetime.datetime.now()
        if filter_type == 'active':
            cur.execute("SELECT user_id FROM allowed_users WHERE expiry_date IS NULL OR expiry_date > %s", (now,))
        elif filter_type == 'expired':
            cur.execute("SELECT user_id FROM allowed_users WHERE expiry_date < %s", (now,))
        else:
            cur.execute("SELECT user_id FROM allowed_users")
            
        return [r[0] for r in cur.fetchall()]

# ================= HELPER: CHANNEL CHECK =================
async def check_membership(user_id, context):
    try:
        # Check Channel 1
        chat1 = await context.bot.get_chat_member(CHANNEL_1_ID, user_id)
        if chat1.status in ['left', 'kicked']: return False
        
        # Check Channel 2
        chat2 = await context.bot.get_chat_member(CHANNEL_2_ID, user_id)
        if chat2.status in ['left', 'kicked']: return False
        
        return True
    except Exception as e:
        print(f"⚠️ Admin check error (Make bot admin in channels): {e}")
        return True # Fallback if ID is wrong, to avoid blocking users completely (Change to False for strict mode)

# ================= ADMIN UI =================
def admin_menu():
    total, active, expired = db_stats()
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📊 Total: {total}", callback_data="noop"), 
         InlineKeyboardButton(f"🟢 Active: {active}", callback_data="noop")],
        [InlineKeyboardButton(f"🔴 Expired: {expired}", callback_data="noop")],
        [InlineKeyboardButton("➕ Add Permanent", callback_data="adm_add_perm"), 
         InlineKeyboardButton("⏳ Give Temp Access", callback_data="adm_add_temp")],
        [InlineKeyboardButton("➖ Remove User", callback_data="adm_remove")],
        [InlineKeyboardButton("📜 List Active", callback_data="adm_list_active"), 
         InlineKeyboardButton("🗑 List Expired", callback_data="adm_list_expired")],
        [InlineKeyboardButton("⬅ Close Panel", callback_data="adm_close")]
    ])

admin_state = {}

# ================= HANDLERS =================

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    status = check_access(uid)

    # 🟢 1. IF ALLOWED -> GO TO BOT
    if status == 'allowed':
        if uid == OWNER_ID:
            await update.message.reply_text("👑 **Owner Menu**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔐 Admin Panel", callback_data="open_admin")]]), parse_mode=ParseMode.MARKDOWN)
        return await bot_core.start(update, ctx)

    # 🔴 2. IF EXPIRED -> SHOW PREMIUM MSG
    if status == 'expired':
        contact_kb = InlineKeyboardMarkup([[InlineKeyboardButton("👨‍💻 Contact Owner", url="https://t.me/MADARAXHEREE")]])
        return await update.message.reply_text(
            "🚫 **Trial Expired!**\n\n"
            "Your 24-hour free trial has ended.\n"
            "To continue using the **Premium VCF Tools**, please purchase a plan.\n\n"
            "💎 **Premium Benefits:**\n"
            "• Unlimited Conversions\n"
            "• High Speed Processing\n"
            "• 24/7 Support",
            reply_markup=contact_kb,
            parse_mode=ParseMode.MARKDOWN
        )

    # ⚪ 3. IF NEW USER -> FORCE JOIN CHANNELS
    join_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel 1", url=CHANNEL_1_LINK)],
        [InlineKeyboardButton("📢 Join Channel 2", url=CHANNEL_2_LINK)],
        [InlineKeyboardButton("✅ Verify & Start Trial", callback_data="verify_join")]
    ])
    
    await update.message.reply_text(
        "👋 **Welcome to Ultimate VCF Bot**\n\n"
        "To get your **Free 24-Hour Trial**, you must join our update channels first.\n\n"
        "👇 **Step 1: Join these channels:**",
        reply_markup=join_kb,
        parse_mode=ParseMode.MARKDOWN
    )

async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()

    # --- VERIFY JOIN LOGIC ---
    if q.data == "verify_join":
        is_member = await check_membership(uid, ctx)
        
        if is_member:
            # Grant 24 Hours (1 Day)
            db_add_user(uid, days=1)
            
            await q.message.edit_text(
                "🎉 **Congratulations!**\n\n"
                "✅ Verification Successful.\n"
                "🎁 **You have received 24 Hours Free Access!**\n\n"
                "👇 Click below to start using the tools.",
                parse_mode=ParseMode.MARKDOWN
            )
            # Send /start command hint
            await ctx.bot.send_message(uid, "🚀 **Your Trial is Active!**\nType /start to begin.")
        else:
            await q.answer("❌ You haven't joined both channels yet!", show_alert=True)
        return

    # --- ADMIN PANEL ---
    if q.data == "open_admin" and uid == OWNER_ID:
        return await q.message.edit_text("🎛 **Admin Control Panel**", reply_markup=admin_menu(), parse_mode=ParseMode.MARKDOWN)
    
    if q.data == "adm_close" and uid == OWNER_ID:
        return await q.message.delete()

    if uid == OWNER_ID and q.data.startswith("adm_"):
        action = q.data
        
        if action == "adm_add_perm":
            admin_state[uid] = "add_perm"
            await q.message.reply_text("✍️ Send User ID to give **Permanent Access**:", parse_mode=ParseMode.MARKDOWN)
            
        elif action == "adm_add_temp":
            admin_state[uid] = "add_temp_id"
            await q.message.reply_text("✍️ Send User ID for **Temporary Access**:", parse_mode=ParseMode.MARKDOWN)
            
        elif action == "adm_remove":
            admin_state[uid] = "remove"
            await q.message.reply_text("✍️ Send User ID to **REMOVE**:", parse_mode=ParseMode.MARKDOWN)
            
        elif action in ["adm_list_active", "adm_list_expired"]:
            l_type = "active" if "active" in action else "expired"
            users = db_get_list(l_type)
            header = "🟢 **Active Users**" if l_type == "active" else "🔴 **Expired Users**"
            
            text = f"{header} ({len(users)}):\n" + "\n".join([f"`{u}`" for u in users])
            if len(text) > 4000:
                with open("list.txt", "w") as f: f.write("\n".join(map(str, users)))
                await q.message.reply_document(open("list.txt", "rb"), caption=header)
                os.remove("list.txt")
            else:
                await q.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return

    # --- IF EXPIRED/NEW USER CLICKS OTHER BUTTONS ---
    status = check_access(uid)
    if status != 'allowed':
        return await q.answer("⛔ Access Denied or Expired", show_alert=True)

    # ✅ PASS TO ORIGINAL BOT
    return await bot_core.buttons(update, ctx)

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    txt = update.message.text.strip()

    # --- ADMIN INPUT HANDLING ---
    if uid == OWNER_ID and admin_state.get(uid):
        state = admin_state[uid]
        
        # 1. Permanent Add
        if state == "add_perm":
            if txt.isdigit():
                db_add_user(int(txt), days=None)
                await update.message.reply_text(f"✅ User `{txt}` added permanently.", reply_markup=admin_menu(), parse_mode=ParseMode.MARKDOWN)
                admin_state.pop(uid)
            else:
                await update.message.reply_text("❌ Invalid ID.")

        # 2. Temp Access - Step 1: Get ID
        elif state == "add_temp_id":
            if txt.isdigit():
                admin_state[uid] = f"add_temp_days_{txt}" # Store ID in state
                await update.message.reply_text(f"⏳ How many **Days** for User `{txt}`?\n(Send number, e.g. 7)", parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text("❌ Invalid ID.")

        # 3. Temp Access - Step 2: Get Days
        elif state.startswith("add_temp_days_"):
            target_id = int(state.split("_")[-1])
            if txt.isdigit():
                days = int(txt)
                db_add_user(target_id, days=days)
                await update.message.reply_text(f"✅ User `{target_id}` given access for **{days} Days**.", reply_markup=admin_menu(), parse_mode=ParseMode.MARKDOWN)
                admin_state.pop(uid)
            else:
                await update.message.reply_text("❌ Please send a number.")

        # 4. Remove
        elif state == "remove":
            if txt.isdigit():
                db_remove_user(int(txt))
                await update.message.reply_text(f"🗑 User `{txt}` removed.", reply_markup=admin_menu(), parse_mode=ParseMode.MARKDOWN)
                admin_state.pop(uid)
            else:
                await update.message.reply_text("❌ Invalid ID.")
                
        return

    # --- GENERAL CHECK ---
    if check_access(uid) == 'allowed':
        return await bot_core.handle_text(update, ctx)

async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if check_access(uid) == 'allowed':
        return await bot_core.handle_file(update, ctx)

# ================= FLASK SERVER =================
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is Running"

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

# ================= MAIN EXECUTION =================
if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("🚀 Premium Bot with 24h Trial Started!")
    app.run_polling()

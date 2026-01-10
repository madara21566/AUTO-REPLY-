import os, re, threading, traceback
import pandas as pd
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ================== RENDER FREE KEEP ALIVE ==================
web = Flask(__name__)

@web.route("/")
def home():
    return "VCF Bot running 24/7 🚀"

def run_web():
    web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

threading.Thread(target=run_web, daemon=True).start()

# ================== CONFIG ==================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 7640327597

ALLOWED_USERS = {
    7856502907,7950732287,8128934569,5849097477,
    7640327597,7669357884,7118726445,7043391463,8047407478
}

# ================== DEFAULT SETTINGS ==================
DEFAULT_SETTINGS = {
    "file_name": "Contacts",
    "contact_name": "Contact",
    "limit": 100,
    "start_index": None,
    "vcf_start": None,
    "country_code": None,
    "group_start": None,
}

user_settings = {}
user_state = {}   # {mode, step}
merge_files = {}

# ================== HELPERS ==================
def auth(uid): 
    return uid in ALLOWED_USERS

def settings(uid):
    if uid not in user_settings:
        user_settings[uid] = DEFAULT_SETTINGS.copy()
    return user_settings[uid]

def state(uid):
    if uid not in user_state:
        user_state[uid] = {"mode": None, "step": None}
    return user_state[uid]

def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def extract_vcf(path):
    s=set()
    with open(path,"r",errors="ignore") as f:
        for l in f:
            if l.startswith("TEL"):
                n=re.sub(r"\D","",l)
                if len(n)>=7: s.add(n)
    return s

def extract_txt(path):
    s=set()
    with open(path,"r",errors="ignore") as f:
        for l in f:
            s.update(re.findall(r"\d{7,}",l))
    return s

def make_vcf(nums, cfg, idx):
    start = cfg["start_index"] if cfg["start_index"] is not None else 1
    start = start + idx*cfg["limit"]
    group = cfg["group_start"]
    out=""
    for i,n in enumerate(nums, start=start):
        name=f"{cfg['contact_name']}{str(i).zfill(3)}"
        if group is not None:
            name+=f" (Group {group+idx})"
        num=f"{cfg['country_code']}{n}" if cfg["country_code"] else n
        out+=f"BEGIN:VCARD\nVERSION:3.0\nFN:{name}\nTEL;TYPE=CELL:{num}\nEND:VCARD\n"
    vnum = cfg["vcf_start"]+idx if cfg["vcf_start"] is not None else idx+1
    fname=f"{cfg['file_name']}_{vnum}.vcf"
    with open(fname,"w") as f:
        f.write(out)
    return fname

# ================== UI ==================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📇 Generate VCF", callback_data="gen")],
        [InlineKeyboardButton("🔁 TXT → VCF", callback_data="txt2vcf"),
         InlineKeyboardButton("🔄 VCF → TXT", callback_data="vcf2txt")],
        [InlineKeyboardButton("🧩 Merge Files", callback_data="merge")],
        [InlineKeyboardButton("📊 My Settings", callback_data="mysettings")],
        [InlineKeyboardButton("♻️ Reset Settings", callback_data="reset")]
    ])

def generate_settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 Set File Name", callback_data="set_file")],
        [InlineKeyboardButton("👤 Set Contact Name", callback_data="set_contact")],
        [InlineKeyboardButton("📊 Set VCF Per Limit", callback_data="set_limit")],
        [InlineKeyboardButton("🔢 Set Contact Number Start", callback_data="set_start")],
        [InlineKeyboardButton("📄 Set VCF Number Start", callback_data="set_vcf")],
        [InlineKeyboardButton("🌍 Set Country Code", callback_data="set_country")],
        [InlineKeyboardButton("📑 Set Group Number", callback_data="set_group")],
        [InlineKeyboardButton("✅ Done", callback_data="gen_done")]
    ])

# ================== START ==================
async def start(update:Update, ctx):
    if not auth(update.effective_user.id):
        return await update.message.reply_text("❌ Access denied")
    await update.message.reply_text(
        "👋 *Welcome to VCF Generator Bot*\n\n"
        "👉 Neeche option select karein",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

# ================== BUTTON HANDLER ==================
async def buttons(update:Update, ctx):
    q=update.callback_query
    await q.answer()
    uid=q.from_user.id
    st=state(uid)
    cfg=settings(uid)

    if q.data=="gen":
        st["mode"]="generate"
        await q.message.reply_text(
            "⚙️ Pehle settings set karein",
            reply_markup=generate_settings_menu()
        )

    elif q.data.startswith("set_"):
        st["step"]=q.data
        prompts={
            "set_file":"✏️ Send your file name",
            "set_contact":"✏️ Send your contact name",
            "set_limit":"✏️ Send VCF per limit (number)",
            "set_start":"✏️ Send contact number start",
            "set_vcf":"✏️ Send VCF file number start",
            "set_country":"✏️ Send country code (Example: +91)",
            "set_group":"✏️ Send group number"
        }
        await q.message.reply_text(prompts[q.data])

    elif q.data=="gen_done":
        st["step"]=None
        await q.message.reply_text(
            "📤 Ab numbers ya file bhejo\n"
            "Example:\n3838376362 8283736272"
        )

    elif q.data=="txt2vcf":
        st["mode"]="txt2vcf"
        await q.message.reply_text("📂 TXT file bhejo")

    elif q.data=="vcf2txt":
        st["mode"]="vcf2txt"
        await q.message.reply_text("📂 VCF file bhejo")

    elif q.data=="merge":
        st["mode"]="merge"
        merge_files[uid]=[]
        await q.message.reply_text("📥 Files bhejo (TXT / VCF)")

    elif q.data=="mysettings":
        txt = (
            "📊 Your Current Settings\n\n"
            f"📂 File name: {cfg['file_name']}\n"
            f"👤 Contact name: {cfg['contact_name']}\n"
            f"📊 Limit: {cfg['limit']}\n"
            f"🔢 Start index: {cfg['start_index'] if cfg['start_index'] is not None else 'Not set'}\n"
            f"📄 VCF start: {cfg['vcf_start'] if cfg['vcf_start'] is not None else 'Not set'}\n"
            f"🌍 Country code: {cfg['country_code'] if cfg['country_code'] else 'None'}\n"
            f"📑 Group start: {cfg['group_start'] if cfg['group_start'] is not None else 'Not set'}"
        )
        await q.message.reply_text(txt)

    elif q.data=="reset":
        user_settings[uid]=DEFAULT_SETTINGS.copy()
        user_state[uid]={"mode":None,"step":None}
        merge_files.pop(uid,None)
        await q.message.reply_text("♻️ All settings reset successfully ✅")

# ================== TEXT HANDLER ==================
async def text(update:Update, ctx):
    uid=update.effective_user.id
    if not auth(uid): return
    st=state(uid)
    cfg=settings(uid)
    t=update.message.text.strip()

    # SETTING INPUT
    if st["step"]:
        m={
            "set_file":"file_name",
            "set_contact":"contact_name",
            "set_limit":"limit",
            "set_start":"start_index",
            "set_vcf":"vcf_start",
            "set_country":"country_code",
            "set_group":"group_start"
        }
        key=m[st["step"]]
        cfg[key]=int(t) if key in ["limit","start_index","vcf_start","group_start"] else t
        st["step"]=None
        return await update.message.reply_text(f"✅ Your {key.replace('_',' ')} is set")

    # MERGE DONE
    if st["mode"]=="merge" and t.lower()=="done":
        nums=set()
        for p in merge_files.get(uid,[]):
            if os.path.exists(p):
                nums |= extract_vcf(p) if p.endswith(".vcf") else extract_txt(p)
                os.remove(p)
        for i,c in enumerate(chunk(list(nums),cfg["limit"])):
            f=make_vcf(c,cfg,i)
            await update.message.reply_document(open(f,"rb"))
            os.remove(f)
        merge_files.pop(uid,None)
        st["mode"]=None
        return

    # NUMBER INPUT
    nums=re.findall(r"\d{7,}",t)
    if nums:
        for i,c in enumerate(chunk(nums,cfg["limit"])):
            f=make_vcf(c,cfg,i)
            await update.message.reply_document(open(f,"rb"))
            os.remove(f)

# ================== FILE HANDLER ==================
async def file(update:Update, ctx):
    uid=update.effective_user.id
    if not auth(uid): return
    st=state(uid)
    cfg=settings(uid)
    d=update.message.document
    p=f"{d.file_unique_id}_{d.file_name}"
    await (await ctx.bot.get_file(d.file_id)).download_to_drive(p)

    try:
        if st["mode"]=="merge":
            merge_files[uid].append(p)
            return await update.message.reply_text("📥 File added, DONE likho jab ready")

        if p.endswith(".vcf"):
            nums=list(extract_vcf(p))
        elif p.endswith(".txt"):
            nums=list(extract_txt(p))
        elif p.endswith(".csv"):
            nums=pd.read_csv(p).iloc[:,0].astype(str).tolist()
        elif p.endswith(".xlsx"):
            nums=pd.read_excel(p).iloc[:,0].astype(str).tolist()
        else:
            return await update.message.reply_text("❌ Unsupported file")

        for i,c in enumerate(chunk(nums,cfg["limit"])):
            f=make_vcf(c,cfg,i)
            await update.message.reply_document(open(f,"rb"))
            os.remove(f)
    finally:
        if st["mode"]!="merge" and os.path.exists(p):
            os.remove(p)

# ================== ERROR ==================
async def error(update, ctx):
    e="".join(traceback.format_exception(None,ctx.error,ctx.error.__traceback__))
    open("bot_errors.log","a").write(e)
    try:
        await ctx.bot.send_message(OWNER_ID,e[:4000])
    except:
        pass

# ================== MAIN ==================
if __name__=="__main__":
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text))
    app.add_handler(MessageHandler(filters.Document.ALL,file))
    app.add_error_handler(error)
    print("🚀 FINAL BOT RUNNING")
    app.run_polling()

# bot.py
# Main Telegram bot for FreeHostingBot
# Requires: BOT_TOKEN, OWNER_ID, BASE_URL in environment

import os
import asyncio
import time
import json
import zipfile
import secrets
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import exceptions
from aiogram.utils.executor import start_polling

from utils import (ROOT_DIR, USERS_DIR, DATA_DIR, BACKUPS_DIR,
                   ensure_user_record, save_json, load_json, now_ts)
from auto_installer import detect_and_install_requirements
from dashboard import user_dashboard_kb
from admin_panel import admin_main_kb
from file_manager import create_token_for_user, token_valid_for_user, filemanager_url_for

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "7640327597"))
BASE_URL = os.getenv("BASE_URL", "")  # e.g., https://python-umarvel475.replit.app
FREE_LIMIT = int(os.getenv("FREE_LIMIT_PROJECTS", "2"))
PREMIUM_LIMIT = int(os.getenv("PREMIUM_LIMIT_PROJECTS", "10"))
FREE_RUNTIME_SECONDS = int(os.getenv("FREE_RUNTIME_HOURS", "12")) * 3600
BACKUP_INTERVAL = int(os.getenv("BACKUP_INTERVAL", "600"))  # seconds
MAX_BACKUPS = int(os.getenv("MAX_BACKUPS", "5"))

if not BOT_TOKEN:
    raise RuntimeError("Set BOT_TOKEN in environment")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# State files
STATE_USERS = DATA_DIR / "users.json"
STATE_PROCS = DATA_DIR / "process_map.json"
STATE_PREM = DATA_DIR / "premium.json"
STATE_ADMINS = DATA_DIR / "admins.json"
STATE_BANNED = DATA_DIR / "banned.json"

# load states
USERS = load_json(STATE_USERS, {})
PROCS = load_json(STATE_PROCS, {})
PREM = load_json(STATE_PREM, {"premium": []})
ADMINS = load_json(STATE_ADMINS, {"admins": []})
BANNED = load_json(STATE_BANNED, {"banned": []})

def save_states():
    save_json(STATE_USERS, USERS)
    save_json(STATE_PROCS, PROCS)
    save_json(STATE_PREM, PREM)
    save_json(STATE_ADMINS, ADMINS)
    save_json(STATE_BANNED, BANNED)

def is_owner(uid: int) -> bool:
    return int(uid) == int(OWNER_ID)

def is_admin(uid: int) -> bool:
    try:
        return is_owner(uid) or int(uid) in ADMINS.get("admins", []) or str(uid) in os.getenv("ADMINS", "")
    except:
        return False

def is_banned(uid: int) -> bool:
    try:
        return int(uid) in BANNED.get("banned", [])
    except:
        return False

def is_premium(uid: int) -> bool:
    try:
        return int(uid) in PREM.get("premium", [])
    except:
        return False

def user_folder(uid: int, project: Optional[str] = None) -> Path:
    base = USERS_DIR / str(uid)
    if project:
        p = base / project
        p.mkdir(parents=True, exist_ok=True)
        return p
    base.mkdir(parents=True, exist_ok=True)
    return base

def can_create_more(uid: int) -> bool:
    ensure_user_record(uid)
    projects = USERS.get(str(uid), {}).get("projects", [])
    limit = PREMIUM_LIMIT_PROJECTS if is_premium(uid) else FREE_LIMIT
    return len(projects) < limit

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    if is_banned(uid):
        await message.answer("You are banned from using this service.")
        return

    ensure_user_record(uid)
    text = (
        "👋 Welcome to the Python Project Hoster!\n\n"
        "I'm your personal bot for securely deploying and managing your Python scripts and applications, right here from Telegram.\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚡ Key Features:\n"
        "🚀 Deploy Instantly — Upload your code as a .zip or .py file and I’ll handle the rest.\n"
        "📂 Easy Management — Use the built-in web file manager to edit your files live.\n"
        "🤖 Full Control — Start, stop, restart, and view logs for all your projects.\n"
        "🪄 Auto Setup — No need for a requirements file; I automatically install everything required!\n"
        "💾 Backup System — Your project data is automatically backed up every 10 minutes.\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "🆓 Free Tier:\n"
        "• You can host up to 2 projects.\n"
        "• Each project runs for 12 hours per session.\n\n"
        "⭐ Premium Tier:\n"
        "• Host up to 10 projects.\n"
        "• Run your scripts 24/7 nonstop.\n"
        "• Automatic daily backup retention.\n\n"
        "Need more power? You can upgrade to Premium anytime by contacting the bot owner!\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "👇 Get Started Now:\n"
        "1️⃣ Tap “🆕 New Project” below.\n"
        "2️⃣ Set your project name.\n"
        "3️⃣ Upload your Python script (.py) or .zip file.\n"
        "4️⃣ Control everything from your dashboard!\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"🧑‍💻 Powered by: @freehostinggbot\n🔒 Secure • Fast • Easy to Use"
    )

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🆕 New Project", callback_data="deploy:start"),
        InlineKeyboardButton("❓ Help", callback_data="menu:help"),
        InlineKeyboardButton("💎 Premium", callback_data="upgrade:premium")
    )
    if is_owner(uid) or is_admin(uid):
        kb.add(InlineKeyboardButton("🛠 Admin Panel", callback_data="admin:main"))
    await message.answer(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("deploy:"))
async def cb_deploy(query: types.CallbackQuery):
    uid = query.from_user.id
    if is_banned(uid):
        await query.answer("Banned")
        return
    if query.data == "deploy:start":
        if not can_create_more(uid):
            await query.answer("Project limit reached. Upgrade to premium.", show_alert=True)
            return
        await bot.send_message(uid, "📦 Send your project name (single-word, no spaces).")
        # store that awaiting name
        USERS.setdefault(str(uid), {}).setdefault("state", {})
        USERS[str(uid)]["state"]["awaiting_name"] = True
        save_states()
        await query.answer()

@dp.message_handler(content_types=types.ContentType.TEXT)
async def text_handler(msg: types.Message):
    uid = msg.from_user.id
    if is_banned(uid):
        return
    s = USERS.get(str(uid), {})
    if s.get("state", {}).get("awaiting_name"):
        name = msg.text.strip()
        if not name or " " in name:
            await msg.reply("Invalid name. Use a single word (no spaces).")
            return
        USERS.setdefault(str(uid), {}).setdefault("projects", [])
        USERS[str(uid)]["projects"].append(name)
        # create folder
        user_folder(uid, name)
        USERS[str(uid)]["state"].pop("awaiting_name", None)
        save_states()
        await msg.reply(f"Project `{name}` created. Now upload a `.py` or `.zip` file (send as document).", parse_mode="Markdown")
        return
    # other texts ignored
    return

@dp.message_handler(content_types=types.ContentType.DOCUMENT)
async def doc_handler(msg: types.Message):
    uid = msg.from_user.id
    if is_banned(uid):
        return
    info = USERS.get(str(uid))
    if not info or not info.get("projects"):
        await msg.reply("No project selected. Use 🆕 New Project first.")
        return
    project = info["projects"][-1]
    doc = msg.document
    dest = user_folder(uid, project) / doc.file_name
    await msg.reply("📤 Uploading file...")
    try:
        await doc.download(destination_file=str(dest))
    except Exception as e:
        await msg.reply(f"Upload failed: {e}")
        return
    await msg.reply("📦 Saved. Preparing project...")
    # If zip, extract
    if doc.file_name.endswith(".zip"):
        try:
            with zipfile.ZipFile(str(dest), "r") as z:
                z.extractall(path=str(user_folder(uid, project)))
            dest.unlink()
        except Exception as e:
            await msg.reply(f"Zip extract failed: {e}")
            return
    # detect requirements and install (best-effort)
    await msg.reply("🔎 Detecting requirements and installing (if any)...")
    try:
        # find a main py file
        mains = list(user_folder(uid, project).glob("*.py"))
        if mains:
            reqs = detect_and_install_requirements(mains[0], msg=msg)
            if reqs:
                await msg.reply("✅ Requirements installed or attempted.")
            else:
                await msg.reply("✅ No requirements detected or nothing to install.")
        else:
            await msg.reply("✅ Files uploaded. Use File Manager to set entrypoint.")
    except Exception as e:
        await msg.reply(f"Install step error: {e}")

    # send dashboard keyboard
    await msg.reply("Project ready. Use the buttons below to manage it.", reply_markup=user_dashboard_kb(project))

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("run:") or c.data and c.data.startswith("stop:") or c.data and c.data.startswith("fm:") or c.data and c.data.startswith("logs:") or c.data == "menu:help" or c.data == "admin:main")
async def generic_cb(query: types.CallbackQuery):
    uid = query.from_user.id
    data = query.data
    if data == "menu:help":
        await query.message.edit_text("📘 Help:\nUse New Project → upload .py/.zip → Run/Stop/Logs via inline buttons.\nFree users: 2 projects (12h). Premium: 10 projects (24/7).", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Back", callback_data="back_home")))
        await query.answer()
        return

    if data == "admin:main":
        if not (is_owner(uid) or is_admin(uid)):
            await query.answer("Only owner/admin", show_alert=True)
            return
        await query.message.edit_text("Admin Panel", reply_markup=admin_main_kb())
        await query.answer()
        return

    if data.startswith("fm:"):
        # send secure file manager link
        _, project = data.split(":", 1)
        token = create_token_for_user(uid)
        link = filemanager_url_for(uid, project, token, base_url=BASE_URL)
        await query.message.answer(f"🔐 Your File Manager link (valid 1 hour):\n{link}")
        await query.answer()
        return

    if data.startswith("run:"):
        _, project, fname = data.split(":", 2)
        await query.answer("Starting...")
        try:
            pid = start_script(uid, project, fname)
            await query.message.edit_text(f"✅ Started `{fname}` (pid {pid})", reply_markup=user_dashboard_kb(project))
        except Exception as e:
            await query.message.edit_text(f"Start failed: {e}")
        return

    if data.startswith("stop:"):
        _, project, fname = data.split(":", 2)
        stop_script(uid, project, fname)
        await query.answer("Stopped" )
        await query.message.edit_text("Stopped", reply_markup=user_dashboard_kb(project))
        return

    if data.startswith("logs:"):
        _, project, fname = data.split(":", 2)
        out = user_folder(uid, project) / f"{fname}.out.log"
        txt = out.read_text(errors="ignore")[-4000:] if out.exists() else "No logs yet."
        await query.message.edit_text(f"Logs for {fname}:\n\n{txt}", reply_markup=user_dashboard_kb(project))
        return

    if data == "back_home":
        await cmd_start(query.message)
        return

# Script runner management
import psutil
import signal

def start_script(uid: int, project: str, filename: str) -> int:
    base = user_folder(uid, project)
    script = base / filename
    if not script.exists():
        raise FileNotFoundError("Script not found")
    venv = base / ".venv"
    if not venv.exists():
        subprocess.run([str(Path(os.sys.executable)), "-m", "venv", str(venv)])
    python_bin = venv / "bin" / "python"
    pip_bin = venv / "bin" / "pip"
    # install requirements if any
    req = base / "requirements.txt"
    if req.exists():
        subprocess.run([str(pip_bin), "install", "-r", str(req)])
    out = base / f"{filename}.out.log"
    err = base / f"{filename}.err.log"
    fo = open(out, "ab")
    fe = open(err, "ab")
    p = subprocess.Popen([str(python_bin), str(script)], cwd=str(base), stdout=fo, stderr=fe)
    key = f"{project}:{filename}"
    PROCS.setdefault(str(uid), {})[key] = {"pid": p.pid, "start": time.time(), "out": str(out), "err": str(err)}
    save_states()
    return p.pid

def stop_script(uid: int, project: str, filename: str) -> bool:
    key = f"{project}:{filename}"
    ent = PROCS.get(str(uid), {}).get(key)
    if not ent:
        return False
    pid = ent.get("pid")
    try:
        p = psutil.Process(pid)
        p.terminate()
        p.wait(timeout=5)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass
    PROCS[str(uid)].pop(key, None)
    save_states()
    return True

# Watchdog + backups
async def watchdog():
    last_backup = 0
    while True:
        now = time.time()
        # enforce free runtime limit
        for uid, items in list(PROCS.items()):
            for key, meta in list(items.items()):
                start = meta.get("start", now)
                uid_int = int(uid)
                limit = None if is_premium(uid_int) else FREE_RUNTIME_SECONDS
                if limit and now - start > limit:
                    try:
                        p = psutil.Process(meta.get("pid"))
                        p.terminate()
                        p.wait(timeout=5)
                    except Exception:
                        pass
                    PROCS[uid].pop(key, None)
                    save_states()
        # periodic backup
        if now - last_backup > BACKUP_INTERVAL:
            create_backup()
            last_backup = now
        await asyncio.sleep(60)

def create_backup():
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out = BACKUPS_DIR / f"backup_{ts}.zip"
    with zipfile.ZipFile(str(out), "w", zipfile.ZIP_DEFLATED) as z:
        for p in USERS_DIR.rglob("*"):
            try:
                z.write(str(p), str(p.relative_to(ROOT_DIR)))
            except Exception:
                pass
    # rotate old backups
    files = sorted(BACKUPS_DIR.glob("backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[MAX_BACKUPS:]:
        try:
            old.unlink()
        except Exception:
            pass
    return out

async def on_startup(dp):
    asyncio.create_task(watchdog())

if __name__ == "__main__":
    # start polling
    start_polling(dp, on_startup=on_startup)
  

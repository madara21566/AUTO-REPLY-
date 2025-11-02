from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import zipfile
import aiofiles
from utils.database import get_projects, add_project, get_project, update_project
from utils.runner import run_script, stop_script, restart_script, get_logs
from utils.backup import backup_project
from utils.monitor import update_uptime

user_states = {}

def register(app: Client):
    @app.on_callback_query(filters.regex("new_project"))
    async def new_project(client, query):
        await query.message.edit_text("Enter a project name:")
        user_states[query.from_user.id] = {'state': 'await_name'}

    @app.on_callback_query(filters.regex("my_projects"))
    async def my_projects(client, query):
        projects = get_projects(query.from_user.id)
        if not projects:
            await query.message.edit_text("No projects found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
            return
        text = "Your Projects:\n" + "\n".join(f"• {p}" for p in projects)
        buttons = [[InlineKeyboardButton(p, callback_data=f"project_{p}")] for p in projects]
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="back")])
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    @app.on_callback_query(filters.regex(r"project_(.+)"))
    async def project_details(client, query):
        project_name = query.data.split("_", 1)[1]
        project = get_project(query.from_user.id, project_name)
        if not project:
            await query.message.edit_text("Project not found.")
            return
        update_uptime(query.from_user.id, project_name)
        status_emoji = "🟢" if project['status'] == 'running' else "🔴"
        text = f"""Project Status for {project_name}

🔹 Status: {status_emoji} {project['status'].capitalize()}
🔹 PID: {project['pid'] or 'N/A'}
🔹 Uptime: {int(project['uptime'] // 3600)}:{int((project['uptime'] % 3600) // 60)}:{int(project['uptime'] % 60)}
🔹 Last Run: {project['last_run'] or 'Never'}
🔹 Last Exit Code: {project['last_exit_code'] or 'N/A'}
🔹 Run Command: {project['run_command']}
"""
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Run", callback_data=f"run_{project_name}"),
             InlineKeyboardButton("⏹ Stop", callback_data=f"stop_{project_name}"),
             InlineKeyboardButton("🔁 Restart", callback_data=f"restart_{project_name}")],
            [InlineKeyboardButton("📜 Logs", callback_data=f"logs_{project_name}"),
             InlineKeyboardButton("📂 File Manager", callback_data=f"file_manager_{project_name}")],
            [InlineKeyboardButton("🔙 Back", callback_data="my_projects")]
        ])
        await query.message.edit_text(text, reply_markup=buttons)

    @app.on_callback_query(filters.regex(r"run_(.+)"))
    async def run_project(client, query):
        project_name = query.data.split("_", 1)[1]
        if run_script(query.from_user.id, project_name):
            await query.answer("Script started!")
        else:
            await query.answer("Failed to start.")

    @app.on_callback_query(filters.regex(r"stop_(.+)"))
    async def stop_project(client, query):
        project_name = query.data.split("_", 1)[1]
        if stop_script(query.from_user.id, project_name):
            await query.answer("Script stopped!")
        else:
            await query.answer("Failed to stop.")

    @app.on_callback_query(filters.regex(r"restart_(.+)"))
    async def restart_project(client, query):
        project_name = query.data.split("_", 1)[1]
        if restart_script(query.from_user.id, project_name):
            await query.answer("Script restarted!")
        else:
            await query.answer("Failed to restart.")

    @app.on_callback_query(filters.regex(r"logs_(.+)"))
    async def show_logs(client, query):
        project_name = query.data.split("_", 1)[1]
        logs = get_logs(query.from_user.id, project_name)
        await query.message.edit_text(f"Logs for {project_name}:\n{logs}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"project_{project_name}")]]))

    @app.on_message(filters.text & ~filters.command)
    async def handle_text(client, message):
        if message.from_user.id in user_states and user_states[message.from_user.id]['state'] == 'await_name':
            user_states[message.from_user.id]['name'] = message.text
            user_states[message.from_user.id]['state'] = 'await_file'
            await message.reply("Now upload your .py or .zip file.")

    @app.on_message(filters.document)
    async def handle_upload(client, message):
        if message.from_user.id in user_states and user_states[message.from_user.id]['state'] == 'await_file':
            state = user_states[message.from_user.id]
            project_name = state['name']
            file = message.document
            if file.file_name.endswith(('.py', '.zip')):
                path = f"projects/{message.from_user.id}/{project_name}"
                os.makedirs(path, exist_ok=True)
                await message.download(f"{path}/upload.{file.file_name.split('.')[-1]}")
                if file.file_name.endswith('.zip'):
                    with zipfile.ZipFile(f"{path}/upload.zip", 'r') as zip_ref:
                        zip_ref.extractall(path)
                add_project(message.from_user.id, project_name, path)
                await message.reply("Project uploaded successfully!", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📂 My Projects", callback_data="my_projects"),
                     InlineKeyboardButton("🔙 Back", callback_data="back")]
                ]))
                del user_states[message.from_user.id]
            else:
                await message.reply("Invalid file type. Upload .py or .zip.")
      

import asyncio
from pyrogram import Client
from dotenv import load_dotenv
import os
from handlers import start_handler, project_handler, admin_handler, file_manager_handler, backup_handler
from web.app import app  # Import Flask app
from utils.backup import backup_loop

load_dotenv()

app = Client("MADARA_HOSTING_BOT", api_id=int(os.getenv("API_ID", 12345)), api_hash=os.getenv("API_HASH"), bot_token=os.getenv("BOT_TOKEN"))

# Register handlers
start_handler.register(app)
project_handler.register(app)
admin_handler.register(app)
file_manager_handler.register(app)
backup_handler.register(app)

async def main():
    # Start backup loop
    asyncio.create_task(backup_loop())
    # Start Flask app in background
    from threading import Thread
    flask_thread = Thread(target=lambda: app.run(host='0.0.0.0', port=8080, debug=False))
    flask_thread.start()
    # Start bot
    await app.start()
    print("Bot started!")
    await app.idle()

if __name__ == "__main__":
    asyncio.run(main())

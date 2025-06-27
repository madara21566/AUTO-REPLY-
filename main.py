import os
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from Bot import (setreply,eletereply,istreplies )

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOT_USERNAME = os.environ.get("BOT_USERNAME")
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{BOT_USERNAME}"

# app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setreply", set_reply))
    app.add_handler(CommandHandler("deletereply", delete_reply))
    app.add_handler(CommandHandler("listreplies", list_replies))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_reply))

if __name__ == "__main__":
    # Start webhook directly (No Flask needed)
    application.run_webhook(
        listen="0.0.0.0",
        port=5000,
        url_path=BOT_USERNAME,
        webhook_url=WEBHOOK_URL
    )

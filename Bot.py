import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

# User-wise replies dictionary
# Structure: { user_id: { keyword: reply } }
user_replies = {}

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Quick Auto-Reply Bot!\n\n"
        "Commands:\n"
        "/setreply <keyword> <message>\n"
        "/deletereply <keyword>\n"
        "/listreplies"
    )

# /setreply
async def set_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage:\n/setreply <keyword> <message>")
        return
    keyword = context.args[0].lower()
    message = " ".join(context.args[1:])
    user_replies.setdefault(user_id, {})[keyword] = message
    await update.message.reply_text(f"✅ Auto-reply set:\n'{keyword}' ➡️ '{message}'")

# /deletereply
async def delete_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("⚠️ Usage:\n/deletereply <keyword>")
        return
    keyword = context.args[0].lower()
    if keyword in user_replies.get(user_id, {}):
        del user_replies[user_id][keyword]
        await update.message.reply_text(f"✅ Deleted auto-reply for '{keyword}'.")
    else:
        await update.message.reply_text(f"⚠️ No auto-reply found for '{keyword}'.")

# /listreplies
async def list_replies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    replies = user_replies.get(user_id, {})
    if not replies:
        await update.message.reply_text("ℹ️ No auto-replies set yet.")
        return
    text = "💬 Your Auto-Replies:\n\n"
    for k, v in replies.items():
        text += f"🔹 '{k}' ➡️ '{v}'\n"
    await update.message.reply_text(text)

# Auto reply handler
async def auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.lower()
    replies = user_replies.get(user_id, {})
    for keyword, reply in replies.items():
        if keyword in text:
            await update.message.reply_text(reply)
            break  # Send only one reply per message

if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setreply", set_reply))
    app.add_handler(CommandHandler("deletereply", delete_reply))
    app.add_handler(CommandHandler("listreplies", list_replies))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_reply))

    app.run_polling()

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# --- Hardcoded Bot Token ---
BOT_TOKEN = "8401246349:AAHvy5jmHDt9VAHUi78AglEqvvvADMpwWtc"  # ← replace with your real token

# --- Initialize Bot ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# --- Reply "Hello 👋" to any message ---
@dp.message_handler()
async def reply_hello(message: types.Message):
    await message.reply("Hello 👋")

# --- Start Bot ---
if __name__ == "__main__":
    print("🤖 Bot is running... Send any message to get 'Hello 👋'")
    executor.start_polling(dp, skip_updates=True)

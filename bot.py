import os
from telegram.ext import ApplicationBuilder

TOKEN = os.environ.get("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN is not set")

if __name__ == "__main__":
    application = ApplicationBuilder().token(TOKEN).build()
    application.run_polling()

import os
import json

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ["BOT_TOKEN"]

PORT = int(os.environ.get("PORT", 10000))

WEBHOOK_PATH = "telegram-webhook"
WEBHOOK_URL = "https://princeprm-bot-1.onrender.com"


# Drama database load
with open("dramas.json", "r", encoding="utf-8") as file:
    dramas = json.load(file)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 Korean Drama Hindi Dubbed Bot\n\n"
        "Drama ka naam bhejo.\n"
        "Example: True Beauty"
    )


async def search_drama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip().lower()

    results = [
        drama for drama in dramas
        if query in drama["title"].lower()
    ]

    if not results:
        await update.message.reply_text(
            "❌ Drama nahi mila.\n\n"
            "Dusra naam try karo."
        )
        return

    for drama in results:
        hindi = "✅ Hindi Dubbed" if drama["hindi_dubbed"] else "❌ Hindi Dubbed"

        message = (
            f"🎬 {drama['title']}\n\n"
            f"📅 Year: {drama['year']}\n"
            f"🎭 Genre: {drama['genre']}\n"
            f"🇮🇳 {hindi}"
        )

        await update.message.reply_text(message)


if __name__ == "__main__":
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, search_drama)
    )

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=f"{WEBHOOK_URL}/{WEBHOOK_PATH}",
    )

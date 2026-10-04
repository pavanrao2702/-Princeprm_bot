import logging
import os
from threading import Thread
from flask import Flask
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)


@flask_app.route("/")
def home():
  return "PrimeMovie Bot is alive and running!"


def run_flask():
  port = int(os.environ.get("PORT", 8080))
  flask_app.run(host="0.0.0.0", port=port)


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_name = update.effective_user.first_name
  msg = (
      f"Hey 👋 {user_name} 🍿\n\n"
      "🍿 **Welcome To PrimeMovie Bot!**\n\n"
      "Kisi bhi movie ka naam bhejein, main usse judi saari movies ki list"
      " dikhaunga!"
  )
  await update.message.reply_text(msg, parse_mode="Markdown")


async def incoming_message_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  query = update.message.text.strip()
  if not TMDB_API_KEY:
    await update.message.reply_text("Error: TMDB API Key is missing.")
    return

  status_msg = await update.message.reply_text(
      f"🔍 Searching **{query}**...", parse_mode="Markdown"
  )

  tmdb_url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={requests.utils.quote(query)}"

  try:
    response = requests.get(tmdb_url).json()
    results = response.get("results", [])
    filtered = [
        r
        for r in results
        if r.get("media_type") in ["movie", "tv"]
        and (r.get("title") or r.get("name"))
    ]

    if not filtered:
      await status_msg.edit_text(
          f"❌ Maaf kijiye, '{query}' se judi koi movie nahi mili."
      )
      return

    keyboard = []
    for item in filtered[:6]:
      title = item.get("title") or item.get("name")
      year = (
          item.get("release_date", "")[:4]
          or item.get("first_air_date", "")[:4]
          or "N/A"
      )
      media_id = item.get("id")
      media_type = item.get("media_type")

      callback_data = f"sel_{media_type}_{media_id}"
      keyboard.append(
          [InlineKeyboardButton(f"🎬 {title} ({year})", callback_data=callback_data)]
      )

    reply_markup = InlineKeyboardMarkup(keyboard)
    await status_msg.edit_text(
        f"✨ *'{query}'* se judi yeh movies mili hain, sahi wali par click"
        " karein:",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )

  except Exception as e:
    logger.error(f"Search error: {e}")
    await status_msg.edit_text(f"⚠️ Error: {str(e)}")


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()

  data = query.data
  if not data.startswith("sel_"):
    return

  _, media_type, media_id = data.split("_")

  detail_url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={TMDB_API_KEY}"
  detail_resp = requests.get(detail_url).json()
  title = detail_resp.get("title") or detail_resp.get("name")
  year = (
      detail_resp.get("release_date", "")[:4]
      or detail_resp.get("first_air_date", "")[:4]
      or ""
  )
  
  full_title_query = f"{title} {year}" if year else title
  encoded_title = requests.utils.quote(full_title_query)
  simple_encoded = requests.utils.quote(title)

  links_msg = (
      f"🎬 *{title}* ({year})\n\n"
      "📥 *Sabse Pehle Dekhein aur Download Karein (Direct Stream & Download):*\n"
      f"• [Archive.org Direct Download & Stream](https://archive.org/search.php?query={encoded_title}+mediatype%3Amovies)\n"
      f"• [YouTube Full Movie Watch](https://www.youtube.com/results?search_query={encoded_title}+full+movie)\n\n"
      "🌐 *Anye Websites aur Links:*\n"
      f"• [Google Video / Web Watch](https://www.google.com/search?q={encoded_title}+watch+online+free)\n"
      f"• [Open Culture Free Movies](https://www.openculture.com/freemoviesonline)\n"
      f"• [Tubi TV Stream](https://tubitv.com/search/{simple_encoded})"
  )

  await query.edit_message_text(links_msg, parse_mode="Markdown")


def main():
  if not TELEGRAM_TOKEN:
    logger.error("Telegram Token is missing!")
    return

  flask_thread = Thread(target=run_flask)
  flask_thread.daemon = True
  flask_thread.start()

  app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

  app.add_handler(CommandHandler("start", start))
  app.add_handler(
      MessageHandler(filters.TEXT & ~filters.COMMAND, incoming_message_handler)
  )
  app.add_handler(CallbackQueryHandler(button_callback_handler))

  app.run_polling()


if __name__ == "__main__":
  main()
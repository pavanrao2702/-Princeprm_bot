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
  return "PrimeMovie Archive Bot is alive and running!"


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

  # TMDB se multi-language search
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
          f"❌ माफ कीजिए, '{query}' से जुड़ी कोई मूवी नहीं मिली।"
      )
      return

    # टॉप 5 विकल्प बटन के रूप में दिखाना
    keyboard = []
    for item in filtered[:5]:  # टॉप 5 परिणाम
      title = item.get("title") or item.get("name")
      year = (
          item.get("release_date", "")[:4]
          or item.get("first_air_date", "")[:4]
          or "N/A"
      )
      media_id = item.get("id")
      media_type = item.get("media_type")

      # कॉलबैक डेटा में ID और type भेजेंगे ताकि सही फिल्म डाउनलोड हो सके
      callback_data = f"sel_{media_type}_{media_id}"
      keyboard.append(
          [InlineKeyboardButton(f"🎬 {title} ({year})", callback_data=callback_data)]
      )

    reply_markup = InlineKeyboardMarkup(keyboard)
    await status_msg.edit_text(
        f"✨ *'{query}'* से जुड़ी ये फिल्में मिली हैं, सही वाली पर क्लिक करें:",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )

  except Exception as e:
    logger.error(f"Search error: {e}")
    await status_msg.edit_text(f"⚠️ Error: {str(e)}")


# जब यूजर किसी फिल्म के बटन पर क्लिक करेगा
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()

  data = query.data
  if not data.startswith("sel_"):
    return

  _, media_type, media_id = data.split("_")

  # TMDB से उस खास फिल्म की डिटेल निकालना
  detail_url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={TMDB_API_KEY}"
  detail_resp = requests.get(detail_url).json()
  title = detail_resp.get("title") or detail_resp.get("name")

  await query.edit_message_text(
      f"📥 Searching **{title}** on Archive.org...", parse_mode="Markdown"
  )

  # Archive.org से फाइल ढूंढना और भेजना
  await process_archive_download(query.message, context, title)


async def process_archive_download(message, context, title):
  try:
    encoded_title = requests.utils.quote(title)
    ia_search_url = f"https://archive.org/advancedsearch.php?q=title%3A({encoded_title})+AND+mediatype%3A(movies)&output=json&rows=1"
    ia_resp = requests.get(ia_search_url).json()
    docs = ia_resp.get("response", {}).get("docs", [])

    if not docs:
      await send_free_links(message, title, "❌ डायरेक्ट फाइल नहीं मिली, फ्री लिंक्स:")
      return

    identifier = docs[0].get("identifier")
    meta_url = f"https://archive.org/metadata/{identifier}"
    meta_resp = requests.get(meta_url).json()
    files = meta_resp.get("files", [])

    mp4_file = None
    for f in files:
      if f.get("name", "").endswith(".mp4"):
        mp4_file = f.get("name")
        break

    if not mp4_file:
      await send_free_links(message, title, "❌ वीडियो फाइल उपलब्ध नहीं है, फ्री लिंक्स:")
      return

    download_url = f"https://archive.org/download/{identifier}/{mp4_file}"
    await message.edit_text(f"📥 Downloading **{title}**...")

    os.makedirs("downloads", exist_ok=True)
    file_path = os.path.join("downloads", f"{title}.mp4")

    dl_response = requests.get(download_url, stream=True)
    if dl_response.status_code == 200:
      with open(file_path, "wb") as f:
        for chunk in dl_response.iter_content(chunk_size=1024 * 1024):
          if chunk:
            f.write(chunk)

      await message.edit_text("📤 Uploading video to Telegram...")
      with open(file_path, "rb") as video_file:
        await context.bot.send_video(chat_id=message.chat_id, video=video_file)

      os.remove(file_path)
      await message.delete()
    else:
      await send_free_links(message, title, "⚠️ डाउनलोड विफल रहा, फ्री लिंक्स:")

  except Exception as e:
    logger.error(f"Download error: {e}")
    await message.edit_text(f"⚠️ Error: {str(e)}")


async def send_free_links(message, title, custom_message):
  encoded_title = requests.utils.quote(title)
  free_links_msg = (
      f"{custom_message}\n\n"
      f"🎬 *{title}*:\n\n"
      f"• [Internet Archive Search](https://archive.org/search.php?query={encoded_title})\n"
      f"• [YouTube (Free / Watch)](https://www.youtube.com/results?search_query={encoded_title}+full+movie)\n"
      f"• [Tubi TV](https://tubitv.com)"
  )
  await message.edit_text(free_links_msg, parse_mode="Markdown")


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

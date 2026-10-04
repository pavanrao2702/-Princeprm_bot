import logging
import os
from threading import Thread
from flask import Flask
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
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
      "Kisi bhi movie ka naam bhejein, bot Archive.org se direct download"
      " karke bhejega! Agar file nahi mili, toh free streaming links mil"
      " jayenge."
  )
  await update.message.reply_text(msg, parse_mode="Markdown")


async def incoming_message_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  text = update.message.text.strip()
  await search_and_download_media(update, context, text)


async def search_and_download_media(
    update: Update, context: ContextTypes.DEFAULT_TYPE, query: str
):
  if not TMDB_API_KEY:
    await update.message.reply_text("Error: TMDB API Key is missing.")
    return

  status_msg = await update.message.reply_text(
      "🔍 *Searching movie details...*", parse_mode="Markdown"
  )

  # TMDB se movie ka sahi naam pata karna
  tmdb_url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={requests.utils.quote(query)}"

  try:
    response = requests.get(tmdb_url).json()
    results = response.get("results", [])
    filtered = [r for r in results if r.get("media_type") in ["movie", "tv"]]

    if not filtered:
      title = query
    else:
      item = filtered[0]
      title = item.get("title") or item.get("name")

    await status_msg.edit_text(f"📥 Searching **{title}** on Archive.org...")

    encoded_title = requests.utils.quote(title)

    # Archive.org Search API
    ia_search_url = f"https://archive.org/advancedsearch.php?q=title%3A({encoded_title})+AND+mediatype%3A(movies)&output=json&rows=1"
    ia_resp = requests.get(ia_search_url).json()
    docs = ia_resp.get("response", {}).get("docs", [])

    # अगर Archive.org पर फाइल नहीं मिलती, तो फ्री लिंक्स भेजें
    if not docs:
      await send_free_links(
          status_msg,
          title,
          "❌ डायरेक्ट वीडियो फाइल नहीं मिली, लेकिन आप यहाँ फ्री में देख सकते हैं:",
      )
      return

    identifier = docs[0].get("identifier")

    # Metadata se direct file (.mp4) ka link nikalna
    meta_url = f"https://archive.org/metadata/{identifier}"
    meta_resp = requests.get(meta_url).json()
    files = meta_resp.get("files", [])

    mp4_file = None
    for f in files:
      if (
          f.get("format") in ["MPEG4", "h.264", "5X MP4"]
          or f.get("name", "").endswith(".mp4")
      ):
        mp4_file = f.get("name")
        break

    if not mp4_file and files:
      for f in files:
        if f.get("name", "").endswith(".mp4"):
          mp4_file = f.get("name")
          break

    # अगर .mp4 फाइल नहीं मिलती, तो फ्री लिंक्स भेजें
    if not mp4_file:
      await send_free_links(
          status_msg,
          title,
          "❌ इस मूवी की वीडियो फाइल उपलब्ध नहीं है, आप इन फ्री लिंक्स का"
          " इस्तेमाल करें:",
      )
      return

    download_url = f"https://archive.org/download/{identifier}/{mp4_file}"

    await status_msg.edit_text(
        f"📥 Downloading **{title}** (Streaming Mode)..."
    )

    os.makedirs("downloads", exist_ok=True)
    file_path = os.path.join("downloads", f"{title}.mp4")

    # Requests streaming download (1MB chunks)
    dl_response = requests.get(download_url, stream=True)
    if dl_response.status_code == 200:
      with open(file_path, "wb") as f:
        for chunk in dl_response.iter_content(chunk_size=1024 * 1024):
          if chunk:
            f.write(chunk)

      await status_msg.edit_text("📤 Uploading video to Telegram...")
      with open(file_path, "rb") as video_file:
        await context.bot.send_video(
            chat_id=update.effective_chat.id, video=video_file
        )

      os.remove(file_path)
      await status_msg.delete()
    else:
      # अगर डाउनलोड फेल हो जाए, तो फ्री लिंक्स भेजें
      await send_free_links(
          status_msg,
          title,
          "⚠️ डाउनलोड विफल रहा। कृपया इन फ्री लीगल लिंक्स से देखें:",
      )

  except Exception as e:
    logger.error(f"Processing error: {e}")
    await status_msg.edit_text(f"⚠️ Error: {str(e)}")


async def send_free_links(status_msg, title, custom_message):
  encoded_title = requests.utils.quote(title)
  free_links_msg = (
      f"{custom_message}\n\n"
      f"🎬 *{title}* के लिए फ्री विकल्प:\n\n"
      f"• [Internet Archive Search](https://archive.org/search.php?query={encoded_title})\n"
      f"• [YouTube (Free / Watch)](https://www.youtube.com/results?search_query={encoded_title}+full+movie)\n"
      f"• [Open Culture Free Movies](https://www.openculture.com/freemoviesonline)\n"
      f"• [Tubi TV](https://tubitv.com)"
  )
  await status_msg.edit_text(free_links_msg, parse_mode="Markdown")


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

  app.run_polling()


if __name__ == "__main__":
  main()

import os
import logging
import asyncio
import requests
import yt_dlp
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "PrimeMovie yt-dlp Bot is alive and running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    msg = (
        f"Hey 👋 {user_name} 🍿\n\n"
        f"🍿 **Welcome To PrimeMovie yt-dlp Bot!**\n\n"
        f"Kisi bhi movie ya song ka naam bhejein, bot yt-dlp se download karke direct video bhejega!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def incoming_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    await search_and_download_media(update, context, text)

async def search_and_download_media(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    if not TMDB_API_KEY:
        await update.message.reply_text("Error: TMDB API Key is missing.")
        return

    status_msg = await update.message.reply_text("🔍 *Searching title details...*", parse_mode="Markdown")
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={requests.utils.quote(query)}"
    
    try:
        response = requests.get(url).json()
        results = response.get("results", [])
        filtered = [r for r in results if r.get("media_type") in ["movie", "tv"]]
        
        if not filtered:
            title = query
        else:
            item = filtered[0]
            title = item.get("title") or item.get("name")
        
        await status_msg.edit_text(f"📥 Downloading **{title}** using yt-dlp engine...")

        os.makedirs("downloads", exist_ok=True)
        
        ydl_opts = {
            'format': '18',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'noplaylist': True,
            'extractor-args': {'youtube': {'player-client': ['android', 'web']}},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        search_query = f"ytsearch1: {title} full movie"
        
        def download_version():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=True)
                if 'entries' in info:
                    info = info['entries'][0]
                return ydl.prepare_filename(info)

        loop = asyncio.get_running_loop()
        filename = await loop.run_in_executor(None, download_version)

        if filename and os.path.exists(filename):
            await status_msg.edit_text("📤 Uploading video to Telegram server...")
            with open(filename, 'rb') as video_file:
                await context.bot.send_video(chat_id=update.effective_chat.id, video=video_file)
            
            os.remove(filename)
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Video download fail ho gaya.")

    except Exception as e:
        logger.error(f"yt-dlp processing error: {e}")
        await status_msg.edit_text(f"⚠️ Error during media processing: {str(e)}")

def main():
    if not TELEGRAM_TOKEN:
        logger.error("Telegram Token is missing!")
        return

    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, incoming_message_handler))
    
    app.run_polling()

if __name__ == '__main__':
    main()

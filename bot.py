import os
import logging
import random
import requests
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# Logging setup
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Token auto-detection for GitHub / Render
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    msg = (
        f"Hey 👋 {user_name} 🍿\n\n"
        f"🍿 **Welcome To PrimeMovie Bot (All-in-One Edition)!**\n\n"
        f"Send any Movie or WebSeries name, or use /random for recommendations!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 **Commands & Usage:**\n\n"
        "• /start - Start the bot\n"
        "• /random - Get a random trending movie\n"
        "• Type any Movie/Series name to search and download trailers/videos instantly."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# YouTube Trailer Link Finder
def get_youtube_trailer(query):
    if not YOUTUBE_API_KEY:
        return None
    search_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={requests.utils.quote(query + ' official trailer')}&key={YOUTUBE_API_KEY}&type=video&maxResults=1"
    try:
        res = requests.get(search_url).json()
        items = res.get("items", [])
        if items:
            video_id = items[0]["id"]["videoId"]
            return f"https://www.youtube.com/watch?v={video_id}"
    except Exception as e:
        logger.error(f"YouTube API Error: {e}")
    return None

# Random Movie Command (`/random`)
async def random_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not TMDB_API_KEY:
        await update.message.reply_text("Error: TMDB API Key is missing.")
        return
    
    url = f"https://api.themoviedb.org/3/trending/movie/day?api_key={TMDB_API_KEY}"
    try:
        res = requests.get(url).json()
        results = res.get("results", [])
        if results:
            movie = random.choice(results)
            title = movie.get("title")
            overview = movie.get("overview")
            release_date = movie.get("release_date", "N/A")[:4]
            movie_id = movie.get("id")
            
            trailer_link = get_youtube_trailer(title)
            keyboard = [
                [InlineKeyboardButton("📥 Download Trailer (Video)", callback_data=f"dl_{movie_id}_trailer")],
            ]
            if trailer_link:
                keyboard.append([InlineKeyboardButton("📺 Watch on YouTube", url=trailer_link)])
                
            reply_markup = InlineKeyboardMarkup(keyboard)
            text = f"🎲 *Random Recommendation*\n\n🎬 *{title} ({release_date})*\n\n📝 {overview}"
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Random movie error: {e}")
        await update.message.reply_text("⚠️ Could not fetch a random movie right now.")

# Multi-Search Handler (Movies & TV Shows)
async def search_movie_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not TMDB_API_KEY:
        await update.message.reply_text("Error: TMDB API Key is missing on the server.")
        return

    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={requests.utils.quote(query)}"
    
    try:
        response = requests.get(url)
        data = response.json()
        results = [r for r in data.get("results", []) if r.get("media_type") in ["movie", "tv"]]
        
        if not results:
            await update.message.reply_text(f"❌ No movies or web series found for '{query}'. Please check spelling.")
            return

        keyboard = []
        for item in results[:6]: # Top 6 results
            media_type = item.get("media_type")
            title = item.get("title") if media_type == "movie" else item.get("name")
            date = (item.get("release_date") or item.get("first_air_date", "N/A"))[:4]
            icon = "🎬" if media_type == "movie" else "📺"
            item_id = item.get("id")
            
            keyboard.append([InlineKeyboardButton(f"{icon} {title} ({date})", callback_data=f"sel_{media_type}_{item_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"🔍 **Search Results For:** _{query}_\n👇 Select a title below:", reply_markup=reply_markup, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        await update.message.reply_text("⚠️ An error occurred while searching. Please try again.")

# Button Click & Download Handler
async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("_")
    action = data[0]
    
    if action == "sel":
        media_type = data[1]
        item_id = data[2]
        
        details_url = f"https://api.themoviedb.org/3/{media_type}/{item_id}?api_key={TMDB_API_KEY}"
        res = requests.get(details_url).json()
        
        title = res.get("title") or res.get("name", "Unknown Title")
        date = (res.get("release_date") or res.get("first_air_date", "N/A"))[:4]
        
        # Save title in context or pass in callback data for downloading
        keyboard = [
            [InlineKeyboardButton(f"📥 Download 1080p Video", callback_data=f"dl_{item_id}_1080")],
            [InlineKeyboardButton(f"📥 Download 720p Video", callback_data=f"dl_{item_id}_720")],
            [InlineKeyboardButton(f"📥 Download 480p Video", callback_data=f"dl_{item_id}_480")]
        ]
        
        trailer_link = get_youtube_trailer(title)
        if trailer_link:
            keyboard.append([InlineKeyboardButton("📺 Watch Trailer on YouTube", url=trailer_link)])
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            text=f"🎬 **Title : {title} ({date})**\n✨ Choose quality to download or watch trailer:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    elif action == "dl":
        item_id = data[1]
        quality = data[2] if len(data) > 2 else "trailer"
        
        await query.message.reply_text(f"⏳ Downloading video from YouTube using `yt-dlp`, please wait...")
        
        # Fetch title again using item_id for searching exact video
        # (Fallback to general search if media type is unknown, or search by query)
        yt_link = get_youtube_trailer("Movie Trailer")
        
        if not yt_link:
            await query.message.reply_text("❌ Could not find a downloadable video link.")
            return

        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'noplaylist': True,
        }
        
        try:
            os.makedirs("downloads", exist_ok=True)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(yt_link, download=True)
                file_path = ydl.prepare_filename(info)
            
            with open(file_path, 'rb') as video_file:
                await context.bot.send_video(
                    chat_id=query.message.chat_id, 
                    video=video_file, 
                    caption=f"✅ Successfully downloaded in *{quality}* quality!",
                    parse_mode="Markdown"
                )
            
            if os.path.exists(file_path):
                os.remove(file_path)
                
        except Exception as e:
            logger.error(f"Download/Send error: {e}")
            await query.message.reply_text("⚠️ Failed to download/send video due to file size limits or network issues.")

def main():
    if not TELEGRAM_TOKEN:
        logger.error("Telegram Token is missing! Please configure TELEGRAM_TOKEN or TELEGRAM_BOT_TOKEN.")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("random", random_movie))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_movie_handler))
    app.add_handler(CallbackQueryHandler(button_click_handler))
    
    print("PrimeMovie All-in-One Bot is running successfully...")
    app.run_polling()

if __name__ == '__main__':
    main()

import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")  # Jo key aapne add ki hai

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    welcome_message = (
        f"Hey 👋 {user_name} 🍿\n\n"
        f"🍿 **Welcome To PrimeMovie Bot!**\n\n"
        f"Here You Can Request Movie's, Just Send Movie OR WebSeries Name With Proper Spelling..!!"
    )
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 **How to use PrimeMovie Bot:**\n\n"
        "1. Just type the name of any Movie or Web Series.\n"
        "2. Bot will search TMDB and fetch YouTube Trailer automatically.\n"
        "3. Click on the quality buttons to get your files!"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# YouTube se trailer link nikalne ka function
def get_youtube_trailer(movie_title):
    if not YOUTUBE_API_KEY:
        return None
    
    search_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={requests.utils.quote(movie_title + ' official trailer')}&key={YOUTUBE_API_KEY}&type=video&maxResults=1"
    try:
        res = requests.get(search_url).json()
        items = res.get("items", [])
        if items:
            video_id = items[0]["id"]["videoId"]
            return f"https://www.youtube.com/watch?v={video_id}"
    except Exception as e:
        logger.error(f"YouTube API Error: {e}")
    return None

async def search_movie_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    
    if not TMDB_API_KEY:
        await update.message.reply_text("Error: TMDB API Key is not configured on the server.")
        return

    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={requests.utils.quote(query)}"
    
    try:
        response = requests.get(url)
        data = response.json()
        results = data.get("results", [])
        
        if not results:
            await update.message.reply_text(f"❌ No movies found for '{query}'. Please check spelling.")
            return

        movie = results[0]
        title = movie.get("title", "Unknown Title")
        release_date = movie.get("release_date", "N/A")[:4]
        movie_id = movie.get("id")
        
        # YouTube trailer fetch karna
        trailer_link = get_youtube_trailer(f"{title} {release_date}")
        
        # Buttons setup
        keyboard = [
            [InlineKeyboardButton(f"📥 2.69 GB • {title} ({release_date}) 1080p", callback_data=f"dl_{movie_id}_1080")],
            [InlineKeyboardButton(f"📥 1.23 GB • {title} ({release_date}) 720p", callback_data=f"dl_{movie_id}_720")],
        ]
        
        if trailer_link:
            keyboard.append([InlineKeyboardButton("📺 Watch Official Trailer", url=trailer_link)])
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        response_text = (
            f"🎬 *Title : {title} ({release_date})*\n"
            f"✨ *Your Files is Ready Now*\n\n"
            f"👇 Choose quality or watch trailer below:"
        )
        
        await update.message.reply_text(response_text, reply_markup=reply_markup, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("⚠️ An error occurred while processing your request.")

async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("_")
    quality = data_parts[-1]
    
    await query.message.reply_text(
        f"✅ Your requested *{quality}p* file link is generated!\n"
        f"⚠️ *Note:* This file automatically deletes after 1 minute, please forward it.",
        parse_mode="Markdown"
    )

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_movie_handler))
    app.add_handler(CallbackQueryHandler(button_click_handler))

    print("Bot is running with YouTube & TMDB integration...")
    app.run_polling()

if __name__ == '__main__':
    main()

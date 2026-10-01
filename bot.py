import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# Logging setup
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Token auto-detection (Pehle jaisa same setting)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    msg = (
        f"Hey 👋 {user_name} 🍿\n\n"
        f"🍿 **Welcome To PrimeMovie Bot!**\n\n"
        f"Here You Can Request Movie's, Just Send Movie OR WebSeries Name With Proper Spelling..!!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 **How to use PrimeMovie Bot:**\n\n"
        "1. Just type the name of any Movie or Web Series.\n"
        "2. Bot will search and show matching titles via buttons.\n"
        "3. Click on a title to get quality options!"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def search_movie_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not TMDB_API_KEY:
        await update.message.reply_text("Error: TMDB API Key is missing on the server.")
        return

    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={requests.utils.quote(query)}"
    
    try:
        response = requests.get(url)
        data = response.json()
        results = data.get("results", [])
        
        filtered_results = [r for r in results if r.get("media_type") in ["movie", "tv"]]
        
        if not filtered_results:
            await update.message.reply_text(f"❌ No movies or web series found for '{query}'. Please check spelling.")
            return

        keyboard = []
        for item in filtered_results[:8]:
            media_type = item.get("media_type")
            if media_type == "movie":
                title = item.get("title", "Unknown")
                date = item.get("release_date", "N/A")[:4]
                icon = "🎬"
            else:
                title = item.get("name", "Unknown")
                date = item.get("first_air_date", "N/A")[:4]
                icon = "📺"
                
            item_id = item.get("id")
            button_text = f"{icon} {title} ({date})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sel_{media_type}_{item_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        response_text = (
            f"🔄 **Rotate your phone to see files' full name...**\n\n"
            f"🎬 **Search Results For:** _{query}_\n"
            f"👇 Select a title below:"
        )
        
        await update.message.reply_text(response_text, reply_markup=reply_markup, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        await update.message.reply_text("⚠️ An error occurred while searching. Please try again.")

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
        
        keyboard = [
            [InlineKeyboardButton(f"📥 2.69 GB • {title} ({date}) 1080p WEB-DL", callback_data=f"dl_1080")],
            [InlineKeyboardButton(f"📥 1.23 GB • {title} ({date}) 720p WEB-DL", callback_data=f"dl_720")],
            [InlineKeyboardButton(f"📥 482 MB • {title} ({date}) 480p WEB-DL", callback_data=f"dl_480")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            text=f"🎬 **Title : {title} ({date})**\n✨ **Your Files is Ready Now**\n\n👇 Choose your preferred quality:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    elif action == "dl":
        quality = data[1]
        await query.message.reply_text(
            f"✅ Your requested *{quality}p* download link is generated!\n"
            f"⚠️ *Note:* This file automatically deletes after 1 minute, so please forward it in another chat.",
            parse_mode="Markdown"
        )

def main():
    if not TELEGRAM_TOKEN:
        logger.error("Telegram Token is missing! Please set TELEGRAM_TOKEN or TELEGRAM_BOT_TOKEN.")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_movie_handler))
    app.add_handler(CallbackQueryHandler(button_click_handler))
    
    print("PrimeMovie Bot is running successfully...")
    app.run_polling()

if __name__ == '__main__':
    main()

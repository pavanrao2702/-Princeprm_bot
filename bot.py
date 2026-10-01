import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Fetching credentials from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Start command handler with professional design based on reference style
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "User"
    welcome_text = (
        f"Hey 👋 {user_name} 🍿\n\n"
        "🍿 **Welcome To PrinceMovie Bot!**\n\n"
        "Here You Can Request Movie's, Just Send Movie OR WebSeries Name With Proper Spelling..!!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# Helper function to fetch YouTube trailer link
def get_youtube_trailer(query):
    if not YOUTUBE_API_KEY:
        return None
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={requests.utils.quote(query + ' official trailer')}&key={YOUTUBE_API_KEY}&type=video&maxResults=1"
    try:
        res = requests.get(url, timeout=5).json()
        items = res.get("items", [])
        if items:
            video_id = items[0]["id"]["videoId"]
            return f"https://www.youtube.com/watch?v={video_id}"
    except Exception:
        pass
    return None

# Helper function to fetch OMDb details
def get_omdb_details(title):
    if not OMDB_API_KEY:
        return "N/A", "N/A"
    url = f"https://www.omdbapi.com/?t={requests.utils.quote(title)}&apikey={OMDB_API_KEY}"
    try:
        res = requests.get(url, timeout=5).json()
        if res.get("Response") == "True":
            imdb_rating = res.get("imdbRating", "N/A")
            box_office = res.get("BoxOffice", "N/A")
            return imdb_rating, box_office
    except Exception:
        pass
    return "N/A", "N/A"

# Main combined search handler
async def search_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
        
    query = update.message.text.strip()
    
    if not TMDB_API_KEY:
        await update.message.reply_text("Error: TMDB API Key is not configured on the server.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # 1. Jikan API (Check if the query matches an anime)
    anime_url = f"https://api.jikan.moe/v4/anime?q={requests.utils.quote(query)}&limit=1"
    try:
        anime_res = requests.get(anime_url, timeout=6).json().get("data", [])
        if anime_res and len(anime_res) > 0:
            anime = anime_res[0]
            title = anime.get("title", "N/A")
            score = anime.get("score", "N/A")
            synopsis = anime.get("synopsis") or "No description available."
            episodes = anime.get("episodes", "N/A")
            url = anime.get("url", "")
            
            response_text = (
                f"⛩️ **Anime Found:**\n\n"
                f"📌 **{title}**\n"
                f"⭐ MyAnimeList Score: {score}\n"
                f"📺 Episodes: {episodes}\n"
                f"🔗 [More Info]({url})\n\n"
                f"📝 {synopsis[:250]}..."
            )
            await update.message.reply_text(response_text, parse_mode="Markdown", disable_web_page_preview=False)
            return
    except Exception:
        pass

    # 2. TMDB Search (Movies, Series & Dramas)
    tmdb_url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={requests.utils.quote(query)}"
    
    try:
        response = requests.get(tmdb_url, timeout=6)
        data = response.json()
        results = data.get("results", [])
        
        if not results:
            await update.message.reply_text(
                f"❌ **No results found.**\n\n"
                f"Please check the spelling and try a different title."
            )
            return
            
        item = results[0]
        title = item.get("title") or item.get("name", "N/A")
        release_date = item.get("release_date") or item.get("first_air_date", "N/A")
        overview = item.get("overview") or "No description available."
        tmdb_rating = item.get("vote_average", "N/A")
        
        imdb_rating, box_office = get_omdb_details(title)
        trailer_link = get_youtube_trailer(title)
        
        response_text = (
            f"🎬 **Result Found:**\n\n"
            f"📌 **{title}** ({release_date})\n"
            f"⭐ TMDB Rating: {tmdb_rating} / 10\n"
            f"🌟 IMDb Rating: {imdb_rating}\n"
            f"💰 Box Office: {box_office}\n"
        )
        
        if trailer_link:
            response_text += f"▶ [Watch Trailer]({trailer_link})\n"
            
        response_text += f"\n📝 {overview[:250]}..."
            
        await update.message.reply_text(response_text, parse_mode="Markdown", disable_web_page_preview=False)
        
    except Exception as e:
        await update.message.reply_text("Error: An internal technical issue occurred while fetching data.")

def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN is missing!")
        return
        
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), search_all))
    
    print("PrinceMovie Bot is running successfully.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

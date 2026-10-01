import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Render environment variables se credentials fetch karna
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Start command handler - Aapke aur aapke friends ke liye welcome message
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "Friend"
    await update.message.reply_text(
        f"Hello {user_name}! Main aapka Ultimate Entertainment Bot hoon 🎬✨\n\n"
        "Aap ya aapke friends jab bhi chahein, kisi bhi **Movie, Web Series ya Anime** ka naam yahan bhejiye. "
        "Main TMDB details, IMDb ratings, YouTube trailers aur Anime ki saari jankari ek sath dhoond kar launga! ❤️"
    )

# YouTube Trailer Link nikalne ka helper function
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

# OMDb Ratings nikalne ka helper function
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

# Main Combined Search Handler - Sabhi friends ke liye safe aur fast search
async def search_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
        
    query = update.message.text.strip()
    
    if not TMDB_API_KEY:
        await update.message.reply_text("Oops! TMDB API Key configure nahi hai Render par.")
        return

    # Typing action dikhana taaki user ko pata chale bot search kar raha hai
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # 1. Jikan API (Check if it's an Anime first)
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

    # 2. TMDB Search (Movies & TV Shows)
    tmdb_url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={requests.utils.quote(query)}"
    
    try:
        response = requests.get(tmdb_url, timeout=6)
        data = response.json()
        results = data.get("results", [])
        
        # Agar movie/series na mile toh friendly message
        if not results:
            await update.message.reply_text(f"Hmm, '{query}' naam se mujhe koi movie ya series nahi mili dost. Spelling check karke dobara try karo!")
            return
            
        # Top result pick karna
        item = results[0]
        title = item.get("title") or item.get("name", "N/A")
        release_date = item.get("release_date") or item.get("first_air_date", "N/A")
        overview = item.get("overview") or "No description available."
        tmdb_rating = item.get("vote_average", "N/A")
        
        # OMDb se extra ratings lana
        imdb_rating, box_office = get_omdb_details(title)
        
        # YouTube se Trailer link lana
        trailer_link = get_youtube_trailer(title)
        
        response_text = (
            f"🎬 **Entertainment Result:**\n\n"
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
        await update.message.reply_text("Oops! Kuch technical issue aa gaya data fetch karne mein. Thodi der baad try karna!")

def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN is missing!")
        return
        
    # Build application securely
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), search_all))
    
    print("Multi-API Entertainment Bot is running smoothly...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

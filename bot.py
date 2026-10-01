import os
import logging
import asyncio
import requests
from threading import Thread
from flask import Flask
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# 1. Logging setup
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Render Port Binding Fix (Dummy Web Server)
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "PrimeMovie Bot is alive and running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

# 3. Environment Variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY") 
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CX = os.getenv("GOOGLE_CX")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# MongoDB Setup
try:
    if MONGO_URI:
        client = MongoClient(MONGO_URI)
        db = client['primemovie_db']
        movies_collection = db['movies']
        logger.info("MongoDB Connected Successfully!")
    else:
        movies_collection = None
        logger.warning("MONGO_URI check bypassed.")
except Exception as e:
    logger.error(f"MongoDB Connection Error: {e}")
    movies_collection = None

# 📢 Telegram Channel Username
CHANNEL_USERNAME = "@Princeprm_bot" 

LANG_MAP = {
    "hi": "Hindi 🇮🇳",
    "en": "English 🇺🇸",
    "te": "Telugu 🇮🇳",
    "ta": "Tamil 🇮🇳",
    "ml": "Malayalam 🇮🇳",
    "kn": "Kannada 🇮🇳",
    "bn": "Bengali 🇮🇳"
}

# 30 minute auto-delete
async def delete_message_after_delay(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay: int = 1800):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Auto-delete failed: {e}")

# Channel subscription check (Fixed Block)
async def is_user_subscribed(bot, user_id: int) -> bool:
    if not CHANNEL_USERNAME or CHANNEL_USERNAME == "@YOUR_CHANNEL_USERNAME":
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        # अगर यूज़र चैनल छोड़कर चला गया है या ब्लॉक्ड है, केवल तभी False रिटर्न करें
        if member.status in ["left", "kicked"]:
            return False
        return True
    except Exception as e:
        logger.error(f"Subscription check error: {e}")
        # अगर कोई और एरर आता है (जैसे बोट एडमिन नहीं है), तो सुरक्षा के लिए False रखें
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    msg = (
        f"Hey 👋 {user_name} 🍿\n\n"
        f"🍿 **Welcome To PrimeMovie Multi-Language Bot!**\n\n"
        f"यहाँ आप किसी भी भाषा में Movies ढूंढ सकते हैं और YouTube वीडियो भी डाउनलोड कर सकते हैं!\n"
        f"बस नाम लिखकर भेजें या लिंक पेस्ट करें।"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# Main message handler
async def incoming_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not await is_user_subscribed(context.bot, user_id):
        invite_link = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
        keyboard = [[InlineKeyboardButton("📢 Join Channel", url=invite_link)]]
        await update.message.reply_text(
            f"❌ **Access Denied!**\n\nबोट का उपयोग करने के लिए आपको हमारे चैनल में शामिल होना होगा।",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    if "youtube.com" in text or "youtu.be" in text:
        status_msg = await update.message.reply_text("⚡ *Processing YouTube link...*", parse_mode="Markdown")
        try:
            res = requests.post("https://cobalt.tools", json={"url": text, "vQuality": "720"}).json()
            if res.get("status") in ["stream", "picker"]:
                await status_msg.delete()
                await update.message.reply_text("🎬 **Ready!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 Download", url=res.get("url"))]]))
            else:
                await status_msg.edit_text("❌ Link fetch failed.")
        except Exception:
            await status_msg.edit_text("⚠️ API Error.")
    else:
        await search_tmdb_and_show_languages(update, context, text)

# TMDB search
async def search_tmdb_and_show_languages(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
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
            await status_msg.edit_text(f"❌ '{query}' नाम की कोई मूवी नहीं मिली।")
            return
        
        item = filtered[0]
        title = item.get("title") or item.get("name")
        orig_lang = item.get("original_language", "en")
        date = (item.get("release_date") or item.get("first_air_date") or "N/A")[:4]
        
        keyboard = [
            [
                InlineKeyboardButton("Hindi 🇮🇳", callback_data=f"lang_hi_{title}_{date}"),
                InlineKeyboardButton("English 🇺🇸", callback_data=f"lang_en_{title}_{date}")
            ],
            [
                InlineKeyboardButton("Telugu 🇮🇳", callback_data=f"lang_te_{title}_{date}"),
                InlineKeyboardButton("Tamil 🇮🇳", callback_data=f"lang_ta_{title}_{date}")
            ],
            [
                InlineKeyboardButton("All Languages Mix 🌐", callback_data=f"lang_all_{title}_{date}")
            ]
        ]
        
        detected_lang = LANG_MAP.get(orig_lang, orig_lang.upper())
        await status_msg.delete()
        await update.message.reply_text(
            text=f"🎬 **Found:** `{title} ({date})`\n🗣️ **Original Language:** {detected_lang}\n\n👇 **अपनी पसंदीदा भाषा चुनें:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"TMDB Search error: {e}")
        await status_msg.edit_text("⚠️ Details fetch error.")

# Button click handler
async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("_")
    if data[0] == "lang":
        selected_lang = data[1]
        title = data[2]
        date = data[3]
        
        lang_suffix = "" if selected_lang == "all" else f"{selected_lang} dubbed"
        search_query = f"{title} {date} {lang_suffix}".strip()
        
        await query.message.edit_text(f"⏳ **Searching links for ({selected_lang.upper()})...**")
        await execute_mega_search(query.message, context, search_query, title)

# Search Architecture: MongoDB -> Google Custom Search -> YouTube Backup
async def execute_mega_search(message, context, search_query, display_title):
    movie_data = None
    
    # स्टेप 1: MongoDB डेटाबेस चेक करें
    if movies_collection is not None:
        movie_data = movies_collection.find_one({"title": {"$regex": display_title, "$options": "i"}})
    
    if movie_data:
        keyboard = [
            [InlineKeyboardButton("📥 1080p Direct Download", url=movie_data.get("link_1080", "#"))],
            [InlineKeyboardButton("📥 720p Direct Download", url=movie_data.get("link_720", "#"))]
        ]
        dl_msg = await message.reply_text(
            text=f"🚀 **{display_title}**\nडेटाबेस में डायरेक्ट लिंक्स मिल गए हैं!\n\n⚠️ यह मैसेज 30 मिनट में डिलीट हो जाएगा।",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        asyncio.create_task(delete_message_after_delay(context, message.chat_id, dl_msg.message_id, 1800))
        await message.delete()
        return

    # स्टेप 2: गूगल कस्टम सर्च (अगर DB में न मिले)
    if GOOGLE_API_KEY and GOOGLE_CX:
        try:
            google_url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={GOOGLE_CX}&q={requests.utils.quote(search_query)}"
            g_res = requests.get(google_url).json()
            items = g_res.get("items", [])
            if items:
                keyboard = []
                for item in items[:3]: # टॉप 3 रिजल्ट्स
                    title_text = item.get("title", "Link")[:30] + "..."
                    keyboard.append([InlineKeyboardButton(title_text, url=item.get("link"))])
                
                dl_msg = await message.reply_text(
                    text=f"🌐 **Web Results for {display_title}:**\nगूगल पर कुछ लिंक्स मिले हैं:\n\n⚠️ 30 मिनट में डिलीट हो जाएगा।",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
                asyncio.create_task(delete_message_after_delay(context, message.chat_id, dl_msg.message_id, 1800))
                await message.delete()
                return
        except Exception as e:
            logger.error(f"Google Search error: {e}")

    # स्टेप 3: यूट्यूब बैकअप सर्च
    if YOUTUBE_API_KEY:
        try:
            yt_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={requests.utils.quote(search_query)}&type=video&key={YOUTUBE_API_KEY}"
            yt_res = requests.get(yt_url).json()
            videos = yt_res.get("items", [])
            if videos:
                keyboard = []
                for vid in videos[:3]:
                    video_id = vid.get("id", {}).get("videoId")
                    video_title = vid.get("snippet", {}).get("title", "Video")[:30] + "..."
                    if video_id:
                        keyboard.append([InlineKeyboardButton(f"▶️ {video_title}", url=f"https://youtube.com/watch?v={video_id}")])
                
                if keyboard:
                    dl_msg = await message.reply_text(
                        text=f"📺 **YouTube Results for {display_title}:**\n\n⚠️ 30 मिनट में डिलीट हो जाएगा।",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="Markdown"
                    )
                    asyncio.create_task(delete_message_after_delay(context, message.chat_id, dl_msg.message_id, 1800))
                    await message.delete()
                    return
        except Exception as e:
            logger.error(f"YouTube Search error: {e}")

    await message.edit_text(f"❌ माफ कीजिए, '{display_title}' के लिए कोई लिंक्स नहीं मिले।")

def main():
    if not TELEGRAM_TOKEN:
        logger.error("Telegram Token is missing!")
        return

    # Flask background server start for Render
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Flask Web Server Started in Background Thread.")

    # Telegram Bot Application
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, incoming_message_handler))
    app.add_handler(CallbackQueryHandler(button_click_handler))
    
    print("PrimeMovie Web Service & Telegram Bot is running successfully...")
    app.run_polling()

if __name__ == '__main__':
    main()

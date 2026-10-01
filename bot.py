import os
import logging
import asyncio
import requests
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# Logging setup
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# All 5 Environment Variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY") 
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CX = os.getenv("GOOGLE_CX")
TMDB_API_KEY = os.getenv("TMDB_API_KEY") or "YOUR_TMDB_API_KEY" # TMDB की यहाँ भी डाल सकते हैं या Render पर

# MongoDB Setup
try:
    client = MongoClient(MONGO_URI)
    db = client['primemovie_db']
    movies_collection = db['movies']
    logger.info("MongoDB Connected Successfully!")
except Exception as e:
    logger.error(f"MongoDB Connection Error: {e}")
    movies_collection = None

# 📢 अपने टेलीग्राम चैनल का यूजरनेम यहाँ सेट करें
CHANNEL_USERNAME = "@YOUR_CHANNEL_USERNAME" 

# भाषा कोड को नाम में बदलने की डिक्शनरी
LANG_MAP = {
    "hi": "Hindi 🇮🇳",
    "en": "English 🇺🇸",
    "te": "Telugu 🇮🇳",
    "ta": "Tamil 🇮🇳",
    "ml": "Malayalam 🇮🇳",
    "kn": "Kannada 🇮🇳",
    "bn": "Bengali 🇮🇳"
}

# ऑटो-डिलीट फंक्शन (30 मिनट)
async def delete_message_after_delay(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay: int = 1800):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Auto-delete failed: {e}")

# चैनल सब्सक्रिप्शन चेक
async def is_user_subscribed(bot, user_id: int) -> bool:
    if not CHANNEL_USERNAME:
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Subscription check error: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    msg = (
        f"Hey 👋 {user_name} 🍿\n\n"
        f"🍿 **Welcome To PrimeMovie Multi-Language Bot!**\n\n"
        f"यहाँ आप किसी भी भाषा (**Hindi, English, Telugu, Tamil**) में Movies ढूंढ सकते हैं!\n"
        f"बस मूवी का नाम लिखकर भेजें।"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# मुख्य मैसेज हैंडलर
async def incoming_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not await is_user_subscribed(context.bot, user_id):
        invite_link = f"https://t.me{CHANNEL_USERNAME.replace('@', '')}"
        keyboard = [[InlineKeyboardButton("📢 Join Channel", url=invite_link)]]
        await update.message.reply_text(
            f"❌ **Access Denied!**\n\nबोट का उपयोग करने के लिए आपको हमारे चैनल में शामिल होना होगा।",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    if "youtube.com" in text or "youtu.be" in text:
        # यूट्यूब डायरेक्ट डाउनलोडर (पुरानी सेटिंग)
        status_msg = await update.message.reply_text("⚡ *Processing YouTube link...*", parse_mode="Markdown")
        try:
            res = requests.post("https://cobalt.tools", json={"url": text, "vQuality": "720"}).json()
            if res.get("status") in ["stream", "picker"]:
                await status_msg.delete()
                await update.message.reply_text("🎬 **Ready!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 Download", url=res.get("url"))]]))
            else:
                await status_msg.edit_text("❌ Link fetch failed.")
        except:
            await status_msg.edit_text("⚠️ API Error.")
    else:
        # 🆕 मूवी का नाम आने पर पहले TMDB से सर्च करके भाषा का विकल्प दिखाएंगे
        await search_tmdb_and_show_languages(update, context, text)

# TMDB से सर्च करके भाषा चुनने का प्लेटफॉर्म दिखाना
async def search_tmdb_and_show_languages(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    if not TMDB_API_KEY:
        await update.message.reply_text("Error: TMDB API Key is missing.")
        return

    status_msg = await update.message.reply_text("🔍 *Searching title details...*", parse_mode="Markdown")
    url = f"https://themoviedb.org{TMDB_API_KEY}&query={requests.utils.quote(query)}"
    
    try:
        response = requests.get(url).json()
        results = response.get("results", [])
        filtered = [r for r in results if r.get("media_type") in ["movie", "tv"]]
        
        if not filtered:
            await status_msg.edit_text(f"❌ '{query}' नाम की कोई मूवी नहीं मिली।")
            return
        
        item = filtered[0] # सबसे सटीक पहला रिज़ल्ट लेंगे
        title = item.get("title") or item.get("name")
        orig_lang = item.get("original_language", "en")
        date = (item.get("release_date") or item.get("first_air_date") or "N/A")[:4]
        
        # भाषाओं के बटन तैयार करना (यूजर को एक ही प्लेटफॉर्म पर सब दिखेगा)
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
            text=f"🎬 **Found:** `{title} ({date})`\n"
                 f"🗣️ **Original Language:** {detected_lang}\n\n"
                 f"👇 **कृपया अपनी पसंदीदा भाषा चुनें जिसमें आप डाउनलोड करना चाहते हैं:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"TMDB Search error: {e}")
        await status_msg.edit_text("⚠️ Details fetch error.")

# बटन क्लिक हैंडलर (भाषा चुनने के बाद का प्रोसेस)
async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("_")
    if data[0] == "lang":
        selected_lang = data[1]
        title = data[2]
        date = data[3]
        
        # सर्च क्वेरी को चुनी हुई भाषा के हिसाब से कस्टमाइज़ करें
        lang_suffix = "" if selected_lang == "all" else f"{selected_lang} dubbed"
        search_query = f"{title} {date} {lang_suffix}".strip()
        
        await query.message.edit_text(f"⏳ **Searching links for ({selected_lang.upper()})...**")
        await execute_mega_search(query.message, context, search_query, title)

# सर्च आर्किटेक्चर (डेटाबेस ➡️ गूगल ➡️ यूट्यूब) चुनी हुई भाषा के साथ
async def execute_mega_search(message, context, search_query, display_title):
    # 1. MongoDB चेक करें
    movie_data = None
    if movies_collection is not None:
        movie_data = movies_collection.find_one({"title": {"$regex": display_title, "$options": "i"}})
    
    if movie_data:
        keyboard = [
            [InlineKeyboardButton("📥 1080p Direct Download", url=movie_data.get("link_1080", "#"))],
            [InlineKeyboardButton("📥 720p Direct Download", url=movie_data.get("link_720", "#"))]
        ]
        dl_msg = await message.reply_text(
            text=f"🚀 **{display_title}**\nडेटाबेस में डायरेक्ट लिंक्स मिल गए हैं!\n\n⚠️ 30 मिनट में डिलीट हो जाएगा।",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        asyncio.create_task(delete_message_after_delay(context, message.chat_id, dl_msg.message_id, 1800))
        await message.delete()
        return

    # 2. Google Custom Search (अगर DB में विशिष्ट भाषा न हो)
    if GOOGLE_API_KEY and GOOGLE_CX:
        g_url = f"https://googleapis.com{GOOGLE_API_KEY}&cx={GOOGLE_CX}&q={requests.utils.quote(search_query + ' download link')}"
        try:
            res = requests.get(g_url).json()
            items = res.get("items", [])
            if items:
                keyboard = [[InlineKeyboardButton(f"🔗 {item['title'][:35]}...", url=item['link'])] for item in items[:4]]
                dl_msg = await message.reply_text(
                    text=f"🌐 **Google Links for:** _{search_query}_\n\n👇 डाउनलोड करने के लिए नीचे क्लिक करें:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
                asyncio.create_task(delete_message_after_delay(context, message.chat_id, dl_msg.message_id, 1800))
                await message.delete()
                return
        except Exception as e:
            logger.error(f"Google error: {e}")

    # 3. YouTube API (अंतिम बैकअप)
    if YOUTUBE_API_KEY:
        yt_url = f"https://googleapis.com{requests.utils.quote(search_query)}&type=video&key={YOUTUBE_API_KEY}"
        try:
            res = requests.get(yt_url).json()
            items = res.get("items", [])
            if items:
                keyboard = []
                for item in items:
                    v_id = item.get("id", {}).get("videoId")
                    v_title = item.get("snippet", {}).get("title", "")
                    if v_id:

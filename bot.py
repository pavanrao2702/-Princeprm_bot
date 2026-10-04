import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# Apne tokens yahan daalein
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TMDB_API_KEY = "YOUR_TMDB_API_KEY"

# Memory/SSL errors se bachne ke liye session pooling
session = requests.Session()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Namaste! Kisi bhi movie ya web series ka naam bhejiye, main aapko uske free aur public domain links provide karunga.")

async def search_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={requests.utils.quote(query_text)}"
    
    response = session.get(url).json()
    results = response.get("results", [])

    if not results:
        await update.message.reply_text("Koi result nahi mila. Kripya sahi naam type karein.")
        return

    keyboard = []
    for item in results[:5]:
        media_type = item.get("media_type")
        if media_type not in ["movie", "tv"]:
            continue
        
        title = item.get("title") or item.get("name")
        year = (item.get("release_date") or item.get("first_air_date") or "")[:4]
        media_id = item.get("id")
        
        display_text = f"{title} ({year})" if year else title
        keyboard.append([InlineKeyboardButton(display_text, callback_data=f"sel_{media_type}_{media_id}")])

    if not keyboard:
        await update.message.reply_text("Koi valid movie ya web series nahi mili.")
        return

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Yeh lijiye, results se apni movie ya series chuniye:", reply_markup=reply_markup)

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("sel_"):
        return

    _, media_type, media_id = data.split("_")

    detail_url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={TMDB_API_KEY}"
    detail_resp = session.get(detail_url).json()
    title = detail_resp.get("title") or detail_resp.get("name")
    year = detail_resp.get("release_date", "")[:4] or detail_resp.get("first_air_date", "")[:4] or ""

    full_title_query = f"{title} {year}" if year else title
    encoded_title = requests.utils.quote(full_title_query)
    encoded_plain_title = requests.utils.quote(title)

    # Internet Archive se exact file ya download link nikalne ki logic
    archive_api_url = f"https://archive.org/advancedsearch.php?q=title:({encoded_title}) AND mediatype:(movies)&output=json"
    archive_resp = session.get(archive_api_url).json()
    
    docs = archive_resp.get("response", {}).get("docs", [])
    direct_download_link = ""
    
    if docs:
        identifier = docs[0].get("identifier")
        meta_url = f"https://archive.org/metadata/{identifier}"
        meta_resp = session.get(meta_url).json()
        files = meta_resp.get("files", [])
        
        for file in files:
            if file.get("format", "").lower() in ["h.264", "mpeg4", "mp4", "webms"]:
                file_name = file.get("name")
                direct_download_link = f"https://archive.org/download/{identifier}/{file_name}"
                break
        
        if not direct_download_link:
            direct_download_link = f"https://archive.org/details/{identifier}"
    else:
        direct_download_link = f"https://archive.org/search.php?query={encoded_title}+mediatype%3Amovies"

    links_msg = (
        f"🎬 *{title}* ({year})\n\n"
        "📥 *Free & Public Domain Links:*\n"
        f"1. [{title} ({year}) Direct File Link]({direct_download_link})\n"
        f"2. [Public Domain Movies](https://publicdomainmovies.net/)\n"
        f"3. [Classic Cinema Online](https://www.classiccinemaonline.com/)\n"
        f"4. [{title} Official Trailer / Video](https://www.youtube.com/results?search_query={encoded_title}+official+trailer)\n"
        f"5. [Tubi TV Search](https://tubitv.com/search/{encoded_plain_title})\n\n"
        "< page 1 >"
    )

    await query.edit_message_text(links_msg, parse_mode="Markdown", disable_web_page_preview=True)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), search_media))
    app.add_handler(CallbackQueryHandler(button_callback_handler))

    print("Bot successfully start ho gaya hai...")
    app.run_polling()

if __name__ == "__main__":
    main()
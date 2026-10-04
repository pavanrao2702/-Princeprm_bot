import requests
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
TMDB_API_KEY = 'YOUR_TMDB_API_KEY'

bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
  welcome_text = (
      '👋 नमस्ते! आपका स्वागत है।\n\n'
      'किसी भी फिल्म की जानकारी के लिए टाइप करें:\n'
      '`/movie फिल्म का नाम`\n\n'
      'उदाहरण: `/movie Dhoom`'
  )
  bot.reply_to(message, welcome_text, parse_mode='Markdown')


@bot.message_handler(commands=['movie'])
def search_movie(message):
  query_parts = message.text.split(maxsplit=1)
  if len(query_parts) < 2:
    bot.reply_to(
        message,
        'कृपया मूवी का नाम लिखें। उदाहरण: `/movie Dhoom`',
        parse_mode='Markdown',
    )
    return

  movie_name = query_parts[1]
  fetch_movies_list(message.chat.id, movie_name, 'en-US', message.message_id)


def fetch_movies_list(chat_id, movie_name, lang, message_id=None):
  url = f'https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={movie_name}&language={lang}'

  try:
    response = requests.get(url)
    data = response.json()
    results = data.get('results', [])

    if not results:
      bot.send_message(
          chat_id, '❌ इस नाम से कोई मूवी नहीं मिली। कृपया दूसरा नाम ट्राय करें।'
      )
      return

    response_text = f'🎬 *"{movie_name}" से जुड़ी फिल्में:*\n\n'

    # टॉप 5 फिल्में दिखाना
    for i, movie in enumerate(results[:5], 1):
      title = movie.get('title', 'N/A')
      release_date = movie.get('release_date', 'N/A')
      year = release_date.split('-')[0] if release_date else 'N/A'
      rating = movie.get('vote_average', 'N/A')
      response_text += f'{i}. *{title}* ({year}) - ⭐ {rating}/10\n'

    # भाषा बदलने के लिए बटन (मैसेज के साथ मूवी का नाम और भाषा स्टोर की गई है)
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton(
            '🇬🇧 English', callback_data=f'lang_en_{movie_name}'
        ),
        InlineKeyboardButton('🇮🇳 हिंदी', callback_data=f'lang_hi_{movie_name}'),
    )

    response_text += '\n👇 *भाषा बदलें:*'

    if message_id:
      bot.send_message(
          chat_id, response_text, parse_mode='Markdown', reply_markup=markup
      )
    else:
      bot.send_message(
          chat_id, response_text, parse_mode='Markdown', reply_markup=markup
      )

  except Exception as e:
    bot.send_message(
        chat_id, '⚠️ कुछ तकनीकी समस्या आ गई है। कृपया थोड़ी देर बाद कोशिश करें।'
    )


# जब यूजर भाषा का बटन दबाएगा
@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def language_callback(call):
  data_parts = call.data.split('_', 2)
  lang_code = data_parts[1]  # en या hi
  movie_name = data_parts[2]  # मूवी का नाम

  # भाषा कोड को TMDB के फॉर्मेट में बदलना
  tmdb_lang = 'hi-IN' if lang_code == 'hi' else 'en-US'

  bot.answer_callback_query(
      call.id,
      f'भाषा बदली जा रही है: {"हिंदी" if lang_code=="hi" else "English"}',
  )

  # चुनी गई भाषा में दोबारा डेटा मंगाना
  url = f'https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={movie_name}&language={tmdb_lang}'

  try:
    response = requests.get(url)
    data = response.json()
    results = data.get('results', [])

    if not results:
      bot.send_message(call.message.chat.id, '❌ इस भाषा में डेटा नहीं मिला।')
      return

    movie = results[0]  # पहली फिल्म की डिटेल
    title = movie.get('title', 'N/A')
    release_date = movie.get('release_date', 'N/A')
    rating = movie.get('vote_average', 'N/A')
    overview = movie.get('overview', 'विवरण उपलब्ध नहीं है।')
    poster_path = movie.get('poster_path')

    poster_url = (
        f'https://image.tmdb.org/t/p/w500{poster_path}'
        if poster_path
        else None
    )

    reply_text = (
        f'🎬 *{title}* ({release_date})\n'
        f'⭐ *Rating:* {rating}/10\n\n'
        f'📝 *Story:* {overview}\n\n'
        '🔗 *फ्री और लीगल देखने के प्लेटफॉर्म्स:*\n'
        '• [Internet Archive](https://archive.org/details/feature_films)\n'
        '• [Open Culture](https://www.openculture.com/freemoviesonline)\n'
        '• [Tubi TV](https://tubitv.com)'
    )

    if poster_url:
      bot.send_photo(
          call.message.chat.id,
          poster_url,
          caption=reply_text,
          parse_mode='Markdown',
      )
    else:
      bot.send_message(
          call.message.chat.id, reply_text, parse_mode='Markdown'
      )

  except Exception as e:
    bot.send_message(call.message.chat.id, '⚠️ डेटा लोड करने में समस्या आई।')


print('Bot is running...')
bot.infinity_polling()

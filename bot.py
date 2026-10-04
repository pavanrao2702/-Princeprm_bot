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

  # TMDB API से इंग्लिश में सर्च (क्योंकि TMDB पर इंग्लिश डेटा सबसे सटीक होता है)
  url = f'https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={movie_name}&language=en-US'

  try:
    response = requests.get(url)
    data = response.json()
    results = data.get('results', [])

    if not results:
      bot.reply_to(
          message, '❌ इस नाम से कोई मूवी नहीं मिली। कृपया दूसरा नाम ट्राय करें।'
      )
      return

    # टॉप 5 फिल्में दिखाना
    response_text = (
        f'🎬 *"{movie_name}" से जुड़ी फिल्में (भाषा विकल्प के साथ):*\n\n'
    )

    for i, movie in enumerate(results[:5], 1):
      title = movie.get('title', 'N/A')
      release_date = movie.get('release_date', 'N/A')
      year = release_date.split('-')[0] if release_date else 'N/A'
      rating = movie.get('vote_average', 'N/A')

      response_text += f'{i}. *{title}* ({year}) - ⭐ {rating}/10\n'

    # यूजर को भाषा चुनने के लिए नीचे बटन देना
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton('🇬🇧 English', callback_data='lang_en'),
        InlineKeyboardButton('🇮🇳 हिंदी (Hindi)', callback_data='lang_hi'),
    )

    response_text += (
        '\n👇 *अपनी पसंदीदा भाषा चुनें:*\n(नोट: सभी फिल्में हर भाषा में उपलब्ध नहीं'
        ' होतीं, इसलिए सटीक जानकारी के लिए इंग्लिश सबसे बेहतर है)'
    )

    bot.reply_to(message, response_text, parse_mode='Markdown', reply_markup=markup)

  except Exception as e:
    bot.reply_to(
        message,
        '⚠️ कुछ तकनीकी समस्या आ गई है। कृपया थोड़ी देर बाद कोशिश करें।',
    )


# बटन क्लिक होने पर क्या होगा
@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def language_callback(call):
  lang = call.data.split('_')[1]
  if lang == 'hi':
    bot.answer_callback_query(
        call.id,
        'हिंदी मोड चुना गया (यदि उपलब्ध हुआ तो डेटा दिखेगा)',
        show_alert=True,
    )
  else:
    bot.answer_callback_query(call.id, 'English mode selected', show_alert=True)


print('Bot is running...')
bot.infinity_polling()

import os
from telegram.ext import ApplicationBuilder

TOKEN = os.environ.get('BOT_TOKEN')

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Yahan apne handlers ya commands add kar sakte ho
    
    print("Bot is starting...")
    application.run_polling()

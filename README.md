A little Telegram bot that tries its best to understand what you're saying.
Sometimes it understands you.
Sometimes it doesn't.
But hey, that's part of the personality. 

🧠 What does it do. 
The bot uses:
Python, python-telegram-bot, spaCy, Random responses, Some questionable conversational skills
It attempts to detect whether you're:
Asking a question ❓
Giving an instruction 🫡
Saying what you want 👀
Just talking nonsense 💀
And then responds accordingly.

🚀 Installation
Install the dependencies: pip install python-telegram-bot spacy
Download the spaCy English language model: python -m spacy download en_core_web_sm

🔑 Telegram Token
Create a file called: dotenv.py
Add your Telegram bot token: TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

Don't upload your actual token to GitHub unless you enjoy random people taking control of your bot.

▶️ Run the Bot
Simply run:python main.py

Then go to Telegram and say:/start

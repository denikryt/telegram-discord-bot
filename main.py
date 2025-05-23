import asyncio
import threading
import os
import logging
from dotenv import load_dotenv
from discord_bot import discord_client
from telegram_bot import tg_bot, run_telegram, set_discord_loop
from logging.handlers import RotatingFileHandler

load_dotenv()

# Create the logs folder if it does not exist
os.makedirs("logs", exist_ok=True)

# Remove the current app.log file when the program starts
log_file_path = os.path.join("logs", "app.log")
with open(log_file_path, 'w', encoding='utf-8'):
    pass 

# Set up log rotation
rotating_handler = RotatingFileHandler(
    log_file_path,
    maxBytes=10 * 1024 * 1024,
    backupCount=5, # Number of backup log files
    encoding='utf-8'
)

# Set up log formatting
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
rotating_handler.setFormatter(formatter)

# Set up the root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(rotating_handler)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN_TEST")

if __name__ == "__main__":
    discord_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(discord_loop)

    set_discord_loop(discord_loop)

    tg_thread = threading.Thread(target=run_telegram)
    tg_thread.start()

    discord_loop.run_until_complete(discord_client.start(DISCORD_TOKEN))

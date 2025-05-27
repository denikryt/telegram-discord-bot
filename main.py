import asyncio
import threading
import config
from dotenv import load_dotenv
from discord_bot import discord_client
from telegram_bot import tg_bot, run_telegram, set_discord_loop
from logger_setup import setup_logger 

load_dotenv()
setup_logger()

DISCORD_TOKEN = config.DISCORD_TOKEN

if __name__ == "__main__":
    discord_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(discord_loop)

    set_discord_loop(discord_loop)

    tg_thread = threading.Thread(target=run_telegram)
    tg_thread.start()

    discord_loop.run_until_complete(discord_client.start(DISCORD_TOKEN))

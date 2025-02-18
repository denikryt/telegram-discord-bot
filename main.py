import threading
import telebot
import discord
from discord import Intents, Client, Message, MessageType
from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_CHANNEL_ID =os.getenv('DISCORD_CHANNEL_ID')  
TELEGRAM_CHANNEL_ID =os.getenv('TELEGRAM_CHANNEL_ID')  

# --------- Telegram bot initialization --------- 
tg_bot = telebot.TeleBot(TELEGRAM_TOKEN)

# --------- Discord bot initialization --------- 
intents = discord.Intents.default()
intents.message_content = True 
dc_bot = commands.Bot(command_prefix="!", intents=intents)

# --------- Function for Telegram bot operations --------- 
tg_previousUserName = ''

def run_telegram():
    @tg_bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        tg_bot.reply_to(message, "Привет! Я Telegram-бот.")
    
    @tg_bot.message_handler(func=lambda message: True)
    def handle_group_messages(message):
        if message.chat.type in ['group', 'supergroup']:
            discord_loop.call_soon_threadsafe(asyncio.create_task, send_to_discord(message))

    print("Telegram-бот запущен")
    tg_bot.polling(none_stop=True)

async def send_to_discord(message):
    user_data = get_telegram_user_data(message)
    global tg_previousUserName

    if user_data['user_name'] == tg_previousUserName:
        text = f"{user_data['text']}"
    else:
        tg_previousUserName = user_data['user_name']
        text = f"**{user_data['user_name']}**\n{user_data['text']}"

    channel = await dc_bot.fetch_channel(DISCORD_CHANNEL_ID)

    if channel:
        await channel.send(text)

def get_telegram_user_data(message):
    if message:
        user_name = message.from_user.first_name
        user_id = message.chat.id
        message_id = message.message_id
        text = message.text

    return {
        'user_name': user_name, 
        'user_id': user_id,
        'message_id': message_id,
        'text': text
    }

# --------- Function for Discord bot operations --------- 

dc_previousUserName = ''

@dc_bot.event
async def on_ready():
    print(f'Logged in as {dc_bot.user}')

@dc_bot.event
async def on_message(message: Message):
    if str(message.channel.id) == DISCORD_CHANNEL_ID and not message.author.bot:
        print(f"Message from Discord: {message.content}")
        await send_to_telegram(message)

async def send_to_telegram(message):
    user_data = get_discord_user_data(message)
    global dc_previousUserName

    if user_data['user_name'] == dc_previousUserName:
        text = f"{user_data['text']}"
    else:
        dc_previousUserName = user_data['user_name']
        text = f"<b>{user_data['user_name']}</b>\n{user_data['text']}"

    tg_bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=text, parse_mode='html')

def get_discord_user_data(message):
        if message:
            user_name = message.author.name
            user_id = message.author.id
            message_id = message.id
            text = message.content

        return {
            'user_name': user_name,
            'user_id': user_id,
            'message_id': message_id,
            'text': text
        }

# --------- Run bots in separate threads --------- 

import asyncio

discord_loop = asyncio.new_event_loop()
asyncio.set_event_loop(discord_loop)

tg_thread = threading.Thread(target=run_telegram)
tg_thread.start()

discord_loop.run_until_complete(dc_bot.start(DISCORD_TOKEN))

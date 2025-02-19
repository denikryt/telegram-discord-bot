import threading
import telebot
import discord
from discord import Intents, Client, Message, MessageType
from discord.ext import commands
from dotenv import load_dotenv
import os
import json
import db
import emoji
import random

load_dotenv()

animal_emojis = [
    ":monkey_face:", ":monkey:", ":gorilla:", ":orangutan:", ":dog:", ":dog2:", ":guide_dog:", ":service_dog:", 
    ":poodle:", ":wolf:", ":fox_face:", ":raccoon:", ":cat:", ":cat2:", ":black_cat:", ":lion:", ":tiger:", ":tiger2:", 
    ":leopard:", ":horse:", ":racehorse:", ":unicorn:", ":zebra:", ":deer:", ":bison:", ":cow:", ":ox:", ":water_buffalo:", 
    ":cow2:", ":pig:", ":pig2:", ":boar:", ":pig_nose:", ":ram:", ":sheep:", ":goat:", ":dromedary_camel:", ":camel:", 
    ":llama:", ":giraffe:", ":elephant:", ":mammoth:", ":rhinoceros:", ":hippopotamus:", ":mouse:", ":mouse2:", ":rat:", 
    ":hamster:", ":rabbit:", ":rabbit2:", ":chipmunk:", ":beaver:", ":hedgehog:", ":bat:", ":bear:", ":polar_bear:", 
    ":koala:", ":panda_face:", ":sloth:", ":otter:", ":skunk:", ":kangaroo:", ":badger:", ":turkey:", ":chicken:", 
    ":rooster:", ":hatching_chick:", ":baby_chick:", ":hatched_chick:", ":bird:", ":penguin:", ":dove:", ":eagle:", 
    ":duck:", ":swan:", ":owl:", ":flamingo:", ":peacock:", ":parrot:", ":whale:", ":whale2:", ":dolphin:", ":seal:", 
    ":fish:", ":tropical_fish:", ":blowfish:", ":shark:", ":octopus:", ":shell:", ":snail:", ":butterfly:", ":bug:", 
    ":ant:", ":bee:", ":beetle:", ":lady_beetle:", ":cricket:", ":cockroach:", ":spider:", ":spider_web:", ":scorpion:", 
    ":mosquito:", ":fly:", ":worm:", ":microbe:", ":turtle:", ":snake:", ":lizard:", ":crocodile:"
]

lastUserName = ''

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

DISCORD_CHANNEL_ID =os.getenv('DISCORD_CHANNEL_ID')  
TELEGRAM_CHANNEL_ID =os.getenv('TELEGRAM_CHANNEL_ID') 

DISCORD_CHANNEL_ID_TEST =os.getenv('DISCORD_CHANNEL_ID_TEST')  
TELEGRAM_CHANNEL_ID_TEST =os.getenv('TELEGRAM_CHANNEL_ID_TEST')  

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
            if str(message.chat.id) == TELEGRAM_CHANNEL_ID:
                discord_channel = DISCORD_CHANNEL_ID
            elif str(message.chat.id) == TELEGRAM_CHANNEL_ID_TEST:
                discord_channel = DISCORD_CHANNEL_ID_TEST
            else:
                return
            
            if message.reply_to_message:
                discord_loop.call_soon_threadsafe(asyncio.create_task, send_to_discord_reply(message, discord_channel))
                return
            
            discord_loop.call_soon_threadsafe(asyncio.create_task, send_to_discord(message, discord_channel))

    print("Telegram-бот запущен")
    tg_bot.polling(none_stop=True)

async def send_to_discord_reply(message, discord_channel):
    user_data = get_telegram_user_data(message)
    reply_to_message_id = message.reply_to_message.message_id

    original_discord_message_id = db.get_discord_message_id(telegram_message_id=reply_to_message_id)

    if original_discord_message_id:
        channel = await dc_bot.fetch_channel(discord_channel)
        original_discord_message = await channel.fetch_message(original_discord_message_id)

        if original_discord_message:
            text = tg_previous_user_check(user_data)
            discord_message = await original_discord_message.reply(text)
            discord_message_id = discord_message.id
            db.save_message_to_db(telegram_message_id=user_data['message_id'], discord_message_id=discord_message_id)

async def send_to_discord(message, discord_channel):
    user_data = get_telegram_user_data(message)
    channel = await dc_bot.fetch_channel(discord_channel)

    if channel:
        text = tg_previous_user_check(user_data)
        discord_message = await channel.send(text)
        discord_message_id = discord_message.id
        db.save_message_to_db(telegram_message_id=user_data['message_id'], discord_message_id=discord_message_id)

def tg_previous_user_check(user_data):
    global tg_previousUserName
    global lastUserName

    if user_data['user_name'] == tg_previousUserName and user_data['user_name'] == lastUserName:
        return f"{user_data['text']}"
    else:
        tg_previousUserName = user_data['user_name']
        lastUserName = user_data['user_name']
        random_emoji = emoji.emojize(random.choice(animal_emojis))
        return f"{random_emoji}**{user_data['user_name']}**\n{user_data['text']}"

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
    if not message.author.bot:
        if str(message.channel.id) == DISCORD_CHANNEL_ID:
            telegram_channel = TELEGRAM_CHANNEL_ID
        elif str(message.channel.id) == DISCORD_CHANNEL_ID_TEST:
            telegram_channel = TELEGRAM_CHANNEL_ID_TEST
        else:
            return
        
        print(f"Message from Discord: {message.content}")
        if message.reference and message.reference.message_id:
            await send_to_telegram_reply(message, telegram_channel)
            return
        await send_to_telegram(message, telegram_channel)

async def send_to_telegram_reply(message, telegram_channel):
    user_data = get_discord_user_data(message)
    reply_to_message_id = message.reference.message_id
    original_telegram_message_id = db.get_telegram_message_id(discord_message_id=reply_to_message_id)

    if original_telegram_message_id:
        text = dc_previous_user_check(user_data)
        tg_message = tg_bot.send_message(chat_id=telegram_channel, text=text, parse_mode='html', reply_to_message_id=original_telegram_message_id)
        telegram_message_id = tg_message.message_id
        db.save_message_to_db(discord_message_id=user_data['message_id'], telegram_message_id=telegram_message_id)
        return
    
async def send_to_telegram(message, telegram_channel):
    user_data = get_discord_user_data(message)
    text = dc_previous_user_check(user_data)

    tg_message = tg_bot.send_message(chat_id=telegram_channel, text=text, parse_mode='html')
    telegram_message_id = tg_message.message_id
    db.save_message_to_db(discord_message_id=user_data['message_id'], telegram_message_id=telegram_message_id)

def dc_previous_user_check(user_data):
    global dc_previousUserName
    global lastUserName
    
    if user_data['user_name'] == dc_previousUserName and user_data['user_name'] == lastUserName:
        return f"{user_data['text']}"
    else:
        dc_previousUserName = user_data['user_name']
        lastUserName = user_data['user_name']
        random_emoji = emoji.emojize(random.choice(animal_emojis))
        return f"{random_emoji}<b>{user_data['user_name']}</b>\n{user_data['text']}"

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

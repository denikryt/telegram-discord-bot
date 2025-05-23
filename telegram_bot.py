import telebot
import os
import asyncio
import logging
import random
import emoji
from dotenv import load_dotenv
import db
import json
import config
import datetime

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN_TEST')

tg_bot = telebot.TeleBot(TELEGRAM_TOKEN)
config.TELEGRAM_BOT_ID = tg_bot.get_me().id
logging.info(f'Telegram bot ID: {config.TELEGRAM_BOT_ID}')

discord_loop = None

# ------------------------
# Global variables and polling
# ------------------------

def set_discord_loop(loop):
    global discord_loop
    discord_loop = loop

def run_telegram():
    logger("Telegram-бот запущен")
    tg_bot.infinity_polling(long_polling_timeout=30)

# ------------------------
# Telegram bot handlers
# ------------------------

@tg_bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    tg_bot.reply_to(message, "Привет! Я Telegram-бот.")
    logging.info(f"Sent welcome message to Telegram user {message.from_user.first_name}")

@tg_bot.message_handler(func=lambda message: True)
def handle_group_messages(message):
    if message.chat.type in ['group', 'supergroup']:
        # Load the channels mapping from the JSON file
        try:
            channels_mapping = load_channels_mapping()
        except Exception as e:
            logger(f"Error loading channels mapping: {e}")
            return
        
        # Print the message data for debugging
        logger(json.dumps(get_telegram_user_data(message), indent=2, default=str))

        # Get the Discord channel ID based on the Telegram channel ID
        discord_channel = str(channels_mapping.get(str(message.chat.id)))
        if not discord_channel:
            logger(f"Discord channel not found for Telegram channel {message.chat.id}")
            return

        # Get the collection name based on the Telegram channel ID
        collection_name = get_collection_name(str(message.chat.id))
        if not collection_name:
            logger(f"Collection not found for Telegram channel {message.chat.id}")
            return
        
        logger(f'--- Message from Telegram ---')
        # Send the message to Discord
        if message.reply_to_message:
            logger(f"Reply to message:\n{message.reply_to_message.text}")
            discord_loop.call_soon_threadsafe(asyncio.create_task, send_to_discord_reply(message, discord_channel, collection_name))
        else:
            logger(f"New message:\n{message.text}")
            discord_loop.call_soon_threadsafe(asyncio.create_task, send_to_discord(message, discord_channel, collection_name))

# ------------------------
# Helper functions
# ------------------------

async def send_to_discord_reply(message, discord_channel, collection_name):
    logger(f"--- Sending reply message to Discord ---")
    from discord_bot import discord_client

    user_data = get_telegram_user_data(message)
    reply_to_message_id = message.reply_to_message.message_id

    original_discord_message_id = db.get_discord_message_id(telegram_message_id=reply_to_message_id, collection_name=collection_name)

    if original_discord_message_id:
        channel = await discord_client.fetch_channel(discord_channel)
        original_discord_message = await channel.fetch_message(original_discord_message_id)

        if original_discord_message:
            update_last_message_user_id()
            if not check_last_message_user_id(current_user_id=str(user_data['user_id']), telegram_channel_id=str(user_data['channel_id']), discord_channel_id=discord_channel):
                avatar_emoji = emoji.emojize(random.choice(config.AVATAR_EMOJIS))
                text = f"{avatar_emoji}**{user_data['user_name']}**\n{user_data['text']}"
            else:
                text = user_data['text']

            set_last_message_user_id(user_name=user_data['user_name'], user_id=str(user_data['user_id']), channel_id=str(user_data['channel_id']))

            discord_message = await original_discord_message.reply(text)
            discord_message_id = discord_message.id

            db.save_message_to_db(telegram_message_id=user_data['message_id'], discord_message_id=discord_message_id, collection_name=collection_name)
            logger('-----------------------')
    else:
        await send_to_discord(message, discord_channel, collection_name)

async def send_to_discord(message, discord_channel, collection_name):
    logger(f"--- Sending message to Discord ---")
    from discord_bot import discord_client
    
    user_data = get_telegram_user_data(message)
    channel = await discord_client.fetch_channel(discord_channel)

    if channel:
        update_last_message_user_id()
        if not check_last_message_user_id(current_user_id=str(user_data['user_id']), telegram_channel_id=str(user_data['channel_id']), discord_channel_id=discord_channel):
            avatar_emoji = emoji.emojize(random.choice(config.AVATAR_EMOJIS))
            text = f"{avatar_emoji}**{user_data['user_name']}**\n{user_data['text']}"
        else:
            text = user_data['text']

        # logger(f"User data:\n{json.dumps(user_data, indent=2, default=str)}")

        set_last_message_user_id(user_name=user_data['user_name'], user_id=str(user_data['user_id']), channel_id=str(user_data['channel_id']))

        discord_message = await channel.send(text)
        discord_message_id = discord_message.id

        db.save_message_to_db(telegram_message_id=user_data['message_id'], discord_message_id=discord_message_id, collection_name=collection_name)
        logger('-----------------------')

def get_telegram_user_data(message):
    if message:
        user_name = message.from_user.first_name
        user_id = message.from_user.id
        message_id = message.message_id
        text = message.text
        channel_id = message.chat.id

    return {
        'user_name': user_name, 
        'user_id': user_id,
        'message_id': message_id,
        'text': text,
        'channel_id': channel_id
    }

def load_channels_mapping():
# Function to load the channels mapping from the JSON file
    try:
        file_path = os.path.abspath('channels.json')
        with open(file_path, 'r', encoding='utf-8') as f:
            channels_data = json.load(f)
        telegram_to_discord = {item['telegram_channel_id']: item['discord_channel_id'] for item in channels_data['channels_mapping']}
        return telegram_to_discord
    except Exception as e:
        logger(f'Error loading JSON from {file_path}: {str(e)}')
        raise e

def get_collection_name(telegram_channel_id):
# Function to get the collection name based on the Telegram channel ID
    try:
        file_path = os.path.abspath('channels.json')
        with open(file_path, 'r', encoding='utf-8') as f:
            channels_data = json.load(f)
        collection_mapping = {item['telegram_channel_id']: item['db_collection'] for item in channels_data['channels_mapping']}
        collection_name = collection_mapping.get(telegram_channel_id)
        return collection_name
    except Exception as e:
        logger(f'Error loading JSON from {file_path}: {str(e)}')
        raise e
    
# ------------------------
# Functions to check and set last message user ID
# ------------------------

def check_last_message_user_id(current_user_id:str, telegram_channel_id:str, discord_channel_id:str):
    # Function to check if the last message user ID is the same as the current user ID

    if telegram_channel_id in config.TELEGRAM_CHANNEL_LAST_USER:
        telegram_channel_last_user_id = config.TELEGRAM_CHANNEL_LAST_USER[telegram_channel_id]['user_id']
        if telegram_channel_last_user_id == current_user_id:
            logger(f'In this telegram channel, the last message was sent by the same user: {telegram_channel_last_user_id}')

            if str(discord_channel_id) in config.DISCORD_CHANNEL_LAST_USER:
                discord_channel_last_user_id = config.DISCORD_CHANNEL_LAST_USER[str(discord_channel_id)]['user_id']
                logger(f'Last message user ID in discord channel: {discord_channel_last_user_id}')
                if discord_channel_last_user_id == str(config.DISCORD_BOT_ID):
                    logger(f'Discord bot was the last user: {discord_channel_last_user_id}')
                    return True
                else:
                    logger(f'Discord bot was not the last user: {discord_channel_last_user_id}')
                    return False
            else:
                if config.TELEGRAM_CHANNEL_LAST_USER[telegram_channel_id]['timestamp'] > (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)):
                    # Check if the last message was sent less than 1 second ago
                    logger(f'New message was sent after less than 1 second from last message')
                    return True
                else:
                    logger(f'No channel {discord_channel_id} found in DISCORD_CHANNEL_LAST_USER: \n{json.dumps(config.DISCORD_CHANNEL_LAST_USER, indent=2, default=str)}')
                    return False
        else:
            logger(f'In this telegram channel, the last message was sent by a different user: {telegram_channel_last_user_id}')
            return False
    else:
        logger(f'No channel {telegram_channel_id} found in TELEGRAM_CHANNEL_LAST_USER')
        return False

def set_last_message_user_id(user_name:str, user_id:str, channel_id:str):
    # Function to set the last message user ID in the config
    config.TELEGRAM_CHANNEL_LAST_USER[channel_id] = {'user_id': user_id, 'timestamp': datetime.datetime.now(datetime.timezone.utc)}
    
    # --- printing for debugging ---
    logger(f'Telegram last message user ID set for channel: {channel_id} by user: {user_name}')
    logger(f'Telegram last message user ID dict: \n{json.dumps(config.TELEGRAM_CHANNEL_LAST_USER, indent=2, default=str)}')

def update_last_message_user_id():
    # Function to update the last message user ID in the config
    for channel_id in list(config.TELEGRAM_CHANNEL_LAST_USER.keys()):
        if config.TELEGRAM_CHANNEL_LAST_USER[channel_id]['timestamp'] < (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)):
            del config.TELEGRAM_CHANNEL_LAST_USER[channel_id]

            # --- printing for debugging ---
            logger(f'Last message user ID deleted for telegram channel: {channel_id}')
    logger(f'Updated telegram last message user ID dict: \n{json.dumps(config.TELEGRAM_CHANNEL_LAST_USER, indent=2, default=str)}')

def logger(log_text):
    print(log_text)
    logging.info(log_text)
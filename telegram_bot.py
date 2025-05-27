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
import telegram_media
import discord

load_dotenv()

tg_bot = telebot.TeleBot(config.TELEGRAM_TOKEN)
config.TELEGRAM_BOT_ID = tg_bot.get_me().id
logging.info(f'Telegram bot ID: {config.TELEGRAM_BOT_ID}')

discord_loop = None

# ------------------------
# Global discord_loop variable initialization and polling
# ------------------------

def set_discord_loop(loop):
    global discord_loop
    discord_loop = loop

def run_telegram():
    logger("Telegram-бот запущен")
    while True:
        try:
            tg_bot.infinity_polling(long_polling_timeout=30, timeout=60)
        except Exception as e:
            logger(f"Ошибка в polling Telegram: \n{e}")
            import time
            time.sleep(5)

# ------------------------
# Telegram bot handlers
# ------------------------

@tg_bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    text = config.WELCOME_MESSAGE
    tg_bot.reply_to(message, text)
    logging.info(f"Sent welcome message to Telegram user {message.from_user.first_name}")

@tg_bot.message_handler(content_types=['text'])
def handle_text_from_group(message):
    if message.chat.type not in ['group', 'supergroup']:
        return
    try:
        discord_channel, collection_name = get_discord_channel_and_collection(message)
    except Exception as e:
        logger('Error while extracting Discord channel and collection name')
        return
    
    logger(f'--- Message from Telegram ---')
    logger(json.dumps(get_telegram_user_data(message), indent=2, ensure_ascii=False, default=str))
   
    if message.reply_to_message:
        discord_loop.call_soon_threadsafe(
            asyncio.create_task, 
            send_message_to_discord_reply(message, discord_channel, collection_name))
    else:
        discord_loop.call_soon_threadsafe(
            asyncio.create_task, 
            send_message_to_discord(message, discord_channel, collection_name, media_files=None))

@tg_bot.message_handler(content_types=['photo', 'video', 'document', 'audio', 'voice'])
def handle_media_from_group(message):
    if message.chat.type not in ['group', 'supergroup']:
        return
    try:
        discord_channel, collection_name = get_discord_channel_and_collection(message)
    except Exception as e:
        logger('Error while extracting Discord channel and collection name')
        return
    
    logger(f'--- Message with media from Telegram ---')
    logger(json.dumps(get_telegram_user_data(message), indent=2, ensure_ascii=False, default=str))

    try:
        media_files = telegram_media.get_media_files(message, tg_bot)
    except ValueError as e:
        logger(f"Error while extracting media files: {e}")

        message.text = 'Error download media files from Telegram'
        discord_loop.call_soon_threadsafe(
            asyncio.create_task, 
            send_message_to_discord(message, discord_channel, collection_name))
        return

    if media_files:
        if message.reply_to_message:
            discord_loop.call_soon_threadsafe(
            asyncio.create_task,
            send_media_to_discord_reply(message, discord_channel, collection_name, media_files))
        else:
            discord_loop.call_soon_threadsafe(
                asyncio.create_task,
                send_media_to_discord(message, discord_channel, collection_name, media_files))
    else:
        logger("-- No media files to send")

@tg_bot.message_handler(content_types=['sticker'])
def handle_sticker(message):
    if message.chat.type not in ['group', 'supergroup']:
        return
    try:
        discord_channel, collection_name = get_discord_channel_and_collection(message)
    except Exception as e:
        logger('Error while extracting Discord channel and collection name')
        return
    
    logger(f'--- Sticker from Telegram ---')
    logger(json.dumps(get_telegram_user_data(message), indent=2, ensure_ascii=False, default=str))
    
    sticker = message.sticker
    if sticker.is_animated:
        logger("-- This is animated sticker")

        message.text = 'There is an animated sticker in telegram message'

        discord_loop.call_soon_threadsafe(
            asyncio.create_task, 
            send_message_to_discord(message, discord_channel, collection_name, media_files=None))
        return

    elif sticker.is_video:
        logger("-- This is video sticker (.webm)")

        message.text = 'There is an animated sticker in telegram message'

        discord_loop.call_soon_threadsafe(
            asyncio.create_task, 
            send_message_to_discord(message, discord_channel, collection_name, media_files=None))
        return
    
    else:
        logger("-- This is regular static sticker (.webp)")
        try:
            media_files = telegram_media.get_media_files(message, tg_bot)
        except ValueError as e:
            logger(f"Error while extracting media files: {e}")
            return
        
        if media_files:
            if message.reply_to_message:
                discord_loop.call_soon_threadsafe(
                asyncio.create_task,
                send_media_to_discord_reply(message, discord_channel, collection_name, media_files))
            else:
                discord_loop.call_soon_threadsafe(
                    asyncio.create_task,
                    send_media_to_discord(message, discord_channel, collection_name, media_files))
        else:
            logger("-- No media files to send")

# ------------------------
# Functions to send messages to Discord
# ------------------------

async def send_message_to_discord_reply(message, discord_channel, collection_name):
    logger(f"--- Sending reply message to Discord ---")
    from discord_bot import discord_client

    user_data = get_telegram_user_data(message)
    reply_to_message_id = message.reply_to_message.message_id
    logger(f"Reply to message ID: {reply_to_message_id}")

    original_discord_message_id = db.get_discord_message_id(telegram_message_id=reply_to_message_id, collection_name=collection_name)
    logger(f"Original Discord message ID: {original_discord_message_id}")

    if original_discord_message_id:
        channel = await discord_client.fetch_channel(discord_channel)
        logger(f"Discord channel fetched: {channel.id}")
        
        try:
            original_discord_message = await channel.fetch_message(original_discord_message_id)
            logger(f"Original Discord message fetched: {original_discord_message.id}")
        
            if original_discord_message:
                update_last_message_user_id()
                if not check_last_message_user_id(current_user_id=str(user_data['user_id']), telegram_channel_id=str(user_data['channel_id']), discord_channel_id=discord_channel):
                    avatar_emoji = emoji.emojize(random.choice(config.AVATAR_EMOJIS))
                    text = f"{avatar_emoji} **{user_data['user_name']}**\n{user_data['text']}"
                else:
                    text = user_data['text']

                set_last_message_user_id(user_name=user_data['user_name'], user_id=str(user_data['user_id']), channel_id=str(user_data['channel_id']))

                discord_message = await original_discord_message.reply(text)
                discord_message_id = discord_message.id

                db.save_message_to_db(telegram_message_id=user_data['message_id'], discord_message_id=discord_message_id, collection_name=collection_name)
                logger('-----------------------')

        except Exception as e:
            logger(f"Error fetching original Discord message: {e}")
    else:
        await send_message_to_discord(message, discord_channel, collection_name)

async def send_message_to_discord(message, discord_channel, collection_name):
    logger(f"--- Sending message to Discord ---")
    from discord_bot import discord_client
    
    user_data = get_telegram_user_data(message)
    channel = await discord_client.fetch_channel(discord_channel)

    if channel:
        update_last_message_user_id()
        if not check_last_message_user_id(current_user_id=str(user_data['user_id']), telegram_channel_id=str(user_data['channel_id']), discord_channel_id=discord_channel):
            avatar_emoji = emoji.emojize(random.choice(config.AVATAR_EMOJIS))
            text = f"{avatar_emoji} **{user_data['user_name']}**\n{user_data['text']}"
        else:
            text = user_data['text']

        set_last_message_user_id(user_name=user_data['user_name'], user_id=str(user_data['user_id']), channel_id=str(user_data['channel_id']))

        discord_message = await channel.send(text)
        discord_message_id = discord_message.id

        db.save_message_to_db(telegram_message_id=user_data['message_id'], discord_message_id=discord_message_id, collection_name=collection_name)
        logger('-----------------------')

# ------------------------
# Functions to send media files to Discord
# ------------------------

async def send_media_to_discord(message, discord_channel, collection_name, media_files=None):
    logger(f"--- Sending message with media to Discord ---")
    from discord_bot import discord_client

    user_data = get_telegram_user_data(message)
    channel = await discord_client.fetch_channel(discord_channel)
    files = get_files(media_files)

    if channel:
        update_last_message_user_id()
        if not check_last_message_user_id(current_user_id=str(user_data['user_id']), telegram_channel_id=str(user_data['channel_id']), discord_channel_id=discord_channel):
            avatar_emoji = emoji.emojize(random.choice(config.AVATAR_EMOJIS))
            if user_data['caption']:
                text = f"{avatar_emoji} **{user_data['user_name']}**\n{user_data['caption']}"
            else:
                text = f"{avatar_emoji} **{user_data['user_name']}**"
        else:
            text = user_data['caption']

        set_last_message_user_id(user_name=user_data['user_name'], user_id=str(user_data['user_id']), channel_id=str(user_data['channel_id']))

        discord_message = await channel.send(content=text, files=files)
        discord_message_id = discord_message.id

        telegram_media.clean_media_files(media_files)
        db.save_message_to_db(telegram_message_id=user_data['message_id'], discord_message_id=discord_message_id, collection_name=collection_name)
        logger('-----------------------')

async def send_media_to_discord_reply(message, discord_channel, collection_name, media_files=None):
    logger(f"--- Sending reply message with media to Discord ---")
    from discord_bot import discord_client

    user_data = get_telegram_user_data(message)
    reply_to_message_id = message.reply_to_message.message_id
    logger(f"Reply to message ID: {reply_to_message_id}")

    original_discord_message_id = db.get_discord_message_id(telegram_message_id=reply_to_message_id, collection_name=collection_name)
    logger(f"Original Discord message ID: {original_discord_message_id}")
    
    files = get_files(media_files)

    if original_discord_message_id:
        channel = await discord_client.fetch_channel(discord_channel)
        logger(f"Discord channel fetched: {channel.id}")
        
        try:
            original_discord_message = await channel.fetch_message(original_discord_message_id)
            logger(f"Original Discord message fetched: {original_discord_message.id}")
        
            if original_discord_message:
                update_last_message_user_id()
                if not check_last_message_user_id(current_user_id=str(user_data['user_id']), telegram_channel_id=str(user_data['channel_id']), discord_channel_id=discord_channel):
                    avatar_emoji = emoji.emojize(random.choice(config.AVATAR_EMOJIS))
                    if user_data['caption']:
                        text = f"{avatar_emoji} **{user_data['user_name']}**\n{user_data['caption']}"
                    else:
                        text = f"{avatar_emoji} **{user_data['user_name']}**"
                else:
                    text = user_data['caption']

                set_last_message_user_id(user_name=user_data['user_name'], user_id=str(user_data['user_id']), channel_id=str(user_data['channel_id']))

                discord_message = await original_discord_message.reply(content=text, files=files)
                discord_message_id = discord_message.id

                telegram_media.clean_media_files(media_files)
                db.save_message_to_db(telegram_message_id=user_data['message_id'], discord_message_id=discord_message_id, collection_name=collection_name)
                logger('-----------------------')

        except Exception as e:
            logger(f"Error fetching original Discord message: {e}")
    else:
        await send_media_to_discord(message, discord_channel, collection_name, media_files=media_files)

# ------------------------

def get_files(media_files):
    if media_files:
        files = []
        for file_path in media_files:
            try:
                files.append(discord.File(file_path))
            except Exception as e:
                print(f"Failed to attach file {file_path}: {e}")
        return files
    else:
        return None

def get_discord_channel_and_collection(message):
    try:
        channels_mapping = load_channels_mapping()
    except Exception as e:
        logger(f"Error loading channels mapping: {e}")
        raise

    discord_channel = str(channels_mapping.get(str(message.chat.id)))
    if not discord_channel:
        error_msg = f"Discord channel not found for Telegram channel {message.chat.id} named {message.chat.title}"
        logger(error_msg)
        raise ValueError(error_msg)

    collection_name = get_collection_name(str(message.chat.id))
    if not collection_name:
        error_msg = f"Collection not found for Telegram channel {message.chat.id} named {message.chat.title}"
        logger(error_msg)
        raise ValueError(error_msg)

    return discord_channel, collection_name

def get_telegram_user_data(message):
    if message:
        user_name = message.from_user.first_name
        user_id = message.from_user.id
        message_id = message.message_id
        text = message.text
        channel_id = message.chat.id
        channel_name = message.chat.title
        caption = message.caption

    return {
        'user_name': user_name, 
        'user_id': user_id,
        'message_id': message_id,
        'text': text,
        'channel_id': channel_id,
        'channel_name': channel_name,
        'caption': caption
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
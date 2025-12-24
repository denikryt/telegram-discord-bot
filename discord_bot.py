import threading
import time
import discord
from discord import Intents, Client, Message, MessageType
from discord.ext import commands
import os
import db
import asyncio
import emoji
import random
import config
import json
import datetime
import logging
from io import BytesIO
import telebot
# from telebot.types import InputFile
from PIL import Image
import pillow_heif
import io
from hackbridge_formatter import hackbridge_header_handler

intents = Intents.default()
intents.message_content = True
discord_client = Client(intents=intents)

discord_loop = asyncio.get_event_loop()

# ------------------------
# Event handlers for Discord bot
# ------------------------

@discord_client.event
async def on_ready():
    config.DISCORD_BOT_ID = discord_client.user.id
    logger(f'Logged in as {discord_client.user}')
    logger(f'Discord bot ID: {config.DISCORD_BOT_ID}')

@discord_client.event
async def on_message(message):
    user_data = get_discord_user_data(message)

    if message.author == discord_client.user:
        logger('--- Message from discord bot')
        update_last_message_user_id()
        set_last_message_user_id(user_id=str(user_data['user_id']), channel_id=str(user_data['channel_id']))

        return json.dumps({"status":"ignored"})

    # Load the channels mapping from the JSON file
    try:
        channels_mapping = load_channels_mapping()
    except Exception as e:
        logger(f"Error loading channels mapping: {e}")
        return
    
    # Get the Telegram channel ID based on the Discord channel ID
    telegram_channel = channels_mapping.get(str(message.channel.id))
    if not telegram_channel:
        logger(f"Telegram channel ID not found for Discord channel ID: {message.channel.id}")
        return

    # Get the collection name based on the Telegram channel ID
    collection_name = get_collection_name(telegram_channel)
    if not collection_name:
        logger(f"Collection name not found for channel ID: {telegram_channel}")
        return
        
    logger(f"--- Message from Discord ---")
    logger(f"Collection name: {collection_name}")
    # Print the message data for debugging
    logger(json.dumps(get_discord_user_data(message), indent=2, default=str))

    # Send the message to Telegram
    if message.reference and message.reference.message_id:        
        update_last_message_user_id()
        await send_to_telegram_reply(message, telegram_channel, collection_name)
        set_last_message_user_id(user_id=str(user_data['user_id']), channel_id=str(user_data['channel_id']))
        set_telegram_last_user_id(user_id=str(config.TELEGRAM_BOT_ID), channel_id=str(telegram_channel))
    else:        
        update_last_message_user_id()
        await send_to_telegram(message, telegram_channel, collection_name)
        set_last_message_user_id(user_id=str(user_data['user_id']), channel_id=str(user_data['channel_id']))
        set_telegram_last_user_id(user_id=str(config.TELEGRAM_BOT_ID), channel_id=str(telegram_channel))

# ------------------------
# Functions to send messages to Telegram
# ------------------------

async def send_to_telegram_reply(message: Message, telegram_channel, collection_name):
    logger(f"--- Sending reply message to Telegram ---")
    from telegram_bot import tg_bot

    user_data = get_discord_user_data(message)
    text, disable_preview = get_text_and_options(message, user_data, telegram_channel)
    reply_to_message_id = message.reference.message_id
    original_telegram_message_id = db.get_telegram_message_id(
        discord_message_id=reply_to_message_id,
        collection_name=collection_name
    )

    if not original_telegram_message_id:
        await send_to_telegram(message, telegram_channel, collection_name)
        return

    try:
        if message.attachments:
            logger(f'--- Reply message has {len(message.attachments)} attachments ---')
            for attachment in message.attachments:
                tg_message = await process_attachment(attachment, text, telegram_channel, reply_to=original_telegram_message_id)
                if tg_message:
                    db.save_message_to_db(
                        discord_message_id=user_data['message_id'],
                        telegram_message_id=tg_message.message_id,
                        collection_name=collection_name
                    )
                    time.sleep(1)
                else:
                    fallback_text = f'{text}\n<code>Failed to send attachment: {attachment.filename}</code>'
                    tg_bot.send_message(
                        chat_id=telegram_channel,
                        text=fallback_text,
                        parse_mode='html',
                        disable_web_page_preview=disable_preview,
                        reply_to_message_id=original_telegram_message_id
                    )
        else:
            tg_message = tg_bot.send_message(
                chat_id=telegram_channel,
                text=text,
                parse_mode='html',
                disable_web_page_preview=disable_preview,
                reply_to_message_id=original_telegram_message_id
            )
            db.save_message_to_db(
                discord_message_id=user_data['message_id'],
                telegram_message_id=tg_message.message_id,
                collection_name=collection_name
            )
    except Exception as e:
        logger(f'Error sending reply message: {e}')

async def send_to_telegram(message, telegram_channel, collection_name):
    logger("--- Sending message to Telegram ---")
    from telegram_bot import tg_bot

    user_data = get_discord_user_data(message)
    text, disable_preview = get_text_and_options(message, user_data, telegram_channel)

    if message.attachments:
        logger(f'--- Message has {len(message.attachments)} attachments')
        for attachment in message.attachments:
            tg_message = await process_attachment(attachment, text, telegram_channel)
            if tg_message:
                db.save_message_to_db(
                    discord_message_id=user_data['message_id'],
                    telegram_message_id=tg_message.message_id,
                    collection_name=collection_name
                )
                time.sleep(1)
            else:
                fallback_text = f'{text}\n<code>Failed to send attachment: {attachment.filename}</code>'
                tg_bot.send_message(
                    chat_id=int(telegram_channel),
                    text=fallback_text,
                    parse_mode='html',
                    disable_web_page_preview=disable_preview
                )
    else:
        tg_message = tg_bot.send_message(
            chat_id=int(telegram_channel),
            text=text,
            parse_mode='html',
            disable_web_page_preview=disable_preview
        )
        db.save_message_to_db(
            discord_message_id=user_data['message_id'],
            telegram_message_id=tg_message.message_id,
            collection_name=collection_name
        )
# ------------------------
# Helper functions
# ------------------------

def set_telegram_last_user_id(user_id:str, channel_id:str):
    # Set the last message user ID for the current channel
    config.TELEGRAM_CHANNEL_LAST_USER[channel_id] = {'user_id': user_id, 'timestamp': datetime.datetime.now(datetime.timezone.utc)}
    
    # --- loggering for debugging ---
    logger(f'Telegram Last message user ID set: {user_id} for channel: {channel_id}')
    logger(f'Telegram Last message user ID dict: \n{json.dumps(config.TELEGRAM_CHANNEL_LAST_USER, indent=2, default=str)}')
    logger('-----------------------')


async def process_attachment(attachment, text, telegram_channel, reply_to=None):
    logger(f'-- Processing attachment: {attachment.filename} ({attachment.content_type})')
    from telegram_bot import tg_bot

    file_bytes = await attachment.read()
    file_name = attachment.filename
    content_type = attachment.content_type or ''

    try:
        tg_file = telebot.types.InputFile(BytesIO(file_bytes))
    except Exception as e:
        logger(f'Error creating InputFile for {file_name}: {e}')
        return None

    try:
        if file_name.lower().endswith(".heic"):
            tg_file = await convert_heic_to_jpeg(file_bytes)
    except Exception as e:
        logger(f'Error preparing file {file_name}: {e}')
        return None

    try:
        if content_type.startswith("image/"):
            logger(f'-- Sending image: {file_name}')
            return tg_bot.send_photo(chat_id=int(telegram_channel), photo=tg_file, caption=text, parse_mode='html', reply_to_message_id=reply_to)
        elif content_type.startswith("video/"):
            logger(f'-- Sending video: {file_name}')
            return tg_bot.send_video(chat_id=int(telegram_channel), video=tg_file, caption=text, parse_mode='html', reply_to_message_id=reply_to)
        else:
            logger(f'-- Sending document: {file_name}')
            return tg_bot.send_document(chat_id=int(telegram_channel), document=tg_file, caption=text, parse_mode='html', reply_to_message_id=reply_to)
    except Exception as e:
        logger(f'Error sending file {file_name}: {e}')
        return None

def get_text(message, user_data, telegram_channel):
    text = format_mentions(message)
    
    if not check_last_message_user_id(
        current_user_id=str(user_data['user_id']),
        telegram_channel_id=str(telegram_channel),
        discord_channel_id=str(user_data['channel_id'])
    ):
        avatar_emoji = emoji.emojize(random.choice(config.AVATAR_EMOJIS))
        return f"{avatar_emoji} <b>{user_data['user_name']}</b>\n{text}"
    return text

def format_mentions(message):
    user_message = str(message.content)
    mentions = message.mentions
    if mentions:
        logger('Mentions were found!')
        for mention in mentions:
            user_message = user_message.replace(f'<@{mention.id}>', f'<b><i>{mention.display_name}</i></b>')
        return user_message
    else:
        logger('Mentions were not found!')
        return user_message

def get_text_and_options(message, user_data, telegram_channel):
    # HackBridge header handler: rewrite formatted headers from the HackBridge bot and drop link previews
    hackbridge_payload = hackbridge_header_handler(message)
    if hackbridge_payload:
        return hackbridge_payload["text"], hackbridge_payload["disable_preview"]
    return get_text(message, user_data, telegram_channel), False

async def convert_heic_to_jpeg(file_bytes: bytes) -> BytesIO:
    heif_file = pillow_heif.read_heif(file_bytes)
    image = Image.frombytes(
        heif_file.mode, 
        heif_file.size, 
        heif_file.data,
        "raw"
    )
    output = BytesIO()
    image.save(output, format='JPEG')
    output.seek(0)
    return output

def get_discord_user_data(message):
    if message:
        user_name = message.author.display_name
        user_id = message.author.id
        message_id = message.id
        text = message.content
        channel_id = message.channel.id

    return {
        'user_name': user_name,
        'user_id': user_id,
        'message_id': message_id,
        'text': text,
        'channel_id': channel_id
    }

def load_channels_mapping():
# Function to get the Telegram channel ID based on the Discord channel ID
    try:    
        file_path = os.path.abspath('channels.json')
        with open(file_path, 'r', encoding='utf-8') as f:
            channels_data = json.load(f)
        discord_to_telegram = {item['discord_channel_id']: item['telegram_channel_id'] for item in channels_data['channels_mapping']}
        return discord_to_telegram
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

    if discord_channel_id in config.DISCORD_CHANNEL_LAST_USER:
        discord_channel_last_user_id = config.DISCORD_CHANNEL_LAST_USER[discord_channel_id]['user_id']
        if discord_channel_last_user_id == current_user_id:
            logger(f'In this discord channel, the last message was sent by the same user: {discord_channel_last_user_id}')

            if telegram_channel_id in config.TELEGRAM_CHANNEL_LAST_USER:
                telegram_channel_last_user_id = config.TELEGRAM_CHANNEL_LAST_USER[telegram_channel_id]['user_id']
                logger(f'Last message user ID in telegram channel: {telegram_channel_last_user_id}')
                if telegram_channel_last_user_id == str(config.TELEGRAM_BOT_ID):
                    logger(f'Telegram bot was the last user: {telegram_channel_last_user_id}')
                    return True
                else:   
                    logger(f'Telegram bot was not the last user: {telegram_channel_last_user_id}')
                    return False
            else:
                if config.DISCORD_CHANNEL_LAST_USER[discord_channel_id]['timestamp'] > (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)):
                    # Check if the last message was sent less than 1 second ago
                    logger(f'New message was sent after less than 1 second from last message')
                    return True
                else:
                    logger(f'No channel found in TELEGRAM_CHANNEL_LAST_USER: \n{json.dumps(config.TELEGRAM_CHANNEL_LAST_USER, indent=2, default=str)}')
                    return False
        else:
            logger(f'In this discord channel, the last message was sent by a different user: {discord_channel_last_user_id}')
            return False
    else:
        logger(f'No channel {discord_channel_id} found in DISCORD_CHANNEL_LAST_USER')
        return False
    
def set_last_message_user_id(user_id:str, channel_id:str):
    # Set the last message user ID for the current channel
    config.DISCORD_CHANNEL_LAST_USER[channel_id] = {'user_id': user_id, 'timestamp': datetime.datetime.now(datetime.timezone.utc)}
    
    # --- loggering for debugging ---
    logger(f'Discord Last message user ID set: {user_id} for channel: {channel_id}')
    logger(f'Discord Last message user ID dict: \n{json.dumps(config.DISCORD_CHANNEL_LAST_USER, indent=2, default=str)}')

def update_last_message_user_id():
    # delete expired object by timestamp after 1 minute 
    for key in list(config.DISCORD_CHANNEL_LAST_USER.keys()):
        if config.DISCORD_CHANNEL_LAST_USER[key]['timestamp'] < (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)):
            del config.DISCORD_CHANNEL_LAST_USER[key]

            # --- loggering for debugging ---
            channel_id = key
            logger(f'Last message user ID deleted for discord channel: {channel_id}')
    logger(f'Updated discord last message user ID dict: \n{json.dumps(config.DISCORD_CHANNEL_LAST_USER, indent=2, default=str)}')

def logger(log_text):
    print(log_text)
    logging.info(log_text)

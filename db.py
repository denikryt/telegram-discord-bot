from pymongo import MongoClient
import logging
import os

# MongoDB configuration
MONGO_DB = os.environ.get('MONGO_DB')
mongo_client = MongoClient(MONGO_DB)  
db = mongo_client['HACKLAB']
messages_collection = db['Telegram-Discord-NU']

def save_message_to_db(telegram_message_id, discord_message_id):
    messages_collection.insert_one({
        "telegram_message_id": telegram_message_id,
        "discord_message_id": discord_message_id
    })
    # logger(f'Message saved to database: {telegram_message_id:} : {discord_message_id}')

def get_discord_message_id(telegram_message_id):
    result = messages_collection.find_one({"telegram_message_id": telegram_message_id})
    if result:
        # logger("Discord message ID have been found for this Slack message ID")
        return result['discord_message_id']
    # logger("Discord message ID not found for this Slack message ID")
    raise KeyError("Discord message ID not found for this Telegram message ID")

def get_telegram_message_id(discord_message_id):
    result = messages_collection.find_one({"discord_message_id": discord_message_id})
    if result:
        # logger("Discord message ID have been found for this Slack message ID")
        return result['telegram_message_id']
    # logger("Discord message ID not found for this Slack message ID")
    raise KeyError("Telegram message ID not found for this Discord message ID")

def logger(log_text):
    print(log_text)
    # logging.info(log_text)
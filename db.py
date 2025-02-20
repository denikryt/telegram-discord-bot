from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import logging
import os
import logging

# Configure logging to overwrite logs by new running of the script
logging.basicConfig(filename='app.log', filemode='w', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

# MongoDB configuration
MONGO_DB = os.environ.get('MONGO_DB')
mongo_client = MongoClient(MONGO_DB, server_api=ServerApi('1'), serverSelectionTimeoutMS=60000)  
db = mongo_client['HACKLAB']
messages_collection = db['Telegram-Discord-NU']

def ping_mongo():
    try:
        mongo_client.admin.command('ping')
        logger("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        logger(e)
        raise e

def save_message_to_db(telegram_message_id, discord_message_id):
    messages_collection.insert_one({
        "telegram_message_id": telegram_message_id,
        "discord_message_id": discord_message_id
    })
    logger(f'Message saved to database: {telegram_message_id:} : {discord_message_id}')

def get_discord_message_id(telegram_message_id):
    result = messages_collection.find_one({"telegram_message_id": telegram_message_id})
    if result:
        logger("Discord message ID have been found for this Telegram message ID")
        return result['discord_message_id']
    logger("Discord message ID not found for this Telegram message ID")
    raise KeyError("Discord message ID not found for this Telegram message ID")

def get_telegram_message_id(discord_message_id):
    result = messages_collection.find_one({"discord_message_id": discord_message_id})
    if result:
        logger("Telegram message ID have been found for this Discord message ID")
        return result['telegram_message_id']
    logger("Telegram message ID not found for this Discord message ID")
    raise KeyError("Telegram message ID not found for this Discord message ID")

def drop_collection():
    messages_collection.drop()
    logger("Collection dropped")

def logger(log_text):
    print(log_text)
    logging.info(log_text)

ping_mongo()
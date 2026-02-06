from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import logging
import os

load_dotenv()

# MongoDB configuration
# Support legacy env name MONGO_DB to avoid localhost fallback.
MONGO_URI = os.environ.get('MONGO_URI') or os.environ.get('MONGO_DB')

if not MONGO_URI:
    raise ValueError("Missing MongoDB connection string. Set MONGO_URI in .env (or MONGO_DB for legacy).")

mongo_client = MongoClient(MONGO_URI, server_api=ServerApi('1'), serverSelectionTimeoutMS=60000)
db = mongo_client['telegram-discord-bot']

def ping_mongo():
    try:
        mongo_client.admin.command('ping')
    except Exception as e:
        logging.error("Error connecting to MongoDB", exc_info=True)
        raise

def save_message_to_db(telegram_message_id, discord_message_id, collection_name):
    # Check if collection exists, if not create it
    if collection_name not in db.list_collection_names():
        create_collection(collection_name)

    messages_collection = db[collection_name]
    try:
        messages_collection.insert_one({
            "telegram_message_id": telegram_message_id,
            "discord_message_id": discord_message_id
        })
    except Exception as e:
        logging.error("Error saving message to database", exc_info=True)
    
def get_discord_message_id(telegram_message_id, collection_name):
    # Check if collection exists, if not create it
    if collection_name not in db.list_collection_names():
        create_collection(collection_name)

    messages_collection = db[collection_name]
    result = messages_collection.find_one({"telegram_message_id": telegram_message_id})
    if result:
        return result['discord_message_id']
    return None

def get_telegram_message_id(discord_message_id, collection_name):
    # Check if collection exists, if not create it
    if collection_name not in db.list_collection_names():
        create_collection(collection_name)

    messages_collection = db[collection_name]
    result = messages_collection.find_one({"discord_message_id": discord_message_id})
    if result:
        return result['telegram_message_id']
    return None

def create_collection(collection_name):
    try:
        db.create_collection(collection_name)
    except Exception as e:
        logging.error("Error creating collection", exc_info=True)

def drop_collection(collection_name):
    collection_name.drop()
    logging.warning("Collection dropped")

ping_mongo()

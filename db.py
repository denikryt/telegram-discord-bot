from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import logging
import os
import logging

load_dotenv()

# MongoDB configuration
MONGO_DB = os.environ.get('MONGO_DB')
mongo_client = MongoClient(MONGO_DB, server_api=ServerApi('1'), serverSelectionTimeoutMS=60000)  
db = mongo_client['HACKLAB']

def ping_mongo():
    try:
        mongo_client.admin.command('ping')
        logger("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        logger(f"Error connecting to MongoDB: {e}")
        raise e

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
        logger(f'Message saved to database: {telegram_message_id:} : {discord_message_id}')
    except Exception as e:
        logger(f"Error saving message to database: {e}")
    
def get_discord_message_id(telegram_message_id, collection_name):
    # Check if collection exists, if not create it
    if collection_name not in db.list_collection_names():
        create_collection(collection_name)

    messages_collection = db[collection_name]
    result = messages_collection.find_one({"telegram_message_id": telegram_message_id})
    if result:
        logger("Discord message ID have been found for this Telegram message ID")
        return result['discord_message_id']
    else:
        logger("Discord message ID not found for this Telegram message ID")
        return None

def get_telegram_message_id(discord_message_id, collection_name):
    # Check if collection exists, if not create it
    if collection_name not in db.list_collection_names():
        create_collection(collection_name)

    messages_collection = db[collection_name]
    result = messages_collection.find_one({"discord_message_id": discord_message_id})
    if result:
        logger(f"Telegram message ID {result['telegram_message_id']} have been found for this Discord message ID {discord_message_id}")
        return result['telegram_message_id']
    else:
        logger(f"Telegram message ID not found for this Discord message ID {discord_message_id}")
        return None

def create_collection(collection_name):
    try:
        db.create_collection(collection_name)
        logger(f"Collection {collection_name} created")
    except Exception as e:
        logger(f"Error creating collection: {e}")

def drop_collection(collection_name):
    collection_name.drop()
    logger("Collection dropped")

def logger(log_text):
    print(log_text)
    logging.info(log_text)

ping_mongo()
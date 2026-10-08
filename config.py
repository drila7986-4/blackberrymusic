import os
from dotenv import load_dotenv

load_dotenv()

# NOTE: API_ID/API_HASH/BOT_TOKEN/SESSION_STRING/OWNER_ID must come from your .env file.
# Never hardcode real secrets here as fallback defaults - a previous version of this file
# shipped a live bot token as a default, which effectively committed the secret to source.
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")  # assistant (userbot) account session
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "downloads")

BOT_NAME = os.environ.get("BOT_NAME", "Blackberry Music")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
SUPPORT_CHAT = os.environ.get("SUPPORT_CHAT", "https://t.me/rika_support_gc")
UPDATE_CHANNEL = os.environ.get("UPDATE_CHANNEL", "https://t.me/ashi_update")

# MongoDB - sudo list, gban list, chat settings, aur warnings sab yahi store hote hain.
MONGO_URI = os.environ.get("MONGO_URI", "")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "blackberry_music")

if not all([API_ID, API_HASH, BOT_TOKEN, SESSION_STRING, OWNER_ID]):
    print(
        "⚠️  Warning: one or more required .env values (API_ID, API_HASH, BOT_TOKEN, "
        "SESSION_STRING, OWNER_ID) are missing or empty. Fill them in your .env file "
        "before running the bot."
    )

if not MONGO_URI:
    print(
        "⚠️  Warning: MONGO_URI is missing or empty. Fill it in your .env file "
        "before running the bot."
    )
